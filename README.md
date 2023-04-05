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

## Collecting list of VMs with multiple floating IPs

```bash
❯ collector -e phx_private multifips
+-----------------+--------------------------------------+-------------------------------------+-----------------------------------------------------+
|       Name      |                  ID                  |             Owning group            |                         FIPs                        |
+-----------------+--------------------------------------+-------------------------------------+-----------------------------------------------------+
| hfl-uCkGbacPHMj | 75076ce6-0886-44ce-b4e0-1479123aebfb | 799 - DEV-HostingFoundationServices |          ['10.32.157.22', '10.32.157.217']          |
| p3tldnshaprxy01 | 44680ac2-01a7-42d4-bfc1-a9851fdc182f |         12 - OPS-Managed DNS        |          ['10.32.157.192', '10.32.142.158']         |
|  p3pldnshapx02  | 9a3db312-36e0-47f7-8cf3-741b022fd6aa |         12 - OPS-Managed DNS        |         ['216.69.136.221', '216.69.138.171']        |
|  p3pldnshapx01  | 08e5c1ea-945c-4474-b3f3-7eff7342347f |         12 - OPS-Managed DNS        |         ['216.69.136.198', '216.69.138.163']        |
| p3pldnssapi0002 | 808fdcab-25ad-425a-ac67-940258222b78 |         12 - OPS-Managed DNS        | ['10.32.154.179', '10.32.154.183', '10.32.154.182'] |
|    hreplha01    | 95d1805c-e7fe-45b0-a5d4-567a9a0bbdde |                 None                |            ['50.62.204.91', '10.22.42.1']           |
+-----------------+--------------------------------------+-------------------------------------+-----------------------------------------------------+
```


## Collecting list of Subnets containing VMs with owning provided by user

```bash
❯ collector -e ams_private group -g "DEV-Private Cloud"

 - Looking for all subnets that have VM with owning group including DEV-Private Cloud in the name...
 - Found 4 subnets containing VMs with that owning group
Lising all found subnets:
------------------------------------
10.36.28.0/22 - f3072f33-0bad-4f2d-9ed4-769a5cde8aa6 - 1 VMs
+-----------------+--------------------------------------+-------------------------+
|       Name      |                  ID                  |       Owning group      |
+-----------------+--------------------------------------+-------------------------+
| n3plztncldcon01 | a6119098-9b25-45fc-a6f0-94245f6c6b87 | 102 - DEV-Private Cloud |
+-----------------+--------------------------------------+-------------------------+

10.30.8.0/22 - 17597ea9-b562-486f-882f-938440538afb - 2 VMs
+-----------------+--------------------------------------+-------------------------+
|       Name      |                  ID                  |       Owning group      |
+-----------------+--------------------------------------+-------------------------+
| testvm-b33f1b07 | 6611be28-48d6-4f8f-86fe-25d87a648d12 | 102 - DEV-Private Cloud |
|   vader-ara-db  | dbfe4f24-9bb0-4a80-b234-e15f01dec229 | 102 - DEV-Private Cloud |
+-----------------+--------------------------------------+-------------------------+

10.36.20.0/22 - a4432946-fe51-44ab-a076-a9e254c85bf0 - 3 VMs
+-----------------+--------------------------------------+---------------------------+
|       Name      |                  ID                  |        Owning group       |
+-----------------+--------------------------------------+---------------------------+
|   darin-b2e24   | e518bc4f-370c-47ab-a7e9-8eb8715cfb23 | 12246 - DEV-Private Cloud |
|  dbing-delme20  | 9c302c3a-6906-45dd-ab21-eba241a227eb |  102 - DEV-Private Cloud  |
| n3plpubcldcon01 | e462ee84-c404-457e-8814-1e13124f5980 |  102 - DEV-Private Cloud  |
+-----------------+--------------------------------------+---------------------------+

10.30.5.0/24 - 5951609f-221c-4fc8-93fa-6aa6fbe53fd2 - 8 VMs
+----------------+--------------------------------------+-------------------------+
|      Name      |                  ID                  |       Owning group      |
+----------------+--------------------------------------+-------------------------+
| rbreker-ws22-3 | 8161c8a6-bbbf-4843-a4ef-c4fbfdb0728d | 102 - DEV-Private Cloud |
|  rbreker-a8-3  | 0cfc6351-308d-4d81-a0f4-9c21d9d05260 | 102 - DEV-Private Cloud |
| rbreker-ws22-2 | d85c8c2c-5c89-4b1f-9ae1-0848d65134dd | 102 - DEV-Private Cloud |
|  rbreker-a8-5  | 015ae05c-38f7-4054-89da-5b59d26aa657 | 102 - DEV-Private Cloud |
| rbreker-ws22-1 | 6e687a34-9d7e-46ed-bd56-473b5a86616e | 102 - DEV-Private Cloud |
|  rbreker-a8-1  | a6caeea2-072b-4db6-ad12-d292a7613423 | 102 - DEV-Private Cloud |
| n3plztncldsg01 | c61be2c7-4801-490c-a082-0d126a48d228 | 102 - DEV-Private Cloud |
|   vader-ara    | cfc1f7b9-c5b8-4d15-b910-78d11320f5b8 | 102 - DEV-Private Cloud |
+----------------+--------------------------------------+-------------------------+
```

## Validating all projects with "migrate_to" tag that have non existing project IDs on destination cloud

```bash
❯ collector -e ams_private project_validate
+---------------------+----------------------------------+-----------------------------+----------------------------------+
|         Name        |                ID                |         Owning Group        |     Set destination project      |
+---------------------+----------------------------------+-----------------------------+----------------------------------+
|   migration-mysql   | 29c00c937a924c71af7ae8d86cd0e792 |         org-sre-emea        | 63c6b3ce553440f8a13890a1413a6254 |
| velia-jenkins-nodes | 71fde4229523479e914a66669380f44d | org-velianetinternetdienste | c581e9ca9e994f28a3247d5a0b1f1058 |
+---------------------+----------------------------------+-----------------------------+----------------------------------+
```

## Collecting a list of all empty projects

```bash
❯ collector -e ams_private empty_projects
+----------------------------------------+----------------------------------+--------------------------------------+
|                  Name                  |                ID                |             Owning Group             |
+----------------------------------------+----------------------------------+--------------------------------------+
|              mrsite-prod               | 0003063fb14140d9b03426253ec3b524 |           org-paragon-sre            |
|            email_cloud_prod            | 0114f21f33d3424c948204f11fec44f3 |          OPS-Email Services          |
|         DNS_MYSQL_ORCHESTRATOR         | 01388e039aec4e15903e2fb91ac893f0 |           OPS-Managed DNS            |
|       nft-hfs-publish-test-ii-11       | 032c09f7e1014133802b5165bff8062b |           DEV-NocturnalFox           |
|             SSH-JumpBoxes              | 057f2b7155dc4452a267606f8f488d21 |            Dev-Networking            |
|              nft-m21xd2yv              | 0a809d1dffc94c6e9664a14d6af9534b |           DEV-NocturnalFox           |
|       nft-hfs-publish-test-ii-18       | 0b516c334d7e464ebc59691cd21b6b7f |           DEV-NocturnalFox           |
|                testing                 | 0b7040814b37477385200803491872bd |         ENG-Migration-Engine         |
|               ReachHeg1                | 101b4b6ef0414aeda3bc3c69458a6683 |         ENG-Network Defense          |
|    org-2ndlevelappwest-team_testing    | 1236b11084744e808e1e090f3db773c5 |       org-2ndlevelappwest-team       |
|           cloud_security-n3            | 12b3748e89824a73a98ab1bed1f026eb |             ENG-CloudSec             |
```

## Collecting list of unlinked VMs per availability zone

```bash
❯ collector -e ams_private unlinked -z ams-private-prd-zone-1
+-----------------+--------------------------------------+----------------------------------+
|       Name      |                  ID                  |             Project              |
+-----------------+--------------------------------------+----------------------------------+
|    n3plppp-a    | 9e4d8390-a946-4f23-917e-2c991233c1bf | 5c9481c450b7458591064924ce877b55 |
|    n3slppp-b    | 023f1f5d-4a7a-48c6-b86a-9dd40de2e7b4 | fa0ae9203d6f4d9288dbae9b31874ea4 |
|    n3dlppp-b    | b53cf032-2fb8-4270-a1c9-fbfd69d4fe03 | 4852b5fc8ca148e484768b875889db10 |
|    n3dlotrs-b   | 5865f4f4-fb6c-4b13-b092-50ed6b2e669b | 4852b5fc8ca148e484768b875889db10 |
|    n3sls4y-b    | 69286d74-f8e9-406c-a998-8fd8e8f9b262 | fa0ae9203d6f4d9288dbae9b31874ea4 |
|    n3dls4y-b    | ea4919e4-96d3-4fe8-a790-fb15319d305c | 4852b5fc8ca148e484768b875889db10 |
|    n3dltest-b   | 84b34273-826e-41c3-8e75-e80e4a1add90 | 4852b5fc8ca148e484768b875889db10 |
|   phousley-mig  | 680cf314-92bc-46ad-9fb5-503e1c43b84c | fd20e94182164c9fa5e2fd2163629a96 |
|     jsink-n3    | d5ef0d9f-7efa-4933-8a60-07d8672e4839 | 66d91e9eb0264b1ba1e8ee3839604be2 |
|  n3plcompiler04 | eee1977d-8a49-4d3f-8a11-2b2803521187 | 1aea1625bf0245ea8db4ba30c01873b6 |
```


## Generate list of active VMs with migrate_to project metadata for provided subnet

```bash
❯ collector -e ams_private svcsubnet --subnet "17597ea9-b562-486f-882f-938440538afb"
+--------------------------------------+-----------------+----------------------------------+----------------------------------+-------------+--------------+
|                vm.id                 |     vm.name     |          vm.project_id           |           dst_project            |     fip     | initial_ping |
+--------------------------------------+-----------------+----------------------------------+----------------------------------+-------------+--------------+
| 6611be28-48d6-4f8f-86fe-25d87a648d12 | testvm-b33f1b07 | 389f6c3921fa41b4a5bab611f8817bcc |           openstack-n3           | 10.30.17.14 |   Success    |
| 6e356920-d6b8-4e50-913e-d20fbec53326 |  N3-Stunnel-Alv | ad9b4aef39f74eaf93dbe8379b7cfc85 | 997bb38cd1df4035a138ab453d34cf85 |             |   Success    |
| aef6a776-ea30-4dc8-9ea7-a80dbeea59e0 |   velia-drone   | 71fde4229523479e914a66669380f44d | c581e9ca9e994f28a3247d5a0b1f1058 |  10.30.17.5 |   Success    |
| 31a81612-1fc2-49cc-9103-994fb4d61a60 | velia-sonarqube | 71fde4229523479e914a66669380f44d | c581e9ca9e994f28a3247d5a0b1f1058 |  10.30.17.6 |   Success    |
+--------------------------------------+-----------------+----------------------------------+----------------------------------+-------------+--------------+
```

# To generate the output in csv:
```bash
❯ collector -e ams_private csvsubnet --subnet "a4432946-fe51-44ab-a076-a9e254c85bf0" --csv


```
