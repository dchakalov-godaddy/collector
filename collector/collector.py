#!/usr/bin/env python

import argparse
import csv
import datetime
from datetime import date, datetime, timedelta, timezone
from functools import reduce
import ipaddress
import json
import math
import openstack
import openstack.config
import os
import prettytable
from requests.exceptions import JSONDecodeError
import sys
from time import sleep
from usage import high_risk_hv, vm_disk_usage

# Getting the configuration data from clouds.yaml file
config = openstack.config.loader.OpenStackConfig()

clouds = [
    'iad_private',
    'phx_private',
    'sin_private'
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
    @staticmethod
    def get_hypervisors_data(cli):
        hypervisors = cli.list_hypervisors()
        hypervisors_data = []
        return print(hypervisors[0])
        for hypervisor in hypervisors:
            hypervisors_data.append(
                [hypervisor.name, hypervisor.state, hypervisor.host_ip,
                 f"{round(hypervisor.local_disk_size/1024, 2)} TB", f"{hypervisor.local_disk_used}",
                 f"{hypervisor.local_disk_free}", round((hypervisor.local_disk_used/hypervisor.local_disk_size) * 100, 1), hypervisor.running_vms])
        return hypervisors_data

    @staticmethod
    def format_hypervisors_data(hypervisors_data):
        headers = ["Name", 'State', "Host IP", 'Disk size',
                   'Used space', 'Free space',  "Use %", 'Running VMs']
        hypervisors_data = sorted(
            hypervisors_data, key=lambda x: int(x[6]), reverse=True)
        table = Table(headers, hypervisors_data)
        return table

    @staticmethod
    def format_hypervisors_data_as_json(hypervisors_data):
        hv_data = []
        for hv in hypervisors_data:
            hv_data.append({
                "name": hv[0], 'state': hv[1],
                "host_ip": hv[2], 'disk_size': hv[3],
                'used_space': hv[4], 'free_space': hv[5],
                "use_percentage": hv[6], 'running_vms': hv[7]
            })
        return hv_data

    @classmethod
    def print_general_info(cls, env, hypervisors):
        print(f"Number of HVs on {env}: {len(hypervisors)}")
        print(
            f"Number of HVs with 0 running VMs: {len([h for h in hypervisors if h[7] == 0])}")
        print(f"Total disk used: {cls.get_total_disk_used(hypervisors)}")
        print(f"Total free space: {cls.get_total_free_space(hypervisors)}")

    @staticmethod
    def get_total_disk_used(hypervisors):
        total_used = reduce(lambda a, b: a + b,
                            [int(h[4]) for h in hypervisors])
        return f"{round(int(total_used)/1024, 2)} TB"

    @staticmethod
    def get_total_free_space(hypervisors):
        total_free = reduce(lambda a, b: a + b,
                            [int(h[5]) for h in hypervisors])
        return f"{round(total_free/1024, 2)} TB"

    def get_resources(self, env, json_output):
        cli = self._get_client(env)
        hypervisors_data = self.get_hypervisors_data(cli)
        if json_output:
            hv_data = self.format_hypervisors_data_as_json(hypervisors_data)
            return {env: sorted(hv_data, key=lambda x: int(x['use_percentage']), reverse=True)}
        else:
            self.print_general_info(env, hypervisors_data)
            table = self.format_hypervisors_data(hypervisors_data)
            table.print_table()


class EmptyHypervisorCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)
        hypervisors = cli.list_hypervisors()
        empty_hypervisors = []
        for hypervisor in hypervisors:
            if hypervisor.running_vms == 0:
                empty_hypervisors.append(hypervisor.name)

        if len(empty_hypervisors) > 0:
            if json_output:
                return {env: empty_hypervisors}
            else:
                print(f"Number of empty HVs on {env}: {len(empty_hypervisors)}")
                print('------------------------------------')
                for hv in empty_hypervisors:
                    print(hv)
                print('------------------------------------')
        else:
            print(f"No empty HVs on {env}")


class MigratedOHVMSCollector(Collector):
    def get_resources(self, env):
        cli = self._get_client(env)
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})
        hypervisors = cli.list_hypervisors()

        total_migrated_vms = [
            vm for vm in servers if "oh_migration_state" in vm.metadata]

        vms_count = {hypervisor.name: 0 for hypervisor in hypervisors}
        for server in servers:
            hypervisor_name = getattr(server, 'hypervisor_hostname', None)
            if hypervisor_name:
                vms_count[server.hypervisor_hostname] += 1

        empty_hvs = []
        fully_migrated_hvs = []
        for hypervisor in hypervisors:
            total_vms = vms_count.get(hypervisor.name, 0)
            migrated_vms = [vm for vm in servers if vm.hypervisor_hostname == hypervisor.name and "oh_migration_state" in vm.metadata]

            if total_vms == 0:
                empty_hvs.append(hypervisor.name)
            if total_vms != 0 and total_vms == len(migrated_vms):
                fully_migrated_hvs.append(hypervisor.name)

        print('------------------------------------')
        print(f"Number of migrated VMs: {len(total_migrated_vms)}")
        print(f"Number of empty HVs: {len(empty_hvs)}")
        print(f"Number of fully migrated HVs: {len(fully_migrated_hvs)}")
        print('------------------------------------')
        if len(empty_hvs) > 0:
            print('Empty HVs:')
            for hv in empty_hvs:
                print(hv)
            print('------------------------------------')
        if len(fully_migrated_hvs) > 0:
            print('Fully migrated HVs:')
            for hv in fully_migrated_hvs:
                print(hv)
            print('------------------------------------')

        # for vm in migrated_vms:
        #     for hv in hypervisors:
        #         if vm.hypervisor_hostname == hv.name:
  
        # for hv in hypervisors:
        #     migrated_vms = []
        #     for vm in vms:
        #         if vm.hypervisor_hostname == hv.name:
        #             if "oh_migration_state" in vm.metadata:
        #                 migrated_vms.append(vm)

        #     if len(migrated_vms) == hv.running_vms:
        #         fully_migrated_hvs.append(hv.name)

        # print(f"Number of migrated VMs: {len(migrated_vms)}")
        # if len(fully_migrated_hvs) > 0:
        #     if json_output:
        #         return {env: fully_migrated_hvs}
        #     else:
        #         print(f"Number of fully migrated HVs on {env}: {len(fully_migrated_hvs)}")
        #         print('------------------------------------')
        #         for hv in fully_migrated_hvs:
        #             print(hv)
        #         print('------------------------------------')
        # else:
        #     print(f"No fully migrated HVs on {env}")


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


class ZoneCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all subnets
        subnets = cli.list_subnets()
        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})
        active_servers = [s for s in servers if s.status == 'ACTIVE']

        # Getting a list of all projects
        projects = cli.list_projects()

        # Filtering only the projects that don't have the migrate_to metadata
        projects_with_no_migrate_meta = [
            p.id for p in projects if 'migrate_to' not in p.meta]

        # Filtering projects that have "do_not_migrate" tag
        do_not_migrate_projects = [p.id for p in projects if p.meta.get(
            'migrate_to') == "do_not_migrate"]

        # Servers mapping:
        server_map = {
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
        # Filtering the subnets to get only the once that are not floating
        needed_subnets = [s for s in subnets if 'floating' not in s.name]

        # Filtering the VMs that contain migration metadata
        for server in servers:
            if "migration_dst" in server.metadata.keys():
                if not any(s.id == server.metadata['migration_dst'] for s in dest_servers_with_migration_meta):
                    needed_servers.append(server)
            else:
                needed_servers.append(server)

        result_subnets = {}

        for sub in needed_subnets:
            cidr = sub.cidr
            subnet_id = sub.id

            if cidr not in result_subnets:
                result_subnets[cidr] = {}
                result_subnets[cidr]['id'] = subnet_id
                result_subnets[cidr]['vms'] = []

            for server in active_servers:
                if bool(server.addresses) == True:
                    network_key = list(server.addresses)[0]
                    ip = server.addresses[network_key][0]['addr']
                    # If IP address is in the subnet range we increment the server count
                    if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr):
                        result_subnets[cidr]['vms'].append(server)

        def collect_subnet_data(result_subnets):
            subnet_data = []

            for subnet in result_subnets:
                subnet_obj = {}
                # Collecting current subnet hypervisors
                subnet_vms = result_subnets[subnet]['vms']

                subnet_obj['subnet'] = f"{subnet} - {result_subnets[subnet]['id']}"
                zones = []
                zones_vms = {}
                subnet_obj['zones'] = get_zones_data(
                    zones_vms, zones, subnet_vms)
                subnet_data.append(subnet_obj)
            return subnet_data

        def get_zones_data(zones_vms, zones, subnet_vms):
            for server in subnet_vms:
                zone = server['OS-EXT-AZ:availability_zone']
                if zone not in zones:
                    zones.append(zone)
                    zones_vms[zone] = []
                    zones_vms[zone].append(server)
                else:
                    zones_vms[zone].append(server)

            zones_data = []
            for zone in zones_vms:
                vms = zones_vms[zone]
                count = len(vms)
                do_not_migrate_vms = len([
                    vm for vm in vms if vm.project_id in do_not_migrate_projects])
                migrated_vms = ([vm for vm in vms if "migration_dst" in vm.metadata.keys()
                                 and any(s.id == vm.metadata['migration_dst'] for s in dest_servers_with_migration_meta)])
                migrated_active = len(
                    [vm for vm in migrated_vms if vm.status == 'ACTIVE'])
                migrated_inactive = len(
                    [vm for vm in migrated_vms if vm.status != 'ACTIVE'])
                unlinked_vms = len(
                    [vm for vm in vms if vm.project_id in projects_with_no_migrate_meta])
                to_be_migrated = count - do_not_migrate_vms - unlinked_vms
                zones_data.append({'zone': zone,
                                   'count': count,
                                   'migrated_active': migrated_active,
                                   'migrated_inactive': migrated_inactive,
                                   'do_not_migrate': do_not_migrate_vms,
                                   'unlinked': unlinked_vms,
                                   'to_be_migrated': to_be_migrated})
            return zones_data

        result_data = collect_subnet_data(result_subnets)

        if json_output:
            return {env: result_data}
        else:
            headers = ['Zone', 'Active Count', 'Migrated Active', 'Migrated Inactive',
                       'Do not migrate', 'Unlinked', 'To be migrated']
            for subnet in result_data:
                print('----------------------------------------------')
                print(f"Subnet: {subnet['subnet']}")
                values = [x.values() for x in subnet['zones']]
                table = Table(headers, values)
                table.print_table()


class CombinedZoneCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        # Getting a list of all projects
        projects = cli.list_projects()

        # Filtering only the projects that don't have the migrate_to metadata
        projects_with_no_migrate_meta = [
            p.id for p in projects if 'migrate_to' not in p.meta]

        # Filtering projects that have "do_not_migrate" tag
        do_not_migrate_projects = [p.id for p in projects if p.meta.get(
            'migrate_to') == "do_not_migrate"]

        # Servers mapping:
        server_map = {
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

        def get_zones(servers):
            zones = []
            zones_vms = {}

            for server in servers:
                zone = server['OS-EXT-AZ:availability_zone']
                if 'gen' not in zone:
                    if env == 'sin_private' and 'prd' in zone:
                        continue
                    else:
                        if zone not in zones:
                            zones.append(zone)
                            zones_vms[zone] = []
                            zones_vms[zone].append(server)
                        else:
                            zones_vms[zone].append(server)
            return zones_vms

        def get_active_vms(vms):
            active_vms = [vm for vm in vms if vm.status == 'ACTIVE']
            return active_vms

        def get_migrated_vms(vms, dest_servers_with_migration_meta):
            migrated = ([vm for vm in vms if "migration_dst" in vm.metadata.keys()
                         and any(s.id == vm.metadata['migration_dst'] for s in dest_servers_with_migration_meta)])
            return migrated

        def get_migrated_active_vms(migrated):
            migrated_active = len(
                [vm for vm in migrated if vm.status == 'ACTIVE'])
            return migrated_active

        def get_migrated_inactive_vms(migrated):
            migrated_inactive = len(
                [vm for vm in migrated if vm.status != 'ACTIVE'])
            return migrated_inactive

        def get_do_not_migrate_vms(active_vms, do_not_migrate_projects):
            do_not_migrate_vms = len([
                vm for vm in active_vms if vm.project_id in do_not_migrate_projects])
            return do_not_migrate_vms

        def get_unlinked_vms(active_vms, projects_with_no_migrate_meta):
            unlinked_vms = len([
                vm for vm in active_vms if vm.project_id in projects_with_no_migrate_meta])
            return unlinked_vms

        def get_to_be_migrated(active_vms, do_not_migrate_vms, unlinked_vms):
            to_be_migrated = len(active_vms) - \
                do_not_migrate_vms - unlinked_vms
            return to_be_migrated

        def get_result_zones(zones_vms, do_not_migrate_projects, projects_with_no_migrate_meta, dest_servers_with_migration_meta):
            result_zones = []
            for zone in zones_vms:
                vms = zones_vms[zone]
                active_vms = get_active_vms(vms)
                migrated = get_migrated_vms(
                    vms, dest_servers_with_migration_meta)
                migrated_active = get_migrated_active_vms(migrated)
                migrated_inactive = get_migrated_inactive_vms(migrated)
                do_not_migrate_vms = get_do_not_migrate_vms(
                    active_vms, do_not_migrate_projects)
                unlinked_vms = get_unlinked_vms(
                    active_vms, projects_with_no_migrate_meta)
                to_be_migrated = get_to_be_migrated(
                    active_vms, do_not_migrate_vms, unlinked_vms)
                result_zones.append({'zone': zone, 'count': len(active_vms), 'migrated_inactive': migrated_inactive, 'migrated_active': migrated_active,
                                    'do_not_migrate': do_not_migrate_vms, 'unlinked': unlinked_vms, 'to_be_migrated': to_be_migrated})
            return result_zones

        result_zones = get_result_zones(get_zones(
            servers), do_not_migrate_projects, projects_with_no_migrate_meta, dest_servers_with_migration_meta)

        if json_output:
            return {env: result_zones}
        else:
            headers = ['Zone', 'Count', 'Migrated Inactive', 'Migrated Active',
                       'Do not migrate', 'Unlinked', 'To be migrated']
            values = [x.values() for x in result_zones]
            table = Table(headers, values)
            table.print_table()


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
        try:
            projects = cli.list_projects()
        except JSONDecodeError:
            # This likes to error randomly in phx_private
            print(f"Error listing projects from cloud {env} - trying one more time.")
            sleep(10)
            projects = cli.list_projects()

        # Filtering projects that have "do_not_migrate" tag
        do_not_migrate_projects = [p.id for p in projects if p.meta.get(
            'migrate_to') == "do_not_migrate"]

        # Filtering only the projects that don't have the migrate_to metadata
        projects_with_no_migrate_meta = [
            p.id for p in projects if 'migrate_to' not in p.meta]

        # Filtering the subnets to get only the once that are not floating
        needed_subnets = [
            s for s in subnets if 'floating' not in s.name and 'lbaas' not in s.name]

        # Servers mapping:
        def get_dest_servers_with_migration_meta(env):
            server_map = {
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

            return dest_servers_with_migration_meta

        dest_servers = get_dest_servers_with_migration_meta(env)

        # Iterating through all subnets and servers to find which servers use which subnets
        def get_network_name(network_id, networks):
            for n in networks:
                if n.id == network_id:
                    return n.name
            return ''

        def process_subnet(sub, networks, servers, env, result_subnets):
            cidr = sub.cidr
            subnet_name = sub.name
            subnet_id = sub.id
            network_id = sub.network_id
            network_name = get_network_name(network_id, networks)

            if should_skip_subnet(network_name, env):
                return
            else:
                if cidr not in result_subnets:
                    result_subnets[cidr] = create_subnet_dict(
                        subnet_name, subnet_id, network_name)

                add_servers_to_subnet(servers, cidr, result_subnets)

        def should_skip_subnet(network_name, env):
            return ('gen' in network_name) or (env == 'sin_private' and 'prd' in network_name)

        # def should_skip_subnet(network_name, env):
        #     return ('gen' in network_name and env == 'sin_private') or 'prd' in network_name

        def create_subnet_dict(subnet_name, subnet_id, network_name):
            return {
                'name': subnet_name,
                'id': subnet_id,
                'network_zone': network_name,
                'vms': [],
                'hvs': [],
                'zones': []
            }

        def add_servers_to_subnet(servers, cidr, result_subnets):
            for server in servers:
                if bool(server.addresses) == True:
                    network_key = list(server.addresses)[0]
                    ip = server.addresses[network_key][0]['addr']

                    if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr):
                        result_subnets[cidr]['vms'].append(server)

                        server_hypervisor = server.hypervisor_hostname

                        if server_hypervisor not in result_subnets[cidr]['hvs']:
                            result_subnets[cidr]['hvs'].append(
                                server_hypervisor)

                        zone = server['OS-EXT-AZ:availability_zone']

                        if zone not in result_subnets[cidr]['zones']:
                            result_subnets[cidr]['zones'].append(zone)

        def process_subnets(needed_subnets, networks, servers, env):
            result_subnets = {}
            for sub in needed_subnets:
                process_subnet(sub, networks, servers, env, result_subnets)
            return result_subnets

        headers = ['Subnet', 'Name', 'Subnet ID',
                   'Network Name', "VMs count", 'Active', 'Migrated Active', 'Migrated Inactive', 'Do not migrate', 'Unlinked', 'To be migrated', 'HVs count', 'Zone']

        result_subnets = process_subnets(
            needed_subnets, networks, servers, env)
        subnets_data = []

        def subnet_total_usage(subnet, active_vms, do_not_migrate_vms, unlinked_vms):
            if "Total usage" not in headers:
                headers.append('Total usage')
            # Collecting current subnet hypervisors
            subnet_hvs = result_subnets[subnet]['hvs']
            # Collecting current subnet servers
            to_be_migrated_vms = [vm for vm in active_vms if vm not in do_not_migrate_vms and vm not in unlinked_vms]
            # Filtering current subnet servers to select only IDs
            subnet_vms_ids = [vm.id for vm in to_be_migrated_vms]
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
            return f"{round(total_subnet_disk_usage / 1024, 1)}G"

        for subnet in result_subnets:
            subnet_obj = {}

            # Collecting all active VMs on the subnet
            active_vms = [vm for vm in result_subnets[subnet]
                          ['vms'] if vm.status == 'ACTIVE']
            migrated_vms = [vm for vm in result_subnets[subnet]['vms'] if "migration_dst" in vm.metadata.keys(
            ) and any(s.id == vm.metadata['migration_dst'] for s in dest_servers)]
            migrated_active = len(
                [vm for vm in migrated_vms if vm.status == 'ACTIVE'])
            migrated_inactive = len(
                [vm for vm in migrated_vms if vm.status != 'ACTIVE'])
            do_not_migrate_vms = [
                vm for vm in active_vms if vm.project_id in do_not_migrate_projects]
            unlinked_vms = [
                vm for vm in active_vms if vm.project_id in projects_with_no_migrate_meta]
            subnet_obj = {
                'subnet': subnet,
                'name': result_subnets[subnet]['name'],
                'subnet_id': result_subnets[subnet]['id'],
                'network_zone': result_subnets[subnet]['network_zone'],
                'count': len(result_subnets[subnet]['vms']),
                'active': len(active_vms),
                'migrated_active': migrated_active,
                'migrated_inactive': migrated_inactive,
                'do_not_migrate': len(do_not_migrate_vms),
                'unlinked': len(unlinked_vms),
                'to_be_migrated': len(active_vms) - len(do_not_migrate_vms) - len(unlinked_vms),
                'hypervisors': len(result_subnets[subnet]['hvs']),
                'zones': result_subnets[subnet]['zones']
            }

            if usage:
                subnet_obj['total_usage'] = subnet_total_usage(subnet, active_vms,
                                                               do_not_migrate_vms, unlinked_vms)

            subnets_data.append(subnet_obj)

        if json_output:
            return {env: sorted(subnets_data, key=lambda x: int((x['count'])), reverse=True)}
        else:
            values = [x.values() for x in sorted(
                subnets_data, key=lambda x: int(x['to_be_migrated']), reverse=True)]
            table = Table(headers, values)
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
        projects = self._list_all_projects(cli)
        dst_project_ids, dst_project_names = self._get_destination_cloud_data(
            env)
        projects_data = self._get_projects_to_migrate(
            projects, dst_project_ids, dst_project_names)
        if json_output:
            return {env: projects_data}
        else:
            headers = ['Name', 'ID', 'Owning Group', 'Set destination project']
            values = [x.values() for x in projects_data]
            table = Table(headers, values)
            table.print_table()

    def _list_all_projects(self, cli):
        projects = cli.identity.projects()
        return projects

    def _get_destination_cloud_data(self, env):
        cloud_map = {
            'iad_private': 'iad_osng',
            'phx_private': 'phx_osng',
            'sin_private': 'sin_osng',
            'phx_understage': 'phx_nxt_2'
        }
        # Getting destination cloud data
        dst_cli = self._get_client(cloud_map[env])
        # Getting destination cloud projects
        dst_projects = dst_cli.list_projects()
        dst_project_ids = [p.id for p in dst_projects]
        dst_project_names = [p.name for p in dst_projects]
        return dst_project_ids, dst_project_names

    def _get_projects_to_migrate(self, projects, dst_project_ids, dst_project_names):
        projects_data = []
        for project in projects:
            if project.meta.get('migrate_to'):
                if project.meta.get('migrate_to') != 'do_not_migrate':
                    if project.meta.get('migrate_to') not in dst_project_ids and project.meta.get('migrate_to') not in dst_project_names:
                        projects_data.append({
                            'name': project.name,
                            'id': project.id,
                            'owning_group': self._owning_group_formatter(project.meta.get('owning_group', 'Unknown')),
                            'set_dst_project': project.meta.get('migrate_to')
                        })
        return projects_data


class VMsWithMultipleFipsCollector(Collector):
    def get_resources(self, env, json_output):
        cli = self._get_client(env)

        # Getting a list of all servers
        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000})

        def generate_do_not_migrate_project_ids(cli):
            # Set the pagination size to 50 projects per page
            # Adjust this value as needed
            pagination_size = 50

            # Use the `limit` and `marker` parameters to paginate the results
            marker = None
            projects = []

            while True:
                page = cli.identity.projects(
                    limit=pagination_size, marker=marker)

                if not page:
                    break

                projects.extend(page)
                marker = page[-1].id

            do_not_migrate_projects = [
                p for p in projects
                if p.get('meta', {}).get('migrate_to') == 'do_not_migrate'
            ]
            do_not_migrate_project_ids = [
                p.id for p in do_not_migrate_projects]

            return do_not_migrate_project_ids

        ports = cli.list_ports()
        floating_ips = cli.list_floating_ips()

        server_data = []

        headers = ['Name', 'ID', 'Owning group', 'FIPs']

        def get_floating_ips(server):
            fips = []
            server_ports = [p for p in ports if p["device_id"] == server.id]
            for port in server_ports:
                port_flips = [
                    f for f in floating_ips if f["port_id"] == port.id]
                for fip in port_flips:
                    fips.append(fip.floating_ip_address)
            return fips

        do_not_migrate_project_ids = generate_do_not_migrate_project_ids(cli)

        needed_servers = [
            s for s in servers if s.project_id not in do_not_migrate_project_ids]

        for server in needed_servers:
            server_fips = get_floating_ips(server)

            if len(server_fips) > 1:
                server_data.append({'name': server.name, 'id': server.id, 'owning_group': self._owning_group_formatter(server.metadata.get(
                    'owning_group', 'None')), 'fips': server_fips})

        if json_output:
            return {env: server_data}
        else:
            if len(server_data) > 0:
                values = [x.values() for x in server_data]
                table = Table(headers, values)
                table.print_table()
            else:
                print("There are no VMs with multiple FIPs in this cloud")


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
                result_subnets[cidr] = {
                    'name': sub.cidr,
                    'id': subnet_id,
                    'network_zone': network_name,
                    'vms': []
                }
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


class UnlinkedCollector(Collector):
    def get_resources(self, env, zone):
        cli = self._get_client(env)

        servers = cli.list_servers(
            all_projects=True, bare=True, filters={'limit': 1000, 'vm_state': 'ACTIVE',
                                                   'availability_zone': zone})

        projects = cli.list_projects()
        unlinked_projects = [
            p.id for p in projects if 'migrate_to' not in p.meta]

        result_servers = []

        for server in servers:
            if server.project_id in unlinked_projects:
                result_servers.append(
                    {'name': server.name, 'id': server.id, 'project': server.project_id})

        headers = ['Name', 'ID', 'Project']

        values = [x.values() for x in result_servers]
        table = Table(headers, values)
        table.print_table()


class SubnetCsvCollector(Collector):
    def get_resources(self, env, subnet, zone, csv_output):
        cli = self._get_client(env)
        if zone:
            servers = cli.list_servers(
                all_projects=True, bare=True, filters={
                    'limit': 1000,
                    'vm_state': 'ACTIVE',
                    'availability_zone': zone
                })
        else:
            print("No zone selected! Including all availability zones!")
            servers = cli.list_servers(
                all_projects=True, bare=True, filters={
                    'limit': 1000,
                    'vm_state': 'ACTIVE'
                })

        try:
            projects = cli.list_projects()
        except JSONDecodeError:
            # This likes to error randomly in phx_private
            sleep(10)
            projects = cli.list_projects()

        def get_dst_project(server, dst_projects):
            dst_project = None
            if server['metadata'].get('migrate_to'):
                dst_project_unsafe = server['metadata'].get('migrate_to')
            else:
                project = [p for p in projects if p.id == server.project_id]
                project = project[0] if project else None
                try:
                    dst_project_unsafe = project.get('meta').get('migrate_to')
                except AttributeError:
                    pass

            if dst_project_unsafe:
                if dst_project_unsafe == 'do_not_migrate':
                    return {'id': 'do_not_migrate', 'name': 'do_not_migrate'}
                dst_project = [
                    p for p in dst_projects if p.id == dst_project_unsafe]
                if not dst_project:
                    dst_project = [
                        p for p in dst_projects if p.name == dst_project_unsafe]

            if dst_project:
                return dst_project[0]
            else:
                return {'id': 'invalid', 'name': dst_project_unsafe}

        def get_filtered_instances():
            filtered_instances = []
            for instance in servers:
                if not get_dst_project(instance, dst_projects):
                    continue
                filtered_instances.append(instance)

            # filtered_instances = [instance for instance in filtered_instances if instance.addresses]
            return filtered_instances

        def get_subnet():
            return cli.get_subnet_by_id(subnet)

        def get_initial_ping(ip):
            try:
                response = os.system(f"ping -c 1 -t 3 -n -q {ip} > /dev/null")
                if response == 0:
                    return "Success"
                else:
                    return "Failed"
            except Exception:
                return "Failed"

        def get_floating_ips(server):
            fips = []
            for port in cli.list_ports({'device_id': server.id}):
                for fip in cli.list_floating_ips({'port_id': port.id}):
                    fips.append(fip.floating_ip_address)
            if len(fips) > 0:
                # Can't use comma here in a CSV. Semicolon and decimal also used in some regions.
                return '-'.join(fips)
            else:
                return ''

        def get_dst_projects(env):
            cloud_map = {
                'iad_private': 'iad_osng',
                'phx_private': 'phx_osng',
                'sin_private': 'sin_osng',
                'phx_understage': 'phx_nxt_2'
            }
            # Getting destination cloud data
            dst_cli = self._get_client(cloud_map[env])
            # Getting destination cloud projects
            dst_projects = dst_cli.list_projects()
            return dst_projects

        def generate_output(stdout):
            subnet = get_subnet()
            table_data = []
            dst_projects = get_dst_projects(env)

            field_names = ['src_vm', 'vm.name', 'vm.project_id', 'dst_project',
                           'dst_project_name', 'fip', 'initial_ping']

            az = zone if zone else 'all'
            with open(f"migration_{subnet.id}_{az}.csv", mode='w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=field_names)
                writer.writeheader()

                for instance in servers:
                    for address in instance.addresses.values():
                        for address_detail in address:
                            ip = address_detail['addr']
                            if ipaddress.ip_address(ip) in ipaddress.ip_network(subnet.cidr):
                                dst_project = get_dst_project(
                                    instance, dst_projects)
                                row = {
                                    'src_vm': instance.id,
                                    'vm.name': instance.name,
                                    'vm.project_id': instance.project_id,
                                    'dst_project': dst_project['id'],
                                    'dst_project_name': dst_project['name'],
                                    'fip': get_floating_ips(instance),
                                    'initial_ping': get_initial_ping(ip)
                                }
                                writer.writerow(row)
                                if stdout:
                                    table_data.append(row.values())

            if stdout:
                table = Table(field_names, table_data)
                table.print_table()

        generate_output(csv_output)


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
            'multifips': VMsWithMultipleFipsCollector(),
            'zones': ZoneCollector(),
            'combined_zones': CombinedZoneCollector()
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
                                              'empty_projects', 'empty_hvs', 'multifips', 'group',
                                              'project_validate', 'zones', 'unlinked',
                                              'combined_zones', 'csvsubnet',
                                              'migrated_oh', 'all'],
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
                        choices=['subnets', 'risky', 'hypervisors', 'vms_per_subnet',
                                 'vms_per_hv', 'projects', 'empty_projects',
                                 'project_validate', 'multifips', 'zones', 'combined_zones'])
    parser.add_argument('-g', '--group',
                        help='Show which subnets this owning group has VMs under',
                        action='store',
                        dest='group')
    parser.add_argument('-z', '--zone',
                        help='Provide AV zone to list VMs under',
                        action='store',
                        dest='zone')
    parser.add_argument('--subnet',
                        help='Provide Subnet to generate list all instances under that subnet',
                        action='store',
                        dest='subnet')
    parser.add_argument('--print',
                        help='Write to stdout',
                        action='store_true',
                        dest='stdout', default=False)

    args = parser.parse_args()

    if args.verbose:
        openstack.enable_logging(
            # With the verbose option on full output will be show and stored in the "collector.log" file
            debug=True, path='collector.log', stream=sys.stdout)

    # Defying dictionary with the possible collectors and their filters
    collectors = {
        'servers': {'type': ServerCollector(),
                    'filters': [
            args.env, args.sorter or 'usage', args.hours or 24, args.bigger or 0]},
        'hypervisors': {'type': HypervisorCollector(),
                        'filters': [args.env, args.json_output]},
        'risky': {'type': HighRiskCollector(),
                  'filters': [args.env, args.json_output]},
        'subnets': {'type': SubnetCollector(),
                    'filters': [args.env, args.usage, args.json_output]},
        'vmpersub': {'type': VMsPerSubnetCollector(),
                     'filters': [args.env, args.json_output]},
        'vmperhv': {'type': VMsPerHypervisorCollector(),
                    'filters': [args.env, args.json_output]},
        'projects': {'type': ProjectCollector(),
                     'filters': [args.env, args.json_output]},
        'empty_projects': {'type': EmptyProjectCollector(),
                           'filters': [args.env, args.json_output]},
        'empty_hvs': {'type': EmptyHypervisorCollector(),
                      'filters': [args.env, args.json_output]},
        'project_validate': {'type': ProjectValidator(),
                             'filters': [args.env, args.json_output]},
        'multifips': {'type': VMsWithMultipleFipsCollector(),
                      'filters': [args.env, args.json_output]},
        'migrated_oh': {'type': MigratedOHVMSCollector(),
                        'filters': [args.env]},
        'group': {'type': OwningGroupCollector(),
                  'filters': [args.env, args.group]},
        'zones': {'type': ZoneCollector(),
                  'filters': [args.env, args.json_output]},
        'unlinked': {'type': UnlinkedCollector(),
                     'filters': [args.env, args.zone]},
        'combined_zones': {'type': CombinedZoneCollector(),
                           'filters': [args.env, args.json_output]},
        'csvsubnet': {'type': SubnetCsvCollector(),
                      'filters': [args.env, args.subnet,
                                  args.zone, args.stdout]},
        'all': {'type': AllCollector(), 'filters': [args.which, args.usage]}
    }

    # Creating a new collector depending on the provided type
    collector = collectors[args.collector]['type']
    # Adding the filters for that particular collector
    filters = (collectors[args.collector]['filters'])
    collector.get_resources(*list(filters))


if __name__ == '__main__':
    main()
