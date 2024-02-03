from typing import Dict, Union
import platform
import re
import socket
import uuid
from datetime import datetime

import psutil
import cpuinfo

class SystemInfo:

    def get_size(self, bytes, suffix="B") -> str:
        factor = 1024
        for unit in ["", "K", "M", "G", "T", "P"]:
            if bytes < factor:
                return f"{bytes:.2f}{unit}{suffix}"
            bytes /= factor

    def system_information(self) -> Dict[str, str]:
        uname = platform.uname()
        return {
            "System": uname.system,
            "Node Name": uname.node,
            "Release": uname.release,
            "Version": uname.version,
            "Machine": uname.machine,
            "Processor": uname.processor,
            "Processor Brand": cpuinfo.get_cpu_info()['brand_raw'],
            "IP-Address": socket.gethostbyname(socket.gethostname()),
            "Mac-Address": ':'.join(re.findall('..', '%012x' % uuid.getnode())),
        }

    def boot_time(self) -> Dict[str, str]:
        boot_time_timestamp = psutil.boot_time()
        bt = datetime.fromtimestamp(boot_time_timestamp)
        return {
            "Boot Time": f"{bt.year}/{bt.month}/{bt.day} {bt.hour}:{bt.minute}:{bt.second}"
        }

    def cpu_info(self) -> Dict[str, Union[str, int, float]]:
        cpufreq = psutil.cpu_freq()
        return {
            "Physical cores": psutil.cpu_count(logical=False),
            "Total cores": psutil.cpu_count(logical=True),
            "Max Frequency": f"{cpufreq.max:.2f}Mhz",
            "Min Frequency": f"{cpufreq.min:.2f}Mhz",
            "Current Frequency": f"{cpufreq.current:.2f}Mhz",
            "CPU Usage Per Core": [f"{percentage}%" for percentage in psutil.cpu_percent(percpu=True, interval=1)],
            "Total CPU Usage": f"{psutil.cpu_percent()}%"
        }

    def memory_info(self) -> Dict[str, Union[str, int, float]]:
        svmem = psutil.virtual_memory()
        return {
            "Memory Total": self.get_size(svmem.total),
            "Memory Available": self.get_size(svmem.available),
            "Memory Used": self.get_size(svmem.used),
            "Memory Percentage": f"{svmem.percent}%"
        }

    def swap_info(self) -> Dict[str, Union[str, int, float]]:
        swap = psutil.swap_memory()
        return {
            "Swap Total": self.get_size(swap.total),
            "Swap Free": self.get_size(swap.free),
            "Swap Used": self.get_size(swap.used),
            "Swap Percentage": f"{swap.percent}%"
        }

    def disk_info(self) -> Dict[str, Union[str, int, float]]:
        partitions = psutil.disk_partitions()
        disk_info = {"Partitions": []}
        for partition in partitions:
            try:
                partition_usage = psutil.disk_usage(partition.mountpoint)
                disk_info["Partitions"].append({
                    "Device": partition.device,
                    "Mountpoint": partition.mountpoint,
                    "File system type": partition.fstype,
                    "Total Size": self.get_size(partition_usage.total),
                    "Used": self.get_size(partition_usage.used),
                    "Free": self.get_size(partition_usage.free),
                    "Percentage": f"{partition_usage.percent}%"
                })
            except PermissionError:
                continue
        disk_io = psutil.disk_io_counters()
        disk_info["Total read"] = self.get_size(disk_io.read_bytes)
        disk_info["Total write"] = self.get_size(disk_io.write_bytes)
        return disk_info

    def network_info(self) -> Dict[str, Union[str, int, float]]:
        if_addrs = psutil.net_if_addrs()
        net_info = {}
        for interface_name, interface_addresses in if_addrs.items():
            addresses = []
            for address in interface_addresses:
                if str(address.family) == 'AddressFamily.AF_INET':
                    addresses.append({
                        "IP Address": address.address,
                        "Netmask": address.netmask,
                        "Broadcast IP": address.broadcast
                    })
                elif str(address.family) == 'AddressFamily.AF_PACKET':
                    addresses.append({
                        "MAC Address": address.address,
                        "Netmask": address.netmask,
                        "Broadcast MAC": address.broadcast
                    })
            net_info[interface_name] = addresses
        net_io = psutil.net_io_counters()
        net_info["Total Bytes Sent"] = self.get_size(net_io.bytes_sent)
        net_info["Total Bytes Received"] = self.get_size(net_io.bytes_recv)
        return net_info

    def enum(self, info: Dict[str, Union[str, int, float]]) -> str:
        """
        Enumerate the information in a readable format.

        :param info: The information to enumerate.
        """
        output_str = ""
        for key, value in info.items():
            if isinstance(value, list):
                output_str += f"{key}:" + "\n"
                if len(value) > 4:
                    # split the list for each 4 items in one column
                    for i in range(0, len(value), 4):
                        output_str += "\t".join(value[i:i+4]) + "\n"
                else:
                    for item in value:
                        output_str += f"\t{item}" + "\n"
            elif isinstance(value, dict):
                output_str += f"{key}:" + "\n"
                for k, v in value.items():
                    output_str += f"\t{k}: {v}" + "\n"
            else:
                output_str += f"{key}: {value}" + "\n"
        return output_str

    def detail_info(self, show: bool = True) -> str:
        output_str = "=================" + "\n"
        output_str += self.enum(self.system_information())
        output_str += self.enum(self.boot_time())
        output_str += self.enum(self.cpu_info())
        output_str += self.enum(self.memory_info())
        output_str += self.enum(self.swap_info())
        output_str += self.enum(self.network_info())
        output_str += "================="

        if show:
            print(output_str)

        return output_str

    def info(self, show: bool = True) -> str:
        output_str = "=================" + "\n"
        output_str += self.enum(self.system_information())
        output_str += self.enum(self.memory_info())
        output_str += self.enum(self.swap_info())
        output_str += "================="

        if show:
            print(output_str)

        return output_str
