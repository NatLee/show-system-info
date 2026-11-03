"""Information the OS does not report is shown as N/A instead of crashing."""
import socket
import sys
from collections import namedtuple

import cpuinfo
import psutil
import pytest

from showsys import ShowSys
from showsys.cli import main

# Same fields as the named tuple returned by psutil.cpu_freq().
CpuFreq = namedtuple('CpuFreq', 'current min max')


def _unresolvable(name):
    raise socket.gaierror(-2, 'Name or service not known')


def _run_cli(monkeypatch, capsys, *flags):
    monkeypatch.setattr(sys, 'argv', ['showsys'] + list(flags))
    main()
    out = capsys.readouterr().out
    assert 'An unexpected error occurred' not in out
    return out


def test_ip_address_is_na_when_the_host_name_cannot_be_resolved(monkeypatch, capsys):
    monkeypatch.setattr(socket, 'gethostbyname', _unresolvable)

    assert ShowSys().system_information()['IP-Address'] == 'N/A'
    assert 'IP-Address: N/A' in ShowSys().info(show=False)
    assert 'IP-Address: N/A' in _run_cli(monkeypatch, capsys)


def test_processor_brand_is_na_when_py_cpuinfo_cannot_detect_it(monkeypatch):
    monkeypatch.setattr(cpuinfo, 'get_cpu_info', lambda: {'arch': 'ARM_8'})

    assert ShowSys().system_information()['Processor Brand'] == 'N/A'


def test_cpu_frequencies_are_na_when_the_os_does_not_report_them(monkeypatch, capsys):
    monkeypatch.setattr(psutil, 'cpu_freq', lambda: None)

    info = ShowSys().cpu_info()
    assert info['Max Frequency'] == 'N/A'
    assert info['Min Frequency'] == 'N/A'
    assert info['Current Frequency'] == 'N/A'
    assert 'Current Frequency: N/A' in _run_cli(monkeypatch, capsys, '-c')
    assert 'Current Frequency: N/A' in _run_cli(monkeypatch, capsys, '-d')


def test_cpu_frequencies_keep_the_readme_format_when_reported(monkeypatch):
    monkeypatch.setattr(psutil, 'cpu_freq', lambda: CpuFreq(current=2100.0, min=0.0, max=2100.0))

    info = ShowSys().cpu_info()
    assert info['Max Frequency'] == '2100.00Mhz'
    assert info['Min Frequency'] == '0.00Mhz'
    assert info['Current Frequency'] == '2100.00Mhz'


def test_disk_totals_are_na_when_there_are_no_disk_statistics(monkeypatch):
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda *args, **kwargs: None)

    info = ShowSys().disk_info()
    assert info['Total read'] == 'N/A'
    assert info['Total write'] == 'N/A'


@pytest.mark.parametrize('field', ['Total read', 'Total write'])
def test_disk_totals_are_sizes_when_reported(field):
    if psutil.disk_io_counters() is None:
        pytest.skip('this machine reports no disk statistics')
    assert ShowSys().disk_info()[field].endswith('B')
