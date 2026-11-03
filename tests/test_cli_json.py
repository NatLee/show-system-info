"""`showsys --json` prints the same data as showsys.collect()."""
import json

import psutil
import pytest

from showsys.cli import main

from .fakes import GB

LEGACY_SECTIONS = {
    (): ['system', 'memory', 'swap'],
    ('-d',): ['system', 'boot', 'cpu', 'memory', 'swap', 'network'],
    ('-b',): ['boot'],
    ('-m',): ['memory'],
    ('-s',): ['swap'],
    ('-c',): ['cpu'],
    ('-n',): ['network'],
    ('-m', '-s'): ['memory'],
}


def _json(capsys, *flags):
    main(list(flags))
    captured = capsys.readouterr()
    assert captured.err == ''
    return json.loads(captured.out)


@pytest.mark.parametrize('flags', list(LEGACY_SECTIONS), ids=lambda f: ' '.join(f) or '(none)')
@pytest.mark.parametrize('json_flag', ['--json', '-j'])
def test_json_has_the_sections_of_the_text_view(fake_machine, capsys, flags, json_flag):
    data = _json(capsys, json_flag, *flags)
    assert list(data) == ['timestamp'] + LEGACY_SECTIONS[flags]


def test_json_values_are_numbers(fake_machine, capsys):
    data = _json(capsys, '--json', '-d')
    assert data['memory']['total'] == 16 * GB
    assert data['cpu']['usage_per_core'][3] == 10.0
    assert data['cpu']['freq_min_mhz'] is None
    assert data['network']['interfaces']['eth0']['addresses'][0] == {
        'family': 'ipv4', 'address': '192.168.1.10', 'netmask': '255.255.255.0', 'broadcast': '192.168.1.255'}


def test_json_uses_null_for_missing_values(fake_machine, capsys, monkeypatch):
    monkeypatch.setattr('socket.gethostbyname', lambda name: (_ for _ in ()).throw(OSError('no')))
    assert _json(capsys, '--json')['system']['ip_address'] is None


def test_json_errors_go_to_stderr(fake_machine, capsys, monkeypatch):
    def broken():
        raise RuntimeError('boom')
    monkeypatch.setattr(psutil, 'virtual_memory', broken)

    main(['--json'])

    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'An unexpected error occurred: boom' in captured.err


@pytest.mark.parametrize('flags', [[], ['-d']], ids=['summary', 'details'])
def test_json_works_on_this_machine(capsys, flags):
    data = _json(capsys, '--json', *flags)
    assert data['system']['system']
    assert data['memory']['total'] > 0
