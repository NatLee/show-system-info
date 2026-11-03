"""Read system information into the records defined in :mod:`showsys.models`.

These functions only collect data; :mod:`showsys.render` turns it into text.
Every value the operating system does not report becomes ``None``.

System calls go through the module objects (``psutil.cpu_freq()``, not an imported name),
so tests can replace them with ``monkeypatch.setattr(psutil, ...)``.
"""
import os
import platform
import re
import socket
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import cpuinfo
import psutil

from .models import (
    BootInfo,
    CpuInfo,
    DiskInfo,
    DiskPartition,
    MemoryInfo,
    NetworkAddress,
    NetworkInfo,
    NetworkInterface,
    SwapInfo,
    SystemInfo,
)

#: Seconds `get_cpu()` waits to measure CPU usage, same as ShowSys 1.0.
DEFAULT_INTERVAL = 1.0


def local_time(timestamp: float) -> str:
    """ISO 8601 local time with its UTC offset, to the second."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec='seconds')


def get_system() -> SystemInfo:
    """Operating system, host name, CPU model and the addresses of this machine."""
    uname = platform.uname()
    return SystemInfo(
        system=uname.system,
        node=uname.node,
        release=uname.release,
        version=uname.version,
        machine=uname.machine,
        processor=uname.processor or None,
        # py-cpuinfo leaves out fields it cannot detect.
        processor_brand=cpuinfo.get_cpu_info().get('brand_raw') or None,
        ip_address=_ip_address(),
        mac_address=':'.join(re.findall('..', '%012x' % uuid.getnode())),
        python_version=platform.python_version(),
    )


def _ip_address() -> Optional[str]:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        # The host name is not in DNS or the hosts file (common on macOS and in containers).
        return None


def get_boot() -> BootInfo:
    """When the machine started and how long it has been running."""
    timestamp = psutil.boot_time()
    return BootInfo(
        timestamp=timestamp,
        time=local_time(timestamp),
        uptime_seconds=max(0.0, time.time() - timestamp),
    )


def get_cpu(interval: float = DEFAULT_INTERVAL) -> CpuInfo:
    """Core counts, frequencies and usage measured over ``interval`` seconds.

    With ``interval=0`` the usage is measured since the previous call instead of waiting.
    """
    freq = _cpu_freq()
    # Start the total measurement now, so it covers the same window as the per-core one.
    psutil.cpu_percent(interval=None)
    per_core = psutil.cpu_percent(interval=interval, percpu=True)
    total = psutil.cpu_percent(interval=None)
    return CpuInfo(
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True),
        freq_current_mhz=freq.current if freq else None,
        # psutil reports 0.0 when it cannot tell the minimum or maximum.
        freq_min_mhz=(freq.min or None) if freq else None,
        freq_max_mhz=(freq.max or None) if freq else None,
        usage_percent=total,
        usage_per_core=list(per_core),
        load_average=_load_average(),
    )


def _cpu_freq() -> Any:
    # psutil has no cpu_freq() on some platforms (e.g. Apple Silicon Macs), and returns None
    # when the OS does not report frequencies (e.g. many ARM machines and virtual machines).
    cpu_freq = getattr(psutil, 'cpu_freq', None)
    if cpu_freq is None:
        return None
    try:
        return cpu_freq()
    except (OSError, NotImplementedError):
        return None


def _load_average() -> Optional[List[float]]:
    # Unix only. psutil emulates it on Windows, but the first readings there are always 0.
    getloadavg = getattr(os, 'getloadavg', None)
    if getloadavg is None:
        return None
    try:
        return [round(value, 2) for value in getloadavg()]
    except OSError:
        return None


def get_memory() -> MemoryInfo:
    """Physical memory in bytes."""
    memory = psutil.virtual_memory()
    return MemoryInfo(
        total=memory.total,
        available=memory.available,
        used=memory.used,
        free=memory.free,
        percent=memory.percent,
    )


def get_swap() -> SwapInfo:
    """Swap (page file) in bytes."""
    swap = psutil.swap_memory()
    return SwapInfo(total=swap.total, used=swap.used, free=swap.free, percent=swap.percent)


def get_disks() -> DiskInfo:
    """Mounted partitions with their usage, and bytes read and written since boot."""
    partitions = []
    for partition in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(partition.mountpoint)
        except OSError:
            # No permission, no media in the drive, or a broken network or FUSE mount.
            continue
        partitions.append(DiskPartition(
            device=partition.device,
            mountpoint=partition.mountpoint,
            fstype=partition.fstype,
            total=usage.total,
            used=usage.used,
            free=usage.free,
            percent=usage.percent,
        ))
    io = psutil.disk_io_counters()
    # No disk statistics are available in some containers.
    return DiskInfo(
        partitions=partitions,
        read_bytes=io.read_bytes if io else None,
        write_bytes=io.write_bytes if io else None,
    )


def _address_family(family: int) -> Optional[str]:
    # Compare the values, not their text: str() of these enums changed in Python 3.11.
    # psutil.AF_LINK is the MAC address family on every OS (AF_PACKET only exists on Linux).
    if family == socket.AF_INET:
        return 'ipv4'
    if family == socket.AF_INET6:
        return 'ipv6'
    if family == psutil.AF_LINK:
        return 'mac'
    return None


def get_network() -> NetworkInfo:
    """Interfaces with their addresses and link state, and bytes sent and received since boot."""
    stats = _interface_stats()
    interfaces = {}
    for name, addresses in psutil.net_if_addrs().items():
        records = []
        for address in addresses:
            family = _address_family(address.family)
            if family is not None:
                records.append(NetworkAddress(family, address.address, address.netmask, address.broadcast))
        link = stats.get(name)
        interfaces[name] = NetworkInterface(
            addresses=records,
            is_up=link.isup if link else None,
            # psutil reports 0 when it cannot tell the speed or MTU.
            speed_mbps=(link.speed or None) if link else None,
            mtu=(link.mtu or None) if link else None,
        )
    io = psutil.net_io_counters()
    return NetworkInfo(
        interfaces=interfaces,
        bytes_sent=io.bytes_sent if io else None,
        bytes_recv=io.bytes_recv if io else None,
    )


def _interface_stats() -> Dict[str, Any]:
    try:
        return psutil.net_if_stats()
    except Exception:  # noqa: BLE001
        # Link state is an extra: a platform quirk here must never hide the addresses.
        return {}
