# Copyright 2019 PerfKitBenchmarker Authors. All rights reserved.
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
"""Runs stress-ng.

From the stress-ng ubuntu documentation:
stress-ng will stress test a computer system in various selectable ways.
It was designed to exercise various physical subsystems of a computer as
well as the various operating system kernel interfaces. stress-ng also has
a wide range of CPU specific stress tests that exercise floating point,
integer, bit manipulation and control flow.

stress-ng manpage:
http://manpages.ubuntu.com/manpages/xenial/man1/stress-ng.1.html
"""

import logging

from absl import flags
import numpy
from perfkitbenchmarker import configs
from perfkitbenchmarker import sample

FLAGS = flags.FLAGS

BENCHMARK_NAME = 'stress_ng'
BENCHMARK_CONFIG = """
stress_ng:
  description: Runs stress-ng
  vm_groups:
    default:
      vm_spec: *default_dual_core
      disk_spec: *default_50_gb
"""

VALID_CPU_METHODS = frozenset({
    'all',
    'ackermann',
    'bitops',
    'callfunc',
    'cdouble',
    'cfloat',
    'clongdouble',
    'correlate',
    'crc16',
    'decimal32',
    'decimal64',
    'decimal128',
    'dither',
    'djb2a',
    'double',
    'euler',
    'explog',
    'fft',
    'fibonacci',
    'float',
    'fnv1a',
    'gamma',
    'gcd',
    'gray',
    'hamming',
    'hanoi',
    'hyperbolic',
    'idct',
    'int128',
    'int64',
    'int32',
    'int16',
    'int8',
    'int128float',
    'int128double',
    'int128longdouble',
    'int128decimal32',
    'int128decimal64',
    'int128decimal128',
    'int64float',
    'int64double',
    'int64longdouble',
    'int32float',
    'int32double',
    'int32longdouble',
    'jenkin',
    'jmp',
    'ln2',
    'longdouble',
    'loop',
    'matrixprod',
    'nsqrt',
    'omega',
    'parity',
    'phi',
    'pi',
    'pjw',
    'prime',
    'psi',
    'queens',
    'rand',
    'rand48',
    'rgb',
    'sdbm',
    'sieve',
    'sqrt',
    'trig',
    'union',
    'zeta',
})

VALID_STRESSORS = frozenset({
    'affinity',
    'af-alg',
    'aio',
    'aio-linux',
    'apparmor',
    'bigheap',
    'brk',
    'bsearch',
    'cache',
    'chdir',
    'chmod',
    'clock',
    'clone',
    'context',
    'cpu',
    'cpu-online',
    'crypt',
    'daemon',
    'dentry',
    'dir',
    'dup',
    'epoll',
    'eventfd',
    'exec',
    'fallocate',
    'fault',
    'fcntl',
    'fiemap',
    'fifo',
    'filename',
    'flock',
    'fork',
    'fp-error',
    'fstat',
    'futex',
    'get',
    'getrandom',
    'getdent',
    'handle',
    'hdd',
    'heapsort',
    'hsearch',
    'icache',
    'iosync',
    'inotify',
    'itimer',
    'kcmp',
    'key',
    'kill',
    'klog',
    'lease',
    'link',
    'lockbus',
    'lockf',
    'longjmp',
    'lsearch',
    'malloc',
    'matrix',
    'membarrier',
    'memcpy',
    'memfd',
    'memrate',
    'mergesort',
    'mincore',
    'mknod',
    'mlock',
    'mmap',
    'mmapfork',
    'mmapmany',
    'mremap',
    'msg',
    'mq',
    'nice',
    'null',
    'numa',
    'oom-pipe',
    'open',
    'personality',
    'pipe',
    'poll',
    'procfs',
    'pthread',
    'ptrace',
    'qsort',
    'quota',
    'rdrand',
    'readahead',
    'remap-file-pages',
    'rename',
    'rlimit',
    'seccomp',
    'seek',
    'sem-posix',
    'sem-sysv',
    'shm-posix',
    'shm-sysv',
    'sendfile',
    'sigfd',
    'sigfpe',
    'sigpending',
    'sigq',
    'sigsegv',
    'sigsuspend',
    'sleep',
    'socket',
    'socket-fd',
    'socket-pair',
    'spawn',
    'splice',
    'stack',
    'str',
    'stream',
    'switch',
    'symlink',
    'sync-file',
    'sysinfo',
    'sysfs',
    'tee',
    'timer',
    'timerfd',
    'tsc',
    'tsearch',
    'udp',
    'udp-flood',
    'unshare',
    'urandom',
    'userfaultfd',
    'utime',
    'vecmath',
    'vfork',
    'vm',
    'vm-rw',
    'vm-splice',
    'wait',
    'wcs',
    'xattr',
    'yield',
    'zero',
    'zlib',
    'zombie',
})
CPU_SUITE = frozenset({
    'af-alg',
    'bsearch',
    'context',
    'cpu',
    'cpu-online',
    'crypt',
    'fp-error',
    'getrandom',
    'heapsort',
    'hsearch',
    'longjmp',
    'lsearch',
    'matrix',
    'mergesort',
    'numa',
    'qsort',
    'rdrand',
    'str',
    'stream',
    'tsc',
    'tsearch',
    'vecmath',
    'wcs',
    'zlib',
})
CPU_CACHE_SUITE = frozenset({
    'bsearch',
    'cache',
    'heapsort',
    'hsearch',
    'icache',
    'lockbus',
    'lsearch',
    'malloc',
    'matrix',
    'membarrier',
    'memcpy',
    'mergesort',
    'qsort',
    'str',
    'stream',
    'tsearch',
    'vecmath',
    'wcs',
    'zlib',
})
MEMORY_SUITE = frozenset({
    'bsearch',
    'context',
    'heapsort',
    'hsearch',
    'lockbus',
    'lsearch',
    'malloc',
    'matrix',
    'membarrier',
    'memcpy',
    'memfd',
    'memrate',
    'mergesort',
    'mincore',
    'null',
    'numa',
    'oom-pipe',
    'pipe',
    'qsort',
    'stack',
    'str',
    'stream',
    'tsearch',
    'vm',
    'vm-rw',
    'wcs',
    'zero',
    'zlib',
})
# Run the stressors that are each part of all of the compute related stress-ng
# classes: cpu, cpu-cache, and memory.
DEFAULT_STRESSORS = sorted(
    CPU_SUITE.intersection(CPU_CACHE_SUITE).intersection(MEMORY_SUITE)
)

flags.DEFINE_integer(
    'stress_ng_duration', 10, 'Number of seconds to run the test.'
)
flags.DEFINE_boolean(
    'stress_ng_calc_geomean', True, 'Whether to calculate geomean or not.'
)
flags.DEFINE_list(
    'stress_ng_custom_stressors',
    DEFAULT_STRESSORS,
    'List of stressors to run against. Default combines cpu,'
    'cpu-cache, and memory suites',
)
flags.DEFINE_list(
    'stress_ng_cpu_methods',
    [],
    'List of cpu methods to run with. By default none are ran.',
)
flags.DEFINE_integer(
    'stress_ng_cpu_load',
    100,
    'Percentage of cpu to load. By default 100% of cpu is loaded.',
)
flags.DEFINE_integer(
    'stress_ng_cpu_load_slice',
    0,
    'Specify --cpu-load-slice to configure time slice during busy load.'
    'A positive value means # of ms to run before idling the CPU.',
)

flags.DEFINE_integer(
    'stress_ng_memrate_rd',
    0,
    'memrate worker read rate in MiB/s. Only applies to "memrate" stressor.'
)
flags.DEFINE_integer(
    'stress_ng_memrate_wr',
    0,
    'memrate worker write rate in MiB/s. Only applies to "memrate" stressor.'
)

ALL_WORKLOADS = ['small', 'medium', 'large']
flags.DEFINE_list(
    'stress_ng_thread_workloads',
    ['large'],
    'List of threads sizes to run against. Options are'
    'small (1 thread total), medium (1 thread per 2 cpus), and '
    'large (1 thread per cpu).',
)
flags.register_validator(
    'stress_ng_thread_workloads',
    lambda workloads: workloads and set(workloads).issubset(ALL_WORKLOADS),
)
flags.register_validator(
    'stress_ng_cpu_load',
    lambda value: 0 < value <= 100,
    message='stress_ng_cpu_load must be between 1 and 100.',
)
flags.register_validator(
    'stress_ng_cpu_load_slice',
    lambda value: -50 <= value <= 50,
    message='stress_ng_cpu_load_slice must be between -50 and 50.',
)


def _GeoMeanOverflow(iterable):
  """Returns the geometric mean.

  See https://en.wikipedia.org/wiki/Geometric_mean#Relationship_with_logarithms

  Args:
    iterable: a list of positive floats to take the geometric mean of.

  Returns: The geometric mean of the list.
  """
  if not iterable:
    return 0.0
  a = numpy.log(iterable)
  return numpy.exp(a.sum() / len(a))


def StressngCustomStressorsValidator(stressors):
  """Returns whether or not the list of custom stressors is valid."""
  return VALID_STRESSORS.issuperset(set(stressors))


def StressngCpuMethodsValidator(cpu_methods):
  """Returns whether or not the list of cpu methods is valid."""
  return 'all_cpu_methods' in cpu_methods or VALID_CPU_METHODS.issuperset(
      set(cpu_methods)
  )


flags.register_validator(
    'stress_ng_custom_stressors', StressngCustomStressorsValidator
)
flags.register_validator('stress_ng_cpu_methods', StressngCpuMethodsValidator)


def GetConfig(user_config):
  return configs.LoadConfig(BENCHMARK_CONFIG, user_config, BENCHMARK_NAME)


def Prepare(benchmark_spec):
  """Installs stress-ng on the target vm.

  Args:
    benchmark_spec: The benchmark specification. Contains all data that is
      required to run the benchmark.
  """
  vm = benchmark_spec.vms[0]
  vm.InstallPackages('stress-ng')


def _ParseStressngResult(
    metadata, output, cpu_method=None
) -> sample.Sample | None:
  """Returns stress-ng data as a sample.

  Sample output eg:
    stress-ng: info:  [2566] dispatching hogs: 2 context
    stress-ng: info:  [2566] successful run completed in 5.00s
    stress-ng: info:  [2566] stressor      bogo ops real time  usr time  sys
  time   bogo ops/s   bogo ops/s
    stress-ng: info:  [2566]                          (secs)    (secs)    (secs)
  (real time) (usr+sys time)
    stress-ng: info:  [2566] context          22429      5.00      5.49
  4.48      4485.82      2249.65
  Args:
    metadata: metadata of the sample.
    output: the output of the stress-ng benchmark.
    cpu_method: an optional flag for the cpu method for the cpu stressor.
  """
  output_list = output.splitlines()
  output_matrix = [i.split() for i in output_list]
  if len(output_matrix) < 5:
    logging.error('output is missing')
    return None
  while len(output_matrix) > 3 and 'stressor' not in output_matrix[-3]:
    output_matrix.pop()
  assert output_matrix[-3][-4] == 'bogo' and output_matrix[-3][-3] == 'ops/s'
  assert output_matrix[-2][-4] == '(real' and output_matrix[-2][-3] == 'time)'
  line = output_matrix[-1]
  name = line[3]
  value = float(line[-2])  # parse bogo ops/s (real time)
  if name == 'cpu' and cpu_method:
    return sample.Sample(
        metric=cpu_method,
        value=value,
        unit='bogus_ops_sec',  # bogus operations per second
        metadata=metadata,
    )

  return sample.Sample(
      metric=name,
      value=value,
      unit='bogus_ops_sec',  # bogus operations per second
      metadata=metadata,
  )


def _RunWorkload(vm, num_threads):
  """Runs stress-ng on the target vm.

  Args:
    vm: The target vm to run on.
    num_threads: Number of instances of stressors to launch.

  Returns:
    A list of sample.Sample objects.
  """

  stressors = FLAGS.stress_ng_custom_stressors
  logging.info('Running stressors: %s', stressors)

  metadata = {
      'duration_sec': FLAGS.stress_ng_duration,
      'threads': num_threads,
      'stressor': [],
  }

  samples = []
  values_to_geomean_list = []

  for stressor_name in stressors:
    cmd_parts = [
        'stress-ng',
        f'--{stressor_name}',
        str(num_threads),
        '--metrics-brief',
        '-t',
        str(FLAGS.stress_ng_duration)
    ]
    metadata['stressor'].append(stressor_name)

    if stressor_name == 'memrate':
      memrate_rd = FLAGS.stress_ng_memrate_rd
      memrate_wr = FLAGS.stress_ng_memrate_wr
      if memrate_rd > 0:
        cmd_parts.extend([
            '--memrate-rd',
            str(memrate_rd),
        ])
        metadata['memrate_rd_mib_per_s'] = memrate_rd
      if memrate_wr > 0:
        cmd_parts.extend([
            '--memrate-wr',
            str(memrate_wr),
        ])
        metadata['memrate_wr_mib_per_s'] = memrate_wr

    cmd = ' '.join(cmd_parts)
    stdout, _ = vm.RemoteCommand(cmd)
    stressng_sample = _ParseStressngResult(metadata, stdout)
    if stressng_sample:
      samples.append(stressng_sample)
      values_to_geomean_list.append(stressng_sample.value)

  cpu_methods = (
      VALID_CPU_METHODS
      if 'all_cpu_methods' in FLAGS.stress_ng_cpu_methods
      else FLAGS.stress_ng_cpu_methods
  )
  if cpu_methods:
    metadata['cpu_methods'] = cpu_methods
  for cpu_method in cpu_methods:
    cmd_parts = [
        'stress-ng',
        '--cpu',
        str(num_threads),
        '--metrics-brief',
        '-t',
        str(FLAGS.stress_ng_duration),
        '--cpu-method',
        cpu_method,
    ]
    cpu_load = FLAGS.stress_ng_cpu_load
    if cpu_load < 100:
      cmd_parts.extend(['--cpu-load', str(cpu_load)])
      metadata['cpu_load'] = cpu_load
    cpu_load_slice = FLAGS.stress_ng_cpu_load_slice
    if cpu_load_slice != 0:
      cmd_parts.extend(
          ['--cpu-load-slice', str(cpu_load_slice)]
      )
      metadata['cpu_load_slice'] = cpu_load_slice
    cmd = ' '.join(cmd_parts)
    stdout, _ = vm.RemoteCommand(cmd)
    stressng_sample = _ParseStressngResult(metadata, stdout, cpu_method)
    if stressng_sample:
      samples.append(stressng_sample)
      values_to_geomean_list.append(stressng_sample.value)

  if FLAGS.stress_ng_calc_geomean:
    geomean_metadata = metadata.copy()
    # True only if each stressor provided a value
    geomean_metadata['valid_run'] = len(values_to_geomean_list) == len(
        stressors
    ) + len(cpu_methods)
    geomean_sample = sample.Sample(
        metric='STRESS_NG_GEOMEAN',
        value=_GeoMeanOverflow(values_to_geomean_list),
        unit='bogus_ops_sec',
        metadata=geomean_metadata,
    )
    samples.append(geomean_sample)

  return samples


def Run(benchmark_spec):
  """Runs stress-ng on the target vm.

  Args:
    benchmark_spec: The benchmark specification. Contains all data that is
      required to run the benchmark.

  Returns:
    A list of sample.Sample objects.
  """

  vm = benchmark_spec.vms[0]

  samples = []
  for workload in FLAGS.stress_ng_thread_workloads:
    if workload == 'small':
      samples.extend(_RunWorkload(vm, 1))
    elif workload == 'medium':
      samples.extend(_RunWorkload(vm, vm.NumCpusForBenchmark() / 2))
    elif workload == 'large':
      samples.extend(_RunWorkload(vm, vm.NumCpusForBenchmark()))

  return samples


def Cleanup(benchmark_spec):
  """Cleans up stress-ng from the target vm.

  Args:
    benchmark_spec: The benchmark specification. Contains all data that is
      required to run the benchmark.
  """
  vm = benchmark_spec.vms[0]
  vm.Uninstall('stress-ng')
