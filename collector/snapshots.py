#!/usr/bin/env python3

import argparse
import openstack
import prettytable

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

    return parser.parse_args(args)


def run(**kwargs):
    cloud = kwargs['cloud']

    try:
        cloud_client = openstack.connect(cloud=cloud)

        images = cloud_client.list_images()

        snapshots_images = []
        active_snapshot_images = []
    
        for image in images:
            props = image.properties
            if props and props.get('image_type') == 'snapshot':
                snapshots_images.append(image)
                if image.status == 'active':
                    active_snapshot_images.append(image)

        print("# Cloud: ", cloud)
        print("# Total images: ", str(len(images)))
        print("# Total snapshots: ", str(len(snapshots_images)))
        print("# Total active snapshots: ", str(len(active_snapshot_images)))

        headers = ['id', 'name']
        table = prettytable.PrettyTable()
        table.field_names = headers
        for snapshot in snapshots_images:
            table.add_row([snapshot.id, snapshot.name])
        print(table)
        # for snapshot in active_snapshot_images:
        #     print(snapshot.id + ' - ' + snapshot.name)

    except Exception as e:
        print(e)


def main():
    args = parse_args()
    cloud = args.env

    run(cloud=cloud)


if __name__ == "__main__":
    main()
