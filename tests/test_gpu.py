"""--gpu and get_gpus() through the optional nvidia-ml-py package (imported as pynvml)."""
import json
import sys
import types
from collections import namedtuple

import pytest

import showsys
from showsys.cli import main

from .fakes import GB

Memory = namedtuple('Memory', 'total free used')
Utilization = namedtuple('Utilization', 'gpu memory')


class NVMLError(Exception):
    pass


def _fake_nvml(monkeypatch, gpus=(), init_error=False, driver='550.54'):
    """A pynvml module with the given GPUs: dicts of name, memory, util, temp and mW."""
    calls = []

    def unsupported(value):
        if value is None:
            raise NVMLError('Not Supported')
        return value

    def init():
        calls.append('init')
        if init_error:
            raise NVMLError('Driver Not Loaded')

    nvml = types.SimpleNamespace(
        NVMLError=NVMLError,
        NVML_TEMPERATURE_GPU=0,
        nvmlInit=init,
        nvmlShutdown=lambda: calls.append('shutdown'),
        nvmlSystemGetDriverVersion=lambda: driver,
        nvmlDeviceGetCount=lambda: len(gpus),
        nvmlDeviceGetHandleByIndex=lambda index: gpus[index],
        nvmlDeviceGetName=lambda gpu: gpu['name'],
        nvmlDeviceGetMemoryInfo=lambda gpu: unsupported(gpu.get('memory')),
        nvmlDeviceGetUtilizationRates=lambda gpu: unsupported(gpu.get('util')),
        nvmlDeviceGetTemperature=lambda gpu, sensor: unsupported(gpu.get('temp')),
        nvmlDeviceGetPowerUsage=lambda gpu: unsupported(gpu.get('mW')),
    )
    monkeypatch.setitem(sys.modules, 'pynvml', nvml)
    return calls


RTX = {'name': 'NVIDIA GeForce RTX 4080', 'memory': Memory(total=16 * GB, free=14 * GB, used=2 * GB),
       'util': Utilization(gpu=37, memory=12), 'temp': 41, 'mW': 52250}


def _text(capsys, *flags):
    main(list(flags))
    captured = capsys.readouterr()
    assert 'An unexpected error occurred' not in captured.out + captured.err
    return captured.out


def test_gpu_lists_each_nvidia_gpu(monkeypatch, capsys):
    calls = _fake_nvml(monkeypatch, [RTX])
    assert _text(capsys, '--gpu') == (
        'GPU 0: NVIDIA GeForce RTX 4080\n'
        '\tDriver: 550.54\n'
        '\tMemory: 2.00GB used of 16.00GB (14.00GB free)\n'
        '\tUtilization: 37%\n'
        '\tTemperature: 41.0C\n'
        '\tPower: 52.25W\n'
        '\n')
    assert calls == ['init', 'shutdown']


def test_gpu_json_has_numbers(monkeypatch, capsys):
    _fake_nvml(monkeypatch, [RTX, {'name': b'Tesla T4'}])
    gpus = json.loads(_text(capsys, '--gpu', '--json'))['gpu']
    assert gpus[0] == {
        'index': 0, 'name': 'NVIDIA GeForce RTX 4080', 'driver_version': '550.54',
        'memory_total': 16 * GB, 'memory_used': 2 * GB, 'memory_free': 14 * GB,
        'utilization_percent': 37.0, 'temperature_c': 41.0, 'power_watts': 52.25}
    # Old nvidia-ml-py returns bytes; values a GPU does not support are null.
    assert gpus[1] == {
        'index': 1, 'name': 'Tesla T4', 'driver_version': '550.54',
        'memory_total': None, 'memory_used': None, 'memory_free': None,
        'utilization_percent': None, 'temperature_c': None, 'power_watts': None}


def test_gpu_values_a_card_does_not_support_are_na(monkeypatch, capsys):
    _fake_nvml(monkeypatch, [{'name': 'Tesla T4'}], driver=None)
    assert _text(capsys, '--gpu') == (
        'GPU 0: Tesla T4\n\tDriver: N/A\n\tMemory: N/A\n\tUtilization: N/A\n'
        '\tTemperature: N/A\n\tPower: N/A\n\n')


def test_gpu_without_the_extra_says_how_to_get_it(monkeypatch, capsys):
    # None in sys.modules makes `import pynvml` raise ImportError.
    monkeypatch.setitem(sys.modules, 'pynvml', None)
    assert showsys.get_gpus() is None
    assert _text(capsys, '--gpu') == (
        'GPU: N/A (NVIDIA GPUs only; install the extra: pip install "showsys[gpu]")\n\n')
    assert json.loads(_text(capsys, '--gpu', '-j'))['gpu'] is None


def test_gpu_without_a_driver(monkeypatch, capsys):
    calls = _fake_nvml(monkeypatch, init_error=True)
    assert _text(capsys, '--gpu') == 'GPU: N/A (no NVIDIA driver found)\n\n'
    assert calls == ['init']


def test_gpu_driver_without_gpus(monkeypatch, capsys):
    _fake_nvml(monkeypatch, [])
    assert _text(capsys, '--gpu') == 'GPU: none found\n\n'
    assert showsys.get_gpus() == []


def test_gpu_works_on_this_machine(capsys):
    gpus = showsys.get_gpus()
    assert gpus is None or all(gpu.name for gpu in gpus)
    assert _text(capsys, '--gpu').startswith('GPU')


@pytest.mark.parametrize('flag', ['--gpu'])
def test_gpu_is_listed_in_help(capsys, flag):
    with pytest.raises(SystemExit):
        main(['-h'])
    assert flag in capsys.readouterr().out
