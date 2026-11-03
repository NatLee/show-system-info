"""A fake machine with fixed values, so showsys output can be compared exactly."""
import socket
from collections import namedtuple
from datetime import datetime

import psutil

# Same fields as the named tuples returned by platform and psutil.
Uname = namedtuple('Uname', 'system node release version machine processor')
CpuFreq = namedtuple('CpuFreq', 'current min max')
VirtualMemory = namedtuple('VirtualMemory', 'total available percent used free')
SwapMemory = namedtuple('SwapMemory', 'total used free percent sin sout')
DiskPartition = namedtuple('DiskPartition', 'device mountpoint fstype opts')
DiskUsage = namedtuple('DiskUsage', 'total used free percent')
DiskIO = namedtuple('DiskIO', 'read_count write_count read_bytes write_bytes')
Address = namedtuple('Address', 'family address netmask broadcast ptp')
NetIO = namedtuple('NetIO', 'bytes_sent bytes_recv packets_sent packets_recv errin errout dropin dropout')
NetStats = namedtuple('NetStats', 'isup duplex speed mtu')
Temperature = namedtuple('Temperature', 'label current high critical')
Fan = namedtuple('Fan', 'label current')
Battery = namedtuple('Battery', 'percent secsleft power_plugged')

GB = 1024 ** 3
MB = 1024 ** 2

# 2026-01-05 03:04:05 local time: pins the "no zero padding" boot time format.
BOOT_TIMESTAMP = datetime(2026, 1, 5, 3, 4, 5).timestamp()

PER_CORE = [1.0, 2.5, 0.0, 10.0, 3.0, 0.0, 0.0, 4.5]
TOTAL_CPU = 2.6


class FakeMachine:
    """Values the fake psutil returns. Tests can change them before calling showsys."""

    def __init__(self):
        self.uname = Uname('Linux', 'demo-host', '6.8.0', '#1 SMP PREEMPT_DYNAMIC', 'x86_64', 'x86_64')
        self.cpu_info = {'brand_raw': 'Example CPU 9000'}
        self.ip_address = '192.168.1.10'
        self.mac_node = 0xaabbccddeeff
        self.boot_time = BOOT_TIMESTAMP
        self.physical_cores = 4
        self.logical_cores = 8
        self.cpu_freq = CpuFreq(current=2100.0, min=0.0, max=3600.0)
        self.per_core = list(PER_CORE)
        self.total_cpu = TOTAL_CPU
        self.memory = VirtualMemory(total=16 * GB, available=9 * GB, percent=43.8, used=6 * GB, free=7 * GB)
        self.swap = SwapMemory(total=2 * GB, used=512 * MB, free=1536 * MB, percent=25.0, sin=0, sout=0)
        self.partitions = [DiskPartition('/dev/sda1', '/', 'ext4', 'rw')]
        self.disk_usage = {'/': DiskUsage(total=100 * GB, used=40 * GB, free=60 * GB, percent=40.0)}
        self.disk_io = DiskIO(read_count=10, write_count=20, read_bytes=1 * GB, write_bytes=2 * GB)
        self.interfaces = {
            'lo': [
                Address(socket.AF_INET, '127.0.0.1', '255.0.0.0', None, None),
                Address(psutil.AF_LINK, '00:00:00:00:00:00', None, None, None),
            ],
            'eth0': [
                Address(socket.AF_INET, '192.168.1.10', '255.255.255.0', '192.168.1.255', None),
                Address(socket.AF_INET6, 'fe80::1', 'ffff:ffff:ffff:ffff::', None, None),
                Address(psutil.AF_LINK, 'aa:bb:cc:dd:ee:ff', None, 'ff:ff:ff:ff:ff:ff', None),
            ],
        }
        self.interface_stats = {
            'lo': NetStats(isup=True, duplex=0, speed=0, mtu=65536),
            'eth0': NetStats(isup=True, duplex=2, speed=1000, mtu=1500),
        }
        self.net_io = NetIO(bytes_sent=int(1.5 * MB), bytes_recv=20 * MB,
                            packets_sent=0, packets_recv=0, errin=0, errout=0, dropin=0, dropout=0)
        self.temperatures = {
            'coretemp': [Temperature('Package id 0', 45.0, 80.0, 100.0), Temperature('Core 0', 43.5, 80.0, 100.0)],
            'acpitz': [Temperature('', 27.8, None, None)],
        }
        self.fans = {'thinkpad': [Fan('', 2400)]}
        self.battery = Battery(percent=87.0, secsleft=5025, power_plugged=False)

    def cpu_percent(self, interval=None, percpu=False):
        return list(self.per_core) if percpu else self.total_cpu

    def cpu_count(self, logical=True):
        return self.logical_cores if logical else self.physical_cores

    def disk_usage_of(self, path):
        return self.disk_usage[path]
