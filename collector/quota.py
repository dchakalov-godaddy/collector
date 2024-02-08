#!/usr/bin/env python3

import argparse
import openstack

CHANGE_PERCENTAGE = 1.5


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description='Collecting all vms under GenNet subnets with migrate_to meta',
        usage="overlap.py [-e ENV]",
    )
    parser.add_argument('-e', '--env',
                        help='Cloud environment for which the results will be shown',
                        action='store',
                        dest='env')
    parser.add_argument('-p', '--project',
                        help='Project name or ID',
                        action='store',
                        dest='project')

    return parser.parse_args(args)


def run(**kwargs):
    cloud = kwargs['cloud']
    project_identifier = kwargs['project']

    # valid_clouds = self.bot.topo_loader.env_names
    # replier = functools.partial(
    #     self.message.reply_text, threaded=True, prefixed=False
    # )

    # Handle invalid cloud name
    # if cloud not in valid_clouds:
    #     replier(f"ERROR: Cloud must be one of {','.join(valid_clouds)}")
    #     return

    # Attempt to fetch OpenStack sdk client
    try:
        cloud_client = openstack.connect(cloud=cloud)

        project = cloud_client.identity.find_project(
            name_or_id=project_identifier, ignore_missing=True)

        # Handle invalid project name or ID
        if project is None:
            print(f"ERROR: Project `{project_identifier}` not found "
                    f"in cloud {cloud}")
            return

        project_id = project.id
        project_name = project.name

        has_cinder = True if cloud == 'phx_nxt_2' else False

        print(f"Found project `{project_name}` ({project_id}) "
              f"in cloud `{cloud}`. Getting quotas now ...")

        default_quotas = get_default_quota(cloud_client,
                                           project_id, has_cinder)

        # Fetching quotas and updating them
        quotas = get_current_quota(cloud_client,
                                   project_id, has_cinder, 'Current')
        changed_quotas_counter = update_quotas(
            cloud_client,
            project_id, quotas, default_quotas, has_cinder)
    except openstack.exceptions.ResourceNotFound:
        print(f"ERROR: Project `{project_identifier}` "
              f"not found in cloud `{cloud}`")
        return

    # Provide feedback on the operation`s status
    if changed_quotas_counter == 0:
        print("No quotas were updated. Usage is below the default quota.")
    else:
        print(f"Successfully updated quota for project `{project_name}` "
              f"in cloud `{cloud}`.")
        # Calling the method again to provide updated quota details
        get_current_quota(
            cloud_client, project_id, has_cinder, 'Updated')


def get_default_quota(cloud_client, project_id, has_cinder):
    default_compute_quota = cloud_client.get_compute_quotas('default')
    default_network_quota = \
        cloud_client.network.get_quota_default(project_id)

    default_quota_dict = {
        'ram': default_compute_quota.ram,
        'cores': default_compute_quota.cores,
        'instances': default_compute_quota.instances,
        'floating_ips': default_network_quota.floating_ips
    }

    if has_cinder:
        default_volume_quota = \
            cloud_client.block_storage.get_quota_set_defaults(
                project_id)
        cinder_quota_dict = {
            'volumes': default_volume_quota.volumes,
            'snapshots': default_volume_quota.snapshots,
            'gigabytes': default_volume_quota.gigabytes,
            'backups': default_volume_quota.backups,
            'backup_gigabytes': default_volume_quota.backup_gigabytes
        }
        default_quota_dict.update(cinder_quota_dict)

    return default_quota_dict

# Method to fetch current quota for the project


def get_current_quota(cloud_client,
                      project_id, has_cinder, status):
    # Fetch compute, volume and network quotas
    quota = {}

    compute_usage = cloud_client.get_compute_limits(project_id)

    compute_quotas = {
        'ram': compute_usage['maxTotalRAMSize'],
        'cores': compute_usage['maxTotalCores'],
        'instances': compute_usage['maxTotalInstances'],
        'ram_used': compute_usage['totalRAMUsed'],
        'cores_used': compute_usage['totalCoresUsed'],
        'instances_used': compute_usage['totalInstancesUsed'],
    }

    quota['compute_quotas'] = compute_quotas

    # Handling quotas for Cinder if available
    if has_cinder:
        volume_limits = cloud_client.get_volume_limits(project_id)
        volume_quota = cloud_client.get_volume_quotas(project_id)
        volume_quotas = {
            'volumes': volume_quota.volumes,
            'snapshots': volume_quota.snapshots,
            'gigabytes': volume_quota.gigabytes,
            'backups': volume_quota.backups,
            'backup_gigabytes': volume_quota.backup_gigabytes,
            'volumes_used': volume_limits.absolute['totalVolumesUsed'],
            'snapshots_used': volume_limits.absolute['totalSnapshotsUsed'],
            'gigabytes_used': volume_limits.absolute['totalGigabytesUsed'],
            'backups_used': volume_limits.absolute['totalBackupsUsed'],
            'backup_gigabytes_used':
                volume_limits.absolute['totalBackupGigabytesUsed']
        }

        quota['volume_quotas'] = volume_quotas

    floating_ips = cloud_client.network.ips(project_id=project_id)

    network_quotas = {
        'floating_ips':
            cloud_client.get_network_quotas(project_id).floating_ips,
        'floating_ips_used': len(list(floating_ips))
    }

    quota['network_quotas'] = network_quotas

    # Providing current usage/quota details
    print(
        f"{status} usage/quota for the project: \n"
        f"RAM: {compute_quotas['ram_used']}/{compute_quotas['ram']} \n"
        f"Cores: {compute_quotas['cores_used']}/"
        f"{compute_quotas['cores']} \n"
        f"Instances: {compute_quotas['instances_used']}/"
        f"{compute_quotas['instances']} \n"
        f"Floating IPs: {network_quotas['floating_ips_used']}/"
        f"{network_quotas['floating_ips']} \n"

        + ("" if not has_cinder else
            f"Volumes: {volume_quotas['volumes_used']}/"
            f"{volume_quotas['volumes']} \n"
            f"Snapshots: {volume_quotas['snapshots_used']}/"
            f"{volume_quotas['snapshots']} \n"
            f"Gigabytes: {volume_quotas['gigabytes_used']}/"
            f"{volume_quotas['gigabytes']} \n"
            f"Backups: {volume_quotas['backups_used']}/"
            f"{volume_quotas['backups']} \n"
            f"Backup Gigabytes: {volume_quotas['backup_gigabytes_used']}/"
            f"{volume_quotas['backup_gigabytes']}")
    )

    return quota

# Method to calculate the new quota value


def calculate_new_quota(usage, attribute, default_quotas):
    multiplier_factor = CHANGE_PERCENTAGE
    default_quota_value = default_quotas[attribute]
    return round(usage * multiplier_factor) if round(
        usage * multiplier_factor
    ) >= default_quota_value else default_quota_value

# Helper method for calculating multipliers


def multiply_quota_dict(quotas, attributes):
    return {attribute: multiply_quota(getattr(quotas, attribute))
            for attribute in attributes}

# Helper method for updating quotas


def update_quotas_helper(cloud_client,
                           pid, updated_quotas,
                          resource_type):
    conn_func = getattr(cloud_client, f"set_{resource_type}_quotas")
    conn_func(pid, **updated_quotas)
    print(f"Going through the {resource_type} quotas\n")

# Method to update quotas


def update_quotas(cloud_client,
                   project_id, quotas, default_quotas, has_cinder):
    changed_quotas_counter = 0

    def update_attribute_quotas(
        attribute_list, quotas_dict,
        resource_type, changed_quotas_counter
    ):
        updated_quotas = {}
        for attribute in attribute_list:
            usage_key = f"{attribute}_used"
            usage_value = quotas_dict[usage_key]
            quota_value = quotas_dict[attribute]
            updated_quotas[attribute] = calculate_new_quota(
                usage_value, attribute, default_quotas)
            if updated_quotas[attribute] != quota_value:
                changed_quotas_counter += 1
        update_quotas_helper(cloud_client, project_id,
                                   updated_quotas, resource_type)
        return changed_quotas_counter

    try:
        compute_attributes = ['ram', 'cores', 'instances']
        compute_quotas = quotas['compute_quotas']

        changed_quotas_counter = update_attribute_quotas(
            compute_attributes,
            compute_quotas, 'compute', changed_quotas_counter)

        if has_cinder:
            volume_attributes = ['gigabytes', 'volumes', 'snapshots',
                                 'backups', 'backup_gigabytes']
            volume_quotas = quotas['volume_quotas']

            changed_quotas_counter = update_attribute_quotas(
                volume_attributes,
                volume_quotas, 'volume', changed_quotas_counter)

        network_attributes = ['floating_ips']
        network_quotas = quotas['network_quotas']

        changed_quotas_counter = update_attribute_quotas(
            network_attributes,
            network_quotas, 'network', changed_quotas_counter)
    except openstack.exceptions.ResourceNotFound as e:
        print(f"ERROR: Resource not found: {e}")
        return
    except openstack.exceptions.SDKException as e:
        print(f"ERROR: SDK Exception occurred: {e}")
        return
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        return

    return changed_quotas_counter


def main():
    args = parse_args()
    cloud = args.env
    project = args.project

    run(cloud=cloud, project=project)


if __name__ == "__main__":
    main()
