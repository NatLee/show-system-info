"""The CPU name comes from public OS sources first, and from py-cpuinfo's public API last."""
import subprocess
import sys
import types

import cpuinfo
import pytest

from showsys import collectors


@pytest.fixture
def slow_path(monkeypatch):
    """py-cpuinfo's get_cpu_info(), recording whether it was needed."""
    calls = []

    def get_cpu_info():
        calls.append(1)
        return {'brand_raw': 'from py-cpuinfo'}
    monkeypatch.setattr(cpuinfo, 'get_cpu_info', get_cpu_info)
    return calls


def _sources(monkeypatch, *answers):
    calls = []

    def source(i, answer):
        def read():
            calls.append(i)
            return answer
        return read
    monkeypatch.setattr(collectors, '_CPU_NAME_SOURCES',
                        tuple(source(i, answer) for i, answer in enumerate(answers)))
    return calls


def test_the_first_source_that_knows_wins(monkeypatch, slow_path):
    calls = _sources(monkeypatch, None, 'Example CPU', 'Other name')
    assert collectors.get_system().processor_brand == 'Example CPU'
    assert calls == [0, 1]
    assert slow_path == []


def test_py_cpuinfo_is_asked_only_when_no_source_knows(monkeypatch, slow_path):
    _sources(monkeypatch, None, None, None)
    assert collectors.get_system().processor_brand == 'from py-cpuinfo'
    assert slow_path == [1]


# /proc/cpuinfo (Linux). The sample lines are copied from real files.

@pytest.mark.parametrize('content, expected', [
    ('processor\t: 0\nvendor_id\t: AuthenticAMD\nmodel name\t: AMD Ryzen 9 9950X 16-Core Processor\n',
     'AMD Ryzen 9 9950X 16-Core Processor'),
    ('processor\t: 0\nBogoMIPS\t: 48.00\nFeatures\t: fp asimd\nCPU implementer\t: 0x41\n', None),
    ('', None),
], ids=['x86', 'arm64 without model name', 'empty'])
def test_proc_cpuinfo(monkeypatch, tmp_path, content, expected):
    path = tmp_path / 'cpuinfo'
    path.write_text(content)
    monkeypatch.setattr(collectors, '_PROC_CPUINFO', str(path))
    assert collectors._cpu_name_from_proc_cpuinfo() == expected


def test_proc_cpuinfo_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(collectors, '_PROC_CPUINFO', str(tmp_path / 'missing'))
    assert collectors._cpu_name_from_proc_cpuinfo() is None


# The Windows registry, through a fake winreg module.

class _Key:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def _fake_winreg(monkeypatch, value=None, error=None):
    def open_key(root, path):
        assert path == collectors._REGISTRY_CPU_KEY
        if error:
            raise error
        return _Key()
    monkeypatch.setitem(sys.modules, 'winreg', types.SimpleNamespace(
        HKEY_LOCAL_MACHINE=object(), OpenKey=open_key,
        QueryValueEx=lambda key, name: (value, 1)))


def test_registry(monkeypatch):
    _fake_winreg(monkeypatch, value='Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz  ')
    assert collectors._cpu_name_from_registry() == 'Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz'


def test_registry_without_the_key(monkeypatch):
    _fake_winreg(monkeypatch, error=FileNotFoundError(2, 'The system cannot find the file specified'))
    assert collectors._cpu_name_from_registry() is None


def test_registry_off_windows(monkeypatch):
    monkeypatch.setitem(sys.modules, 'winreg', None)  # makes `import winreg` fail
    assert collectors._cpu_name_from_registry() is None


# sysctl (macOS), through a fake subprocess.run.

@pytest.mark.parametrize('returncode, stdout, expected', [
    (0, 'Apple M2 Pro (Virtual)\n', 'Apple M2 Pro (Virtual)'),
    (255, '', None),   # Linux sysctl: "cannot stat /proc/sys/machdep/cpu/brand_string"
    (0, '\n', None),
], ids=['macos', 'unknown name', 'empty'])
def test_sysctl(monkeypatch, returncode, stdout, expected):
    def run(command, **kwargs):
        assert tuple(command) == collectors._SYSCTL_CPU_NAME
        return subprocess.CompletedProcess(command, returncode, stdout=stdout)
    monkeypatch.setattr(subprocess, 'run', run)
    assert collectors._cpu_name_from_sysctl() == expected


@pytest.mark.parametrize('error', [FileNotFoundError(2, 'No such file'),
                                   subprocess.TimeoutExpired('sysctl', 5)])
def test_sysctl_missing_or_stuck(monkeypatch, error):
    def run(command, **kwargs):
        raise error
    monkeypatch.setattr(subprocess, 'run', run)
    assert collectors._cpu_name_from_sysctl() is None


def test_the_name_matches_py_cpuinfo_on_this_machine():
    # CI runs this on Linux, Windows and macOS.
    names = [source() for source in collectors._CPU_NAME_SOURCES]
    quick = next((name for name in names if name), None)
    if quick is None:
        pytest.skip('no OS source names this CPU; showsys asks py-cpuinfo')
    assert quick == cpuinfo.get_cpu_info().get('brand_raw')
