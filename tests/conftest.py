"""Shared fixtures."""
import platform
import socket
import time
import uuid

import cpuinfo
import psutil
import pytest

from showsys import collectors, live

from .fakes import FakeMachine, FakeSocket


def _no_dns(name):
    raise AssertionError(f'showsys looked up {name!r} in DNS; the IP address must come from the interfaces')


@pytest.fixture
def fake_machine(monkeypatch):
    """Replace every system call showsys makes with fixed values."""
    machine = FakeMachine()
    monkeypatch.setattr(platform, 'uname', lambda: machine.uname)
    monkeypatch.setattr(cpuinfo, 'get_cpu_info', lambda: machine.cpu_info)
    # Only the fake py-cpuinfo names the CPU; the OS sources would read the real machine.
    monkeypatch.setattr(collectors, '_CPU_NAME_SOURCES', ())
    monkeypatch.setattr(socket, 'socket', lambda *args, **kwargs: FakeSocket(machine, *args, **kwargs))
    monkeypatch.setattr(socket, 'gethostbyname', _no_dns)
    monkeypatch.setattr(uuid, 'getnode', lambda: machine.mac_node)
    monkeypatch.setattr(psutil, 'boot_time', lambda: machine.boot_time)
    monkeypatch.setattr(psutil, 'cpu_count', machine.cpu_count)
    monkeypatch.setattr(psutil, 'cpu_freq', lambda *args, **kwargs: machine.cpu_freq, raising=False)
    monkeypatch.setattr(psutil, 'cpu_percent', machine.cpu_percent)
    monkeypatch.setattr(psutil, 'virtual_memory', lambda: machine.memory)
    monkeypatch.setattr(psutil, 'swap_memory', lambda: machine.swap)
    monkeypatch.setattr(psutil, 'disk_partitions', lambda *args, **kwargs: list(machine.partitions))
    monkeypatch.setattr(psutil, 'disk_usage', machine.disk_usage_of)
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda *args, **kwargs: machine.disk_io)
    monkeypatch.setattr(psutil, 'net_if_addrs', lambda: machine.interfaces)
    monkeypatch.setattr(psutil, 'net_if_stats', lambda: machine.interface_stats)
    monkeypatch.setattr(psutil, 'net_io_counters', lambda *args, **kwargs: machine.net_io)
    # raising=False: psutil has no temperatures or fans on Windows and macOS.
    monkeypatch.setattr(psutil, 'sensors_temperatures', lambda *args, **kwargs: machine.temperatures,
                        raising=False)
    monkeypatch.setattr(psutil, 'sensors_fans', lambda: machine.fans, raising=False)
    monkeypatch.setattr(psutil, 'sensors_battery', lambda: machine.battery, raising=False)
    monkeypatch.setattr(psutil, 'process_iter', lambda *args, **kwargs: iter(machine.processes))
    # Measurements wait for real time to pass; the fake machine only records how long.
    monkeypatch.setattr(time, 'sleep', machine.sleep)
    monkeypatch.setattr(live, '_clock', lambda: machine.clock)
    return machine
