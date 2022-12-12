# Openstack Collector

Tool that gathers data regarding openstack hypervisors and instances

## Help menu 

```bash
collector --help
usage: collector.py [-e ENV] [-v --verbose] [-s --sort] [-b]

Collects data via OpenStack API

positional arguments:
  {servers,hypervisors}
                        Collect data about instances or hypervisors

optional arguments:
  -h, --help            show this help message and exit
  -e ENV, --env ENV     Cloud environment for which the results will be shown
  -s {name,status,date,flavor,disk,ram,vcpus}, --sort {name,status,date,flavor,disk,ram,vcpus}
  -b BIGGER             Filter instances by flavor size bigger than the provided value in GB
  -v, --verbose         Showing verbose output for the query
  -t HOURS              Show number of VMs created in the last specified hours
  -d, --disk            List each VM real disk usage on every HV
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
collector -e ams_private hypervisors
Number of HVs on ams_private: 135
Number of HVs with 0 running VMs: 40
Total disk used: 75.1 TB
Total free space: 284585 GB
+-------------------------------+-------+--------------+-----------+------------+------------+-------------+
|              Name             | State |   Host IP    | Disk size | Used space | Free space | Running VMs |
+-------------------------------+-------+--------------+-----------+------------+------------+-------------+
| n3plcldhv001-02.prod.ams3.gdg |   up  |  10.30.12.2  |  1.33 TB  |   860 GB   |   499 GB   |      4      |
| n3plcldhv001-01.prod.ams3.gdg |   up  |  10.30.12.1  |  1.33 TB  |   940 GB   |   419 GB   |      4      |
| n3plcldhv001-03.prod.ams3.gdg |   up  |  10.30.12.3  |  1.33 TB  |   900 GB   |   459 GB   |      7      |
| n3plcldhv001-04.prod.ams3.gdg |   up  |  10.30.12.4  |  1.33 TB  |   160 GB   |  1199 GB   |      1      |
| n3plcldhv001-05.prod.ams3.gdg |   up  |  10.30.12.5  |  1.33 TB  |   140 GB   |  1219 GB   |      1      |
| n3plcldhv001-06.prod.ams3.gdg |   up  |  10.30.12.6  |  1.33 TB  |   700 GB   |   659 GB   |      3      |
| n3plcldhv002-22.prod.ams3.gdg |   up  | 10.36.27.214 |  2.67 TB  |   660 GB   |  2079 GB   |      6      |
```

## Collecting servers data

```bash
collector -e ams_private servers
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
+-----------------+---------+----------------------+-------------+----------------+-------+-------+
|  Instance name  |  State  |      Created at      |    Flavor   | Allocated Disk |  RAM  | VCPUs |
+-----------------+---------+----------------------+-------------+----------------+-------+-------+
|  n3plvps4app47  | SHUTOFF | 2022-12-07T22:27:11Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app44  | SHUTOFF | 2022-12-07T22:27:11Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app42  | SHUTOFF | 2022-12-07T22:27:10Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app41  | SHUTOFF | 2022-12-07T22:27:10Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app46  | SHUTOFF | 2022-12-07T22:27:10Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app43  | SHUTOFF | 2022-12-07T22:27:10Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app45  | SHUTOFF | 2022-12-07T22:27:10Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app39  | SHUTOFF | 2022-12-07T21:00:15Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app22  |  ACTIVE | 2022-12-07T20:49:51Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app18  |  ACTIVE | 2022-12-07T20:48:05Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app21  |  ACTIVE | 2022-12-07T20:48:05Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app14  |  ACTIVE | 2022-12-07T20:46:13Z |  m1.medium  |       60       |  4096 |   4   |
|  n3plvps4app16  |  ACTIVE | 2022-12-07T20:46:12Z |  m1.medium  |       60       |  4096 |   4   |
```

## Collecting each VM real disk usage

```bash
collector -e ams_private hypervisors -d
Number of HVs on ams_private: 135
Number of HVs with 0 running VMs: 40
Total disk used: 74.43 TB
Total free space: 278.58 TB
------------------------------------
Hypervisor: n3plcldhv001-02.prod.ams3.gdg
+----------------+--------+--------------------------------------+----------------+------------+
|      Name      | State  |                 UUID                 | Allocated disk | Disk Usage |
+----------------+--------+--------------------------------------+----------------+------------+
| n3plipmimsg007 | ACTIVE | 3f3cd35d-6dfe-465f-90c3-aa520b0acd57 |      360G      |    53G     |
|  n3plpncps01   | ACTIVE | f71dd510-6a76-4e52-a8f8-ec141748c316 |      240G      |    28G     |
| n3pliciendp001 | ACTIVE | 156d14c4-e9a1-4111-8d16-fba3ac9dca17 |      120G      |    32G     |
|   he-jumper    | ACTIVE | 2404599c-c981-4e61-b5b0-235efda300ce |      40G       |    17G     |
+----------------+--------+--------------------------------------+----------------+------------+
------------------------------------
Hypervisor: n3plcldhv001-01.prod.ams3.gdg
+----------------+--------+--------------------------------------+----------------+------------+
|      Name      | State  |                 UUID                 | Allocated disk | Disk Usage |
+----------------+--------+--------------------------------------+----------------+------------+
| n3possyncutil1 | ACTIVE | 4c1d4c48-05b0-4052-a4dd-90536e8b8260 |      240G      |    240G    |
|  n3plproxy001  | ACTIVE | df7723f3-6311-4199-9d3e-c5d1e10d246a |      120G      |    28G     |
|   dbox-win1    | ACTIVE | a8f95b60-825e-4a4f-a924-2d3e82bdf8f1 |      240G      |    236G    |
|   n3pliiq001   | ACTIVE | 4e221b4a-5ba3-4584-9c91-1e2ff9ea84b1 |      240G      |    27G     |
+----------------+--------+--------------------------------------+----------------+------------+
------------------------------------
Hypervisor: n3plcldhv001-03.prod.ams3.gdg
+----------------+---------+--------------------------------------+----------------+------------+
|      Name      |  State  |                 UUID                 | Allocated disk | Disk Usage |
+----------------+---------+--------------------------------------+----------------+------------+
|  n3ansible02   |  ACTIVE | 2bea6025-f10f-4557-a132-f5033ec4b662 |      240G      |    74G     |
|  n3phdtest01   |  ACTIVE | 57559315-0239-4eeb-987b-f0486314473b |      40G       |    14G     |
|  n3phdtest02   |  ACTIVE | 1ddd387f-b86a-46f7-a4f8-9c78253ed578 |      40G       |    13G     |
| n3plztncldsg01 |  ACTIVE | c61be2c7-4801-490c-a082-0d126a48d228 |      240G      |    76G     |
|  n3plshell001  |  ACTIVE | 3b004f74-df11-4bd3-8e6e-5e1f04efe43b |      120G      |    75G     |
| n3pancmbgp0303 |  ACTIVE | a4b2ef23-80da-4caa-adba-7cc418f2bba5 |      60G       |    21G     |
| n3plncmbgp0303 | SHUTOFF | 53760c4e-9b05-4e39-8f31-c57c29928092 |      60G       |    19G     |
+----------------+---------+--------------------------------------+----------------+------------+
```