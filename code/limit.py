import yaml
from util import *
import logging
import os

class LimitCollection:
    """
    Synch the limit definition file and update when necessary
    """
    limits = {}
    tenants = {}
    restricted_limit_name = ''
    default_limit_name = ''
    #config_scp_location = ''
    meter_file_path = ''
    logger = logging.getLogger(__name__)


    def __init__(self):
        #self.config_scp_location = config_scp_location
        self.meter_file_path = '/etc/metering/meter.yaml'
        self.__update_limits()


    #def __fetch_meter_file(self):
    #    try:
    #        subprocess_cmd('scp -o StrictHostKeyChecking=no ' + self.config_scp_location + ' ' + self.meter_file_path, 0) #Todo where to put the file
    #    except Exception:
    #        raise Exception('Could not fetch metering definition file from the controller. '
    #                    'Ensure that the compute node can ssh into the controller, and that the file exists')


    def synch_limits(self, vms):
        self.logger.info('Resynching limits file and updating affected VMs')
        self.__update_limits()
        for vm_id in vms:
            vms[vm_id].set_limit(self)


    def __update_limits(self):
        '''
        Load definitions of the metering rules
        Create the rules in Neutron
        After calling this funciton, must update the VM limits
        '''
        #self.__fetch_meter_file()
        self.limits = {}
        self.tenants = {}

        qos_policy_list = subprocess_cmd('neutron qos-policy-list')
        with open(self.meter_file_path, 'r') as stream:
            vm_defs = yaml.load(stream)
            if 'restricted' not in vm_defs or 'default' not in vm_defs:
                raise ValueError('File: ' + self.meter_file_path + ' does not define restricted or default value')
            if 'meters' not in vm_defs or 'tenants' not in vm_defs:
                raise ValueError('File: ' + self.meter_file_path + ' does not define meters or tenants lists')
            else:
                self.restricted_limit_name = vm_defs.get('restricted')
                self.default_limit_name = vm_defs.get('default')
            meters = vm_defs.get('meters')
            for limit in meters:
                time_period = meters.get(limit).get('time_period')
                band_limit = meters.get(limit).get('bandwidth_limit')
                band_per_sec = meters.get(limit).get('bandwith_per_sec')
                if not type(time_period) is int and not type(band_limit) is int and not type(band_per_sec) is int:
                    raise ValueError('Something seems to be misconfigured in the yaml definition file for limit: ' + limit + '.')
                limit_type = LimitType(limit, time_period, band_limit, band_per_sec)
                self.limits[limit] = limit_type
                limit_type.synch_metering_rule(qos_policy_list)
            tenants = vm_defs.get('tenants')
            for tenant in tenants:
                tenant_limit = tenants.get(tenant)
                if tenant_limit not in self.limits and tenant_limit != 'restricted' and tenant_limit != 'default':
                    raise ValueError('The tenant ' + tenant + ' has an undefined limit, ' + tenant_limit + '.')
                self.tenants[tenant] = tenants.get(tenant)


    def get_limit_for_tenant(self, tenant_id):
        if tenant_id in self.tenants:
            return self.limits[self.tenants[tenant_id]]
        else:
            return self.limits[self.default_limit_name]



class LimitType:
    """
    limitation placed on the VM, i.e if its whitelisted it can use more bandwidth
    """
    name = ''
    time_period = 0
    band_limit = 0
    band_per_sec = 0
    logger = logging.getLogger(__name__)


    def __init__(self, name, time_period, band_limit, band_per_sec):
        self.name = name
        self.time_period = time_period
        self.band_limit = band_limit
        self.band_per_sec = band_per_sec


    def synch_metering_rule(self, qos_policy_list = None):
        """
        For each definition, create a metering rule.
        :param qos_policy_list:
        :return:
        """
        if qos_policy_list == None:
            qos_policy_list = subprocess_cmd('neutron qos-policy-list')
        if qos_policy_list.find(self.name) == -1:
            self.logger.info('Creating QOS rule: ' + self.name)
            bash_create_policy = ('neutron qos-policy-create '+ self.name + '; '
                                  'neutron qos-bandwidth-limit-rule-create '+ self.name +
                                  ' --max-kbps ' +  str(self.band_per_sec) +
                                  ' --max-burst-kbps ' + str(self.band_per_sec))
            subprocess_cmd(bash_create_policy)
        else:
            qos_bandwidth_list = subprocess_cmd("neutron qos-bandwidth-limit-rule-list " + self.name +
                                                " | awk '{print $2}' | tail -n +4 | head -n -1").split()
            if len(qos_bandwidth_list) != 1:
                raise Exception('There should only be one bandwith rule in the QOS policy ' + self.name)
            bash_update_rule = (  'neutron qos-bandwidth-limit-rule-update '+ qos_bandwidth_list[0] + ' ' + self.name +
                                  ' --max-kbps ' +  str(self.band_per_sec) +
                                  ' --max-burst-kbps ' + str(self.band_per_sec))
            subprocess_cmd(bash_update_rule)


    def __str__(self):
        output =  ('name:               ' + self.name + '\n'
                   'time_period:        ' + str(self.time_period) + '\n'
                   'band_per_sec:        ' + str(self.band_per_sec) + '\n'
                   'band_limit:         ' + str(self.band_limit))
        return output


    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.name == other.name and self.time_period == other.time_period \
                and self.band_limit == other.band_limit and self.band_per_sec == other.band_per_sec
        else:
            return False