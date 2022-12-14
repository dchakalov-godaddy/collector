#!/usr/bin/env python

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import shutil

import ansible.constants as C
from ansible.executor.task_queue_manager import TaskQueueManager
from ansible.module_utils.common.collections import ImmutableDict
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.playbook.play import Play
from ansible.plugins.callback import CallbackBase
from ansible.vars.manager import VariableManager
from ansible import context

# Create a callback plugin so we can capture the output
class ResultsCollectorJSONCallback(CallbackBase):
    """A sample callback plugin used for performing an action as results come in.

    If you want to collect all results into a single object for processing at
    the end of the execution, look into utilizing the ``json`` callback plugin
    or writing your own custom callback plugin.
    """

    def __init__(self, *args, **kwargs):
        super(ResultsCollectorJSONCallback, self).__init__(*args, **kwargs)
        self.host_ok = {}
        self.host_unreachable = {}
        self.host_failed = {}

    def v2_runner_on_unreachable(self, result):
        host = result._host
        self.host_unreachable[host.get_name()] = result

    def v2_runner_on_ok(self, result, *args, **kwargs):
        """Print a json representation of the result.

        Also, store the result in an instance attribute for retrieval later
        """
        host = result._host
        self.host_ok[host.get_name()] = result
        # print(json.dumps({host.name: result._result}, indent=4))
        # print((result._result['stdout']))
    def v2_runner_on_failed(self, result, *args, **kwargs):
        host = result._host
        self.host_failed[host.get_name()] = result


def vm_disk_usage(hvs):
    if isinstance(hvs, list):
        host_list = hvs
    else:
        host_list = [hvs]
    # since the API is constructed for CLI it expects certain options to always be set in the context object
    context.CLIARGS = ImmutableDict(connection='smart', module_path=['/to/mymodules', '/usr/share/ansible'], forks=10, become='yes',
                                    become_method='sudo', become_flags='-i', become_user=None, check=False, diff=False, verbosity=0)
    # required for
    # https://github.com/ansible/ansible/blob/devel/lib/ansible/inventory/manager.py#L204
    sources = ','.join(host_list)
    if len(host_list) == 1:
        sources += ','

    # initialize needed objects
    loader = DataLoader()  # Takes care of finding and reading yaml, json and ini files
    passwords = dict(vault_pass='secret')

    # Instantiate our ResultsCollectorJSONCallback for handling results as they come in. Ansible expects this to be one of its main display outlets
    results_callback = ResultsCollectorJSONCallback()

    # create inventory, use path to host config file as source or hosts in a comma separated string
    inventory = InventoryManager(loader=loader, sources=sources)

    # variable manager takes care of merging all the different sources to give you a unified view of variables available in each context
    variable_manager = VariableManager(loader=loader, inventory=inventory)

    # instantiate task queue manager, which takes care of forking and setting up all objects to iterate over host list and tasks
    # IMPORTANT: This also adds library dirs paths to the module loader
    # IMPORTANT: and so it must be initialized before calling `Play.load()`.
    tqm = TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=passwords,
        stdout_callback=results_callback,  # Use our custom callback instead of the ``default`` callback plugin, which prints to stdout
    )

    # create data structure that represents our play, including tasks, this is basically what our YAML loader does internally.
    play_source = dict(
        name="Ansible Play",
        hosts=host_list,
        gather_facts='no',
        tasks=[
            dict(action=dict(module='shell', args="du -sh /var/lib/docker/volumes/nova_compute/_data/instances/* /var/lib/nova/instances/* 2> /dev/null | grep -vE 'base|locks|nodes|snapshots' | awk '{print $2, $1}' | awk -F 'instances/' '{print$2}'"), register='disk_out'),
            # dict(action=dict(module='shell', args="for i in $(/bin/virsh list --all --uuid); do echo $i ; du -sh /var/lib/nova/instances/$i | awk '{print $1}'; done"), register='disk_out'),
            # dict(action=dict(module='shell', args="du -sh /var/lib/docker/volumes/nova_compute/_data/instances/* | grep -vE 'base|locks|nodes|snapshots' | awk '{print $2, $1}'"), register='disk_out')
        ]
    )

    # Create play object, playbook objects use .load instead of init or new methods,
    # this will also automatically create the task objects from the info provided in play_source
    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    # Actually run it
    try:
        result = tqm.run(play)  # most interesting data for a play is actually sent to the callback's methods
    finally:
        # we always need to cleanup child procs and the structures we use to communicate with them
        tqm.cleanup()
        if loader:
            loader.cleanup_all_tmp_files()

    # Remove ansible tmpdir
    shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)
    disk_usage_list = []
    for host, result in results_callback.host_ok.items():
        disk_usage_list += (result._result['stdout_lines'])
        # Returning a dictionary of VM UUID and disk usage key value pair from list result
    if any('/var/lib/docker/volumes/nova_compute/_data/instances/' in str for str in disk_usage_list ):   
        disk_usage_list = [item.replace("/var/lib/docker/volumes/nova_compute/_data/instances/", "") for item in disk_usage_list]
    else:
        disk_usage_list = [item.replace("/var/lib/nova/instances/", "") for item in disk_usage_list]
    disk_usage_list = [str.split(' ') for str in disk_usage_list ]
    new_list = []
    for lst in disk_usage_list:
        new_list += lst
    disk_usage_list = new_list
    return (dict(zip(disk_usage_list[::2], disk_usage_list[1::2])))

def high_risk_hv(hvs):
    if isinstance(hvs, list):
        host_list = hvs
    else:
        host_list = [hvs]
    # since the API is constructed for CLI it expects certain options to always be set in the context object
    context.CLIARGS = ImmutableDict(connection='smart', module_path=['/to/mymodules', '/usr/share/ansible'], forks=10, become='yes',
                                    become_method='sudo', become_flags='-i', become_user=None, check=False, diff=False, verbosity=0)
    # required for
    # https://github.com/ansible/ansible/blob/devel/lib/ansible/inventory/manager.py#L204
    sources = ','.join(host_list)
    if len(host_list) == 1:
        sources += ','

    # initialize needed objects
    loader = DataLoader()  # Takes care of finding and reading yaml, json and ini files
    passwords = dict(vault_pass='secret')

    # Instantiate our ResultsCollectorJSONCallback for handling results as they come in. Ansible expects this to be one of its main display outlets
    results_callback = ResultsCollectorJSONCallback()

    # create inventory, use path to host config file as source or hosts in a comma separated string
    inventory = InventoryManager(loader=loader, sources=sources)

    # variable manager takes care of merging all the different sources to give you a unified view of variables available in each context
    variable_manager = VariableManager(loader=loader, inventory=inventory)

    # instantiate task queue manager, which takes care of forking and setting up all objects to iterate over host list and tasks
    # IMPORTANT: This also adds library dirs paths to the module loader
    # IMPORTANT: and so it must be initialized before calling `Play.load()`.
    tqm = TaskQueueManager(
        inventory=inventory,
        variable_manager=variable_manager,
        loader=loader,
        passwords=passwords,
        stdout_callback=results_callback,  # Use our custom callback instead of the ``default`` callback plugin, which prints to stdout
    )

    # create data structure that represents our play, including tasks, this is basically what our YAML loader does internally.
    play_source = dict(
        name="Ansible Play",
        hosts=host_list,
        gather_facts='no',
        tasks=[
            dict(action=dict(module='shell', args="df -h | awk '/mapper/ {print $5}' && free | awk '/Mem/ {print $3/$2 * 100}' && /opt/MegaRAID/MegaCli/MegaCli -AdpAlILog -aAll | grep Punc | wc -l"), register='disk_out'),
        ]
    )

    # Create play object, playbook objects use .load instead of init or new methods,
    # this will also automatically create the task objects from the info provided in play_source
    play = Play().load(play_source, variable_manager=variable_manager, loader=loader)

    # Actually run it
    try:
        result = tqm.run(play)  # most interesting data for a play is actually sent to the callback's methods
    finally:
        # we always need to cleanup child procs and the structures we use to communicate with them
        tqm.cleanup()
        if loader:
            loader.cleanup_all_tmp_files()

    # Remove ansible tmpdir
    shutil.rmtree(C.DEFAULT_LOCAL_TMP, True)
    result_list = {}
    for host, result in results_callback.host_ok.items():
        result_list[host] = {
        'disk_usage': result._result['stdout_lines'][0].replace('%', ''),
        'ram_usage': result._result['stdout_lines'][1], 
        'raid_punctures': result._result['stdout_lines'][2]}
    return result_list