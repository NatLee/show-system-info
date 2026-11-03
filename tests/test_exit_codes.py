"""Exit status: 0 when showsys works, 1 when it fails, 2 for usage errors (argparse)."""
import os
import shutil
import subprocess
import sys

import psutil
import pytest

from showsys import cli
from showsys.cli import main

# Breaks psutil.virtual_memory() in a new Python process, before showsys starts.
BREAK_MEMORY = (
    'import psutil\n'
    'def _broken(*args, **kwargs):\n'
    '    raise RuntimeError("simulated failure")\n'
    'psutil.virtual_memory = _broken\n'
)


def _broken(*args, **kwargs):
    raise RuntimeError('simulated failure')


@pytest.mark.parametrize('argv', [[], ['-m'], ['--json'], ['-m', '--json'], ['--all']])
def test_success_returns_zero(fake_machine, capsys, argv):
    assert main(argv) == cli.EXIT_OK == 0


@pytest.mark.parametrize('argv', [[], ['-m'], ['--json'], ['-d', '--json'], ['--all']])
def test_failure_returns_one(fake_machine, capsys, monkeypatch, argv):
    monkeypatch.setattr(psutil, 'virtual_memory', _broken)
    assert main(argv) == cli.EXIT_FAILURE == 1
    captured = capsys.readouterr()
    assert 'An unexpected error occurred: simulated failure' in captured.out + captured.err


def test_a_failure_during_watch_returns_one(fake_machine, capsys, monkeypatch):
    monkeypatch.setattr(psutil, 'swap_memory', _broken)
    assert main(['--watch', '--count', '1']) == 1


def test_stopping_watch_with_ctrl_c_is_a_normal_exit(fake_machine, capsys, monkeypatch):
    def interrupted(interval, count):
        raise KeyboardInterrupt
        yield  # pragma: no cover
    monkeypatch.setattr(cli.live, 'watch', interrupted)
    assert main(['--watch']) == 0


def test_usage_errors_still_exit_with_two(capsys):
    with pytest.raises(SystemExit) as exc:
        main(['--top', '0'])
    assert exc.value.code == 2


def _run(command, tmp_path):
    (tmp_path / 'sitecustomize.py').write_text(BREAK_MEMORY)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(tmp_path), os.environ.get('PYTHONPATH', '')]))
    return subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


def test_python_dash_m_exits_with_one_on_failure(tmp_path):
    result = _run([sys.executable, '-m', 'showsys', '-m'], tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'simulated failure' in result.stdout


def test_the_showsys_script_exits_with_one_on_failure(tmp_path):
    script = shutil.which('showsys', path=os.path.dirname(sys.executable)) or shutil.which('showsys')
    if script is None:
        pytest.skip('the showsys script is not installed next to this Python')
    result = _run([script, '--json'], tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout == ''
    assert 'simulated failure' in result.stderr
