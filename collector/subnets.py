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

        # Filtering only the projects that don't have the migrate_to metadata
        projects_with_no_migrate_meta = [
            p.id for p in projects if 'migrate_to' not in p.meta]

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
            if 'gen' not in network_name:
                if env == 'sin_private' and 'prd' in network_name:
                    continue
                else:
                    if cidr not in result_subnets:
                        result_subnets[cidr] = {}
                        result_subnets[cidr]['name'] = subnet_name
                        result_subnets[cidr]['id'] = subnet_id
                        result_subnets[cidr]['network_zone'] = network_name
                        result_subnets[cidr]['vms'] = []
                        result_subnets[cidr]['hvs'] = []
                        result_subnets[cidr]['zones'] = []
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

                                zone = server['OS-EXT-AZ:availability_zone']

                                if zone not in result_subnets[cidr]['zones']:
                                    result_subnets[cidr]['zones'].append(
                                        zone)

        headers = ['Subnet', 'Name', 'Subnet ID',
                   'Network Name', "VMs count", 'Active', 'Migrated', 'Do not migrate', 'Unlinked', 'To be migrated', 'HVs count', 'Zone']

        subnets_data = []

        for subnet in result_subnets:
                subnet_obj = {}
                if usage:
                    headers.append('Total usage')
                    if "Total usage" not in headers:
                        headers.append('Total usage')
                    # Collecting current subnet hypervisors
                    subnet_hvs = result_subnets[subnet]['hvs']
                    # Collecting current subnet servers
                    subnet_vms = [vm for vm in result_subnets[subnet]
                                  ['vms'] if vm.status == 'ACTIVE']
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
                active_vms = [vm for vm in result_subnets[subnet]
                              ['vms'] if vm.status == 'ACTIVE']
                migrated_vms = len([vm for vm in active_vms if "migration_dst" in vm.metadata.keys()
                                    and any(s.id == vm.metadata['migration_dst'] for s in dest_servers_with_migration_meta)])
                do_not_migrate_vms = [
                    vm for vm in active_vms if vm.project_id in do_not_migrate_projects]
                unlinked_vms = [
                    vm for vm in active_vms if vm.project_id in projects_with_no_migrate_meta]
                subnet_obj['subnet'] = subnet
                subnet_obj['name'] = result_subnets[subnet]['name']
                subnet_obj['subnet_id'] = result_subnets[subnet]['id']
                subnet_obj['network_zone'] = result_subnets[subnet]['network_zone']
                subnet_obj['count'] = len(result_subnets[subnet]['vms'])
                subnet_obj['active'] = len(active_vms)
                subnet_obj['migrated'] = migrated_vms
                subnet_obj['do_not_migrate'] = len(do_not_migrate_vms)
                subnet_obj['unlinked'] = len(unlinked_vms)
                subnet_obj['to_be_migrated'] = len(
                    active_vms) - migrated_vms - len(do_not_migrate_vms) - len(unlinked_vms)
                subnet_obj['hypervisors'] = len(result_subnets[subnet]['hvs'])
                subnet_obj['zones'] = result_subnets[subnet]['zones']
                subnets_data.append(subnet_obj)
        

        if json_output:
            return {env: sorted(subnets_data, key=lambda x: int((x['count'])), reverse=True)} 
        else:
            values = [x.values() for x in  sorted(
                subnets_data, key=lambda x: int(x[5]), reverse=True)]
            table = Table(headers, values)
            table.print_table()
