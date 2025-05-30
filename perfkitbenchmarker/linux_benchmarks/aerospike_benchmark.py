# Copyright 2022 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Runs Aerospike (http://www.aerospike.com).

Aerospike is an opensource NoSQL solution. This benchmark runs a read/update
load test with varying numbers of client threads against an Aerospike server.

This test can be run in a variety of configurations including memory only,
remote/persistent ssd, and local ssd. The Aerospike configuration is controlled
by the "aerospike_storage_type" and "data_disk_type" flags.
"""

import functools
from typing import Any, Dict, List
from absl import flags
from perfkitbenchmarker import background_tasks
from perfkitbenchmarker import benchmark_spec as bm_spec
from perfkitbenchmarker import configs
from perfkitbenchmarker import disk
from perfkitbenchmarker import errors
from perfkitbenchmarker import sample
from perfkitbenchmarker import vm_util
from perfkitbenchmarker.linux_packages import aerospike_client
from perfkitbenchmarker.linux_packages import aerospike_server


FLAGS = flags.FLAGS

_DEFAULT_NAMESPACES = ['test']


AEROSPIKE_CLIENT_VMS = flags.DEFINE_integer(
    'aerospike_client_vms',
    1,
    'Number of client machines to use for running asbench.',
)
AEROSPIKE_CLIENT_THREADS_FOR_LOAD_PHASE = flags.DEFINE_integer(
    'aerospike_client_threads_for_load_phase',
    8,
    'The minimum number of client threads to use during the load phase.',
    lower_bound=1,
)
AEROSPIKE_MIN_CLIENT_THREADS = flags.DEFINE_integer(
    'aerospike_min_client_threads',
    8,
    'The minimum number of Aerospike client threads per vm.',
    lower_bound=1,
)
AEROSPIKE_MAX_CLIENT_THREADS = flags.DEFINE_integer(
    'aerospike_max_client_threads',
    128,
    'The maximum number of Aerospike client threads per vm.',
    lower_bound=1,
)
AEROSPIKE_CLIENT_THREADS_STEP_SIZE = flags.DEFINE_integer(
    'aerospike_client_threads_step_size',
    8,
    'The number to increase the Aerospike client threads '
    'per vm by for each iteration of the test.',
    lower_bound=1,
)
AEROSPIKE_READ_PERCENT = flags.DEFINE_integer(
    'aerospike_read_percent',
    90,
    'The percent of operations which are reads. This is on the path of'
    ' DEPRECATION. Do not use.',
    lower_bound=0,
    upper_bound=100,
)
AEROSPIKE_NUM_KEYS = flags.DEFINE_integer(
    'aerospike_num_keys',
    1000000,
    'The number of keys to load Aerospike with. The index '
    'must fit in memory regardless of where the actual '
    'data is being stored and each entry in the '
    'index requires 64 bytes.',
)
AEROSPIKE_BENCHMARK_DURATION = flags.DEFINE_integer(
    'aerospike_benchmark_duration',
    60,
    'Duration of each test iteration in secs.',
)
flags.DEFINE_boolean(
    'aerospike_publish_detailed_samples',
    False,
    'Whether or not to publish one sample per aggregation'
    'window with histogram. By default, only TimeSeries '
    'sample will be generated.',
)
flags.DEFINE_integer(
    'aerospike_instances',
    1,
    'Number of aerospike_server processes to run. '
    'e.g. if this is set to 2, we will launch 2 aerospike '
    'processes on the same VM. Flags such as '
    'aerospike_num_keys and client threads will be applied '
    'to each instance.',
)
AEROSPIKE_CLIENT_MACHINE_TYPE = flags.DEFINE_string(
    'aerospike_client_machine_type',
    None,
    'Machine type to use for the aerospike client if different '
    'from aerospike server machine type.',
)
AEROSPIKE_NAMESPACES = flags.DEFINE_list(
    'aerospike_namespaces',
    _DEFAULT_NAMESPACES,
    'The Aerospike namespaces to test against',
)
flags.DEFINE_boolean(
    'aerospike_enable_strong_consistency',
    False,
    'Whether or not to enable strong consistency for the Aerospike namespaces.',
)
AEROSPIKE_TEST_WORKLOAD_TYPES = flags.DEFINE_string(
    'aerospike_test_workload_types',
    'RU, 75',
    'The test workload types to generate. If there are multuple types, they'
    ' should be separated by semicolon.',
)
AEROSPIKE_TEST_WORKLOAD_EXTRA_ARGS = flags.DEFINE_list(
    'aerospike_test_workload_extra_args',
    None,
    'The extra args to use in asbench commands.',
)
AEROSPIKE_SKIP_DB_PREPOPULATION = flags.DEFINE_boolean(
    'aerospike_skip_db_prepopulation',
    False,
    'Whether or not to skip pre-populating the Aerospike DB.',
)
AEROSPIKE_TEST_WORKLOAD_OBJECT_SPEC = flags.DEFINE_string(
    'aerospike_test_workload_object_spec',
    'B1000',
    'The object spec to generate for the test workload.',
)
_PUBLISH_PERCENTILE_TIME_SERIES = flags.DEFINE_boolean(
    'aerospike_publish_percentile_time_series',
    True,
    (
        'Whether or not to publish one sample per aggregation'
        'window with percentiles to capture'
    ),
)

_PERCENTILES_TO_CAPTURE = flags.DEFINE_list(
    'aerospike_percentiles_to_capture',
    ['50', '90', '99', '99.9', '99.99'],
    (
        'List of percentiles to capture if'
        ' aerospike_publish_percentile_time_series is set.'
    ),
)
AEROSPIKE_SERVER_MACHINE_TYPE = flags.DEFINE_string(
    'aerospike_server_machine_type',
    None,
    (
        'Machine type to use for the aerospike server if different '
        'from aerospike client machine type.'
    ),
)

BENCHMARK_NAME = 'aerospike'
BENCHMARK_CONFIG = """
aerospike:
  description: Runs Aerospike.
  vm_groups:
    workers:
      vm_spec: *default_dual_core
      disk_spec: *default_500_gb
      vm_count: null
      disk_count: 0
    clients:
      vm_spec: *default_dual_core
"""


def GetConfig(user_config: Dict[str, Any]) -> Dict[str, Any]:
  """Gets the Aerospike config."""
  config = configs.LoadConfig(BENCHMARK_CONFIG, user_config, BENCHMARK_NAME)
  if FLAGS.aerospike_storage_type == aerospike_server.DISK:
    config['vm_groups']['workers']['disk_count'] = 1
    if FLAGS.data_disk_type == disk.LOCAL:
      # Didn't know max number of local disks, decide later.
      if FLAGS.cloud == 'GCP':
        config['vm_groups']['workers']['vm_spec']['GCP']['num_local_ssds'] = (
            FLAGS.gce_num_local_ssds or FLAGS.server_gce_num_local_ssds
        )
        FLAGS['gce_num_local_ssds'].present = False
        FLAGS.gce_num_local_ssds = 0
        if FLAGS['server_gce_ssd_interface'].present:
          config['vm_groups']['workers']['vm_spec']['GCP'][
              'ssd_interface'
          ] = FLAGS.server_gce_ssd_interface
          FLAGS['gce_ssd_interface'].present = False
          FLAGS.gce_ssd_interface = FLAGS.server_gce_ssd_interface
        config['vm_groups']['clients']['vm_spec']['GCP']['num_local_ssds'] = 0

  if AEROSPIKE_SERVER_MACHINE_TYPE.value:
    vm_spec = config['vm_groups']['workers']['vm_spec']
    for cloud in vm_spec:
      vm_spec[cloud]['machine_type'] = AEROSPIKE_SERVER_MACHINE_TYPE.value
  if AEROSPIKE_CLIENT_MACHINE_TYPE.value:
    vm_spec = config['vm_groups']['clients']['vm_spec']
    for cloud in vm_spec:
      vm_spec[cloud]['machine_type'] = AEROSPIKE_CLIENT_MACHINE_TYPE.value

  if FLAGS['aerospike_vms'].present:
    config['vm_groups']['workers']['vm_count'] = FLAGS.aerospike_vms

  if FLAGS['aerospike_client_vms'].present:
    config['vm_groups']['clients']['vm_count'] = AEROSPIKE_CLIENT_VMS.value

  if FLAGS.aerospike_instances > 1 and FLAGS.aerospike_vms > 1:
    raise errors.Setup.InvalidFlagConfigurationError(
        'Only one of aerospike_instances and aerospike_vms can be set.'
    )

  return config


def Prepare(benchmark_spec: bm_spec.BenchmarkSpec) -> None:
  """Install Aerospike server and Aerospike tools on the other.

  Args:
    benchmark_spec: The benchmark specification. Contains all data that is
      required to run the benchmark.
  """
  clients = benchmark_spec.vm_groups['clients']
  num_client_vms = len(clients)
  servers = benchmark_spec.vm_groups['workers']
  # VMs where the server is not up yet.
  servers_not_up = [
      server for server in servers if not aerospike_server.IsServerUp(server)
  ]

  seed_ips = [str(vm.internal_ip) for vm in servers]
  aerospike_install_fns = []
  if servers_not_up:
    # Prepare the VMs where the server isn't up yet.
    aerospike_install_fns = [
        functools.partial(
            aerospike_server.ConfigureAndStart,
            vm,
            seed_node_ips=seed_ips,
        )
        for vm in servers
    ]
  if FLAGS.aerospike_enable_strong_consistency:
    for server in servers:
      aerospike_server.EnableStrongConsistency(
          server, AEROSPIKE_NAMESPACES.value
      )
  client_install_fns = [
      functools.partial(vm.Install, 'aerospike_client') for vm in clients
  ]

  background_tasks.RunThreaded(
      lambda f: f(), aerospike_install_fns + client_install_fns
  )

  loader_counts = [
      int(AEROSPIKE_NUM_KEYS.value) // len(clients)
      + (1 if i < (AEROSPIKE_NUM_KEYS.value % num_client_vms) else 0)
      for i in range(num_client_vms)
  ]

  if AEROSPIKE_SKIP_DB_PREPOPULATION.value:
    return

  extra_args = FLAGS.aerospike_test_workload_extra_args or ['']
  @vm_util.Retry(max_retries=3)  # Retry if the server is not fully up yet.
  def _Load(namespace, client_idx, process_idx):
    ips = ','.join(seed_ips)
    # Default to use the first extra arg.
    extra_arg_str = f'{extra_args[0]}' if extra_args[0] else ''
    load_command = (
        'asbench '
        f'--threads {AEROSPIKE_CLIENT_THREADS_FOR_LOAD_PHASE.value} '
        f'--namespace {namespace} --workload I '
        f'--object-spec {AEROSPIKE_TEST_WORKLOAD_OBJECT_SPEC.value} '
        f'--keys {loader_counts[client_idx]} '
        f'--start-key {sum(loader_counts[:client_idx])} '
        f' -h {ips} -p {3 + process_idx}000 '
        f'{extra_arg_str}'
    )
    clients[client_idx].RobustRemoteCommand(load_command)

  run_params = []
  for namespace in AEROSPIKE_NAMESPACES.value:
    for child_idx in range(len(clients)):
      for process_idx in range(FLAGS.aerospike_instances):
        run_params.append(((namespace, child_idx, process_idx), {}))

  background_tasks.RunThreaded(_Load, run_params)


def Run(benchmark_spec: bm_spec.BenchmarkSpec) -> List[sample.Sample]:
  """Runs a read/update load test on Aerospike.

  Args:
    benchmark_spec: The benchmark specification. Contains all data that is
      required to run the benchmark.

  Returns:
    A list of sample.Sample objects.
  """
  clients = benchmark_spec.vm_groups['clients']
  num_client_vms = len(clients)
  servers = benchmark_spec.vm_groups['workers']
  samples = []
  seed_ips = ','.join([str(vm.internal_ip) for vm in servers])
  metadata = {}

  for threads in range(
      AEROSPIKE_MIN_CLIENT_THREADS.value,
      AEROSPIKE_MAX_CLIENT_THREADS.value + 1,
      AEROSPIKE_CLIENT_THREADS_STEP_SIZE.value,
  ):
    stdout_samples = []

    def _Run(namespace, client_idx, process_idx, op, extra_arg):
      extra_arg_str = f'{extra_arg} ' if extra_arg else ''
      run_command = (
          f'asbench '
          f'--threads {threads} --namespace {namespace} '  # pylint: disable=cell-var-from-loop
          f'--workload "{op}" '
          f'{extra_arg_str} '
          f'--object-spec {AEROSPIKE_TEST_WORKLOAD_OBJECT_SPEC.value} '
          f'--keys {AEROSPIKE_NUM_KEYS.value} '
          f'--hosts {seed_ips} --port {3 + process_idx}000 '
          f'--duration {AEROSPIKE_BENCHMARK_DURATION.value} '
          '--latency --percentiles 50,90,99,99.9,99.99 '
          '--output-file '
          f'result.{client_idx}.{process_idx}.{threads} '
      )
      stdout, _ = clients[client_idx].RobustRemoteCommand(run_command)
      stdout_samples.extend(aerospike_client.ParseAsbenchStdout(stdout))  # pylint: disable=cell-var-from-loop

    workload_types = AEROSPIKE_TEST_WORKLOAD_TYPES.value.split(';')

    extra_args = (
        AEROSPIKE_TEST_WORKLOAD_EXTRA_ARGS.value
        if AEROSPIKE_TEST_WORKLOAD_EXTRA_ARGS.value
        else [None] * len(workload_types)
    )
    if len(extra_args) != len(workload_types):
      raise ValueError(
          'aerospike_test_workload_extra_args must be the same length as '
          'aerospike_test_workload_types'
      )
    for op, extra_arg in zip(workload_types, extra_args):
      for namespace in AEROSPIKE_NAMESPACES.value:
        run_params = []
        for client_idx in range(len(clients)):
          for process_idx in range(FLAGS.aerospike_instances):
            run_params.append(
                ((namespace, client_idx, process_idx, op, extra_arg), {})
            )
        background_tasks.RunThreaded(_Run, run_params)
        for server in servers:
          server.RemoteCommand('sudo asadm -e summary')

    if num_client_vms * FLAGS.aerospike_instances == 1:
      detailed_samples = stdout_samples
    else:
      detailed_samples = aerospike_client.AggregateAsbenchSamples(
          stdout_samples
      )

    temp_samples = aerospike_client.CreateTimeSeriesSample(detailed_samples)

    result_files = []
    for client_idx in range(len(clients)):
      for process_idx in range(FLAGS.aerospike_instances):
        filename = f'result.{client_idx}.{process_idx}.{threads}'
        clients[client_idx].PullFile(vm_util.GetTempDir(), filename)
        result_files.append(filename)
    if (
        FLAGS.aerospike_publish_detailed_samples
        or _PUBLISH_PERCENTILE_TIME_SERIES.value
    ):
      detailed_samples.extend(
          aerospike_client.ParseAsbenchHistogram(result_files)
      )
      temp_samples.extend(detailed_samples)
    metadata.update({
        'num_clients_vms': AEROSPIKE_CLIENT_VMS.value,
        'num_aerospike_vms': len(servers),
        'num_aerospike_instances': FLAGS.aerospike_instances,
        'storage_type': FLAGS.aerospike_storage_type,
        'memory_size': int(servers[0].total_memory_kb * 0.8),
        'service_threads': FLAGS.aerospike_service_threads,
        'replication_factor': FLAGS.aerospike_replication_factor,
        'client_threads': threads,
        'read_percent': AEROSPIKE_READ_PERCENT.value,
        'aerospike_edition': FLAGS.aerospike_edition.value,
        'aerospike_enable_strong_consistency': (
            FLAGS.aerospike_enable_strong_consistency
        ),
        'aerospike_test_workload_types': AEROSPIKE_TEST_WORKLOAD_TYPES.value,
        'aerospike_test_workload_extra_args': (
            AEROSPIKE_TEST_WORKLOAD_EXTRA_ARGS.value
        ),
        'aerospike_skip_db_prepopulation': (
            AEROSPIKE_SKIP_DB_PREPOPULATION.value
        ),
        'aerospike_test_workload_object_spec': (
            AEROSPIKE_TEST_WORKLOAD_OBJECT_SPEC.value
        ),
    })
    if FLAGS.aerospike_edition == aerospike_server.AerospikeEdition.ENTERPRISE:
      metadata.update({
          'aerospike_version': FLAGS.aerospike_enterprise_version,
      })
    for s in temp_samples:
      s.metadata.update(metadata)
    samples.extend(temp_samples)

  return samples


def Cleanup(benchmark_spec: bm_spec.BenchmarkSpec) -> None:
  """Cleanup Aerospike.

  Args:
    benchmark_spec: The benchmark specification. Contains all data that is
      required to run the benchmark.
  """
  servers = benchmark_spec.vm_groups['workers']
  clients = benchmark_spec.vm_groups['client']

  def StopClient(client):
    client.RemoteCommand('sudo rm -rf aerospike*')

  background_tasks.RunThreaded(StopClient, clients)

  def StopServer(server):
    server.RemoteCommand(
        'cd %s && nohup sudo make stop' % aerospike_server.AEROSPIKE_DIR
    )
    server.RemoteCommand('sudo rm -rf aerospike*')

  background_tasks.RunThreaded(StopServer, servers)
