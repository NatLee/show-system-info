"""The structured Python API: get_*() records and collect()."""
import json
import os
import re

import psutil
import pytest

import showsys
from showsys.models import CpuInfo

from .fakes import BOOT_TIMESTAMP, GB, MB, PER_CORE, TOTAL_CPU


def test_package_exports_the_api():
    for name in showsys.__all__:
        assert hasattr(showsys, name), name
    assert 'ShowSys' in showsys.__all__
    assert 'collect' in showsys.__all__


def test_get_system_returns_plain_values(fake_machine):
    info = showsys.get_system()
    assert info.system == 'Linux'
    assert info.node == 'demo-host'
    assert info.processor == 'x86_64'
    assert info.processor_brand == 'Example CPU 9000'
    assert info.ip_address == '192.168.1.10'
    assert info.mac_address == 'aa:bb:cc:dd:ee:ff'
    assert re.match(r'^\d+\.\d+\.\d+', info.python_version)


def test_get_system_uses_none_for_missing_values(fake_machine, monkeypatch):
    fake_machine.uname = fake_machine.uname._replace(processor='')
    fake_machine.cpu_info = {}
    monkeypatch.setattr('socket.gethostbyname', lambda name: (_ for _ in ()).throw(OSError('no')))

    info = showsys.get_system()
    assert info.processor is None
    assert info.processor_brand is None
    assert info.ip_address is None


def test_get_boot_reports_timestamp_iso_time_and_uptime(fake_machine):
    info = showsys.get_boot()
    assert info.timestamp == BOOT_TIMESTAMP
    assert info.time.startswith('2026-01-05T03:04:05')
    assert info.uptime_seconds > 0


def test_get_cpu_reports_numbers(fake_machine):
    info = showsys.get_cpu(interval=0)
    assert info.physical_cores == 4
    assert info.logical_cores == 8
    assert info.freq_current_mhz == 2100.0
    assert info.freq_max_mhz == 3600.0
    # psutil's 0.0 means "unknown".
    assert info.freq_min_mhz is None
    assert info.usage_per_core == PER_CORE
    assert info.usage_percent == TOTAL_CPU


def test_get_cpu_frequencies_are_none_when_not_reported(fake_machine):
    fake_machine.cpu_freq = None
    info = showsys.get_cpu(interval=0)
    assert (info.freq_current_mhz, info.freq_min_mhz, info.freq_max_mhz) == (None, None, None)


def test_get_cpu_load_average_follows_the_os(fake_machine, monkeypatch):
    monkeypatch.setattr(os, 'getloadavg', lambda: (0.5, 0.25, 0.125), raising=False)
    assert showsys.get_cpu(interval=0).load_average == [0.5, 0.25, 0.12]
    monkeypatch.delattr(os, 'getloadavg', raising=False)
    assert showsys.get_cpu(interval=0).load_average is None


def test_get_memory_and_swap_are_bytes(fake_machine):
    memory = showsys.get_memory()
    assert (memory.total, memory.available, memory.used, memory.free, memory.percent) == (
        16 * GB, 9 * GB, 6 * GB, 7 * GB, 43.8)
    swap = showsys.get_swap()
    assert (swap.total, swap.used, swap.free, swap.percent) == (2 * GB, 512 * MB, 1536 * MB, 25.0)


def test_get_disks_lists_partitions_and_io(fake_machine):
    info = showsys.get_disks()
    assert [p.to_dict() for p in info.partitions] == [{
        'device': '/dev/sda1', 'mountpoint': '/', 'fstype': 'ext4',
        'total': 100 * GB, 'used': 40 * GB, 'free': 60 * GB, 'percent': 40.0,
    }]
    assert (info.read_bytes, info.write_bytes) == (1 * GB, 2 * GB)


def test_get_disks_io_is_none_without_statistics(fake_machine, monkeypatch):
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda *args, **kwargs: None)
    info = showsys.get_disks()
    assert (info.read_bytes, info.write_bytes) == (None, None)


def test_get_network_keeps_ipv6_and_link_state(fake_machine):
    info = showsys.get_network()
    eth0 = info.interfaces['eth0']
    assert [(a.family, a.address) for a in eth0.addresses] == [
        ('ipv4', '192.168.1.10'), ('ipv6', 'fe80::1'), ('mac', 'aa:bb:cc:dd:ee:ff')]
    assert (eth0.is_up, eth0.speed_mbps, eth0.mtu) == (True, 1000, 1500)
    # psutil's speed 0 means "unknown".
    assert info.interfaces['lo'].speed_mbps is None
    assert (info.bytes_sent, info.bytes_recv) == (int(1.5 * MB), 20 * MB)


def test_get_network_still_lists_addresses_when_link_state_fails(fake_machine, monkeypatch):
    def broken():
        raise OSError('No such device')
    monkeypatch.setattr(psutil, 'net_if_stats', broken)

    eth0 = showsys.get_network().interfaces['eth0']
    assert len(eth0.addresses) == 3
    assert eth0.is_up is None


def test_records_convert_to_dicts():
    info = CpuInfo(physical_cores=None, logical_cores=2, freq_current_mhz=None, freq_min_mhz=None,
                   freq_max_mhz=None, usage_percent=1.5, usage_per_core=[1.0, 2.0], load_average=None)
    assert info.to_dict()['usage_per_core'] == [1.0, 2.0]
    assert info.to_dict()['physical_cores'] is None


def test_collect_returns_json_ready_sections_in_a_fixed_order(fake_machine):
    data = showsys.collect('memory', 'system', interval=0)
    assert list(data) == ['timestamp', 'system', 'memory']
    assert data['memory']['total'] == 16 * GB
    assert data['system']['node'] == 'demo-host'
    assert json.loads(json.dumps(data)) == data


def test_collect_without_names_returns_every_section(fake_machine):
    data = showsys.collect(interval=0)
    assert list(data) == ['timestamp'] + list(showsys.SECTIONS)
    json.dumps(data)


def test_collect_rejects_unknown_sections():
    with pytest.raises(ValueError, match="unknown section 'gpus'"):
        showsys.collect('gpus')


def test_collect_works_on_this_machine():
    # No fakes: whatever this OS reports must still serialise.
    data = showsys.collect(interval=0.1)
    text = json.dumps(data)
    assert '"memory"' in text


def test_get_cpu_rounds_frequencies_to_two_decimals(fake_machine):
    fake_machine.cpu_freq = fake_machine.cpu_freq._replace(current=4291.815000000001, max=5752.0039)
    info = showsys.get_cpu(interval=0)
    assert (info.freq_current_mhz, info.freq_max_mhz) == (4291.82, 5752.0)
    assert showsys.ShowSys().cpu_info()['Current Frequency'] == '4291.82Mhz'
