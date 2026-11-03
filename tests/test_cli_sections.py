"""Sections added after ShowSys 1.0: --disk, --sensors, --top, --gpu and --all."""
import json

import psutil
import pytest

import showsys
from showsys.cli import main

from .fakes import GB, MB, Battery, DiskPartition, DiskUsage, FakeProcess


def _text(capsys, *flags):
    main(list(flags))
    captured = capsys.readouterr()
    assert 'An unexpected error occurred' not in captured.out + captured.err
    return captured.out


def _json(capsys, *flags):
    return json.loads(_text(capsys, '--json', *flags))


# --disk

def test_disk_prints_a_table_and_the_totals(fake_machine, capsys):
    fake_machine.partitions.append(DiskPartition('/dev/sdb1', '/data', 'xfs', 'rw'))
    fake_machine.disk_usage['/data'] = DiskUsage(total=2 * 1024 * GB, used=512 * GB, free=1536 * GB, percent=25.0)

    assert _text(capsys, '--disk') == (
        'Partitions:\n'
        'DEVICE     MOUNTPOINT  TYPE     TOTAL      USED     FREE   USE%\n'
        '/dev/sda1  /           ext4  100.00GB   40.00GB  60.00GB  40.0%\n'
        '/dev/sdb1  /data       xfs     2.00TB  512.00GB   1.50TB  25.0%\n'
        'Total read: 1.00GB\n'
        'Total write: 2.00GB\n'
        '\n')


def test_disk_shows_na_without_partitions_or_statistics(fake_machine, capsys, monkeypatch):
    fake_machine.partitions = []
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda *args, **kwargs: None)

    assert _text(capsys, '--disk') == 'Partitions: N/A\nTotal read: N/A\nTotal write: N/A\n\n'


def test_disk_json(fake_machine, capsys):
    data = _json(capsys, '--disk')
    assert list(data) == ['timestamp', 'disk']
    assert data['disk']['partitions'][0]['total'] == 100 * GB
    assert data['disk']['read_bytes'] == 1 * GB


def test_disk_works_on_this_machine(capsys):
    assert 'Total read:' in _text(capsys, '--disk')
    assert 'partitions' in _json(capsys, '--disk')['disk']


# --sensors

def test_sensors_prints_temperatures_fans_and_battery(fake_machine, capsys):
    assert _text(capsys, '--sensors') == (
        'Temperatures:\n'
        '\tcoretemp Package id 0: 45.0C (high 80.0C, critical 100.0C)\n'
        '\tcoretemp Core 0: 43.5C (high 80.0C, critical 100.0C)\n'
        '\tacpitz: 27.8C\n'
        'Fans:\n'
        '\tthinkpad: 2400 RPM\n'
        'Battery: 87.0%, on battery, 1:23:45 left\n'
        '\n')


def test_sensors_battery_while_charging(fake_machine, capsys):
    fake_machine.battery = Battery(percent=55.5, secsleft=psutil.POWER_TIME_UNLIMITED, power_plugged=True)
    assert 'Battery: 55.5%, plugged in\n' in _text(capsys, '--sensors')
    assert _json(capsys, '--sensors')['sensors']['battery'] == {
        'percent': 55.5, 'seconds_left': None, 'power_plugged': True}


def test_sensors_are_na_where_the_os_has_none(fake_machine, capsys, monkeypatch):
    # Windows and macOS: psutil has no sensors_temperatures() or sensors_fans().
    monkeypatch.delattr(psutil, 'sensors_temperatures', raising=False)
    monkeypatch.delattr(psutil, 'sensors_fans', raising=False)
    fake_machine.battery = None  # a desktop

    assert _text(capsys, '--sensors') == 'Temperatures: N/A\nFans: N/A\nBattery: N/A\n\n'
    assert _json(capsys, '--sensors')['sensors'] == {'temperatures': None, 'fans': None, 'battery': None}


def test_sensors_are_na_when_psutil_fails(fake_machine, capsys, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError('odd driver')
    monkeypatch.setattr(psutil, 'sensors_temperatures', broken, raising=False)

    assert 'Temperatures: N/A\n' in _text(capsys, '--sensors')


def test_sensors_empty_lists_mean_supported_but_nothing_found(fake_machine, capsys):
    # A Linux container: the functions exist but find no sensors.
    fake_machine.temperatures = {}
    fake_machine.fans = {}
    assert _json(capsys, '--sensors')['sensors']['temperatures'] == []
    assert 'Temperatures: N/A\nFans: N/A\n' in _text(capsys, '--sensors')


def test_sensors_json_lists_every_reading(fake_machine, capsys):
    sensors = _json(capsys, '--sensors')['sensors']
    assert sensors['temperatures'][0] == {
        'sensor': 'coretemp', 'label': 'Package id 0', 'current': 45.0, 'high': 80.0, 'critical': 100.0}
    assert sensors['temperatures'][2]['label'] is None
    assert sensors['fans'] == [{'sensor': 'thinkpad', 'label': None, 'rpm': 2400}]


def test_sensors_work_on_this_machine(capsys):
    assert 'Battery:' in _text(capsys, '--sensors')
    assert set(_json(capsys, '--sensors')['sensors']) == {'temperatures', 'fans', 'battery'}


# --top

def test_top_lists_the_busiest_processes(fake_machine, capsys):
    assert _text(capsys, '--top') == (
        'Top 3 processes by CPU:\n'
        'PID  NAME       CPU%  MEM%    MEMORY  USER\n'
        '101  python    12.3%  1.8%  300.00MB  nat\n'
        '202  postgres   3.0%  6.2%    1.00GB  postgres\n'
        '303  bash       0.0%  0.0%    4.00MB  nat\n'
        '\n')
    # CPU usage per process is measured over one second.
    assert fake_machine.slept and fake_machine.slept[0] == pytest.approx(1.0, abs=0.1)


def test_top_takes_a_count_and_a_sort_order(fake_machine, capsys):
    text = _text(capsys, '--top', '2', '--sort', 'memory')
    assert text.startswith('Top 2 processes by memory:\n')
    assert [line.split()[1] for line in text.splitlines()[2:4]] == ['postgres', 'python']


def test_top_skips_processes_that_are_gone_or_hidden(fake_machine, capsys):
    fake_machine.processes[0].error = psutil.NoSuchProcess(101)
    fake_machine.processes[1].memory_error = psutil.AccessDenied(202)

    rows = _json(capsys, '--top')['processes']

    assert [p['pid'] for p in rows] == [202, 303]
    assert rows[0]['memory_rss'] is None
    assert rows[0]['memory_percent'] is None
    assert '202  postgres  3.0%   N/A     N/A  postgres\n' in _text(capsys, '--top')


def test_top_leaves_out_the_windows_idle_process(fake_machine, capsys, monkeypatch):
    monkeypatch.setattr(psutil, 'WINDOWS', True)
    fake_machine.processes.insert(0, FakeProcess(0, 'System Idle Process', None, cpu=790.0, rss=8 * 1024,
                                                 memory_percent=0.0))
    assert [p['pid'] for p in _json(capsys, '--top')['processes']] == [101, 202, 303]


def test_top_json_has_numbers(fake_machine, capsys):
    assert _json(capsys, '--top', '1')['processes'] == [{
        'pid': 101, 'name': 'python', 'username': 'nat', 'cpu_percent': 12.3,
        'memory_percent': 1.83, 'memory_rss': 300 * MB}]


def test_top_without_processes_is_na(fake_machine, capsys):
    fake_machine.processes = []
    assert _text(capsys, '--top') == 'Processes: N/A\n\n'


@pytest.mark.parametrize('value', ['0', '-3', 'many'])
def test_top_rejects_counts_below_one(capsys, value):
    with pytest.raises(SystemExit) as exc:
        main(['--top', value])
    assert exc.value.code == 2
    assert 'expected a whole number above 0' in capsys.readouterr().err


def test_get_processes_rejects_bad_arguments():
    with pytest.raises(ValueError):
        showsys.get_processes(limit=0)
    with pytest.raises(ValueError):
        showsys.get_processes(sort_by='name')


def test_top_works_on_this_machine(capsys):
    text = _text(capsys, '--top', '3')
    assert text.startswith('Top ')
    rows = _json(capsys, '--top', '3', '--sort', 'memory')['processes']
    assert 1 <= len(rows) <= 3
    assert all(isinstance(p['pid'], int) for p in rows)
