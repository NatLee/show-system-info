__version__ = "1.0.1"

from .collectors import (
    SECTIONS,
    collect,
    get_boot,
    get_cpu,
    get_disks,
    get_memory,
    get_network,
    get_sensors,
    get_swap,
    get_system,
)
from .showsys import ShowSys
from .cli import main

__all__ = [
    'SECTIONS',
    'ShowSys',
    'collect',
    'get_boot',
    'get_cpu',
    'get_disks',
    'get_memory',
    'get_network',
    'get_sensors',
    'get_swap',
    'get_system',
    'main',
]
