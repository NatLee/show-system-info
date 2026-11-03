"""Live readings for ``showsys --watch``: usage and throughput, every few seconds."""
import time
from typing import Iterator, Optional, Tuple

import psutil

from .collectors import local_time
from .models import Rates

_Totals = Tuple[Optional[int], Optional[int]]


def _clock() -> float:
    return time.monotonic()


def _net_totals() -> _Totals:
    io = psutil.net_io_counters()
    return (io.bytes_sent, io.bytes_recv) if io else (None, None)


def _disk_totals() -> _Totals:
    io = psutil.disk_io_counters()
    return (io.read_bytes, io.write_bytes) if io else (None, None)


def _rate(new: Optional[int], old: Optional[int], seconds: float) -> Optional[float]:
    if new is None or old is None or seconds <= 0:
        return None
    # A counter can go down when an interface or disk disappears; that is not negative traffic.
    return round(max(0, new - old) / seconds, 1)


def watch(interval: float = 1.0, count: Optional[int] = None) -> Iterator[Rates]:
    """Yield a reading every ``interval`` seconds, ``count`` times or until you stop iterating.

    Each reading covers the time since the previous one::

        for rates in showsys.watch(interval=2, count=5):
            print(rates.cpu_percent, rates.net_recv_per_sec)
    """
    if interval <= 0:
        raise ValueError('interval must be above 0')
    if count is not None and count < 1:
        raise ValueError('count must be at least 1')
    psutil.cpu_percent(interval=None)  # Start the first CPU measurement now.
    net, disk, last = _net_totals(), _disk_totals(), _clock()
    taken = 0
    while count is None or taken < count:
        # Sleep until the next tick, so slow readings do not make the pace drift.
        time.sleep(max(0.0, last + interval - _clock()))
        now = _clock()
        new_net, new_disk = _net_totals(), _disk_totals()
        seconds = now - last
        yield Rates(
            timestamp=local_time(time.time()),
            interval_seconds=round(seconds, 3),
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=psutil.virtual_memory().percent,
            swap_percent=psutil.swap_memory().percent,
            net_sent_per_sec=_rate(new_net[0], net[0], seconds),
            net_recv_per_sec=_rate(new_net[1], net[1], seconds),
            disk_read_per_sec=_rate(new_disk[0], disk[0], seconds),
            disk_write_per_sec=_rate(new_disk[1], disk[1], seconds),
        )
        net, disk, last = new_net, new_disk, now
        taken += 1
