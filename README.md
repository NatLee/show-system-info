# Show System Information

[![Test](https://github.com/NatLee/show-system-info/actions/workflows/test.yml/badge.svg)](https://github.com/NatLee/show-system-info/actions/workflows/test.yml)
[![Release](https://github.com/NatLee/show-system-info/actions/workflows/release.yml/badge.svg)](https://github.com/NatLee/show-system-info/actions/workflows/release.yml)

Show System Information is a Python package that provides a simple way to display system information. It is designed to be easy to use and easy to understand. It is also easy to extend and customize.

## Installation

```bash
pip install showsys
```

Visit [ShowSys on PyPI](https://pypi.org/project/ShowSys/) for more details.

ShowSys needs Python 3.7 or newer and works on Linux, Windows and macOS.

## Usage

### As a Library

You can use ShowSys as a library in your Python code. Here is an example.

```python
from showsys import ShowSys
sysinfo = ShowSys()
sysinfo.info()
```

`info()` prints a summary (system, memory and swap) and `detail_info()` prints everything (system, boot time, CPU, memory, swap and network). Both also return the text; pass `show=False` to get the text without printing it.

There are several methods available to display system information. Each one returns a dictionary.

- system_information
- boot_time
- cpu_info
- memory_info
- swap_info
- network_info
- disk_info

Just call the method you want to use. For example, you can use the following code to display CPU information.

```python
from showsys import ShowSys
sysinfo = ShowSys()
print(sysinfo.cpu_info())
```

It will display the following information.

```python
{
    'Physical cores': 12,
    'Total cores': 20,
    'Max Frequency': '2100.00Mhz',
    'Min Frequency': '0.00Mhz',
    'Current Frequency': '2100.00Mhz',
    'CPU Usage Per Core': ['0.0%', '0.0%', '0.0%', '0.0%', '0.0%', '1.6%', '0.0%', '0.0%', '0.0%', '15.4%', '3.1%', '0.0%', '1.6%', '0.0%', '0.0%', '0.0%', '0.0%', '0.0%', '0.0%', '0.0%'],
    'Total CPU Usage': '1.6%'
}
```

Some values are not reported on every machine. ShowSys shows them as `N/A` instead of failing, for example:

- the CPU frequencies on many ARM machines and virtual machines,
- the IP address when the computer's host name cannot be resolved (common on macOS),
- the disk read and write totals in some containers.

### Command Line Interface

ShowSys also provides a command line interface. You can use it to display system information from the command line.

```bash
showsys -d # Display system information details
```

Other options are available.

```bash
showsys    # Summary: system, memory and swap
showsys -b # Boot time (--boot_time)
showsys -m # Memory (--memory)
showsys -s # Swap (--swap)
showsys -c # CPU, including usage per core measured over one second (--cpu)
showsys -n # Network interfaces and their addresses (--network)
```

Use one option at a time. You can use the following command to see all available options.

```bash
showsys -h # Show help
```

## Development

```bash
git clone https://github.com/NatLee/show-system-info.git
cd show-system-info
pip install -e ".[test]"
pytest
```

`tox -e py` also checks that the source distribution contains every tracked file.

