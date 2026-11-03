"""Turn the records from :mod:`showsys.collectors` into text.

The ``*_dict`` functions build the dicts that the :class:`showsys.ShowSys` methods have
always returned; :func:`enum` prints them. Their output must not change: scripts read it.
"""
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence

from .collectors import DEFAULT_SORT, GPU_EXTRA, PROCESS_ORDERS
from .models import (
    Battery,
    BootInfo,
    CpuInfo,
    DiskInfo,
    GpuInfo,
    MemoryInfo,
    NetworkInfo,
    ProcessInfo,
    Rates,
    SensorsInfo,
    SwapInfo,
    SystemInfo,
)

#: Shown instead of a value the operating system does not report.
NA = 'N/A'

BORDER = '================='

_SIZE_STEP = 1024
_SIZE_UNITS = ('', 'K', 'M', 'G', 'T', 'P', 'E')

# ShowSys 1.0 printed lists longer than this with this many items per line.
_ITEMS_PER_LINE = 4


def size(num_bytes: float, suffix: str = 'B') -> str:
    """Format a byte count with binary units, e.g. ``1536`` -> ``1.50KB``."""
    value = num_bytes
    for unit in _SIZE_UNITS[:-1]:
        if value < _SIZE_STEP:
            return f'{value:.2f}{unit}{suffix}'
        value /= _SIZE_STEP
    return f'{value:.2f}{_SIZE_UNITS[-1]}{suffix}'


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
            if len(value) > _ITEMS_PER_LINE:
                # str(): the items can be dicts, e.g. disk partitions.
                for i in range(0, len(value), _ITEMS_PER_LINE):
                    output += '\t'.join(str(item) for item in value[i:i + _ITEMS_PER_LINE]) + '\n'
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


#: What `showsys` (and ShowSys.info()) and `showsys -d` (and detail_info()) show, in order.
SUMMARY_SECTIONS = ('system', 'memory', 'swap')
DETAIL_SECTIONS = ('system', 'boot', 'cpu', 'memory', 'swap', 'network')

#: The 1.0 display dict of each section in DETAIL_SECTIONS, for --all.
LEGACY_DICTS: Dict[str, Callable[[Any], Dict[str, Any]]] = {
    'system': system_dict,
    'boot': boot_dict,
    'cpu': cpu_dict,
    'memory': memory_dict,
    'swap': swap_dict,
    'network': network_dict,
}


def framed(*sections: Mapping[str, Any]) -> str:
    """Sections between two borders, as printed by ``info()`` and ``detail_info()``."""
    return BORDER + '\n' + ''.join(enum(section) for section in sections) + BORDER


# Text for the options added after 1.0 (--disk, ...). These are free to improve.

class Column(NamedTuple):
    """A column of a text table: its header, its alignment and the widest value it expects."""
    header: str
    right: bool = False
    """Right-align, for numbers."""
    sample: str = ''
    """A value as wide as the widest one, for tables printed a line at a time (--watch)."""

    def width(self, cells: Sequence[str] = ()) -> int:
        return max(len(self.header), len(self.sample), *(len(cell) for cell in cells))


def _row(columns: Sequence[Column], cells: Sequence[str], widths: Sequence[int]) -> str:
    """One line of a table: cells separated by two spaces, without trailing blanks."""
    return '  '.join(cell.rjust(width) if column.right else cell.ljust(width)
                     for column, cell, width in zip(columns, cells, widths)).rstrip()


def table(columns: Sequence[Column], rows: Sequence[Sequence[str]]) -> str:
    """A header line and a line per row, each column as wide as its widest cell."""
    widths = [column.width([row[i] for row in rows]) for i, column in enumerate(columns)]
    lines = [_row(columns, [column.header for column in columns], widths)]
    lines += [_row(columns, row, widths) for row in rows]
    return '\n'.join(lines) + '\n'


_DISK_COLUMNS = (
    Column('DEVICE'), Column('MOUNTPOINT'), Column('TYPE'),
    Column('TOTAL', right=True), Column('USED', right=True), Column('FREE', right=True),
    Column('USE%', right=True),
)


def disk_text(info: DiskInfo) -> str:
    if info.partitions:
        rows = [[p.device, p.mountpoint, p.fstype, size(p.total), size(p.used), size(p.free), percent(p.percent)]
                for p in info.partitions]
        text = 'Partitions:\n' + table(_DISK_COLUMNS, rows)
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


_PROCESS_COLUMNS = (
    Column('PID', right=True), Column('NAME'), Column('CPU%', right=True),
    Column('MEM%', right=True), Column('MEMORY', right=True), Column('USER'),
)
# Long process names (common on macOS) would push the other columns off the screen.
_MAX_NAME_WIDTH = 30


def processes_text(processes: Sequence[ProcessInfo], sort_by: str = DEFAULT_SORT) -> str:
    if not processes:
        return f'Processes: {NA}\n'
    rows = [[
        str(p.pid),
        (p.name or NA)[:_MAX_NAME_WIDTH],
        f'{p.cpu_percent:.1f}%',
        NA if p.memory_percent is None else f'{p.memory_percent:.1f}%',
        size_or_na(p.memory_rss),
        p.username or NA,
    ] for p in processes]
    return f'Top {len(processes)} processes by {PROCESS_ORDERS[sort_by].label}:\n' + table(
        _PROCESS_COLUMNS, rows)


GPU_EXTRA_HINT = f'NVIDIA GPUs only; install the extra: pip install "{GPU_EXTRA}"'


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


def all_text(records: Mapping[str, Any], sort_by: str = DEFAULT_SORT, nvml_installed: bool = True) -> str:
    """Every section between borders: the ``detail_info()`` text, then disks, sensors,
    processes and GPUs. ``records`` is what ``collectors.gather()`` returns for all sections."""
    details = ''.join(enum(LEGACY_DICTS[name](records[name])) for name in DETAIL_SECTIONS)
    return (BORDER + '\n' + details
            + disk_text(records['disk'])
            + sensors_text(records['sensors'])
            + processes_text(records['processes'], sort_by)
            + gpu_text(records['gpu'], nvml_installed)
            + BORDER)


# --watch prints a line at a time, so each column is as wide as its widest possible value.
_WIDEST_PERCENT = '100.0%'
# Rounding can show 1024.00 next to a unit letter, e.g. '1024.00KB': the widest size().
_WIDEST_SIZE = size(_SIZE_STEP ** 2 - 1)
_WATCH_COLUMNS = (
    Column('TIME', sample='00:00:00'),
    Column('CPU', right=True, sample=_WIDEST_PERCENT),
    Column('MEM', right=True, sample=_WIDEST_PERCENT),
    Column('SWAP', right=True, sample=_WIDEST_PERCENT),
    Column('NET SENT/s', right=True, sample=_WIDEST_SIZE),
    Column('NET RECV/s', right=True, sample=_WIDEST_SIZE),
    Column('DISK READ/s', right=True, sample=_WIDEST_SIZE),
    Column('DISK WRITE/s', right=True, sample=_WIDEST_SIZE),
)
_WATCH_WIDTHS = [column.width() for column in _WATCH_COLUMNS]


def watch_header() -> str:
    return _row(_WATCH_COLUMNS, [column.header for column in _WATCH_COLUMNS], _WATCH_WIDTHS)


def watch_line(rates: Rates) -> str:
    return _row(_WATCH_COLUMNS, [
        datetime.fromisoformat(rates.timestamp).strftime('%H:%M:%S'),
        f'{rates.cpu_percent:.1f}%',
        f'{rates.memory_percent:.1f}%',
        f'{rates.swap_percent:.1f}%',
        size_or_na(rates.net_sent_per_sec),
        size_or_na(rates.net_recv_per_sec),
        size_or_na(rates.disk_read_per_sec),
        size_or_na(rates.disk_write_per_sec),
    ], _WATCH_WIDTHS)
