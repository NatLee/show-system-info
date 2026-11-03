"""The CPU name comes from py-cpuinfo's quick sources, skipping its one-second CPUID probe."""
import types

import cpuinfo
import pytest

from showsys import collectors


def _fake_cpuinfo(monkeypatch, **brands):
    """py-cpuinfo with every quick source returning nothing, except the ones given."""
    calls = []

    def source(name):
        def read():
            calls.append(name)
            value = brands.get(name)
            if isinstance(value, Exception):
                raise value
            return {'brand_raw': value} if value else {}
        return read

    module = types.SimpleNamespace(**{
        f'_get_cpu_info_from_{name}': source(name) for name in collectors._QUICK_BRAND_SOURCES})
    monkeypatch.setattr(cpuinfo, 'cpuinfo', module)
    monkeypatch.setattr(cpuinfo, 'get_cpu_info', lambda: {'brand_raw': 'from the slow path'})
    return module, calls


def test_the_first_quick_source_with_a_name_wins(monkeypatch):
    _, calls = _fake_cpuinfo(monkeypatch, proc_cpuinfo='Example CPU', lscpu='Other name')
    assert collectors.get_system().processor_brand == 'Example CPU'
    # Stops at the first answer, like get_cpu_info() keeps the first value it finds.
    assert calls == ['wmic', 'registry', 'proc_cpuinfo']


def test_the_slow_path_runs_when_no_quick_source_knows(monkeypatch):
    _fake_cpuinfo(monkeypatch)
    assert collectors.get_system().processor_brand == 'from the slow path'


@pytest.mark.parametrize('broken', ['missing', 'raises'])
def test_an_unfamiliar_py_cpuinfo_falls_back_to_its_public_api(monkeypatch, broken):
    module, _ = _fake_cpuinfo(monkeypatch, sysctl='Example CPU')
    if broken == 'missing':
        del module._get_cpu_info_from_registry
    else:
        module._get_cpu_info_from_registry = lambda: 1 / 0
    assert collectors.get_system().processor_brand == 'from the slow path'


def test_quick_name_matches_py_cpuinfo_on_this_machine():
    quick = collectors._quick_processor_brand()
    if quick is None:
        pytest.skip('no quick source knows this CPU; showsys uses get_cpu_info()')
    assert quick == cpuinfo.get_cpu_info().get('brand_raw')
