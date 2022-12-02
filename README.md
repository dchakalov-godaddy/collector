# Openstack Collector

Tool that gathers data regarding openstack hypervisors and instances

## Help

Help menu
### `collector --help`
```bash
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

```

# OpenStack Client Configuration file

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


# Basic command example

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