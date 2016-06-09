#!/usr/bin/env python
#
#  metering_check.py
#
# PLATFORMS:
#   Linux
#
# DEPENDENCIES:
#  Python 2.7+ (untested on Python3)
#
# USAGE:
#
#  Todo

# DESCRIPTION:
# Report potential abuse cases to sensu, and ensures that the metering daemon is running,
#
# Released under the same terms as Sensu (the MIT license); see MITLICENSE
# for details.
#
# Daniel Levy <dlevy@us.ibm.com>

import optparse
import sys
import os
import time
from collections import Counter

STATE_OK = 0
STATE_WARNING = 1
STATE_CRITICAL = 2

def read_errors_from_status_file(f_name):
    if not os.path.exists(f_name):
            print ('The file ' + f_name + ' could not be opened')
            sys.exit(STATE_CRITICAL)
    with open(f_name) as f:
        for vm_entry in f.readlines()[1:]:
            vm_entry_split = vm_entry.split(',')
            if len(vm_entry_split) != 4:
                print ('The line ' + vm_entry + ' does not have the correct number of fields')
                sys.exit(STATE_CRITICAL)
            vm_id = vm_entry_split[0]
            if not vm_id.isdigit():
                print ('The entry ' + vm_id + ' should be a vm_id, but it is not a number.')
                sys.exit(STATE_CRITICAL)
            try:
                date = (float(vm_entry_split[1]))
            except ValueError:
                print ('The entry ' + vm_entry_split[1] + ' should be a date in float format.')
                sys.exit(STATE_CRITICAL)
            try:
                bandwidth = (float(vm_entry_split[2]))
            except ValueError:
                print ('The entry ' + vm_entry_split[2] + ' should be a bandwidth, but it is not a number.')
                sys.exit(STATE_CRITICAL)
            is_restricted = vm_entry_split[3]
            if is_restricted:
                print ('vm with virsh_id ' + vm_id + ' has been restricted. The restriction will be lifted during the vm\'s next cycle')

                sys.exit(STATE_WARNING)

def main():
    parser = optparse.OptionParser()

    parser.add_option('-f', '--file-name',
        help    = 'name of file to collect metering status from',
        dest    = 'file_name',
        metavar = 'FILE_NAME')


    (options, args) = parser.parse_args()
    f_name = options.file_name
    read_errors_from_status_file(f_name)
    sys.exit(STATE_OK)

#Todo add check that daemon is running and output file has been updated within x time


if __name__ == "__main__":
    main()