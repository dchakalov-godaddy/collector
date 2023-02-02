# Openstack Collector

Tool that gathers data regarding openstack hypervisors and instances. Uses the Ansible Python Api to collect real disk usage data for each VM

## Help menu 

```bash
❯ collector --help
usage: collector.py [-e ENV] [-v --verbose] [-s --sort] [-b] [-t] [-d --disk]

Collects data via OpenStack API

positional arguments:
  {servers,hypervisors,risky,subnets,vmpersub,vmperhv,all}
                        Collect data about instances, hypervisors or subnets

optional arguments:
  -h, --help            show this help message and exit
  -e ENV, --env ENV     Cloud environment for which the results will be shown
  -s {name,status,date,flavor,disk,ram,vcpus,usage}, --sort {name,status,date,flavor,disk,ram,vcpus,usage}
  -b BIGGER             Filter instances by flavor size bigger than the provided value in GB
  -v, --verbose         Showing verbose output for the query
  -t HOURS              Show number of VMs created in the last specified hours
  -d, --disk            List each VM real disk usage on every HV
  -j, --json            Provide output in JSON format
  -w {subnets,risky,hypervisors,vms_per_subnet}
                        Select the type of collector you wish to collect all data for
```

## OpenStack Client Configuration file

OpenStack client setup (if you have not already have one)

1. Create a file `~/.config/openstack/clouds.yaml` file
2. Within that file, add something like the following:
```yaml

---
clouds:
    sin_ztn:
        auth:
            auth_url: https://sin-ztn.openstack.int.godaddy.com:5000/
            project_domain_name: Default
            user_domain_name: Default
            project_name: openstack
            username: your-username
            password: your-password
    ams_ztn:
        auth:
            auth_url: https://ams-ztn.openstack.int.godaddy.com:5000/
            project_domain_name: Default
            user_domain_name: Default
            project_name: openstack
            username: your-username
            password: your-password
    iad_ztn:
        auth:
            auth_url: https://iad-ztn.openstack.int.godaddy.com:5000/
            project_domain_name: Default
            user_domain_name: Default
            project_name: openstack
            username: your-username
            password: your-password
...

```
This file requires your auth above ^ has `admin` privilege and assumes you have
that access in the `openstack` project.


## Basic command example

```bash
❯ collector -e ams_private hypervisors
Number of HVs on ams_private: 135
Number of HVs with 0 running VMs: 40
Total disk used: 74.38 TB
Total free space: 278.64 TB
+-------------------------------+-------+--------------+-----------+------------+------------+-------+-------------+
|              Name             | State |   Host IP    | Disk size | Used space | Free space | Use % | Running VMs |
+-------------------------------+-------+--------------+-----------+------------+------------+-------+-------------+
| n3plcldhv001-01.prod.ams3.gdg |   up  |  10.30.12.1  |  1.33 TB  |   940 GB   |   419 GB   |  69.2 |      4      |
| n3plcldhv001-03.prod.ams3.gdg |   up  |  10.30.12.3  |  1.33 TB  |   900 GB   |   459 GB   |  66.2 |      7      |
| n3plcldhv001-02.prod.ams3.gdg |   up  |  10.30.12.2  |  1.33 TB  |   860 GB   |   499 GB   |  63.3 |      4      |
| n3plcldhv002-20.prod.ams3.gdg |   up  | 10.36.27.212 |  2.67 TB  |  1440 GB   |  1299 GB   |  52.6 |      9      |
| n3plcldhv001-06.prod.ams3.gdg |   up  |  10.30.12.6  |  1.33 TB  |   700 GB   |   659 GB   |  51.5 |      3      |
| n3plcldhv002-21.prod.ams3.gdg |   up  | 10.36.27.213 |  2.67 TB  |  1380 GB   |  1359 GB   |  50.4 |      6      |
| n3plcldhv003-21.prod.ams3.gdg |   up  | 10.36.27.237 |  2.67 TB  |  1360 GB   |  1379 GB   |  49.7 |      9      |
| n3plcldhv002-24.prod.ams3.gdg |   up  | 10.36.27.216 |  2.67 TB  |  1340 GB   |  1399 GB   |  48.9 |      5      |
| n3plcldhv003-14.prod.ams3.gdg |   up  | 10.36.27.230 |  2.67 TB  |  1320 GB   |  1419 GB   |  48.2 |      6      |
```

## Collecting servers data

```bash
❯ collector -e ams_private servers
------------------------------------
Collecting data from ams_private
Number of VMs: 423
VMs created in the last 24 hours: 0
Number of VMs per disk size:
 - 480 GB: 19 VMs
 - 360 GB: 17 VMs
 - 240 GB: 112 VMs
 - 120 GB: 98 VMs
 - 60 GB: 90 VMs
 - 40 GB: 82 VMs
 - 20 GB: 5 VMs
------------------------------------
+-----------------+---------+----------------------+-------------+----------------+-----------+-------+-------+-------+
|  Instance name  |  State  |      Created at      |    Flavor   | Allocated Disk | Used disk | Use % |  RAM  | VCPUs |
+-----------------+---------+----------------------+-------------+----------------+-----------+-------+-------+-------+
|  qs-w-prodn-03  |  ACTIVE | 2021-09-13T22:32:21Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
|  qs-w-prodn-07  |  ACTIVE | 2021-09-13T22:32:13Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
|  qs-w-prodn-06  |  ACTIVE | 2021-09-13T22:32:03Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
|  qs-w-prodn-02  |  ACTIVE | 2021-09-13T22:31:56Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
|  qs-w-prodn-08  |  ACTIVE | 2021-09-13T22:31:56Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
|  n3possyncutil1 |  ACTIVE | 2020-05-08T19:28:42Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
|   n3pldnsyum02  |  ACTIVE | 2019-11-11T23:15:59Z |  m1.xlarge  |      240       |    240    | 100.0 | 16384 |   8   |
```

## Collecting each VM real disk usage

```bash
❯ collector -e ams_private vmperhv
Number of HVs on ams_private: 135
Number of HVs with 0 running VMs: 40
Total disk used: 74.43 TB
Total free space: 278.58 TB
------------------------------------
Hypervisor: n3plcldhv001-02.prod.ams3.gdg
+----------------+--------+--------------------------------------+----------------+------------+-------+
|      Name      | State  |                 UUID                 | Allocated disk | Disk Usage | Use % |
+----------------+--------+--------------------------------------+----------------+------------+-------+
|   he-jumper    | ACTIVE | 2404599c-c981-4e61-b5b0-235efda300ce |      40G       |    17G     |  42.5 |
| n3pliciendp001 | ACTIVE | 156d14c4-e9a1-4111-8d16-fba3ac9dca17 |      120G      |    32G     |  26.7 |
| n3plipmimsg007 | ACTIVE | 3f3cd35d-6dfe-465f-90c3-aa520b0acd57 |      360G      |    54G     |  15.0 |
|  n3plpncps01   | ACTIVE | f71dd510-6a76-4e52-a8f8-ec141748c316 |      240G      |    28G     |  11.7 |
+----------------+--------+--------------------------------------+----------------+------------+-------+
------------------------------------
Hypervisor: n3plcldhv001-01.prod.ams3.gdg
+----------------+--------+--------------------------------------+----------------+------------+-------+
|      Name      | State  |                 UUID                 | Allocated disk | Disk Usage | Use % |
+----------------+--------+--------------------------------------+----------------+------------+-------+
| n3possyncutil1 | ACTIVE | 4c1d4c48-05b0-4052-a4dd-90536e8b8260 |      240G      |    240G    | 100.0 |
|   dbox-win1    | ACTIVE | a8f95b60-825e-4a4f-a924-2d3e82bdf8f1 |      240G      |    236G    |  98.3 |
|  n3plproxy001  | ACTIVE | df7723f3-6311-4199-9d3e-c5d1e10d246a |      120G      |    28G     |  23.3 |
|   n3pliiq001   | ACTIVE | 4e221b4a-5ba3-4584-9c91-1e2ff9ea84b1 |      240G      |    28G     |  11.7 |
+----------------+--------+--------------------------------------+----------------+------------+-------+
```

## Collecting each VM real disk usage per Subnet
```bash
❯ collector -e ams_ztn vmpersub
----------------------------------------------
Subnet: 10.197.172.0/22 - 35c9c874-02a0-431a-9b35-239223d3ca7e - 22559.2G
+--------------------------------------+----------------------------------+------------+------------+
|                  ID                  |            Hypervisor            | Disk usage | Created by |
+--------------------------------------+----------------------------------+------------+------------+
| e74bda51-73e3-4b9e-8231-be7d7f5d3f6c | n3plztncldhv004-25.prod.ams3.gdg |    44G     |  Unknown   |
| 9eccee98-09a0-4924-87a9-22d5aa936d48 | n3plztncldhv004-25.prod.ams3.gdg |    29G     |  Unknown   |
| de0d5bff-0e0c-4cce-b7c4-f0951de63417 | n3plztncldhv004-30.prod.ams3.gdg |    58G     |  Unknown   |
| 5fe98c0b-4bd0-40a5-97cd-e913d4430a9b | n3plztncldhv004-32.prod.ams3.gdg |    85G     |  Unknown   |
| 2dd40931-8a4c-4533-806b-3dd8d3395290 | n3plztncldhv004-30.prod.ams3.gdg |    376G    |  Unknown   |
| 4cd821c9-546a-4321-ad35-cd217fa362d8 | n3plztncldhv004-26.prod.ams3.gdg |    345G    |  Unknown   |
| 981b0570-20c2-4426-b3b5-82d61586618d | n3plztncldhv004-32.prod.ams3.gdg |    73G     |  Unknown   |
| eb93e212-c71b-4d10-b36a-a244003d0527 | n3plztncldhv004-23.prod.ams3.gdg |    28G     |  Unknown   |
| b96111f6-51c2-44e1-8025-13c5b0f81ab9 | n3plztncldhv004-11.prod.ams3.gdg |    137G    |  Unknown   |
```


## Collecting data from all clouds by collector type

```bash
❯ collector all -w subnets
{
  "2023-01-23": [
    {
      "ams_ztn": [
        {
          "subnet": "10.217.192.0/22",
          "subnet_id": "caf5ddda-9cfd-45ca-9a4e-faed933e10f9",
          "network_id": "0af05db8-3ac7-4e2d-8cdb-9e12ced56fe5",
          "count": 546,
          "hypervisors": 41
        },
        {
          "subnet": "10.197.156.0/22",
          "subnet_id": "39bf2161-f618-4a7a-bdb5-daec73cabae3",
          "network_id": "0af05db8-3ac7-4e2d-8cdb-9e12ced56fe5",
          "count": 525,
          "hypervisors": 43
        },
```
