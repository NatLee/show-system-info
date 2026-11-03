"""Shared fixtures."""
import platform
import socket
import uuid

import cpuinfo
import psutil
import pytest

from .fakes import FakeMachine


@pytest.fixture
def fake_machine(monkeypatch):
    """Replace every system call showsys makes with fixed values."""
    machine = FakeMachine()
    monkeypatch.setattr(platform, 'uname', lambda: machine.uname)
    monkeypatch.setattr(cpuinfo, 'get_cpu_info', lambda: machine.cpu_info)
    monkeypatch.setattr(socket, 'gethostname', lambda: 'demo-host')
    monkeypatch.setattr(socket, 'gethostbyname', lambda name: machine.ip_address)
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
    return machine
