#!/usr/bin/env python

import sys
import openstack
import openstack.config
import prettytable
import datetime
import argparse
from datetime import datetime, timezone
import subprocess
from functools import reduce

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

    def get_resources(self, env):
        cli = self._get_client(env)
        hypervisors = cli.list_hypervisors()

        # Setting the result table headings
        headers = ["Name", 'State', "Host IP", 'Disk size', 'Used space', 'Free space', 'Running VMs']
        
        # Filling the table rows only with the needed columns
        hypervisors_data = []
        for hypervisor in hypervisors:
            hypervisors_data.append(
                [hypervisor.name, hypervisor.state, hypervisor.host_ip, 
                f"{round(hypervisor.local_disk_size/1024, 2)} TB", f"{hypervisor.local_disk_used} GB", 
                f"{hypervisor.local_disk_free} GB", hypervisor.running_vms])
        
        print(f"Number of HVs on {env}: {len(hypervisors)}")
        print(f"Number of HVs with 0 running VMs: {len([h for h in hypervisors if h.running_vms == 0])}")
        print(f"Total disk used: {round(reduce(lambda a, b: a + b, [h.local_disk_used for h in hypervisors ])/1024, 2)} TB")
        print(f"Total free space: {round(reduce(lambda a, b: a + b, [h.local_disk_free for h in hypervisors ])/1024, 2)} TB")
        table = Table(headers, hypervisors_data)
        table.print_table()


class ServerCollector(Collector):
    def get_resources(self, env, sorter,  hours, disk):
        cli = self._get_client(env)
        servers = cli.list_servers(all_projects=True,)

        # Setting the result table headings
        headers = ["Instance name", "State", "Created at",
                   'Flavor', "Disk", "RAM", "VCPUs"]

        # Filling the table rows only with the needed columns
        servers_data = []
        for server in servers:
            id = server.flavor.id
            srv_flavor = cli.get_flavor_by_id(id)
            servers_data.append([server.name, server.status, server.created_at, srv_flavor.name,
                                srv_flavor.disk, srv_flavor.ram, srv_flavor.vcpus])

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

        elif sorter == 'ram':
            servers_data = sorted(
                servers_data, key=lambda x: int(x[5]), reverse=True)

        elif sorter == 'vcpus':
            servers_data = sorted(
                servers_data, key=lambda x: int(x[6]), reverse=True)
        return servers_data


def main():
    parser = argparse.ArgumentParser(
        prog='Openstack Collector',
        description='Collects data via OpenStack API',
        usage="collector.py [-e ENV] [-v --verbose] [-s --sort] [-b]",
    )

    parser.add_argument('collector', choices=['servers', 'hypervisors'],
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
                        choices=['name', 'status', 'date', 'flavor', 'disk', 'ram', 'vcpus'])
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

    args = parser.parse_args()

    if args.verbose:
        openstack.enable_logging(
            # With the verbose option on full output will be show and stored in the "collector.log" file
            debug=True, path='collector.log', stream=sys.stdout)

    # Defying dictionary with the possible collectors and their filters
    collectors = {'servers': {'type': ServerCollector(), 'filters': [
        args.env, args.sorter or 'size', args.hours or 24, args.bigger or 0]}, 'hypervisors': {'type': HypervisorCollector(), 'filters': [args.env]}}

    # Creating a new collector depending on the provided type
    collector = collectors[args.collector]['type']
    # Adding the filters for that particular collector
    filters = (collectors[args.collector]['filters'])
    collector.get_resources(*list(filters))

if __name__ == '__main__':
    main()
