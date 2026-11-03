"""The original ShowSys interface: each method returns a dict of display strings.

The data comes from :mod:`showsys.collectors` and the formatting from :mod:`showsys.render`.
New code that wants numbers instead of strings can call those modules, or
:func:`showsys.collect`, directly.
"""
from typing import Any, Dict, Mapping

from . import collectors, render


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

    def detail_info(self, show: bool = True) -> str:
        """System, boot time, CPU, memory, swap and network. Prints it unless ``show=False``."""
        output = render.framed(
            self.system_information(),
            self.boot_time(),
            self.cpu_info(),
            self.memory_info(),
            self.swap_info(),
            self.network_info(),
        )
        if show:
            print(output)
        return output

    def info(self, show: bool = True) -> str:
        """System, memory and swap. Prints it unless ``show=False``."""
        output = render.framed(self.system_information(), self.memory_info(), self.swap_info())
        if show:
            print(output)
        return output
