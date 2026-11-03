"""Typed records for the information showsys collects.

Every record is a dataclass whose fields are plain JSON types. Units are part of the
contract: sizes are bytes, frequencies are MHz and percentages go from 0 to 100.
A field is ``None`` when the operating system does not report that value.
"""
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Record:
    """Base class for every record."""

    def to_dict(self) -> Dict[str, Any]:
        """Return the record as a dict that ``json.dumps`` accepts."""
        return asdict(self)


@dataclass
class SystemInfo(Record):
    system: str
    node: str
    release: str
    version: str
    machine: str
    processor: Optional[str]
    processor_brand: Optional[str]
    ip_address: Optional[str]
    mac_address: str
    python_version: str


@dataclass
class BootInfo(Record):
    timestamp: float
    """Seconds since the Unix epoch."""
    time: str
    """Local time in ISO 8601, for example ``2026-01-05T03:04:05+08:00``."""
    uptime_seconds: float


@dataclass
class CpuInfo(Record):
    physical_cores: Optional[int]
    logical_cores: Optional[int]
    freq_current_mhz: Optional[float]
    freq_min_mhz: Optional[float]
    freq_max_mhz: Optional[float]
    usage_percent: float
    usage_per_core: List[float]
    load_average: Optional[List[float]]
    """1, 5 and 15 minute load averages. ``None`` on Windows."""


@dataclass
class MemoryInfo(Record):
    total: int
    available: int
    used: int
    free: int
    percent: float


@dataclass
class SwapInfo(Record):
    total: int
    used: int
    free: int
    percent: float


@dataclass
class DiskPartition(Record):
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class DiskInfo(Record):
    partitions: List[DiskPartition]
    read_bytes: Optional[int]
    """Bytes read since boot, over all disks."""
    write_bytes: Optional[int]


@dataclass
class NetworkAddress(Record):
    family: str
    """``"ipv4"``, ``"ipv6"`` or ``"mac"``."""
    address: str
    netmask: Optional[str]
    broadcast: Optional[str]


@dataclass
class NetworkInterface(Record):
    addresses: List[NetworkAddress]
    is_up: Optional[bool]
    speed_mbps: Optional[int]
    mtu: Optional[int]


@dataclass
class NetworkInfo(Record):
    interfaces: Dict[str, NetworkInterface]
    bytes_sent: Optional[int]
    """Bytes sent since boot, over all interfaces."""
    bytes_recv: Optional[int]


@dataclass
class Temperature(Record):
    sensor: str
    """The chip or driver, for example ``coretemp``."""
    label: Optional[str]
    current: float
    """Degrees Celsius, like ``high`` and ``critical``."""
    high: Optional[float]
    critical: Optional[float]


@dataclass
class Fan(Record):
    sensor: str
    label: Optional[str]
    rpm: int


@dataclass
class Battery(Record):
    percent: float
    seconds_left: Optional[int]
    """``None`` while charging or when the OS cannot estimate it."""
    power_plugged: Optional[bool]


@dataclass
class SensorsInfo(Record):
    temperatures: Optional[List[Temperature]]
    """``None`` when this OS gives no access to temperatures (Windows, macOS)."""
    fans: Optional[List[Fan]]
    """``None`` when this OS gives no access to fans (everything but Linux)."""
    battery: Optional[Battery]
    """``None`` when there is no battery."""


@dataclass
class ProcessInfo(Record):
    pid: int
    name: Optional[str]
    username: Optional[str]
    cpu_percent: float
    """Share of one core over the measurement window: above 100 for busy multi-threaded programs."""
    memory_percent: Optional[float]
    memory_rss: Optional[int]
    """Resident memory in bytes. ``None`` when the OS denies access to this process."""


@dataclass
class GpuInfo(Record):
    index: int
    name: str
    driver_version: Optional[str]
    memory_total: Optional[int]
    memory_used: Optional[int]
    memory_free: Optional[int]
    utilization_percent: Optional[float]
    temperature_c: Optional[float]
    power_watts: Optional[float]


@dataclass
class Rates(Record):
    """One reading of :func:`showsys.watch`; throughput is in bytes per second."""
    timestamp: str
    """Local time of the reading, ISO 8601."""
    interval_seconds: float
    """Time since the previous reading, which every value here covers."""
    cpu_percent: float
    memory_percent: float
    swap_percent: float
    net_sent_per_sec: Optional[float]
    net_recv_per_sec: Optional[float]
    disk_read_per_sec: Optional[float]
    disk_write_per_sec: Optional[float]
