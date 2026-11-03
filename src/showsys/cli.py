"""The ``showsys`` command."""
import argparse
import json
import sys
import traceback
from typing import Any, Callable, List, NamedTuple, Optional, TextIO, Tuple

from . import __version__
from . import collectors, render
from .collectors import collect
from .showsys import ShowSys

ISSUES_URL = 'https://github.com/NatLee/show-system-info/issues'
DEFAULT_TOP = 5


ShowText = Callable[[ShowSys, argparse.Namespace], None]


class View(NamedTuple):
    """One thing ``showsys`` can show: the option that selects it, its sections and its text."""
    option: str
    sections: Tuple[str, ...]
    show_text: ShowText


def _print_method(method: str) -> ShowText:
    """Text of the options from ShowSys 1.0: exactly what they have always printed."""
    def show(sysinfo: ShowSys, args: argparse.Namespace) -> None:
        print(sysinfo.enum(getattr(sysinfo, method)()))
    return show


def _print_record(text: Callable[[Any], str], get: Callable[[], Any]) -> ShowText:
    def show(sysinfo: ShowSys, args: argparse.Namespace) -> None:
        print(text(get()))
    return show


SUMMARY = View('', ('system', 'memory', 'swap'), lambda sysinfo, args: sysinfo.info())

# When several options are given, the first one in this order wins (as in ShowSys 1.0).
VIEWS: Tuple[View, ...] = (
    View('details', ('system', 'boot', 'cpu', 'memory', 'swap', 'network'),
         lambda sysinfo, args: sysinfo.detail_info()),
    View('boot_time', ('boot',), _print_method('boot_time')),
    View('memory', ('memory',), _print_method('memory_info')),
    View('swap', ('swap',), _print_method('swap_info')),
    View('cpu', ('cpu',), _print_method('cpu_info')),
    View('network', ('network',), _print_method('network_info')),
    View('all', collectors.SECTIONS, lambda sysinfo, args: print(render.all_text(
        collectors.gather(collectors.SECTIONS, top=_top(args), sort_by=_sort(args)),
        _sort(args), collectors.nvml_installed()))),
    View('disk', ('disk',), _print_record(render.disk_text, collectors.get_disks)),
    View('sensors', ('sensors',), _print_record(render.sensors_text, collectors.get_sensors)),
    View('top', ('processes',), lambda sysinfo, args: print(render.processes_text(
        collectors.get_processes(_top(args), _sort(args)), _sort(args)))),
    View('gpu', ('gpu',), lambda sysinfo, args: print(render.gpu_text(
        collectors.get_gpus(), collectors.nvml_installed()))),
)


def _top(args: argparse.Namespace) -> int:
    return getattr(args, 'top', None) or DEFAULT_TOP


def _sort(args: argparse.Namespace) -> str:
    return getattr(args, 'sort', None) or 'cpu'


def pick_view(args: argparse.Namespace) -> View:
    for view in VIEWS:
        if getattr(args, view.option, None):
            return view
    return SUMMARY


def _report(error: Exception, out: TextIO) -> None:
    print(f'An unexpected error occurred: {error}', file=out)
    print('Here are the details:', file=out)
    print('==========================', file=out, flush=True)
    traceback.print_exc()
    print('==========================', file=out)
    print('Please report this issue with the full traceback.', file=out)
    print(f'-> {ISSUES_URL}', file=out)


def cli(args: argparse.Namespace) -> None:
    """
    Command-line interface for the ShowSys package.

    :param args: Parsed command-line arguments.
    """
    # getattr: callers that build the Namespace themselves may not set the newer options.
    as_json = getattr(args, 'json', False)
    try:
        view = pick_view(args)
        if as_json:
            print(json.dumps(collect(*view.sections, top=_top(args), sort_by=_sort(args)), indent=2))
        else:
            view.show_text(ShowSys(), args)
    except Exception as e:
        # Keep stdout clean for JSON readers: the report goes to stderr in that mode.
        _report(e, sys.stderr if as_json else sys.stdout)


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise argparse.ArgumentTypeError(f'expected a whole number above 0, got {text!r}')
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='showsys', description='Show system information.')

    sections = parser.add_argument_group(
        'sections', 'Without an option, showsys prints a summary (system, memory and swap). '
                    'Pick one option; with several, the first one in this list wins.')
    sections.add_argument('-d', '--details', action='store_true', help='Show detailed system information.')
    sections.add_argument('-b', '--boot_time', action='store_true', help='Show system boot time.')
    sections.add_argument('-m', '--memory', action='store_true', help='Show memory information.')
    sections.add_argument('-s', '--swap', action='store_true', help='Show swap information.')
    sections.add_argument('-c', '--cpu', action='store_true', help='Show CPU information.')
    sections.add_argument('-n', '--network', action='store_true', help='Show network information.')
    sections.add_argument('-a', '--all', action='store_true',
                          help='Show everything: --details plus disks, sensors, top processes and GPUs.')
    sections.add_argument('--disk', action='store_true',
                          help='Show disk partitions, their usage, and bytes read and written since boot.')
    sections.add_argument('--sensors', action='store_true',
                          help='Show temperatures, fans and battery, where this OS reports them.')
    sections.add_argument('--top', nargs='?', const=DEFAULT_TOP, type=_positive_int, metavar='N',
                          help=f'Show the N busiest processes (default {DEFAULT_TOP}), '
                               f'CPU measured over one second.')
    sections.add_argument('--gpu', action='store_true',
                          help='Show NVIDIA GPUs (needs the extra: pip install "showsys[gpu]").')

    output = parser.add_argument_group('output')
    output.add_argument('--sort', choices=collectors.PROCESS_SORT_KEYS, default='cpu',
                        help='Order --top and --all processes by CPU or memory use (default: cpu).')
    output.add_argument('-j', '--json', action='store_true',
                        help='Print JSON instead of text: plain numbers (bytes, MHz, percent) and null '
                             'for values this OS does not report.')
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """
    Main entry point for the `showsys` command-line interface.

    :param argv: Command-line arguments without the program name. Defaults to ``sys.argv[1:]``.
    """
    args = build_parser().parse_args(argv)
    cli(args)
