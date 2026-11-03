"""Sections added after ShowSys 1.0: --disk, --sensors, --top, --gpu and --all."""
import json

import psutil

from showsys.cli import main

from .fakes import GB, Battery, DiskPartition, DiskUsage


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
