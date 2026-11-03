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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import cpuinfo
import psutil

from .models import (
    Battery,
    BootInfo,
    CpuInfo,
    DiskInfo,
    DiskPartition,
    Fan,
    MemoryInfo,
    NetworkAddress,
    NetworkInfo,
    NetworkInterface,
    ProcessInfo,
    Record,
    SensorsInfo,
    SwapInfo,
    SystemInfo,
    Temperature,
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


def _read_sensor(name: str) -> Any:
    """The result of ``psutil.<name>()``, or None when this OS lacks it or it fails."""
    read = getattr(psutil, name, None)
    if read is None:
        return None
    try:
        return read()
    except Exception:  # noqa: BLE001
        # Sensors are best effort: unusual hardware drivers make psutil raise all sorts of errors.
        return None


def _seconds_left(secsleft: Optional[int]) -> Optional[int]:
    # psutil uses negative values for "unlimited" (charging) and "unknown".
    return int(secsleft) if secsleft is not None and secsleft >= 0 else None


def get_sensors() -> SensorsInfo:
    """Temperatures (Linux, FreeBSD), fans (Linux) and the battery (laptops on every OS)."""
    temperatures = _read_sensor('sensors_temperatures')
    fans = _read_sensor('sensors_fans')
    battery = _read_sensor('sensors_battery')
    return SensorsInfo(
        temperatures=None if temperatures is None else [
            Temperature(sensor=name, label=entry.label or None, current=entry.current,
                        high=entry.high, critical=entry.critical)
            for name, entries in temperatures.items() for entry in entries
        ],
        fans=None if fans is None else [
            Fan(sensor=name, label=entry.label or None, rpm=entry.current)
            for name, entries in fans.items() for entry in entries
        ],
        battery=None if battery is None else Battery(
            percent=round(battery.percent, 1),
            seconds_left=_seconds_left(battery.secsleft),
            power_plugged=battery.power_plugged,
        ),
    )


#: Orders accepted by :func:`get_processes`.
PROCESS_SORT_KEYS: Tuple[str, ...] = ('cpu', 'memory')


class _ProcessSampler:
    """Per-process CPU usage needs two readings: one now and one in :meth:`top`."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self._processes: List[psutil.Process] = []
        for process in psutil.process_iter(['name', 'username']):
            if psutil.WINDOWS and process.pid == 0:
                continue  # "System Idle Process" reports idle time as CPU usage.
            try:
                process.cpu_percent(None)
            except psutil.Error:
                continue  # Gone already, or the OS denies access.
            self._processes.append(process)

    def wait(self, interval: float) -> None:
        """Sleep until ``interval`` seconds have passed since the first reading."""
        remaining = interval - (time.monotonic() - self.started)
        if remaining > 0:
            time.sleep(remaining)

    def top(self, limit: int, sort_by: str) -> List[ProcessInfo]:
        found = []
        for process in self._processes:
            with process.oneshot():
                try:
                    cpu = process.cpu_percent(None)
                except psutil.Error:
                    continue
                try:
                    memory_rss: Optional[int] = process.memory_info().rss
                    memory_percent: Optional[float] = round(process.memory_percent(), 2)
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    memory_rss = memory_percent = None
            found.append(ProcessInfo(
                pid=process.pid,
                name=process.info.get('name') or None,
                username=process.info.get('username') or None,
                cpu_percent=round(cpu, 1),
                memory_percent=memory_percent,
                memory_rss=memory_rss,
            ))
        if sort_by == 'memory':
            found.sort(key=lambda p: p.memory_rss or 0, reverse=True)
        else:
            found.sort(key=lambda p: p.cpu_percent, reverse=True)
        return found[:limit]


def _check_top(limit: int, sort_by: str) -> None:
    if limit < 1:
        raise ValueError('limit must be at least 1')
    if sort_by not in PROCESS_SORT_KEYS:
        raise ValueError(f"unknown sort key {sort_by!r}; choose from {', '.join(PROCESS_SORT_KEYS)}")


def get_processes(limit: int = 5, sort_by: str = 'cpu',
                  interval: float = DEFAULT_INTERVAL) -> List[ProcessInfo]:
    """The ``limit`` busiest processes by ``'cpu'`` or ``'memory'``, CPU measured over ``interval``.

    Processes the OS does not let this user inspect are left out, or listed without memory.
    """
    _check_top(limit, sort_by)
    sampler = _ProcessSampler()
    sampler.wait(interval)
    return sampler.top(limit, sort_by)


#: Section names accepted by :func:`collect`, in the order they are returned.
SECTIONS: Tuple[str, ...] = (
    'system', 'boot', 'cpu', 'memory', 'swap', 'disk', 'network', 'sensors', 'processes')


def _check_sections(sections: Sequence[str]) -> List[str]:
    unknown = [name for name in sections if name not in SECTIONS]
    if unknown:
        raise ValueError(f"unknown section {unknown[0]!r}; choose from {', '.join(SECTIONS)}")
    wanted = set(sections) if sections else set(SECTIONS)
    return [name for name in SECTIONS if name in wanted]


def gather(sections: Sequence[str] = (), interval: float = DEFAULT_INTERVAL,
           top: int = 5, sort_by: str = 'cpu') -> Dict[str, Any]:
    """Like :func:`collect`, but returns the records themselves instead of dicts."""
    wanted = _check_sections(sections)
    sampler = None
    if 'processes' in wanted:
        _check_top(top, sort_by)
        # Start now, so the process measurement overlaps the CPU one instead of adding a second wait.
        sampler = _ProcessSampler()

    def processes() -> List[ProcessInfo]:
        assert sampler is not None
        sampler.wait(interval)
        return sampler.top(top, sort_by)

    getters: Dict[str, Callable[[], Any]] = {
        'system': get_system,
        'boot': get_boot,
        'cpu': lambda: get_cpu(interval),
        'memory': get_memory,
        'swap': get_swap,
        'disk': get_disks,
        'network': get_network,
        'sensors': get_sensors,
        'processes': processes,
    }
    return {name: getters[name]() for name in wanted}


def to_jsonable(value: Any) -> Any:
    """Records become dicts; lists, dicts and plain values pass through."""
    if isinstance(value, Record):
        return value.to_dict()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def collect(*sections: str, interval: float = DEFAULT_INTERVAL,
            top: int = 5, sort_by: str = 'cpu') -> Dict[str, Any]:
    """Collect sections of system information as plain dicts, ready for ``json.dumps``.

    Example::

        data = collect('cpu', 'memory')
        data['memory']['total']        # bytes
        data['cpu']['usage_percent']   # measured over ``interval`` seconds

    Pass no names to get every section (see :data:`SECTIONS`). The result also has a
    ``timestamp`` key with the local time the collection started. ``top`` and ``sort_by``
    apply to the ``processes`` section. Unknown section names raise ``ValueError``.
    """
    started = local_time(time.time())
    records = gather(sections, interval=interval, top=top, sort_by=sort_by)
    result: Dict[str, Any] = {'timestamp': started}
    result.update((name, to_jsonable(record)) for name, record in records.items())
    return result
