#!/usr/bin/env python3

import argparse
import csv
import ipaddress
import openstack
import csv
import neutronclient.v2_0.client as neutronclient
import openstackclient

# List of clouds to be used by the script
clouds = ['ams_private', 'iad_private', 'phx_private', 'sin_private']


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description='Collecting all vms under GenNet subnets with migrate_to meta',
        usage="overlap.py [-e ENV]",
    )
    parser.add_argument('-e', '--env',
                        help='Cloud environment for which the results will be shown',
                        action='store',
                        dest='env')

    return parser.parse_args(args)


def check_migrate_to(server, projects):
    vm_project_id = server.project_id

    vm_project = [p for p in projects if p.id == vm_project_id][0]

    if 'migrate_to' in vm_project.meta and vm_project.meta['migrate_to'] != 'do_not_migrate':
        return True
    else: 
        return False
    

def add_servers_to_subnet(servers, cidr, vms, projects):
    for server in servers:
        if bool(server.addresses) == True:
            network_key = list(server.addresses)[0]
            ip = server.addresses[network_key][0]['addr']

            owning_group = server.metadata.get('owning_group', "")

            if ipaddress.ip_address(ip) in ipaddress.ip_network(cidr) and check_migrate_to(server, projects):
                vms.append({'id': server.id,
                            'name': server.name,
                            'owning_group':  owning_group,
                            'migration_dst': server.metadata.get('migration_dst')})


def generate_csv_file(data):
    args = parse_args()

    if args.env:
        mode = 'w'
    else:
        mode = 'a'

    # Open the file in the appropriate mode
    with open('gen_vms.csv', mode, newline='') as csvfile:
        fieldnames = ['id', 'name',
                      'owning_group', 'migration_dst']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        # Adding an empty row after cloud data
        writer.writerow({})


def get_vms(cloud):
    conn = openstack.connect(cloud=cloud)

    servers = conn.list_servers(
        all_projects=True, bare=True, filters={'limit': 1000})

    networks = conn.list_networks()

    gen_networks = [n for n in networks if 'gen' in n.name or (cloud == 'sin_private' and 'prd' in n.name)]

    projects = conn.list_projects()

    gen_subnets = []
    for n in gen_networks:
        subnets = conn.network.subnets(network_id=n.id)
        for s in list(subnets):
            gen_subnets.append(s)

    vms = []

    for sub in gen_subnets:
        add_servers_to_subnet(servers, sub.cidr, vms, projects)

    if len(vms) > 0:
        generate_csv_file(vms)


def test_neutron(cloud):
    conn = openstack.connect(cloud=cloud)
    # nc = neutronclient.Client(session=conn.session)

    address_groups = conn.network.get_address_group()
    print(address_groups.name)


def main():

    args = parse_args()
    cloud = args.env

    test_neutron(cloud)

    # if cloud:
    #     get_vms(cloud)
    # else:
    #     for cloud in clouds:
    #         get_vms(cloud)


if __name__ == "__main__":
    main()
