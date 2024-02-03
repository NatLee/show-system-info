import traceback
import argparse

from . import __version__
from .systeminfo import SystemInfo

def cli(args):
    """
    Command-line interface for the systeminfo package.

    :param args: Parsed command-line arguments.
    """
    sysinfo = SystemInfo()

    try:
        if args.details:
            sysinfo.detail_info()
        elif args.boot_time:
            sysinfo.enum(sysinfo.boot_time())
        elif args.memory:
            sysinfo.enum(sysinfo.memory_info())
        elif args.swap:
            sysinfo.enum(sysinfo.swap_info())
        elif args.cpu:
            sysinfo.enum(sysinfo.cpu_info())
        elif args.network:
            sysinfo.enum(sysinfo.network_info())
        else:
            sysinfo.info()

    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        print('Here are the details:')
        print('==========================')
        traceback.print_exc()
        print('==========================')
        print('Please report this issue with the full traceback.')
        print('-> https://github.com/NatLee/system-info/issues')

def main():
    """
    Main entry point for the `systeminfo` command-line interface.
    """
    register_heif_opener()

    print(f'System Info v{__version__}')

    parser = argparse.ArgumentParser(description="Show system information.")
    parser.add_argument("-d", "--details", action="store_true", help="Show detailed system information.")
    parser.add_argument("-b", "--boot_time", action="store_true", help="Show system boot time.")
    parser.add_argument("-m", "--memory", action="store_true", help="Show memory information.")
    parser.add_argument("-s", "--swap", action="store_true", help="Show swap information.")
    parser.add_argument("-c", "--cpu", action="store_true", help="Show CPU information.")
    parser.add_argument("-n", "--network", action="store_true", help="Show network information.")

    args = parser.parse_args()
    cli(args)
