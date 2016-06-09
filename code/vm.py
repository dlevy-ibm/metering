import xml.etree.ElementTree as ElementTree
import datetime
import time
import logging
from util import *



class Cycle:
    '''
    Records date and bandwidth at start of cycle
    '''
    date = 0       #unix time format
    bandwidth = 0  #Bandwidth in GB
    is_restricted = False
    logger = logging.getLogger(__name__)


    def __init__(self, date, bandwidth, is_restricted = False):
        self.date = date
        self.bandwidth = bandwidth
        self.is_restricted = is_restricted


    def __format_time(self):
        '''
        User readable format for a date
        :return:
        '''
        return datetime.datetime.fromtimestamp(float(self.date)).strftime('%Y-%m-%d %H:%M:%S')


    def reset_limit(self, current_bandwidth):
        self.bandwidth = current_bandwidth
        self.date = time.time()
        self.is_restricted = False


    def stringify(self):
        '''
        Converts the object to a format that can be written to a text file
        :return: String
        '''
        return str(self.date) + ', ' + str(self.bandwidth) + ', ' + str(self.is_restricted)


    def __str__(self):
        output =  ('Cycle start date:      ' + self.__format_time() + ' \n'
                   'Cycle inital bandwith  ' + str(self.bandwidth) + 'GB')
        return output



class Vm:
    '''
    Stores variables to identify and track a VMs bandwidth
    and set configure QOS rules on the VMs port
    '''
    virsh_id = -1 #id in virsh
    nova_id = -1
    mac_address = ''
    tap_interface = ''
    tenant = ''
    port_id = ''
    cycle = None
    band_limit = None
    state_change_required = True
    logger = logging.getLogger(__name__)


    def __init__(self, virsh_id, limits, cycle = None):
        self.virsh_id = virsh_id
        self.__set_values_from_virsh_xml(virsh_id)
        self.port_id = self.__get_port_id()

        if (cycle == None):
            self.cycle = self.__get_current_bandwidth()
        else:
            self.cycle = cycle
        self.set_limit(limits)


    def __str__(self):
        output =  ('virsh_id:             ' + self.virsh_id + '\n'
                   'nova_id:              ' + self.nova_id + '\n'
                   'mac_address:          ' + str(self.mac_address) + '\n'
                   'tap_interface:        ' + self.tap_interface + '\n'
                   'tenant:               ' + self.tenant + '\n'
                   'port_id:              ' + self.port_id + '\n'
                   'cycle bandwidth used: ' + str(self.__get_current_bandwidth().bandwidth - self.cycle.bandwidth) + 'GB\n'
                   'cycle:                ' + str(self.cycle) + '\n'
                   'band_limit:           ' + str(self.band_limit))
        return output


    def set_limit(self, limits):
        new_limit = limits.get_limit_for_tenant(self.tenant)
        if self.band_limit != new_limit:
            self.state_change_required = True
            self.band_limit = new_limit
            self.update_cycle(limits.restricted_limit_name)


    def __get_port_id(self):
        return subprocess_cmd("neutron port-list | grep " + self.mac_address + " |  awk '{print $2}'")


    def __set_values_from_virsh_xml(self, virsh_id):
        xml_data = subprocess_cmd('sudo virsh dumpxml ' + virsh_id)
        root = ElementTree.fromstring(xml_data)
        self.tap_interface = self.__get_tap(root)
        self.nova_id = self.__get_nova_id(root)
        self.mac_address = self.__get_mac(root)
        self.tenant = self.__get_tenant(xml_data)


    def __get_tap(self, root):
        for interface in root.iter('interface'):
           for target in interface.iter('target'):
               for key in target.keys():
                   if (key ==  'dev'):
                       return target.get('dev')
        raise LookupError('Could not find tap device from xml parsing for vm ' + self.virsh_id)


    def __get_nova_id(self, root):
        for domain in root.iter('domain'):
           for uuid in domain.iter('uuid'):
                return uuid.text
        raise LookupError('Could not find nova_id from xml parsing for vm ' + self.virsh_id)


    def __get_mac(self, root):
        for interface in root.iter('interface'):
            for mac in interface.iter('mac'):
                for key in mac.keys():
                   if (key ==  'address'):
                       return mac.get('address')
        raise LookupError('Could not find mac from xml parsing for vm ' + self.virsh_id)


    def __get_tenant(self, xml):
        #nova elements are defined oddly, so just use python to parse
        for line in xml.splitlines():
            if 'nova:project uuid' in line:
                s_name = line.find('>')
                f_name = line.find('</')
                if s_name > 0 and f_name > s_name:
                    return line[s_name+1:f_name]
        raise LookupError('Could not find tenant from xml parsing for vm ' + self.virsh_id)


    def __capture_packets(self):
        bandwidth_data = subprocess_cmd('sudo virsh domifstat ' + self.virsh_id + ' ' + self.tap_interface)
        for bandwith_data_line in bandwidth_data.splitlines():
            if ('rx_bytes' in bandwith_data_line):
                return round(float(bandwith_data_line.split()[-1])/float(1000000000), 4) #convert to GB
        raise LookupError('Could not find rx_byte data for vm ' + self.virsh_id)


    def __get_current_bandwidth(self):
        return Cycle(time.time(), self.__capture_packets())


    def update_cycle(self, restricted_limit_name):
        """
        Get current bandwidth and test for abuse
        """
        current_bandwidth = self.__get_current_bandwidth()
        time_diff_in_days = (current_bandwidth.date - self.cycle.date)/86400
        #start of new cycle
        if (time_diff_in_days > self.band_limit.time_period):
            if self.cycle.is_restricted == True:
                self.state_change_required = True
            self.cycle.reset_limit(current_bandwidth.bandwidth)
        if self.cycle.is_restricted == False:
            bandwidth_diff = (current_bandwidth.bandwidth - self.cycle.bandwidth)
            #abuse detected
            if (bandwidth_diff > self.band_limit.band_limit):
                self.logger.warning('Abuse detected for VM: ' + self.virsh_id)
                self.cycle.is_restricted = True
                self.state_change_required = True
        #Run synch
        if self.state_change_required == True:
            subprocess_cmd('neutron port-update ' + self.port_id + ' --qos-policy ' + self.band_limit.name)
            #if self.cycle.is_restricted == True:
                #subprocess_cmd('neutron port-update ' + self.port_id + ' --qos-policy ' + restricted_limit_name)
            #else:
                #subprocess_cmd('neutron port-update ' + self.port_id + ' --qos-policy ' + self.band_limit.name)
            self.state_change_required = False



    def stringify(self):
        return self.virsh_id + ', ' + self.cycle.stringify() + '\n'






