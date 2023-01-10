#!/usr/bin/env python

import sys
import openstack
import openstack.config
import prettytable
import datetime
import argparse
from datetime import datetime, timezone
from functools import reduce
import math
import ipaddress

from usage import vm_disk_usage, high_risk_hv

# Getting the configuration data from clouds.yaml file
config = openstack.config.loader.OpenStackConfig()

class Table:
    def __init__(self, headers, data_list):
        self.headers = headers
        self.data = data_list

    def print_table(self):
        table = prettytable.PrettyTable()
        table.field_names = self.headers
        for row in self.data:
            table.add_row(row)

        return print(table)


class Collector:
    def __init__(self):
        self.client = {}

    def _get_client(self, env):
        cli = openstack.connect(cloud=env)
        self._store_client(cli)
        return cli

    def _store_client(self, client):
        self.client = client


class HypervisorCollector(Collector):

    def get_resources(self, env, usage):
        cli = self._get_client(env)
        hypervisors = cli.list_hypervisors()

        # Setting the result table headings
        headers = ["Name", 'State', "Host IP", 'Disk size', 'Used space', 'Free space',  "Use %", 'Running VMs']
        
        # Filling the table rows only with the needed columns
        hypervisors_data = []
        for hypervisor in hypervisors:
            hypervisors_data.append(
                [hypervisor.name, hypervisor.state, hypervisor.host_ip, 
                f"{round(hypervisor.local_disk_size/1024, 2)} TB", f"{hypervisor.local_disk_used} GB", 
                f"{hypervisor.local_disk_free} GB", round((hypervisor.local_disk_used/hypervisor.local_disk_size)* 100, 1) , hypervisor.running_vms])

        self.print_general_info(env, hypervisors)
        if usage:
            # Getting all servers
            servers = cli.list_servers(all_projects=True, bare=True, filters={'limit': 1000})
            # Getting all flavors
            flavors = cli.list_flavors()
            # Creating a list of Hypervisor hostnames
            hypervisors_list = [ h.name for h in hypervisors]
            # Getting a dictionary containing all VMs and their real disk usage
            vm_data = vm_disk_usage(hypervisors_list)
            for hv in hypervisors_list:
                # Creating list of VMs on the current Hypervisor
                current_hv_vm_list = [srv for srv in servers if srv.hypervisor_hostname == hv]
                # If there are no VMs on this HV we skip this HV
                if len(current_hv_vm_list) == 0:
                    continue
                print('----------------------------------------------')
                print(f"Hypervisor: {hv}")
                vm_usage_headers = ['Name', 'State', 'UUID', 'Allocated disk', 'Disk Usage', 'Use %']
                # Getting list of VMs UUIDs and real disk usage from the usage ansible module
                data = []
                for server in current_hv_vm_list:

                    # Getting the server flavor
                    flavor = [f for f in flavors if f.id == server.flavor.id or f.name == server.flavor.id][0]
                    if server.id not in vm_data:
                        continue
                    real_usage = vm_data[server.id]
                    real_usage = format_disk_usage(real_usage)
                    data.append([server.name, server.status, server.id, f"{flavor.disk}G", vm_data[server.id], round((float(real_usage) / flavor.disk)* 100, 1)])     
                data = sorted(data, key=lambda x: int(x[5]), reverse=True)    
                vm_table = Table(vm_usage_headers, data)
                vm_table.print_table()
        else: 
            hypervisors_data = sorted(
                hypervisors_data, key=lambda x: int(x[6]), reverse=True)
            table = Table(headers, hypervisors_data)
            table.print_table()

    
    @classmethod
    def print_general_info(self, env, hypervisors):
            print(f"Number of HVs on {env}: {len(hypervisors)}")
            print(f"Number of HVs with 0 running VMs: {len([h for h in hypervisors if h.running_vms == 0])}")
            print(f"Total disk used: {round(reduce(lambda a, b: a + b, [h.local_disk_used for h in hypervisors ])/1024, 2)} TB")
            print(f"Total free space: {round(reduce(lambda a, b: a + b, [h.local_disk_free for h in hypervisors ])/1024, 2)} TB")


class ServerCollector(Collector):
    def get_resources(self, env, sorter,  hours, disk):
        cli = self._get_client(env)
        # Getting all servers
        servers = cli.list_servers(all_projects=True, bare=True, filters={'limit': 1000})
        # Getting all flavors
        flavors = cli.list_flavors()
        # Setting the result table headings
        headers = ["Instance name", "State", "Created at",
                   'Flavor', "Allocated Disk", 'Used disk', 'Use %', "RAM", "VCPUs"]
        # Filling the table rows only with the needed columns
        servers_data = []
        hypervisors = cli.list_hypervisors()
        # Creating a list of Hypervisor hostnames
        hypervisors_list = [h.name for h in hypervisors]
        # Getting a dictionary containing all VMs and their real disk usage
        vm_disk_usage_list = vm_disk_usage(hypervisors_list)
        for server in servers:
            flavor_id = server.flavor.id
            # Getting the server flavor
            srv_flavor = [f for f in flavors if f.id == flavor_id or f.name == flavor_id][0] 
            real_usage = vm_disk_usage_list.get(server.id)
            real_usage = format_disk_usage(real_usage)
            usage_percentage = round((real_usage / srv_flavor.disk) * 100, 2) 
            servers_data.append([server.name, server.status, server.created_at, srv_flavor.name,
                                srv_flavor.disk, real_usage, usage_percentage,  srv_flavor.ram, srv_flavor.vcpus])

        # Filtering instance by disk size
        servers_data = [x for x in servers_data if int(x[4]) >= int(disk)]
        self.print_general_info(servers_data, env, hours)
        servers_data = self.switch(sorter, servers_data)
        table = Table(headers, servers_data)
        table.print_table()
    
    @classmethod
    def print_general_info(self, servers_data, env, hours):
        print('------------------------------------')
        print(f"Collecting data from {env}")

        def time_difference(server_date_str):
            # Openstack returns the created_at date as string so we convert it to datetime object
            server_date = datetime.strptime(
                server_date_str, "%Y-%m-%dT%H:%M:%S%z")
            # Getting the current time
            current_time = datetime.now(timezone.utc)
            time_diff = current_time - server_date
            # time_diff is an object from which we get the total seconds and convert them to hours
            return time_diff.total_seconds() / 3600

            
        def get_servers_size_data(servers_data):
            size_data = {}
            for server in sorted(
                servers_data, key=lambda x: int(x[4]), reverse=True):
                ''' Checking if the size key exist in the size_data dictionary
                    if it does its value is increased else its added to the dictionary with value 1'''
                if server[4] in size_data.keys():
                    size_data[server[4]] = size_data[server[4]] + 1
                else:
                    size_data[server[4]] = 1

            print('Number of VMs per disk size:')
            for size in size_data:
                print(f" - {size} GB: {size_data[size]} VMs")

        # Filtering the list of servers by provided hours or default value of 24 hours
        servers_in_last_24_hours = [
            s for s in servers_data if time_difference(s[2]) <= int(hours)]
        print(f"Number of VMs: {len(servers_data)}")
        print(
            f"VMs created in the last {hours} hours: {len(servers_in_last_24_hours)}")
        get_servers_size_data(servers_data)
        print('------------------------------------')

    # Serves sorting method
    @classmethod
    def switch(self, sorter, servers_data):
        if sorter == 'name':
            servers_data = sorted(
                servers_data, key=lambda x: x[0])

        elif sorter == 'status':
            servers_data = sorted(
                servers_data, key=lambda x: x[1])

        elif sorter == 'date':
            servers_data = sorted(
                servers_data, key=lambda x: x[2], reverse=True)

        elif sorter == 'flavor':
            servers_data = sorted(
                servers_data, key=lambda x: x[3], reverse=True)

        elif sorter == 'disk':
            servers_data = sorted(
                servers_data, key=lambda x: int(x[4]), reverse=True)

        elif sorter == 'usage':
            servers_data = sorted(
                servers_data, key=lambda x: (x[6]), reverse=True)

        elif sorter == 'ram':
            servers_data = sorted(
                servers_data, key=lambda x: int(x[7]), reverse=True)

        elif sorter == 'vcpus':
            servers_data = sorted(
                servers_data, key=lambda x: int(x[8]), reverse=True)
        return servers_data

class HighRiskCollector(Collector):
    def get_resources(self, env):
        cli = self._get_client(env)

        # Getting a full list of hypervisors
        hypervisors = cli.list_hypervisors()

        # Creating a list of hypervisors hostnames
        hypervisors_hostnames = [h.name for h in hypervisors]

        # Running an ansible playbook to check disk, ram usage and raid puncture errors
        hv_data = high_risk_hv(hypervisors_hostnames)

        # Creating a list to check if the disk or ram usage is above 90% or if any raid puncture errors present
        high_risk_hypervisors = {}
        for host in hv_data:
            if int(hv_data[host]['disk_usage']) > 90 or int(float(hv_data[host]['ram_usage'])) > 90 or int(hv_data[host]['raid_punctures']) > 0:
                high_risk_hypervisors[host] = hv_data[host]

        # In case of any high risk HV we print
        if len(high_risk_hypervisors) > 0:
            print(f"Number of high risk hypervisors on {env}:{len(high_risk_hypervisors)}")

            headers = ['Host', 'Disk usage', 'Ram usage', 'Raid Punctures']

            data = []

            for hv in high_risk_hypervisors:
                data.append([hv, 
                f"{high_risk_hypervisors[hv]['disk_usage']}%",
                f"{math.ceil(float(high_risk_hypervisors[hv]['ram_usage']))}%",
                high_risk_hypervisors[hv]['raid_punctures']])

            table = Table(headers, data)
            table.print_table()    
            
        # In case of no high risk HV we print
        else:
            print(f"No high risk hypervisors on {env}")

class SubnetCollector(Collector):
    def get_resources(self, env):
        cli = self._get_client(env)

        # Getting a list of all subnets
        subnets = cli.list_subnets()

        # Getting a list of all servers
        servers = cli.list_servers(all_projects=True, bare=True, filters={'limit': 1000})

        # Creating an empty result object
        result_subnets = {}

        # Iterating through all subnets and servers to find which servers use which subnets 
        for sub in subnets:
            cidr = sub.cidr
            subnet_id = sub.id
            network_id = sub.network_id
            # Checking if subnet key exists in the object and if not creating it
            if cidr not in result_subnets:
                result_subnets[cidr]= {}
                result_subnets[cidr]['id'] = subnet_id
                result_subnets[cidr]['network_id'] = network_id
                result_subnets[cidr]['count'] = 0
            for server in servers:
                if bool(server.addresses) == True:   
                    network_key = list(server.addresses)[0]
                    ip = server.addresses[network_key][0]['addr']
                    # If IP address is in the subnet range we increment the server count
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr):
                        result_subnets[cidr]['count'] += 1
        
        headers = ['Subnet', 'Subnet ID', 'Network ID', "VMs count"]
        subnets_data = []

        for subnet in result_subnets:
            subnets_data.append([subnet, result_subnets[subnet]['id'],result_subnets[subnet]['network_id'], result_subnets[subnet]['count']])

        table = Table(headers, subnets_data)
        table.print_table()


# Function to remove the usage output into integer (used for sorting purposes)
def format_disk_usage(real_usage):
    if real_usage is not None:
        if "M" in real_usage:
            real_usage = round(int(real_usage.replace('M', ""))/ 1024, 2)
        elif 'G' in real_usage:
            real_usage = int(float(real_usage.replace('G', "")))
        else:
            real_usage = 0
    else:
        real_usage = 0
    return real_usage
       

def main():
    parser = argparse.ArgumentParser(
        prog='Openstack Collector',
        description='Collects data via OpenStack API',
        usage="collector.py [-e ENV] [-v --verbose] [-s --sort] [-b] [-t] [-d --disk]",
    )

    parser.add_argument('collector', choices=['servers', 'hypervisors', 'risky', 'subnets'],
                        help='Collect data about instances or hypervisors'
                        )
    parser.add_argument('-e', '--env',
                        help='Cloud environment for which the results will be shown',
                        required=True,
                        action='store',
                        dest='env')
    parser.add_argument('-s', '--sort',
                        action='store',
                        dest='sorter',
                        choices=['name', 'status', 'date', 'flavor', 'disk', 'ram', 'vcpus', 'usage'])
    parser.add_argument('-b',
                        help='Filter instances by flavor size bigger than the provided value in GB',
                        action='store',
                        dest='bigger'
                        )
    parser.add_argument('-v', '--verbose',
                        help='Showing verbose output for the query',
                        action='store_true',
                        dest='verbose')
    parser.add_argument(
        '-t', help='Show number of VMs created in the last specified hours', action='store', dest='hours')
    parser.add_argument('-d', '--disk',help= 'List each VM real disk usage on every HV', action='store_true', dest='usage')

    args = parser.parse_args()

    if args.verbose:
        openstack.enable_logging(
            # With the verbose option on full output will be show and stored in the "collector.log" file
            debug=True, path='collector.log', stream=sys.stdout)

    # Defying dictionary with the possible collectors and their filters
    collectors = {'servers': {'type': ServerCollector(), 'filters': [
        args.env, args.sorter or 'usage', args.hours or 24, args.bigger or 0]}, 'hypervisors': {'type': HypervisorCollector(), 'filters': [args.env, args.usage or False]},
        'risky': {'type': HighRiskCollector(), 'filters':[args.env]}, 'subnets': {'type': SubnetCollector(), 'filters': [args.env]}}

    # Creating a new collector depending on the provided type
    collector = collectors[args.collector]['type']
    # Adding the filters for that particular collector
    filters = (collectors[args.collector]['filters'])
    collector.get_resources(*list(filters))

if __name__ == '__main__':
    main()
