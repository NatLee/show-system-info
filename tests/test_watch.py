"""--watch and showsys.watch(): live usage and throughput."""
import json
import re

import psutil
import pytest

import showsys
from showsys import live, render
from showsys.cli import main

from .fakes import MB

HEADER = 'TIME         CPU     MEM    SWAP  NET SENT/s  NET RECV/s  DISK READ/s  DISK WRITE/s'
TIME = re.compile(r'^\d\d:\d\d:\d\d  ')


def _traffic(machine, sent=0, recv=0, read=0, write=0):
    """Make the fake counters grow by these bytes per second while time passes."""
    def tick(seconds):
        machine.net_io = machine.net_io._replace(
            bytes_sent=machine.net_io.bytes_sent + int(sent * seconds),
            bytes_recv=machine.net_io.bytes_recv + int(recv * seconds))
        machine.disk_io = machine.disk_io._replace(
            read_bytes=machine.disk_io.read_bytes + int(read * seconds),
            write_bytes=machine.disk_io.write_bytes + int(write * seconds))
    machine.on_sleep.append(tick)


def test_watch_yields_rates_per_second(fake_machine):
    _traffic(fake_machine, sent=2048, recv=10 * 1024, read=1 * MB)

    readings = list(showsys.watch(interval=2, count=3))

    assert len(readings) == 3
    assert fake_machine.slept == [2.0, 2.0, 2.0]
    first = readings[0]
    assert first.interval_seconds == 2.0
    assert (first.cpu_percent, first.memory_percent, first.swap_percent) == (2.6, 43.8, 25.0)
    assert (first.net_sent_per_sec, first.net_recv_per_sec) == (2048.0, 10240.0)
    assert (first.disk_read_per_sec, first.disk_write_per_sec) == (1 * MB, 0.0)
    assert re.match(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', first.timestamp)


def test_watch_keeps_a_steady_pace(fake_machine, monkeypatch):
    def slow_network_counters(*args, **kwargs):
        fake_machine.clock += 0.1  # each reading takes 0.1 s
        return fake_machine.net_io
    monkeypatch.setattr(psutil, 'net_io_counters', slow_network_counters)

    list(showsys.watch(interval=1, count=3))

    # The time a reading takes comes out of the next sleep, so ticks stay one second apart.
    assert fake_machine.slept == pytest.approx([1.0, 0.9, 0.9])


def test_watch_rates_are_none_without_counters(fake_machine, monkeypatch):
    monkeypatch.setattr(psutil, 'net_io_counters', lambda *args, **kwargs: None)
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda *args, **kwargs: None)

    reading = next(showsys.watch(count=1))

    assert reading.net_sent_per_sec is None
    assert reading.disk_write_per_sec is None
    assert render.watch_line(reading).endswith('    N/A         N/A          N/A           N/A')


def test_watch_counters_that_go_down_are_not_negative(fake_machine):
    fake_machine.on_sleep.append(lambda seconds: setattr(
        fake_machine, 'net_io', fake_machine.net_io._replace(bytes_sent=0)))
    assert next(showsys.watch(count=1)).net_sent_per_sec == 0.0


@pytest.mark.parametrize('kwargs', [{'interval': 0}, {'interval': -1}, {'count': 0}])
def test_watch_rejects_bad_arguments(kwargs):
    with pytest.raises(ValueError):
        next(showsys.watch(**kwargs))


def test_watch_cli_prints_a_header_and_a_line_per_reading(fake_machine, capsys):
    _traffic(fake_machine, sent=1536, recv=3 * MB, write=512)

    main(['--watch', '2', '--count', '2'])

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == HEADER
    assert len(lines) == 3
    for line in lines[1:]:
        assert TIME.match(line)
        assert line[8:] == '    2.6%   43.8%   25.0%      1.50KB      3.00MB        0.00B       512.00B'
    assert fake_machine.slept == [2.0, 2.0]


def test_watch_cli_shows_na_without_counters(fake_machine, capsys, monkeypatch):
    monkeypatch.setattr(psutil, 'disk_io_counters', lambda *args, **kwargs: None)
    main(['-w', '--count', '1'])
    line = capsys.readouterr().out.splitlines()[1]
    assert line.endswith('          N/A           N/A')
    # Without a number, --watch reads every second.
    assert fake_machine.slept == [1.0]


def test_watch_cli_json_lines(fake_machine, capsys):
    _traffic(fake_machine, recv=1000)

    main(['--watch', '0.5', '--count', '3', '--json'])

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3
    readings = [json.loads(line) for line in lines]
    assert readings[0]['net_recv_per_sec'] == 1000.0
    assert readings[0]['interval_seconds'] == 0.5
    assert list(readings[0]) == [
        'timestamp', 'interval_seconds', 'cpu_percent', 'memory_percent', 'swap_percent',
        'net_sent_per_sec', 'net_recv_per_sec', 'disk_read_per_sec', 'disk_write_per_sec']


def test_watch_cli_stops_quietly_on_ctrl_c(fake_machine, capsys, monkeypatch):
    def interrupted(interval, count):
        yield from showsys.watch(interval, 1)
        raise KeyboardInterrupt
    monkeypatch.setattr(live, 'watch', interrupted)

    main(['--watch'])

    out = capsys.readouterr().out
    assert out.splitlines()[0] == HEADER
    assert len(out.splitlines()) == 2
    assert 'An unexpected error occurred' not in out


@pytest.mark.parametrize('argv, message', [
    (['--count', '3'], '--count only works together with --watch'),
    (['--watch', '--cpu'], '--watch has its own columns'),
    (['--watch', '--top'], '--watch has its own columns'),
    (['--watch', '0'], 'expected a number of seconds above 0'),
    (['--watch', 'soon'], 'expected a number of seconds above 0'),
    (['--watch', 'inf'], 'expected a number of seconds above 0'),
    (['--watch', 'nan'], 'expected a number of seconds above 0'),
    (['--watch', '--count', '0'], 'expected a whole number above 0'),
])
def test_watch_cli_rejects_bad_combinations(capsys, argv, message):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 2
    assert message in capsys.readouterr().err


def test_watch_works_on_this_machine(capsys):
    main(['--watch', '0.2', '--count', '2'])
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == HEADER
    assert len(lines) == 3 and all(TIME.match(line) for line in lines[1:])
    main(['--watch', '0.2', '--count', '1', '--json'])
    assert 'cpu_percent' in json.loads(capsys.readouterr().out)
