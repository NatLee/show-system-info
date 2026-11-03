"""Turn the records from :mod:`showsys.collectors` into text.

The ``*_dict`` functions build the dicts that the :class:`showsys.ShowSys` methods have
always returned; :func:`enum` prints them. Their output must not change: scripts read it.
"""
from datetime import datetime, timedelta
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence

from .models import (
    Battery,
    BootInfo,
    CpuInfo,
    DiskInfo,
    GpuInfo,
    MemoryInfo,
    NetworkInfo,
    ProcessInfo,
    SensorsInfo,
    SwapInfo,
    SystemInfo,
)

#: Shown instead of a value the operating system does not report.
NA = 'N/A'

BORDER = '================='

_SIZE_UNITS = ('', 'K', 'M', 'G', 'T', 'P')


def size(num_bytes: float, suffix: str = 'B') -> str:
    """Format a byte count with binary units, e.g. ``1536`` -> ``1.50KB``."""
    value = num_bytes
    for unit in _SIZE_UNITS:
        if value < 1024:
            return f'{value:.2f}{unit}{suffix}'
        value /= 1024
    return f'{value:.2f}E{suffix}'


def size_or_na(num_bytes: Optional[float], suffix: str = 'B') -> str:
    return NA if num_bytes is None else size(num_bytes, suffix)


def percent(value: float) -> str:
    return f'{value}%'


def _count(value: Optional[int]) -> Any:
    return NA if value is None else value


def _mhz(value: Optional[float]) -> str:
    return NA if value is None else f'{value:.2f}Mhz'


def system_dict(info: SystemInfo) -> Dict[str, Any]:
    return {
        'System': info.system,
        'Node Name': info.node,
        'Release': info.release,
        'Version': info.version,
        'Machine': info.machine,
        # An empty processor name has always been printed as an empty string.
        'Processor': info.processor or '',
        'Processor Brand': info.processor_brand or NA,
        'IP-Address': info.ip_address or NA,
        'Mac-Address': info.mac_address,
    }


def boot_dict(info: BootInfo) -> Dict[str, str]:
    bt = datetime.fromtimestamp(info.timestamp)
    return {'Boot Time': f'{bt.year}/{bt.month}/{bt.day} {bt.hour}:{bt.minute}:{bt.second}'}


def cpu_dict(info: CpuInfo) -> Dict[str, Any]:
    if info.freq_current_mhz is None:
        max_freq = min_freq = current_freq = NA
    else:
        # ShowSys 1.0 printed the 0.0 that psutil uses for an unknown minimum or maximum.
        max_freq = _mhz(info.freq_max_mhz or 0.0)
        min_freq = _mhz(info.freq_min_mhz or 0.0)
        current_freq = _mhz(info.freq_current_mhz)
    return {
        'Physical cores': _count(info.physical_cores),
        'Total cores': _count(info.logical_cores),
        'Max Frequency': max_freq,
        'Min Frequency': min_freq,
        'Current Frequency': current_freq,
        'CPU Usage Per Core': [percent(value) for value in info.usage_per_core],
        'Total CPU Usage': percent(info.usage_percent),
    }


def memory_dict(info: MemoryInfo) -> Dict[str, str]:
    return {
        'Memory Total': size(info.total),
        'Memory Available': size(info.available),
        'Memory Used': size(info.used),
        'Memory Percentage': percent(info.percent),
    }


def swap_dict(info: SwapInfo) -> Dict[str, str]:
    return {
        'Swap Total': size(info.total),
        'Swap Free': size(info.free),
        'Swap Used': size(info.used),
        'Swap Percentage': percent(info.percent),
    }


def disk_dict(info: DiskInfo) -> Dict[str, Any]:
    partitions: List[Dict[str, str]] = [{
        'Device': partition.device,
        'Mountpoint': partition.mountpoint,
        'File system type': partition.fstype,
        'Total Size': size(partition.total),
        'Used': size(partition.used),
        'Free': size(partition.free),
        'Percentage': percent(partition.percent),
    } for partition in info.partitions]
    return {
        'Partitions': partitions,
        'Total read': size_or_na(info.read_bytes),
        'Total write': size_or_na(info.write_bytes),
    }


def network_dict(info: NetworkInfo) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for name, interface in info.interfaces.items():
        entries = []
        for address in interface.addresses:
            if address.family == 'ipv4':
                entries.append({
                    'IP Address': address.address,
                    'Netmask': address.netmask,
                    'Broadcast IP': address.broadcast,
                })
            elif address.family == 'mac':
                entries.append({
                    'MAC Address': address.address,
                    'Netmask': address.netmask,
                    'Broadcast MAC': address.broadcast,
                })
        result[name] = entries
    result['Total Bytes Sent'] = size_or_na(info.bytes_sent)
    result['Total Bytes Received'] = size_or_na(info.bytes_recv)
    return result


def enum(info: Mapping[str, Any]) -> str:
    """One ``key: value`` line per entry; lists and dicts get one indented line per item."""
    output = ''
    for key, value in info.items():
        if isinstance(value, list):
            output += f'{key}:\n'
            if len(value) > 4:
                # Four items per line. str(): the items can be dicts, e.g. disk partitions.
                for i in range(0, len(value), 4):
                    output += '\t'.join(str(item) for item in value[i:i + 4]) + '\n'
            else:
                for item in value:
                    output += f'\t{item}\n'
        elif isinstance(value, dict):
            output += f'{key}:\n'
            for k, v in value.items():
                output += f'\t{k}: {v}\n'
        else:
            output += f'{key}: {value}\n'
    return output


def framed(*sections: Mapping[str, Any]) -> str:
    """Sections between two borders, as printed by ``info()`` and ``detail_info()``."""
    return BORDER + '\n' + ''.join(enum(section) for section in sections) + BORDER


# Text for the options added after 1.0 (--disk, ...). These are free to improve.

def table(headers: Sequence[str], rows: Sequence[Sequence[str]], right: Collection[int] = ()) -> str:
    """Columns separated by two spaces; the columns listed in ``right`` are right-aligned."""
    widths = [max(len(cell) for cell in column) for column in zip(headers, *rows)]
    lines = []
    for row in [headers, *rows]:
        cells = [cell.rjust(width) if i in right else cell.ljust(width)
                 for i, (cell, width) in enumerate(zip(row, widths))]
        lines.append('  '.join(cells).rstrip())
    return '\n'.join(lines) + '\n'


def disk_text(info: DiskInfo) -> str:
    if info.partitions:
        rows = [[p.device, p.mountpoint, p.fstype, size(p.total), size(p.used), size(p.free), percent(p.percent)]
                for p in info.partitions]
        text = 'Partitions:\n' + table(
            ['DEVICE', 'MOUNTPOINT', 'TYPE', 'TOTAL', 'USED', 'FREE', 'USE%'], rows, right={3, 4, 5, 6})
    else:
        text = f'Partitions: {NA}\n'
    return text + f'Total read: {size_or_na(info.read_bytes)}\nTotal write: {size_or_na(info.write_bytes)}\n'


def _celsius(value: float) -> str:
    # ASCII only: a degree sign can fail on Windows consoles with a legacy code page.
    return f'{value:.1f}C'


def _name(sensor: str, label: Optional[str]) -> str:
    return f'{sensor} {label}' if label else sensor


def _battery_text(battery: Optional[Battery]) -> str:
    if battery is None:
        return NA
    parts = [percent(battery.percent)]
    if battery.power_plugged is not None:
        parts.append('plugged in' if battery.power_plugged else 'on battery')
    if battery.seconds_left is not None:
        parts.append(f'{timedelta(seconds=battery.seconds_left)} left')
    return ', '.join(parts)


def sensors_text(info: SensorsInfo) -> str:
    lines = []
    if info.temperatures:
        lines.append('Temperatures:')
        for t in info.temperatures:
            limits = [f'{name} {_celsius(value)}'
                      for name, value in (('high', t.high), ('critical', t.critical)) if value]
            extra = f" ({', '.join(limits)})" if limits else ''
            lines.append(f'\t{_name(t.sensor, t.label)}: {_celsius(t.current)}{extra}')
    else:
        lines.append(f'Temperatures: {NA}')
    if info.fans:
        lines.append('Fans:')
        lines.extend(f'\t{_name(fan.sensor, fan.label)}: {fan.rpm} RPM' for fan in info.fans)
    else:
        lines.append(f'Fans: {NA}')
    lines.append(f'Battery: {_battery_text(info.battery)}')
    return '\n'.join(lines) + '\n'


def processes_text(processes: Sequence[ProcessInfo], sort_by: str = 'cpu') -> str:
    if not processes:
        return f'Processes: {NA}\n'
    order = 'memory' if sort_by == 'memory' else 'CPU'
    rows = [[
        str(p.pid),
        (p.name or NA)[:30],
        f'{p.cpu_percent:.1f}%',
        NA if p.memory_percent is None else f'{p.memory_percent:.1f}%',
        size_or_na(p.memory_rss),
        p.username or NA,
    ] for p in processes]
    return f'Top {len(processes)} processes by {order}:\n' + table(
        ['PID', 'NAME', 'CPU%', 'MEM%', 'MEMORY', 'USER'], rows, right={0, 2, 3, 4})


GPU_EXTRA_HINT = 'NVIDIA GPUs only; install the extra: pip install "showsys[gpu]"'


def gpu_text(gpus: Optional[Sequence[GpuInfo]], nvml_installed: bool = True) -> str:
    if gpus is None:
        reason = 'no NVIDIA driver found' if nvml_installed else GPU_EXTRA_HINT
        return f'GPU: {NA} ({reason})\n'
    if not gpus:
        return 'GPU: none found\n'
    lines = []
    for gpu in gpus:
        if gpu.memory_total is None or gpu.memory_used is None:
            memory = NA
        else:
            memory = (f'{size(gpu.memory_used)} used of {size(gpu.memory_total)} '
                      f'({size_or_na(gpu.memory_free)} free)')
        lines += [
            f'GPU {gpu.index}: {gpu.name}',
            f'\tDriver: {gpu.driver_version or NA}',
            f'\tMemory: {memory}',
            f"\tUtilization: {NA if gpu.utilization_percent is None else f'{gpu.utilization_percent:g}%'}",
            f'\tTemperature: {NA if gpu.temperature_c is None else _celsius(gpu.temperature_c)}',
            f"\tPower: {NA if gpu.power_watts is None else f'{gpu.power_watts:.2f}W'}",
        ]
    return '\n'.join(lines) + '\n'


def all_text(records: Mapping[str, Any], sort_by: str = 'cpu', nvml_installed: bool = True) -> str:
    """Every section between borders: the ``detail_info()`` text, then disks, sensors,
    processes and GPUs. ``records`` is what ``collectors.gather()`` returns for all sections."""
    return (BORDER + '\n'
            + enum(system_dict(records['system']))
            + enum(boot_dict(records['boot']))
            + enum(cpu_dict(records['cpu']))
            + enum(memory_dict(records['memory']))
            + enum(swap_dict(records['swap']))
            + enum(network_dict(records['network']))
            + disk_text(records['disk'])
            + sensors_text(records['sensors'])
            + processes_text(records['processes'], sort_by)
            + gpu_text(records['gpu'], nvml_installed)
            + BORDER)
