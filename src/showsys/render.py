"""Turn the records from :mod:`showsys.collectors` into text.

The ``*_dict`` functions build the dicts that the :class:`showsys.ShowSys` methods have
always returned; :func:`enum` prints them. Their output must not change: scripts read it.
"""
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from .models import BootInfo, CpuInfo, DiskInfo, MemoryInfo, NetworkInfo, SwapInfo, SystemInfo

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


def size_or_na(num_bytes: Optional[float], suffix: str = 'B') -> str:
    return NA if num_bytes is None else size(num_bytes, suffix)


def percent(value: float) -> str:
    return f'{value}%'


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
        'Physical cores': info.physical_cores,
        'Total cores': info.logical_cores,
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
                # Four items per line.
                for i in range(0, len(value), 4):
                    output += '\t'.join(value[i:i + 4]) + '\n'
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
