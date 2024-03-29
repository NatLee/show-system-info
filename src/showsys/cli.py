import traceback
import argparse

from . import __version__
from .showsys import ShowSys

def cli(args):
    """
    Command-line interface for the ShowSys package.

    :param args: Parsed command-line arguments.
    """
    sysinfo = ShowSys()

    try:
        if args.details:
            sysinfo.detail_info()
        elif args.boot_time:
            print(sysinfo.enum(sysinfo.boot_time()))
        elif args.memory:
            print(sysinfo.enum(sysinfo.memory_info()))
        elif args.swap:
            print(sysinfo.enum(sysinfo.swap_info()))
        elif args.cpu:
            print(sysinfo.enum(sysinfo.cpu_info()))
        elif args.network:
            print(sysinfo.enum(sysinfo.network_info()))
        else:
            sysinfo.info()

    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        print('Here are the details:')
        print('==========================')
        traceback.print_exc()
        print('==========================')
        print('Please report this issue with the full traceback.')
        print('-> https://github.com/NatLee/show-system-info/issues')

def main():
    """
    Main entry point for the `showsys` command-line interface.
    """
    parser = argparse.ArgumentParser(description="Show system information.")
    parser.add_argument("-d", "--details", action="store_true", help="Show detailed system information.")
    parser.add_argument("-b", "--boot_time", action="store_true", help="Show system boot time.")
    parser.add_argument("-m", "--memory", action="store_true", help="Show memory information.")
    parser.add_argument("-s", "--swap", action="store_true", help="Show swap information.")
    parser.add_argument("-c", "--cpu", action="store_true", help="Show CPU information.")
    parser.add_argument("-n", "--network", action="store_true", help="Show network information.")

    args = parser.parse_args()
    cli(args)
