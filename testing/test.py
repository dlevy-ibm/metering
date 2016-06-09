from time import sleep
import os
import unittest
from code.vm import *
from code.limit import *
from code.daemon import *
from code.util import *


class TestStringMethods(unittest.TestCase):

    output_f = sys.path[0] + "recovery.txt"
    logging.basicConfig(filename="meter.log", level="DEBUG", format='%(asctime)s %(levelname)s %(message)s')

    def debug_print(self, text):
        print text
        sys.stdout.flush()

    @classmethod
    def tearDownClass(cls):
        limit_rule_ids = subprocess_cmd("neutron qos-policy-list | awk '{print $2}' | tail -n +4 | head -n -1").split()
        for limit_rule_id in limit_rule_ids:
            subprocess_cmd("neutron qos-policy-delete " + limit_rule_id)


    def tearDown(self):
        if os.path.exists(self.output_f):
            os.remove(self.output_f)
        vm_list = subprocess_cmd("nova list | awk '{print $2}' | tail -n +4 | head -n -1")
        for vm_name in vm_list.split():
            subprocess_cmd("nova delete " + vm_name)


    def upload_file_from_compute1_to_vm(self, num_times, vm_ip):
        for i in range(1, num_times):
            subprocess_cmd("ip netns exec qprobe-13d4c155-c2ff-456e-ac91-7a97d5631442 sshpass -p 'cubswin:)' scp -o StrictHostKeyChecking=no -o ConnectTimeout=10 code/3mb.zip cirros@" + vm_ip + ":/home/cirros/3mb.zip")

    def boot_vm(self, vm_name):
        subprocess_cmd("nova boot --image cirros --flavor m1.tiny --nic net-name=testnet --availability-zone nova:compute1 " + vm_name)
        sleep(10)


    def del_vm(self, vm_name):
        subprocess_cmd("nova delete " + vm_name)
        #self.vm_names.remove[vm_name]
        sleep(2)


    def compare_vm(self, vm1, vm2):
        if (vm1.id == vm2.id and vm1.tap_interface == vm2.tap_interface and
                vm1.id != -1 and vm1.tap_interface != ""):
            return True
        else:
            return False


    def get_port_rule(self, vm):
        policy_id = subprocess_cmd("neutron port-show " + vm.port_id + " | grep qos_policy_id  | awk '{print $4}'")
        policy_name = subprocess_cmd("neutron qos-policy-list | grep " + policy_id + " | awk '{print $4}'")
        return policy_name


    def compare_status(self, vm_list_live, vm_list_f):
        daemon = Daemon( -1, -1)
        vm_list_file = daemon.load_file()
        for vm_key in vm_list_live:
            vm_live = vm_list_live[vm_key]
            vm_file = vm_list_file[vm_key]
            self.assertTrue(self.compare_vm(vm_live, vm_file))


    def test_catch_abuse(self):
        self.debug_print("-STARTING- test_catch_abuse")
        self.boot_vm("vm1")
        daemon = Daemon(-1, -1)
        vms = daemon.load_file()
        daemon.limits.meter_file_path = os.path.dirname(os.path.realpath(__file__)) + '/meter_small_limit.yaml'
        daemon.limits.synch_limits(vms)
        vm_ip = subprocess_cmd("nova show vm1 | grep testnet | awk '{print $5}'")
        self.debug_print("Sleeping 20 sec until we can ping")
        sleep(25)
        self.upload_file_from_compute1_to_vm(2, vm_ip)
        daemon.get_live_results(vms)
        vm = vms[vms.keys()[0]]
        self.assertFalse(vm.cycle.is_restricted)
        #self.assertEqual(self.get_port_rule(vm), "metering_whitelist")
        self.upload_file_from_compute1_to_vm(5, vm_ip)
        daemon.get_live_results(vms)
        self.assertTrue(vm.cycle.is_restricted)
        #self.assertEqual(self.get_port_rule(vm), "metering_restricted")
        self.debug_print("Sleep 20 seconds so bandwidth limit can reset")
        sleep(20)
        daemon.get_live_results(vms)
        self.assertFalse(vm.cycle.is_restricted)
        #self.assertEqual(self.get_port_rule(vm), "metering_whitelist")
        #ToDO test bandwidth from file

    def test_normal_tenant_and_default_tenant(self):
        self.debug_print("-STARTING- test_normal_tenant_and_default_tenant")
        self.boot_vm("vm1")
        daemon = Daemon(-1, -1)
        vms = daemon.load_file()
        daemon.get_live_results(vms)
        vm = vms[vms.keys()[0]]
        self.assertEqual(vm.band_limit.name, "metering_whitelist")

        self.boot_vm("vm2")
        daemon.limits.meter_file_path = os.path.dirname(os.path.realpath(__file__))  + '/meter_default_tenant.yaml'
        daemon.limits.synch_limits(vms)
        daemon.get_live_results(vms)
        vm = vms[vms.keys()[1]]
        self.assertEqual(vm.band_limit.name, "metering_blacklist")


    def test_boot_one_vm(self):
        #Load single item from a live and check all values
        self.debug_print("-STARTING- test_boot_one_vm")
        self.boot_vm("vm1")

        daemon = Daemon(-1, -1)
        vm_list = daemon.load_file()
        vm_ip = subprocess_cmd("nova show vm1 | grep testnet | awk '{print $5}'")
        self.debug_print("Sleeping 20 sec until we can ping")
        sleep(25)
        self.upload_file_from_compute1_to_vm(5, vm_ip)
        daemon.get_live_results(vm_list)
        self.assertEqual(len(vm_list), 1)
        vm = vm_list[vm_list.keys()[0]]
        self.assertGreater(vm.virsh_id, 0)
        self.assertTrue(vm.tap_interface.find("tap") != -1)
        self.assertEquals(len(vm.mac_address), 17)
        self.assertTrue(len(vm.nova_id) > 20)

        self.assertGreater(vm.cycle.date, 1000000000) #unix time
        orig_bandwidth = vm.cycle.bandwidth
        self.assertGreater(orig_bandwidth, 0.01)
        i_time = vm.cycle.date
        self.assertEqual(vm.band_limit.time_period, 20)
        self.assertEqual(vm.band_limit.band_limit, 5000)
        self.assertEqual(vm.band_limit.band_per_sec, 1000)
        self.assertEqual(vm.tenant, "admin")
        self.assertTrue(vm.band_limit.name != "")

        #Check bandwidth after no changes
        daemon.get_live_results(vm_list)
        self.assertEqual(orig_bandwidth, vm.cycle.bandwidth)
        #Time should remain approx the same
        self.assertTrue(vm.cycle.date - i_time < 2)

        self.upload_file_from_compute1_to_vm(1, vm_ip)
        daemon.get_live_results(vm_list)

        self.assertEqual(vm.cycle.bandwidth, orig_bandwidth)
        f_time = vm.cycle.date
        self.assertEqual(f_time, i_time)





    def test_dump_and_recover(self):
        """
        #Boot,
        :return:
        """
        self.debug_print("-STARTING- test_dump_and_recover")
        self.boot_vm("vm1")
        daemon = Daemon(-1, -1)
        vm_list = daemon.load_file()
        daemon.get_live_results(vm_list)
        self.assertEqual(len(vm_list), 1)
        daemon = Daemon(-1, -1)
        vm_list = daemon.load_file()
        self.assertEqual(len(vm_list), 1)
        daemon.get_live_results(vm_list)
        self.assertEqual(len(vm_list), 1)


    def test_boot_delete_boot(self):
        """
        End to End
        Start from a status file with 2 entries
        Boot a VM
        Delete a VM
        :return:
        """
        self.debug_print("-STARTING- test_boot_delete_boot")
        self.boot_vm("vm1")
        self.boot_vm("vm2")
        daemon = Daemon(-1, -1)
        vm_list = daemon.load_file()
        daemon.get_live_results(vm_list)
        self.assertEqual(len(vm_list), 2)
        self.del_vm("vm2")
        daemon.get_live_results(vm_list)
        self.assertEqual(len(vm_list), 1)
        self.boot_vm("vm3")
        daemon.get_live_results(vm_list)
        self.assertEqual(len(vm_list), 2)




    def test_dynamic_limit(self):
        """
        Make an update to the limit file
        Ensure the daemon sees it
        :return:
        """
        self.debug_print("-STARTING- test_dynamic_limit")
        self.boot_vm("vm1")
        daemon = Daemon(-1, -1)
        vms = daemon.load_file()
        daemon.get_live_results(vms)
        vm = vms[vms.keys()[0]]
        daemon.get_live_results(vms)
        self.assertEqual(self.get_port_rule(vm), "metering_whitelist")

        daemon.limits.meter_file_path = os.path.dirname(os.path.realpath(__file__)) + '/meter_default_tenant.yaml'
        daemon.limits.synch_limits(vms)
        self.assertEqual(self.get_port_rule(vm), "metering_blacklist")







if __name__ == '__main__':
    unittest.main()



#Use database instead of local files
#ToDo enable QOS in neutron.conf - Johns doing this
#check packets ivc and outgoing
#recheck logger is working
#RBAC to ensure users can't change QOS
#What happens when stackrc info changes
#Log rotate
#only update limit if its changed
# #write ansible playbook to puh update of metering file
