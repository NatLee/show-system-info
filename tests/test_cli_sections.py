"""Sections added after ShowSys 1.0: --disk, --sensors, --top, --gpu and --all."""
import json

import psutil

from showsys.cli import main

from .fakes import GB, DiskPartition, DiskUsage


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
