"""--version and `python -m showsys`."""
import subprocess
import sys

import pytest

import showsys
from showsys.cli import main


@pytest.mark.parametrize('flag', ['--version', '-V'])
def test_version_prints_the_package_version(capsys, flag):
    with pytest.raises(SystemExit) as exc:
        main([flag])
    assert exc.value.code == 0
    assert capsys.readouterr().out == f'showsys {showsys.__version__}\n'


def test_python_dash_m_runs_the_command():
    result = subprocess.run([sys.executable, '-m', 'showsys', '--memory'],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    assert result.returncode == 0
    assert result.stdout.startswith('Memory Total: ')
    assert result.stderr == ''
