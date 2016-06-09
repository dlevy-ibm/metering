import os
import signal
import logging
from vm import *
from limit import *
from util import *


class Daemon():
    """
    Starts a daemon that sets QOS rules and monitors bandwidth
    The easiest way to start the daemon is to simply run the startup.py file
    There is a recovery file that gets written every cycle that holds basic data about
    all the VMs we are monitoring to record the last bandwidth cycle values.
    Definitions of the QOS rules are read from a yaml file whose path is passed it
    when the daemon is started. If this file is updated, you can send an interupt 30 (kill -30 pid) to
    the process, to tell the daemon to read the updated file. The file will automatically be reread once per 24 hours

    """


    logger = logging.getLogger(__name__)
    recovery_fname = ''
    cycle_update_time = -1 #seconds
    limit_synch_time = -1 # seconds (converted from daemon init which is hours)
    resynch_flag = False
    limits = {}


    def __init__(self, cycle_update_time, limit_synch_time):
        """

        :param recovery_fname: Name of the file to dump status
        :param meter_fname: limit definition file (Todo, move and read this file from the controller)
        :param log_level:
        :param cycle_update_time: How often to read data from virsh (seconds)
        :param limit_synch_time: How often to reread the limit file (Hours)
        :return:
        """
        try:
            self.cycle_update_time = int(cycle_update_time)
            self.limit_synch_time = int(limit_synch_time) * 3600
        except ValueError:
            raise Exception("Either cycle_update_time or limit_synch_time is not a valid integer.")
        self.__check_credentials()
        self.__check_qos_enabled()
        self.recovery_fname = os.path.dirname(os.path.realpath(__file__))  + "/recovery.txt"
        self.limits = LimitCollection()
        signal.signal(30, self.__signal_handler) #catch interupt 30
        self.logger.info("Daemon started succesfully")



    def __check_credentials(self):
        try:
            subprocess_cmd('nova list', 0)
        except RuntimeError:
            raise Exception('Unable to access the openstack services. Please source a stackrc/openrc and ensure the openstack cloud '
                            'is up and running succesfully.')


    def __check_qos_enabled(self):
        try:
            subprocess_cmd('neutron qos-policy-list', 0)
        except Exception as exception:
            raise Exception('Unable to access QOS service. Either it is not enabled, or Openstack is not working properly.')



    def __signal_handler(self, signal, frame):
        """
        Tell the daemon to resynch on next cycle if we catch an interupt 30 signal
        :param signal:
        :param frame:
        :return:
        """
        self.resynch_flag = True


    def __get_vm_id(self, virsh_vm_output):
        virsh_output_split = virsh_vm_output.split()
        if len(virsh_output_split) > 2  and virsh_output_split[0].isdigit():
            return virsh_output_split[0]
        else:
            raise LookupError('virsh output did not provide an instance id. Ensure output of virsh has not changed.')


    def __get_live_vm_ids(self):
        vm_ids = []
        virsh_vms = subprocess_cmd('sudo virsh list | tail -n +3 | head -n -1')
        for virsh_vm_output in virsh_vms.splitlines():
            vm_ids.append(self.__get_vm_id(virsh_vm_output))
        return vm_ids


    def __dump_to_recovery_file(self, vms):
        """
        Write output to a file that we can use to recover if there is a crash or issue
        :param vms:
        :return:
        """
        recovery_fname_temp = self.recovery_fname + '.tmp'
        with open(recovery_fname_temp, 'w+') as f:
            f.write('vm id, date(unix time), date (GB), restricted(t/f)\n')
            for vm in vms:
                f.write(vms[vm].stringify())
        os.rename(recovery_fname_temp, self.recovery_fname) #copy to a temp file to ensure file is written to completion


    def load_file(self):
        """
        Initializes the live cache with last known data stored in file
        This allows us to recover if the processes dies unexpectedly
        :param output_f:
        :return:
        """
        vms = {}
        if not os.path.exists(self.recovery_fname):
            return vms
        self.logger.info('Loading VM data from file ' + self.recovery_fname)
        vm_live_ids = self.__get_live_vm_ids()
        with open(self.recovery_fname) as f:
            for vm_entry in f.readlines()[1:]:
                vm_entry_split = vm_entry.split(',')
                if len(vm_entry_split) != 4:
                    raise LookupError('The dump file does not have the right number of entries')
                vm_id = vm_entry_split[0]
                if not vm_id.isdigit():
                    raise LookupError('The entry ' + vm_id + ' should be a vm_id, but it is not a number.')
                #Check that VM still exists in live
                if vm_id not in vm_live_ids:
                    continue
                try:
                    date = (float(vm_entry_split[1]))
                except ValueError:
                    raise LookupError('The entry ' + vm_entry_split[1] + ' should be a date in float format.')
                try:
                    bandwidth = (float(vm_entry_split[2]))
                except ValueError:
                    raise LookupError('The entry ' + vm_entry_split[2] + ' should be a bandwidth, but it is not a number.')
                restricted = str2bool(vm_entry_split[3])
                cycle = Cycle(date, bandwidth, restricted)
                vm = Vm(vm_id, self.limits, cycle)
                vms[vm_id] = vm
        return vms


    def get_live_results(self, vms):
        self.logger.info('Beginning live update cycle')
        live_vm_ids = self.__get_live_vm_ids()
        #Purge deleted VMs
        for vm_id in vms.keys():
            if vm_id not in live_vm_ids:
                del vms[vm_id]
        #main loop to update measurements for all VMs
        for vm_id in live_vm_ids:
            #Pick up newly created VMs
            if vm_id not in vms:
                self.logger.info('New VM detected: ' + vm_id)
                vm =  Vm(vm_id, self.limits)
                vms[vm_id] = vm
            else:
                vms[vm_id].update_cycle(self.limits.restricted_limit_name)
        self.__dump_to_recovery_file(vms)
        return vms


    def start(self):
        time_left = self.limit_synch_time
        vms = self.load_file()
        while True:
            try:
                if self.resynch_flag or time_left < 0:
                    self.limits.synch_limits(vms)
                    self.resynch_flag = False
                    time_left = self.limit_synch_time + self.cycle_update_time
                vms = self.get_live_results(vms)
                sleep(self.cycle_update_time)
                time_left = time_left - self.cycle_update_time
            except Exception as exception:
                self.logger.error(exception)
                #Todo Tell Sensu
