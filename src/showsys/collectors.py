"""Read system information into the records defined in :mod:`showsys.models`.

These functions only collect data; :mod:`showsys.render` turns it into text.
Every value the operating system does not report becomes ``None``.

System calls go through the module objects (``psutil.cpu_freq()``, not an imported name),
so tests can replace them with ``monkeypatch.setattr(psutil, ...)``.
"""
import ipaddress
import os
import platform
import re
import socket
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

import cpuinfo
import psutil

from .models import (
    Battery,
    BootInfo,
    CpuInfo,
    DiskInfo,
    DiskPartition,
    Fan,
    GpuInfo,
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

#: How many processes `get_processes()` and `showsys --top` list unless told otherwise.
DEFAULT_TOP = 5

#: The optional extra that installs NVIDIA's NVML bindings, as named in setup.py.
GPU_EXTRA = 'showsys[gpu]'


# What "this system cannot tell" looks like: a facility the OS lacks (NotImplementedError),
# a failed or refused system call (OSError), or psutil's own errors such as AccessDenied.
# Anything else is a bug and must reach the error report instead of turning into N/A.
_UNAVAILABLE = (OSError, NotImplementedError, psutil.Error)


def _optional(module: Any, name: str) -> Any:
    """``module.<name>()``, or None when this platform lacks the function or cannot answer."""
    read = getattr(module, name, None)
    if read is None:
        return None
    try:
        return read()
    except _UNAVAILABLE:
        return None


def local_time(timestamp: float) -> str:
    """ISO 8601 local time with its UTC offset, to the second."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone().isoformat(timespec='seconds')


def get_system() -> SystemInfo:
    """Operating system, host name, CPU model and the addresses of this machine.

    ``ip_address`` follows the rule in :func:`primary_address`.
    """
    uname = platform.uname()
    return SystemInfo(
        system=uname.system,
        node=uname.node,
        release=uname.release,
        version=uname.version,
        machine=uname.machine,
        processor=uname.processor or None,
        processor_brand=_processor_brand(),
        ip_address=primary_address(get_network().interfaces),
        mac_address=':'.join(re.findall('..', '%012x' % uuid.getnode())),
        python_version=platform.python_version(),
    )


# Public places where an OS names the CPU. These are the same places py-cpuinfo reads first,
# but py-cpuinfo's get_cpu_info() also starts two Python processes (about one second).
_PROC_CPUINFO = '/proc/cpuinfo'                                        # Linux
_REGISTRY_CPU_KEY = r'HARDWARE\DESCRIPTION\System\CentralProcessor\0'  # Windows
_SYSCTL_CPU_NAME = ('sysctl', '-n', 'machdep.cpu.brand_string')        # macOS
_COMMAND_TIMEOUT = 5.0  # seconds; sysctl answers at once, this only guards against a hang


def _cpu_name_from_proc_cpuinfo() -> Optional[str]:
    """The first ``model name`` in /proc/cpuinfo; None without the file or the field."""
    try:
        with open(_PROC_CPUINFO, encoding='utf-8', errors='replace') as cpuinfo_file:
            for line in cpuinfo_file:
                key, separator, value = line.partition(':')
                if separator and key.strip() == 'model name':
                    return value.strip() or None
    except OSError:
        return None
    return None


def _cpu_name_from_registry() -> Optional[str]:
    """``ProcessorNameString`` of the first CPU in the Windows registry; None elsewhere."""
    try:
        import winreg
    except ImportError:
        return None
    registry: Any = winreg  # The type stubs only define winreg's contents on Windows.
    try:
        with registry.OpenKey(registry.HKEY_LOCAL_MACHINE, _REGISTRY_CPU_KEY) as key:
            value = registry.QueryValueEx(key, 'ProcessorNameString')[0]
    except OSError:
        return None
    return str(value).strip() or None


def _cpu_name_from_sysctl() -> Optional[str]:
    """``sysctl -n machdep.cpu.brand_string`` (macOS); None where sysctl lacks that name."""
    try:
        result = subprocess.run(_SYSCTL_CPU_NAME, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                universal_newlines=True, timeout=_COMMAND_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout.strip() or None) if result.returncode == 0 else None


#: Tried in order; each source returns None on systems where it does not apply.
_CPU_NAME_SOURCES: Tuple[Callable[[], Optional[str]], ...] = (
    _cpu_name_from_proc_cpuinfo,
    _cpu_name_from_registry,
    _cpu_name_from_sysctl,
)


def _processor_brand() -> Optional[str]:
    for source in _CPU_NAME_SOURCES:
        name = source()
        if name:
            return name
    # None of the quick sources knows (e.g. ARM boards without "model name"): ask py-cpuinfo,
    # which also probes the CPU itself. It leaves out fields it cannot detect.
    return cpuinfo.get_cpu_info().get('brand_raw') or None


# Where to "send" a UDP packet when asking the routing table which source address outbound
# traffic uses, per address family, in order of preference. These are documentation addresses
# (RFC 5737, RFC 3849) that never belong to a real host, and connect() on a UDP socket only looks
# up the route: no packet leaves the machine. Any port works; 9 is the "discard" service.
_ROUTE_PROBES: Dict[str, Tuple[int, Tuple[str, int]]] = {
    'ipv4': (socket.AF_INET, ('192.0.2.1', 9)),
    'ipv6': (socket.AF_INET6, ('2001:db8::1', 9)),
}


def _outbound_address(family: int, destination: Tuple[str, int]) -> Optional[str]:
    """The source address the routing table picks for ``destination``, or None without a route."""
    try:
        with socket.socket(family, socket.SOCK_DGRAM) as probe:
            probe.connect(destination)
            return str(probe.getsockname()[0])
    except OSError:
        return None


def _ip(address: str) -> Any:
    # psutil adds the scope to IPv6 link-local addresses ("fe80::1%eth0"); ipaddress on
    # Python < 3.9 does not accept it, and the scope is not part of the address itself.
    return ipaddress.ip_address(address.split('%', 1)[0])


def _reachable(address: str) -> bool:
    """Whether another machine could reach this address: not loopback, link-local or unspecified."""
    ip = _ip(address)
    return not (ip.is_loopback or ip.is_link_local or ip.is_unspecified)


def primary_address(interfaces: Mapping[str, NetworkInterface]) -> Optional[str]:
    """The IP address of this machine that other machines would see, read from its interfaces.

    The rule, for IPv4 first and IPv6 only when there is no usable IPv4 address:

    1. Candidates are the addresses of interfaces that are up (or whose state is unknown),
       leaving out loopback, link-local and unspecified addresses.
    2. Of those, the one the routing table uses for outbound traffic (the default route) wins.
    3. Without a default route, the first candidate in the order the OS lists its interfaces.

    ``None`` only when no interface has a usable address. No DNS lookup is involved.
    """
    for family, (socket_family, destination) in _ROUTE_PROBES.items():
        candidates = [
            address.address
            for interface in interfaces.values() if interface.is_up is not False
            for address in interface.addresses
            if address.family == family and _reachable(address.address)
        ]
        if not candidates:
            continue
        routed = _outbound_address(socket_family, destination)
        if routed is not None:
            for candidate in candidates:
                if _ip(candidate) == _ip(routed):
                    return candidate
        return candidates[0]
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
    # psutil has no cpu_freq() on some platforms (e.g. Apple Silicon Macs), and returns None
    # when the OS does not report frequencies (e.g. many ARM machines and virtual machines).
    freq = _optional(psutil, 'cpu_freq')
    # Start the total measurement now, so it covers the same window as the per-core one.
    psutil.cpu_percent(interval=None)
    per_core = psutil.cpu_percent(interval=interval, percpu=True)
    total = psutil.cpu_percent(interval=None)
    return CpuInfo(
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True),
        freq_current_mhz=_mhz(freq.current) if freq else None,
        # psutil reports 0.0 when it cannot tell the minimum or maximum.
        freq_min_mhz=_mhz(freq.min or None) if freq else None,
        freq_max_mhz=_mhz(freq.max or None) if freq else None,
        usage_percent=total,
        usage_per_core=list(per_core),
        load_average=_load_average(),
    )


def _mhz(value: Optional[float]) -> Optional[float]:
    # psutil's readings carry float noise such as 4291.815000000001; the text shows two decimals.
    return None if value is None else round(value, 2)


def _load_average() -> Optional[List[float]]:
    # Unix only. psutil emulates it on Windows, but the first readings there are always 0.
    values = _optional(os, 'getloadavg')
    return None if values is None else [round(value, 2) for value in values]


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
    read_bytes, write_bytes = disk_io_totals()
    return DiskInfo(partitions=partitions, read_bytes=read_bytes, write_bytes=write_bytes)


def disk_io_totals() -> Tuple[Optional[int], Optional[int]]:
    """Bytes read and written since boot over all disks; None in containers without statistics."""
    io = _optional(psutil, 'disk_io_counters')
    return (io.read_bytes, io.write_bytes) if io else (None, None)


def net_io_totals() -> Tuple[Optional[int], Optional[int]]:
    """Bytes sent and received since boot over all interfaces; None without statistics."""
    io = _optional(psutil, 'net_io_counters')
    return (io.bytes_sent, io.bytes_recv) if io else (None, None)


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
    # Link state is an extra: when the OS cannot tell, the addresses are still listed.
    stats: Dict[str, Any] = _optional(psutil, 'net_if_stats') or {}
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
    bytes_sent, bytes_recv = net_io_totals()
    return NetworkInfo(interfaces=interfaces, bytes_sent=bytes_sent, bytes_recv=bytes_recv)




def _seconds_left(secsleft: Optional[int]) -> Optional[int]:
    # psutil uses negative values for "unlimited" (charging) and "unknown".
    return int(secsleft) if secsleft is not None and secsleft >= 0 else None


def get_sensors() -> SensorsInfo:
    """Temperatures (Linux, FreeBSD), fans (Linux) and the battery (laptops on every OS)."""
    temperatures = _optional(psutil, 'sensors_temperatures')
    fans = _optional(psutil, 'sensors_fans')
    battery = _optional(psutil, 'sensors_battery')
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


def _import_nvml() -> Any:
    try:
        import pynvml  # From the optional nvidia-ml-py package, see GPU_EXTRA.
    except ImportError:
        return None
    return pynvml


def nvml_installed() -> bool:
    """Whether the optional NVIDIA library (:data:`GPU_EXTRA`) is installed."""
    return _import_nvml() is not None


def _text(value: Any) -> str:
    # Old nvidia-ml-py versions return bytes.
    return value.decode() if isinstance(value, bytes) else str(value)


def get_gpus() -> Optional[List[GpuInfo]]:
    """NVIDIA GPUs, through the optional :data:`GPU_EXTRA`.

    ``None`` when the extra is not installed or no NVIDIA driver is loaded;
    a value a GPU does not support (e.g. power on some laptops) is ``None``.
    """
    nvml = _import_nvml()
    if nvml is None:
        return None
    try:
        nvml.nvmlInit()
    except nvml.NVMLError:
        return None

    def ask(query: Callable[..., Any], *args: Any) -> Any:
        try:
            return query(*args)
        except nvml.NVMLError:
            return None

    try:
        driver = ask(nvml.nvmlSystemGetDriverVersion)
        gpus = []
        for index in range(nvml.nvmlDeviceGetCount()):
            handle = nvml.nvmlDeviceGetHandleByIndex(index)
            memory = ask(nvml.nvmlDeviceGetMemoryInfo, handle)
            usage = ask(nvml.nvmlDeviceGetUtilizationRates, handle)
            temperature = ask(nvml.nvmlDeviceGetTemperature, handle, nvml.NVML_TEMPERATURE_GPU)
            milliwatts = ask(nvml.nvmlDeviceGetPowerUsage, handle)
            gpus.append(GpuInfo(
                index=index,
                name=_text(nvml.nvmlDeviceGetName(handle)),
                driver_version=None if driver is None else _text(driver),
                memory_total=memory.total if memory else None,
                memory_used=memory.used if memory else None,
                memory_free=memory.free if memory else None,
                utilization_percent=float(usage.gpu) if usage else None,
                temperature_c=None if temperature is None else float(temperature),
                power_watts=None if milliwatts is None else milliwatts / 1000,
            ))
        return gpus
    except nvml.NVMLError:
        return None
    finally:
        ask(nvml.nvmlShutdown)


class ProcessOrder(NamedTuple):
    """One way to rank processes: a name for people and the value to rank by, biggest first."""
    label: str
    key: Callable[[ProcessInfo], float]


#: Orders accepted by :func:`get_processes` and ``--sort``; the first one is the default.
PROCESS_ORDERS: Dict[str, ProcessOrder] = {
    'cpu': ProcessOrder('CPU', lambda p: p.cpu_percent),
    # Processes the OS hides the memory of rank last.
    'memory': ProcessOrder('memory', lambda p: p.memory_rss or 0),
}
PROCESS_SORT_KEYS: Tuple[str, ...] = tuple(PROCESS_ORDERS)
DEFAULT_SORT = PROCESS_SORT_KEYS[0]


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
        found.sort(key=PROCESS_ORDERS[sort_by].key, reverse=True)
        return found[:limit]


def _check_top(limit: int, sort_by: str) -> None:
    if limit < 1:
        raise ValueError('limit must be at least 1')
    if sort_by not in PROCESS_SORT_KEYS:
        raise ValueError(f"unknown sort key {sort_by!r}; choose from {', '.join(PROCESS_SORT_KEYS)}")


def get_processes(limit: int = DEFAULT_TOP, sort_by: str = DEFAULT_SORT,
                  interval: float = DEFAULT_INTERVAL) -> List[ProcessInfo]:
    """The ``limit`` busiest processes, ranked by one of :data:`PROCESS_ORDERS`.

    CPU use is measured over ``interval`` seconds.

    Processes the OS does not let this user inspect are left out, or listed without memory.
    """
    _check_top(limit, sort_by)
    sampler = _ProcessSampler()
    sampler.wait(interval)
    return sampler.top(limit, sort_by)


#: Section names accepted by :func:`collect`, in the order they are returned.
SECTIONS: Tuple[str, ...] = (
    'system', 'boot', 'cpu', 'memory', 'swap', 'network', 'disk', 'sensors', 'processes', 'gpu')


def _check_sections(sections: Sequence[str]) -> List[str]:
    unknown = [name for name in sections if name not in SECTIONS]
    if unknown:
        raise ValueError(f"unknown section {unknown[0]!r}; choose from {', '.join(SECTIONS)}")
    wanted = set(sections) if sections else set(SECTIONS)
    return [name for name in SECTIONS if name in wanted]


def gather(sections: Sequence[str] = (), interval: float = DEFAULT_INTERVAL,
           top: int = DEFAULT_TOP, sort_by: str = DEFAULT_SORT) -> Dict[str, Any]:
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
        'gpu': get_gpus,
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
            top: int = DEFAULT_TOP, sort_by: str = DEFAULT_SORT) -> Dict[str, Any]:
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
