"""The original ShowSys interface: each method returns a dict of display strings.

The data comes from :mod:`showsys.collectors` and the formatting from :mod:`showsys.render`.
New code that wants numbers instead of strings can call those modules, or
:func:`showsys.collect`, directly.
"""
from typing import Any, Callable, Dict, Mapping, Sequence

from . import collectors, render


#: The ShowSys method that returns each section's display dict (names from ShowSys 1.0).
SECTION_METHODS: Dict[str, str] = {
    'system': 'system_information',
    'boot': 'boot_time',
    'cpu': 'cpu_info',
    'memory': 'memory_info',
    'swap': 'swap_info',
    'network': 'network_info',
}


class ShowSys:

    def get_size(self, bytes: float, suffix: str = 'B') -> str:
        """Format a byte count with binary units, e.g. ``1536`` -> ``1.50KB``."""
        return render.size(bytes, suffix)

    def system_information(self) -> Dict[str, str]:
        return render.system_dict(collectors.get_system())

    def boot_time(self) -> Dict[str, str]:
        return render.boot_dict(collectors.get_boot())

    def cpu_info(self) -> Dict[str, Any]:
        """CPU counts, frequencies and usage. Takes one second to measure the usage."""
        return render.cpu_dict(collectors.get_cpu())

    def memory_info(self) -> Dict[str, str]:
        return render.memory_dict(collectors.get_memory())

    def swap_info(self) -> Dict[str, str]:
        return render.swap_dict(collectors.get_swap())

    def disk_info(self) -> Dict[str, Any]:
        return render.disk_dict(collectors.get_disks())

    def network_info(self) -> Dict[str, Any]:
        return render.network_dict(collectors.get_network())

    def enum(self, info: Mapping[str, Any]) -> str:
        """
        Enumerate the information in a readable format.

        :param info: The information to enumerate.
        """
        return render.enum(info)

    def _section(self, name: str) -> Dict[str, Any]:
        """The display dict of one section, e.g. ``_section('memory')`` is ``memory_info()``."""
        method: Callable[[], Dict[str, Any]] = getattr(self, SECTION_METHODS[name])
        return method()

    def _framed(self, sections: Sequence[str]) -> str:
        return render.framed(*(self._section(name) for name in sections))

    def detail_info(self, show: bool = True) -> str:
        """System, boot time, CPU, memory, swap and network. Prints it unless ``show=False``."""
        output = self._framed(render.DETAIL_SECTIONS)
        if show:
            print(output)
        return output

    def info(self, show: bool = True) -> str:
        """System, memory and swap. Prints it unless ``show=False``."""
        output = self._framed(render.SUMMARY_SECTIONS)
        if show:
            print(output)
        return output
