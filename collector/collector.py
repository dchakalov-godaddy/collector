#!/usr/bin/env python

import argparse
import datetime
import ipaddress
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from functools import reduce

import openstack
import openstack.config
import prettytable
from usage import high_risk_hv, vm_disk_usage

# Getting the configuration data from clouds.yaml file
config = openstack.config.loader.OpenStackConfig()

clouds = [
    'ams_private',
    'iad_private',
    'phx_private',
    'sin_private'
    # 'ams_ztn'
]


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

    def _owning_group_formatter(self, group):
        split = group.split(' - ')
        if len(split) > 1:
            return split[1]
        else:
            return split[0]


class HypervisorCollector(Collector):

    def get_resources(self, env, json_output):
        cli = self._get_client(env)
        hypervisors = cli.list_hypervisors()

        # Setting the result table headings
        headers = ["Name", 'State', "Host IP", 'Disk size',
                   'Used space', 'Free space',  "Use %", 'Running VMs']

        # Filling the table rows only with the needed columns
        hypervisors_data = []
        for hypervisor in hypervisors:
            hypervisors_data.append(
                [hypervisor.name, hypervisor.state, hypervisor.host_ip,
                 f"{round(hypervisor.local_disk_size/1024, 2)} TB", f"{hypervisor.local_disk_used} GB",
                 f"{hypervisor.local_disk_free} GB", round((hypervisor.local_disk_used/hypervisor.local_disk_size) * 100, 1), hypervisor.running_vms])

        hv_data = []
        if json_output:
            for hv in hypervisors_data:
                hv_data.append({
                    "name": hv[0], 'state': hv[1],
                    "host_ip": hv[2], 'disk_size': hv[3],
                    'used_space': hv[4], 'free_space': hv[5],
                    "use_percentage": hv[6], 'running_vms': hv[7]
                })

            return {env: sorted(hv_data, key=lambda x: int(x['use_percentage']), reverse=True)}

        else:
            self.print_general_info(env, hypervisors)
            hypervisors_data = sorted(
                hypervisors_data, key=lambda x: int(x[6]), reverse=True)
            table = Table(headers, hypervisors_data)
            table.print_table()

    @classmethod
    def print_general_info(self, env, hypervisors):
        print(f"Number of HVs on {env}: {len(hypervisors)}")
        print(
            f"Number of HVs with 0 running VMs: {len([h for h in hypervisors if h.running_vms == 0])}")
        print(
            f"Total disk used: {round(reduce(lambda a, b: a + b, [h.local_disk_used for h in hypervisors ])/1024, 2)} TB")
        print(
            f"Total free space: {round(reduce(lambda a, b: a + b, [h.local_disk_free for h in hypervisors ])/1024, 2)} TB")


class ServerCollector(Collector):
    def get_resources(self, env, sorter,  hours, disk):
        cli = self._get_client(env)
        # Getting all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})
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
            srv_flavor = [f for f in flavors if f.id ==
                          flavor_id or f.name == flavor_id][0]
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
    def get_resources(self, env, json_output):
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

        data = []

        if json_output:
            # In case of any high risk HV we print
            if len(high_risk_hypervisors) > 0:
                for hv in high_risk_hypervisors:
                    data.append({
                        'hv': hv,
                        'disk_usage': f"{high_risk_hypervisors[hv]['disk_usage']}%",
                        'ram_usage': f"{math.ceil(float(high_risk_hypervisors[hv]['ram_usage']))}%",
                        'raid_punctures': high_risk_hypervisors[hv]['raid_punctures']
                    })
                return {env: data}
            # In case of no high risk HV we print
            else:
                return {env: 'No high risk hypervisors'}
        else:
            # In case of any high risk HV we print
            if len(high_risk_hypervisors) > 0:
                print(
                    f"Number of high risk hypervisors on {env}:{len(high_risk_hypervisors)}")
                headers = ['Host', 'Disk usage', 'Ram usage', 'Raid Punctures']
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
    def get_resources(self, env, usage, json_output):
        cli = self._get_client(env)

        # Getting a list of all subnets
        subnets = cli.list_subnets()
        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        # Getting a list of all networks
        networks = cli.list_networks()

        # Getting a list of all projects
        projects = cli.list_projects()

        # Filtering projects that have "do_not_migrate" tag
        do_not_migrate_projects = [p.id for p in projects if p.meta.get(
            'migrate_to') == "do_not_migrate"]

        # Filtering the subnets to get only the once that are not floating
        needed_subnets = [s for s in subnets if 'floating' not in s.name]

        # Servers mapping:
        server_map = {
            'ams_private': 'ams_osng',
            'iad_private': 'iad_osng',
            'phx_private': 'phx_osng',
            'sin_private': 'sin_osng'
        }

        # Getting destination cloud data
        dest_cli = self._get_client(server_map[env])
        dest_servers = dest_cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        # Filtering destination VMs that contain migration metadata
        dest_servers_with_migration_meta = [
            s for s in dest_servers if "migration_src" in s.metadata.keys()]

        needed_servers = []

        # Filtering the VMs that contain migration metadata
        for server in servers:
            if "migration_dst" in server.metadata.keys():
                if not any(s.id == server.metadata['migration_dst'] for s in dest_servers_with_migration_meta):
                    needed_servers.append(server)
            else:
                needed_servers.append(server)

        # Creating an empty result object
        result_subnets = {}

        # Iterating through all subnets and servers to find which servers use which subnets
        for sub in needed_subnets:
            cidr = sub.cidr
            subnet_name = sub.name
            subnet_id = sub.id
            network_id = sub.network_id
            network_name = [n for n in networks if n.id == network_id][0].name
            # Checking if subnet key exists in the object and if not creating it
            if cidr not in result_subnets:
                result_subnets[cidr] = {}
                result_subnets[cidr]['name'] = subnet_name
                result_subnets[cidr]['id'] = subnet_id
                result_subnets[cidr]['network_zone'] = network_name
                result_subnets[cidr]['vms'] = []
                result_subnets[cidr]['hvs'] = []
            for server in servers:
                if bool(server.addresses) == True:
                    network_key = list(server.addresses)[0]
                    ip = server.addresses[network_key][0]['addr']
                    # If IP address is in the subnet range we increment the server count
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr):
                        result_subnets[cidr]['vms'].append(server)

                        # Collecting the hypervisor the VM is hosted on
                        server_hypervisor = server.hypervisor_hostname
                        # Adding the HV if not in the subnet list already
                        if server_hypervisor not in result_subnets[cidr]['hvs']:
                            result_subnets[cidr]['hvs'].append(
                                server_hypervisor)

        headers = ['Subnet', 'Name', 'Subnet ID',
                   'Network Name', "VMs count", 'Active', 'Migrated', 'Do not migrate', 'To be migrated', 'HVs count']

        subnets_data = []
        if json_output:
            for subnet in result_subnets:
                subnet_obj = {}
                if usage:
                    if "Total usage" not in headers:
                        headers.append('Total usage')
                    # Collecting current subnet hypervisors
                    subnet_hvs = result_subnets[subnet]['hvs']
                    # Collecting current subnet servers
                    subnet_vms = result_subnets[subnet]['vms']
                    # Filtering current subnet servers to select only IDs
                    subnet_vms_ids = [vm.id for vm in subnet_vms]
                    # Getting each VM disk usage on the subnet hypervisors
                    total_subnet_disk_usage = 0
                    if len(subnet_hvs) != 0:
                        vm_data = vm_disk_usage(
                            [hv for hv in subnet_hvs if hv is not None])
                        for vm in vm_data:
                            if vm in subnet_vms_ids:
                                current_vm_disk_usage = vm_data[vm]
                                if 'G' in current_vm_disk_usage:
                                    total_subnet_disk_usage += float(
                                        current_vm_disk_usage.replace("G", "")) * 1024
                                elif "M" in current_vm_disk_usage:
                                    total_subnet_disk_usage += float(
                                        current_vm_disk_usage.replace("M", ""))
                    subnet_obj['total_usage'] = f"{round(total_subnet_disk_usage / 1024, 1)}G"

                # Collecting all active VMs on the subnet
                active_vms = len(
                    [vm for vm in result_subnets[subnet]['vms'] if vm.status == 'ACTIVE'])
                migrated_vms = len([vm for vm in result_subnets[subnet]['vms'] if "migration_dst" in vm.metadata.keys()
                                    and any(s.id == vm.metadata['migration_dst'] for s in dest_servers_with_migration_meta)])
                do_not_migrate_vms = [
                    vm for vm in result_subnets[subnet]['vms'] if vm.project_id in do_not_migrate_projects]
                subnet_obj['subnet'] = subnet
                subnet_obj['name'] = result_subnets[subnet]['name']
                subnet_obj['subnet_id'] = result_subnets[subnet]['id']
                subnet_obj['network_zone'] = result_subnets[subnet]['network_zone']
                subnet_obj['count'] = len(result_subnets[subnet]['vms'])
                subnet_obj['active'] = active_vms
                subnet_obj['migrated'] = migrated_vms
                subnet_obj['do_not_migrate'] = len(do_not_migrate_vms)
                subnet_obj['to_be_migrated'] = len(
                    result_subnets[subnet]['vms']) - migrated_vms - len(do_not_migrate_vms)
                subnet_obj['hypervisors'] = len(result_subnets[subnet]['hvs'])
                subnets_data.append(subnet_obj)

            return {env: sorted(subnets_data, key=lambda x: int((x['count'])), reverse=True)}
        else:
            print(env)
            print(f"Number of subnets: {len(subnets)}")

            for subnet in result_subnets:
                active_vms = len(
                    [vm for vm in result_subnets[subnet]['vms'] if vm.status == 'ACTIVE'])
                migrated_vms = len([vm for vm in result_subnets[subnet]['vms'] if "migration_dst" in vm.metadata.keys()
                                    and any(s.id == vm.metadata['migration_dst'] for s in dest_servers_with_migration_meta)])
                do_not_migrate_vms = [
                    vm for vm in result_subnets[subnet]['vms'] if vm.project_id in do_not_migrate_projects]
                if usage:
                    if "Total usage" not in headers:
                        headers.append('Total usage')
                    # Collecting current subnet hypervisors
                    subnet_hvs = result_subnets[subnet]['hvs']
                    # Collecting current subnet servers
                    subnet_vms = result_subnets[subnet]['vms']
                    # Filtering current subnet servers to select only IDs
                    subnet_vms_ids = [vm.id for vm in subnet_vms]
                    # Getting each VM disk usage on the subnet hypervisors
                    total_subnet_disk_usage = 0
                    if len(subnet_hvs) != 0:
                        vm_data = vm_disk_usage(
                            [hv for hv in subnet_hvs if hv is not None])
                        for vm in vm_data:
                            if vm in subnet_vms_ids:
                                current_vm_disk_usage = vm_data[vm]
                                if 'G' in current_vm_disk_usage:
                                    total_subnet_disk_usage += float(
                                        current_vm_disk_usage.replace("G", "")) * 1024
                                elif "M" in current_vm_disk_usage:
                                    total_subnet_disk_usage += float(
                                        current_vm_disk_usage.replace("M", ""))

                    subnets_data.append([subnet, result_subnets[subnet]['name'], result_subnets[subnet]['id'], result_subnets[subnet]
                                         ['network_zone'], len(
                                             result_subnets[subnet]['vms']), active_vms, migrated_vms, len(do_not_migrate_vms),
                                         len(result_subnets[subnet]['vms'])-migrated_vms-len(do_not_migrate_vms), len(
                                             result_subnets[subnet]['hvs']),
                                         f"{round(total_subnet_disk_usage / 1024, 1)}G"])
                else:
                    subnets_data.append([subnet, result_subnets[subnet]['name'], result_subnets[subnet]['id'], result_subnets[subnet]
                                         ['network_zone'],
                                         len(result_subnets[subnet]['vms']
                                             ), active_vms, migrated_vms,
                                        len(do_not_migrate_vms),
                                         len(result_subnets[subnet]['vms'])-migrated_vms - len(do_not_migrate_vms), len(result_subnets[subnet]['hvs'])])

            table = Table(headers, sorted(
                subnets_data, key=lambda x: int(x[5]), reverse=True))
            table.print_table()


class VMsPerSubnetCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all subnets
        subnets = cli.list_subnets()

        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        # Getting a list of all networks
        networks = cli.list_networks()

        # Creating an empty result object
        result_subnets = {}

        # Iterating through all subnets and servers to find which servers use which subnets
        for sub in subnets:
            cidr = sub.cidr
            subnet_id = sub.id
            network_id = sub.network_id
            network_name = [n for n in networks if n.id == network_id][0].name
            # Checking if subnet key exists in the object and if not creating it
            if cidr not in result_subnets:
                result_subnets[cidr] = {}
                result_subnets[cidr]['id'] = subnet_id
                result_subnets[cidr]['network_zone'] = network_name
                result_subnets[cidr]['vms'] = []
                result_subnets[cidr]['hvs'] = []
            for server in servers:
                if bool(server.addresses) == True:
                    network_key = list(server.addresses)[0]
                    ip = server.addresses[network_key][0]['addr']
                    # If IP address is in the subnet range we increment the server count
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr):
                        result_subnets[cidr]['vms'].append(server)

                        # Collecting the hypervisor the VM is hosted on
                        server_hypervisor = server.hypervisor_hostname
                        # Adding the HV if not in the subnet list already
                        if server_hypervisor not in result_subnets[cidr]['hvs']:
                            result_subnets[cidr]['hvs'].append(
                                server_hypervisor)

        headers = ['ID', 'Hypervisor', 'Disk usage', "Created by", 'Zone']

        subnets_data = []

        for subnet in result_subnets:
            subnet_obj = {}
            # Collecting current subnet hypervisors
            subnet_hvs = result_subnets[subnet]['hvs']
            # Collecting current subnet servers
            subnet_vms = result_subnets[subnet]['vms']
            # Filtering current subnet servers to select only IDs
            subnet_vms_ids = [vm.id for vm in subnet_vms]
            # Getting each VM disk usage on the subnet hypervisors
            total_subnet_disk_usage = 0
            if len(subnet_hvs) != 0:
                vm_data = vm_disk_usage(
                    [hv for hv in subnet_hvs if hv is not None])
                for vm in vm_data:
                    if vm in subnet_vms_ids:
                        current_vm_disk_usage = vm_data[vm]
                        if 'G' in current_vm_disk_usage:
                            total_subnet_disk_usage += float(
                                current_vm_disk_usage.replace("G", "")) * 1024
                        elif "M" in current_vm_disk_usage:
                            total_subnet_disk_usage += float(
                                current_vm_disk_usage.replace("M", ""))

            if round(total_subnet_disk_usage / 1024, 1) > 0:
                subnet_obj[
                    'subnet'] = f"{subnet} - {result_subnets[subnet]['id']} - {round(total_subnet_disk_usage / 1024, 1)}G"
                vm_list = []

                for vm in result_subnets[subnet]['vms']:
                    vm_id = vm.id
                    vm_hv = vm.hypervisor_hostname
                    vm_metadata = vm.metadata
                    av_zone = vm['OS-EXT-AZ:availability_zone']
                    # current_vm_disk_usage = vm_data[vm_id]
                    if (vm_id in vm_data):
                        current_vm_disk_usage = vm_data[vm_id]
                    else:
                        current_vm_disk_usage = 0
                    if json_output:
                        vm_list.append({'id': vm_id, 'hypervisor': vm_hv,
                                        'usage': current_vm_disk_usage, 'metadata': vm_metadata, 'zone': av_zone})
                    else:
                        if 'created_by' in vm_metadata:
                            created_by = vm_metadata['created_by']
                        else:
                            created_by = 'Unknown'
                        vm_list.append(
                            [vm.id, vm_hv, current_vm_disk_usage, created_by, av_zone])
                if len(vm_list) > 0:
                    subnet_obj['vms_list'] = vm_list
                subnets_data.append(subnet_obj)
        if json_output:
            return (
                # {env: sorted(subnets_data, key=lambda x: int((x['count'])), reverse=True)}
                {env: subnets_data}
            )
        else:
            for subnet in subnets_data:
                print('----------------------------------------------')
                print(f"Subnet: {subnet['subnet']}")
                table = Table(headers, subnet['vms_list'])
                table.print_table()


class VMsPerHypervisorCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting all hypervisors
        hypervisors = cli.list_hypervisors()

        # Filling the table rows only with the needed columns
        # hypervisors_data = []
        # for hypervisor in hypervisors:
        # hypervisors_data.append(
        #     [hypervisor.name, hypervisor.state, hypervisor.host_ip,
        #      f"{round(hypervisor.local_disk_size/1024, 2)} TB", f"{hypervisor.local_disk_used} GB",
        #      f"{hypervisor.local_disk_free} GB", round((hypervisor.local_disk_used/hypervisor.local_disk_size) * 100, 1), hypervisor.running_vms])

        hv_json_data = []

        # Getting all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})
        # Getting all flavors
        flavors = cli.list_flavors()
        # Creating a list of Hypervisor hostnames
        hypervisors_list = [h.name for h in hypervisors]
        # Getting a dictionary containing all VMs and their real disk usage
        vm_data = vm_disk_usage(hypervisors_list)

        if json_output == False:
            self.print_general_info(env, hypervisors)

        for hv in hypervisors_list:
            # Creating list of VMs on the current Hypervisor
            current_hv_vm_list = [
                srv for srv in servers if srv.hypervisor_hostname == hv]
            # If there are no VMs on this HV we skip this HV
            if len(current_hv_vm_list) == 0:
                continue

            # Getting list of VMs UUIDs and real disk usage from the usage ansible module
            if json_output:
                hv_vm_list = []
                for server in current_hv_vm_list:
                    flavor = [f for f in flavors if f.id ==
                              server.flavor.id or f.name == server.flavor.id][0]
                    if server.id not in vm_data:
                        continue
                    real_usage = vm_data[server.id]
                    real_usage = format_disk_usage(real_usage)
                    hv_vm_list.append({
                        'name': server.name, 'state': server.status, 'uuid': server.id,
                        'allocated_disk': f"{flavor.disk}G", 'disk_usage': vm_data[server.id],
                        'use_percentage': round((float(real_usage) / flavor.disk) * 100, 1)
                    })

                    hv_json_data.append({hv: hv_vm_list})
            else:
                print('----------------------------------------------')
                print(f"Hypervisor: {hv}")
                vm_usage_headers = ['Name', 'State', 'UUID',
                                    'Allocated disk', 'Disk Usage', 'Use %']

                data = []
                for server in current_hv_vm_list:

                    # Getting the server flavor
                    flavor = [f for f in flavors if f.id ==
                              server.flavor.id or f.name == server.flavor.id][0]
                    if server.id not in vm_data:
                        continue
                    real_usage = vm_data[server.id]
                    real_usage = format_disk_usage(real_usage)
                    data.append([server.name, server.status, server.id, f"{flavor.disk}G", vm_data[server.id], round(
                        (float(real_usage) / flavor.disk) * 100, 1)])
                data = sorted(data, key=lambda x: int(x[5]), reverse=True)
                vm_table = Table(vm_usage_headers, data)
                vm_table.print_table()
            if json_output:
                return {env: hv_json_data}

    @classmethod
    def print_general_info(self, env, hypervisors):
        print(f"Number of HVs on {env}: {len(hypervisors)}")
        print(
            f"Number of HVs with 0 running VMs: {len([h for h in hypervisors if h.running_vms == 0])}")
        print(
            f"Total disk used: {round(reduce(lambda a, b: a + b, [h.local_disk_used for h in hypervisors ])/1024, 2)} TB")
        print(
            f"Total free space: {round(reduce(lambda a, b: a + b, [h.local_disk_free for h in hypervisors ])/1024, 2)} TB")


class ProjectCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)
        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})
        # Getting a list of all projects
        projects = cli.list_projects()
        # Filtering only the projects that don't have the migrate_to metadata
        projects_with_no_migrate_meta = [
            p for p in projects if 'migrate_to' not in p.meta]
        # Creating an empty data array
        projects_data = []

        for project in projects_with_no_migrate_meta:
            # For each project getting only name, id, owning group and list of VMs under that project
            project_obj = {
                'project': f"{project.name} - {project.id} - {self._owning_group_formatter(project.meta.get('owning_group', 'Unknown'))}", 'vm_list': []}
            vm_list = [s for s in servers if s.project_id == project.id]

            for vm in vm_list:
                # For each VM under the project getting only the important data
                project_obj['vm_list'].append(
                    {'name': vm.name, 'id': vm.id, 'hypervisor': vm.hypervisor_hostname})
            if len(project_obj['vm_list']) > 0:
                projects_data.append(project_obj)

        if json_output:
            return {env: sorted(projects_data, key=lambda x: len(x['vm_list']), reverse=True)}
        else:
            headers = ['Name', 'ID', "Hypervisor"]

            for project in projects_data:
                print('----------------------------------------------')
                print(f"Project: {project['project']}")
                if len(project['vm_list']) == 0:
                    print("No instances under this project")
                else:
                    values = [x.values() for x in project['vm_list']]
                    table = Table(headers, values)
                    table.print_table()


class EmptyProjectCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})
        # Getting a list of all projects
        projects = cli.list_projects()

        projects_data = []

        for project in projects:
            vm_list = [s for s in servers if s.project_id == project.id]
            if len(vm_list) == 0:
                projects_data.append({'name': project.name, 'id': project.id,
                                     'owning_group': self._owning_group_formatter(project.meta.get('owning_group', 'Unknown'))})

        if json_output:
            return {env: projects_data}
        else:
            headers = ['Name', 'ID', "Owning Group"]
            values = [x.values() for x in projects_data]
            table = Table(headers, values)
            table.print_table()


class ProjectValidator(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all projects
        projects = cli.list_projects()

        cloud_map = {
            'ams_private': 'ams_osng',
            'iad_private': 'iad_osng',
            'phx_private': 'phx_osng',
            'sin_private': 'sin_osng'
        }

        # Getting destination cloud data
        dest_cli = self._get_client(cloud_map[env])
        # Getting destination cloud projects
        dst_projects = dest_cli.list_projects()
        dst_project_ids = [p.id for p in dst_projects]

        projects_data = []

        for project in projects:
            if project.meta.get('migrate_to'):
                if project.meta.get('migrate_to') != 'do_not_migrate':
                    if project.meta.get('migrate_to') not in dst_project_ids:
                        projects_data.append({'name': project.name, 'id': project.id, 'owning_group': self._owning_group_formatter(project.meta.get(
                            'owning_group', 'Unknown')), 'Set dst project': project.meta.get('migrate_to')})

        if json_output:
            return {env: projects_data}
        else:
            headers = ['Name', 'ID', 'Owning Group', 'Set destination project']
            values = [x.values() for x in projects_data]
            table = Table(headers, values)
            table.print_table()


class VMsWithMultipleFipsCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        ports = cli.list_ports()

        flips = cli.list_floating_ips()

        server_data = []

        headers = ['Name', 'ID', 'Owning group', 'FIPs', 'Port_IPs']

        for server in servers:
            if bool(server.addresses) == True:
                server.ports = []
                # Getting the network name key
                network_key = list(server.addresses)[0]
                # Getting the list of server addresses
                ips = server.addresses[network_key]

                # Checking the count of floating IPs for each VM
                floating_ips_count = 0
                floating_ips = []
                port_ips = []
                for ip in ips:
                    if (ip['OS-EXT-IPS:type']) == 'floating':
                        floating_ips_count += 1
                        floating_ips.append(ip['addr'])

                        flip_list = [
                            f for f in flips if f['floating_ip_address'] == ip['addr']]
                        if len(flip_list) > 0:
                            server.ports.append(flip_list[0].port_id)

                # Checking for VMs with more than 1 FIP
                if len(server.ports) > 0:
                    for port in server.ports:
                        if port != None:
                            current_port = [
                                p for p in ports if p.id == port][0]
                            allowed_address_pairs = current_port.allowed_address_pairs
                            if len(allowed_address_pairs) > 1:
                                for ip in allowed_address_pairs:
                                    port_ips.append(ip['ip_address'])
                if floating_ips_count > 1 or len(port_ips):

                    server_data.append({'name': server.name, 'id': server.id, 'owning_group': self._owning_group_formatter(server.metadata.get(
                        'owning_group', 'None')), 'fips': floating_ips, 'port_ips': port_ips})

        if json_output:
            return {env: server_data}
        else:
            values = [x.values() for x in server_data]
            table = Table(headers, values)
            table.print_table()


class OwningGroupCollector(Collector):
    def get_resources(self, env, group):
        cli = self._get_client(env)

        # Getting a list of all subnets
        subnets = cli.list_subnets()
        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        # Getting a list of all networks
        networks = cli.list_networks()

        needed_servers = [s for s in servers if group.lower(
        ) in s.metadata['owning_group'].lower()]

        # Creating an empty result object
        result_subnets = {}

        # Iterating through all subnets and servers to find which servers use which subnets
        for sub in subnets:
            cidr = sub.cidr
            subnet_id = sub.id
            network_id = sub.network_id
            network_name = [n for n in networks if n.id == network_id][0].name
            # Checking if subnet key exists in the object and if not creating it
            if cidr not in result_subnets:
                result_subnets[cidr] = {}
                result_subnets[cidr]['name'] = sub.cidr
                result_subnets[cidr]['id'] = subnet_id
                result_subnets[cidr]['network_zone'] = network_name
                result_subnets[cidr]['vms'] = []
                result_subnets[cidr]['hvs'] = []
            for server in needed_servers:
                if bool(server.addresses) == True:
                    network_key = list(server.addresses)[0]
                    ip = server.addresses[network_key][0]['addr']
                    # If IP address is in the subnet range we increment the server count
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr):
                        result_subnets[cidr]['vms'].append(server)

        needed_subnets = []

        for sub in result_subnets:
            if len(result_subnets[sub]['vms']) > 0:
                needed_subnets.append(result_subnets[sub])

        headers = ['Name', 'ID', 'Owning group']

        print("")
        print(
            f" - Looking for all subnets that have VM with owning group including {group} in the name...")
        print(
            f" - Found {len(needed_subnets)} subnets containing VMs with that owning group")
        print("Lising all found subnets:")
        print('------------------------------------')
        for sub in needed_subnets:
            print(f"{sub['name']} - {sub['id']} - {len(sub['vms'])} VMs")
            # print('------------------------------------')
            server_data = []
            for vm in sub['vms']:
                server_data.append({'name': vm.name, 'id': vm.id,
                                   'owning_group': self._owning_group_formatter(vm.metadata.get('owning_group', 'None'))})
            values = [x.values() for x in server_data]
            table = Table(headers, values)
            table.print_table()
            print("")


class AllCollector(Collector):
    def get_resources(self, which, usage):

        type = {
            'subnets': SubnetCollector(),
            'risky': HighRiskCollector(),
            'hypervisors': HypervisorCollector(),
            'vms_per_subnet': VMsPerSubnetCollector(),
            'vms_per_hv': VMsPerHypervisorCollector(),
            'projects': ProjectCollector(),
            'empty_projects': EmptyProjectCollector(),
            'project_validate': ProjectValidator(),
            'multifips': VMsWithMultipleFipsCollector()
        }

        collector_type = type[which]

        today = date.today()

        # Uncomment below to use week date range instead of actual date
        # dt = datetime.strptime(str(today), '%Y-%m-%d')
        # start = dt - timedelta(days=dt.weekday())
        # end = start + timedelta(days=6

        json_data = []
        for cloud in clouds:
            if which == 'subnets':
                json_data.append(
                    collector_type.get_resources(cloud, usage, True))
            else:
                json_data.append(collector_type.get_resources(cloud, True))

        current_date_obj = {str(today): json_data}
        current_date_json = json.dumps(
            current_date_obj, default=lambda x: x.__dict__, indent=2)
        print((current_date_json))


# Function to remove the usage output into integer (used for sorting purposes)
def format_disk_usage(real_usage):
    if real_usage is not None:
        if "M" in real_usage:
            real_usage = round(int(real_usage.replace('M', "")) / 1024, 2)
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

    parser.add_argument('collector', choices=['servers', 'hypervisors', 'risky',
                                              'subnets', 'vmpersub', 'vmperhv', 'projects',
                                              'empty_projects', 'multifips', 'group',
                                              'project_validate', 'all'],
                        help='Collect data about instances, hypervisors or subnets',
                        default='all'
                        )
    parser.add_argument('-e', '--env',
                        help='Cloud environment for which the results will be shown',
                        # required=True,
                        action='store',
                        default='all',
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
    parser.add_argument('-t',
                        help='Show number of VMs created in the last specified hours',
                        action='store',
                        dest='hours')
    parser.add_argument('-d', '--disk',
                        help='List each VM real disk usage on every HV',
                        action='store_true',
                        dest='usage',
                        default=False)
    parser.add_argument('-j', '--json',
                        help='Provide output in JSON format',
                        action='store_true',
                        dest='json_output',
                        default=False)
    parser.add_argument('-w',
                        help='Select the type of collector you wish to collect all data for',
                        action='store',
                        dest='which',
                        choices=['subnets', 'risky', 'hypervisors', 'vms_per_subnet', 'vms_per_hv', 'projects', 'empty_projects', 'project_validate', 'multifips'])
    parser.add_argument('-g', '--group',
                        help='Show which subnets this owning group has VMs under',
                        action='store',
                        dest='group')

    args = parser.parse_args()

    if args.verbose:
        openstack.enable_logging(
            # With the verbose option on full output will be show and stored in the "collector.log" file
            debug=True, path='collector.log', stream=sys.stdout)

    # Defying dictionary with the possible collectors and their filters
    collectors = {
        'servers': {'type': ServerCollector(), 'filters': [
            args.env, args.sorter or 'usage', args.hours or 24, args.bigger or 0]},
        'hypervisors': {'type': HypervisorCollector(), 'filters': [args.env, args.usage, args.json_output]},
        'risky': {'type': HighRiskCollector(), 'filters': [args.env, args.json_output]},
        'subnets': {'type': SubnetCollector(), 'filters': [args.env, args.usage, args.json_output]},
        'vmpersub': {'type': VMsPerSubnetCollector(), 'filters': [args.env, args.json_output]},
        'vmperhv': {'type': VMsPerHypervisorCollector(), 'filters': [args.env, args.json_output]},
        'projects': {'type': ProjectCollector(), 'filters': [args.env, args.json_output]},
        'empty_projects': {'type': EmptyProjectCollector(), 'filters': [args.env, args.json_output]},
        'project_validate': {'type': ProjectValidator(), 'filters': [args.env, args.json_output]},
        'multifips': {'type': VMsWithMultipleFipsCollector(), 'filters': [args.env, args.json_output]},
        'group': {'type': OwningGroupCollector(), 'filters': [args.env, args.group]},
        'all': {'type': AllCollector(), 'filters': [args.which, args.usage]}
    }

    # Creating a new collector depending on the provided type
    collector = collectors[args.collector]['type']
    # Adding the filters for that particular collector
    filters = (collectors[args.collector]['filters'])
    collector.get_resources(*list(filters))


if __name__ == '__main__':
    main()
