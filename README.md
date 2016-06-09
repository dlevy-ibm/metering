# metering
Metering daemon. 

Goals:
Set a bandwidth cap for all newly booted VMs based on a config file. Different tenants can be configured to have higher/lower caps
Monitor bandwidth for a predefined cycle and send a sensu warning when a VM passed a certain quota.

Bandwidth is applied on a VM's port using QOS
Incoming/Outgoing packets are tracked using virsh domifstat

The daemon is installed onto all compute nodes. The config file is read periodcally from the controller node (use database in the future). Can trigger a reread of the config file by sending an interupt 30 to the daemon (more detail later)