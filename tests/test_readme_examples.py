"""Run the examples from README.md and every documented command line option."""
import sys

import pytest

from showsys import ShowSys
from showsys.cli import main

# Keys shown in the README's `print(sysinfo.cpu_info())` example.
README_CPU_KEYS = {
    'Physical cores',
    'Total cores',
    'Max Frequency',
    'Min Frequency',
    'Current Frequency',
    'CPU Usage Per Core',
    'Total CPU Usage',
}

# Methods listed in the README's "As a Library" section.
README_METHODS = [
    'system_information',
    'boot_time',
    'cpu_info',
    'memory_info',
    'swap_info',
    'network_info',
]

CLI_FLAGS = [
    [],
    ['-d'], ['--details'],
    ['-b'], ['--boot_time'],
    ['-m'], ['--memory'],
    ['-s'], ['--swap'],
    ['-c'], ['--cpu'],
    ['-n'], ['--network'],
]


def test_readme_info_example_prints_the_summary(capsys):
    sysinfo = ShowSys()
    text = sysinfo.info()
    assert text in capsys.readouterr().out
    for key in ('System:', 'IP-Address:', 'Memory Total:', 'Swap Total:'):
        assert key in text


def test_readme_cpu_info_example_has_the_documented_keys():
    sysinfo = ShowSys()
    assert set(sysinfo.cpu_info()) == README_CPU_KEYS


@pytest.mark.parametrize('method', README_METHODS)
def test_readme_methods_return_information(method):
    info = getattr(ShowSys(), method)()
    assert isinstance(info, dict)
    assert info


@pytest.mark.parametrize('flags', CLI_FLAGS, ids=lambda f: ' '.join(f) or '(none)')
def test_cli_option_prints_information(monkeypatch, capsys, flags):
    monkeypatch.setattr(sys, 'argv', ['showsys'] + flags)
    main()
    out = capsys.readouterr().out
    assert out.strip()
    assert 'An unexpected error occurred' not in out


def test_cli_help_lists_every_option(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['showsys', '-h'])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for option in ('--details', '--boot_time', '--memory', '--swap', '--cpu', '--network'):
        assert option in out
