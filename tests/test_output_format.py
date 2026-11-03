"""Pin the exact text and return values of ShowSys 1.0.x on a fake machine.

These tests were written against the code before the refactor. They must keep passing:
scripts and users read this output.
"""
import sys

import psutil
import pytest

from showsys import ShowSys
from showsys.cli import main

BORDER = '================='

SYSTEM_LINES = [
    'System: Linux',
    'Node Name: demo-host',
    'Release: 6.8.0',
    'Version: #1 SMP PREEMPT_DYNAMIC',
    'Machine: x86_64',
    'Processor: x86_64',
    'Processor Brand: Example CPU 9000',
    'IP-Address: 192.168.1.10',
    'Mac-Address: aa:bb:cc:dd:ee:ff',
]
BOOT_LINES = ['Boot Time: 2026/1/5 3:4:5']
CPU_LINES = [
    'Physical cores: 4',
    'Total cores: 8',
    'Max Frequency: 3600.00Mhz',
    'Min Frequency: 0.00Mhz',
    'Current Frequency: 2100.00Mhz',
    'CPU Usage Per Core:',
    '1.0%\t2.5%\t0.0%\t10.0%',
    '3.0%\t0.0%\t0.0%\t4.5%',
    'Total CPU Usage: 2.6%',
]
MEMORY_LINES = [
    'Memory Total: 16.00GB',
    'Memory Available: 9.00GB',
    'Memory Used: 6.00GB',
    'Memory Percentage: 43.8%',
]
SWAP_LINES = [
    'Swap Total: 2.00GB',
    'Swap Free: 1.50GB',
    'Swap Used: 512.00MB',
    'Swap Percentage: 25.0%',
]
NETWORK_LINES = [
    'lo:',
    "\t{'IP Address': '127.0.0.1', 'Netmask': '255.0.0.0', 'Broadcast IP': None}",
    "\t{'MAC Address': '00:00:00:00:00:00', 'Netmask': None, 'Broadcast MAC': None}",
    'eth0:',
    "\t{'IP Address': '192.168.1.10', 'Netmask': '255.255.255.0', 'Broadcast IP': '192.168.1.255'}",
    "\t{'MAC Address': 'aa:bb:cc:dd:ee:ff', 'Netmask': None, 'Broadcast MAC': 'ff:ff:ff:ff:ff:ff'}",
    'Total Bytes Sent: 1.50MB',
    'Total Bytes Received: 20.00MB',
]

INFO_TEXT = '\n'.join([BORDER] + SYSTEM_LINES + MEMORY_LINES + SWAP_LINES + [BORDER])
DETAIL_TEXT = '\n'.join([BORDER] + SYSTEM_LINES + BOOT_LINES + CPU_LINES + MEMORY_LINES
                        + SWAP_LINES + NETWORK_LINES + [BORDER])


def _section(lines):
    """What `print(sysinfo.enum(...))` writes: one line per value plus print's own newline."""
    return '\n'.join(lines) + '\n\n'


CLI_OUTPUT = {
    (): INFO_TEXT + '\n',
    ('-d',): DETAIL_TEXT + '\n',
    ('-b',): _section(BOOT_LINES),
    ('-m',): _section(MEMORY_LINES),
    ('-s',): _section(SWAP_LINES),
    ('-c',): _section(CPU_LINES),
    ('-n',): _section(NETWORK_LINES),
    # With several options the first one in this order wins: -d, -b, -m, -s, -c, -n.
    ('-m', '-s'): _section(MEMORY_LINES),
    ('-n', '-c'): _section(CPU_LINES),
    ('-n', '-d'): DETAIL_TEXT + '\n',
}


def _run(monkeypatch, capsys, *flags):
    monkeypatch.setattr(sys, 'argv', ['showsys'] + list(flags))
    main()
    return capsys.readouterr().out


@pytest.mark.parametrize('flags', list(CLI_OUTPUT), ids=lambda f: ' '.join(f) or '(none)')
def test_cli_text_output_is_unchanged(fake_machine, monkeypatch, capsys, flags):
    assert _run(monkeypatch, capsys, *flags) == CLI_OUTPUT[flags]


def test_info_returns_and_prints_the_summary(fake_machine, capsys):
    assert ShowSys().info(show=False) == INFO_TEXT
    assert capsys.readouterr().out == ''
    assert ShowSys().info() == INFO_TEXT
    assert capsys.readouterr().out == INFO_TEXT + '\n'


def test_detail_info_returns_and_prints_everything(fake_machine, capsys):
    assert ShowSys().detail_info(show=False) == DETAIL_TEXT
    assert capsys.readouterr().out == ''
    assert ShowSys().detail_info() == DETAIL_TEXT
    assert capsys.readouterr().out == DETAIL_TEXT + '\n'


def test_an_empty_processor_name_keeps_the_trailing_space(fake_machine):
    fake_machine.uname = fake_machine.uname._replace(processor='')
    assert 'Processor: \n' in ShowSys().info(show=False)


def test_cpu_usage_with_up_to_four_cores_is_one_value_per_line(fake_machine):
    fake_machine.per_core = [5.0, 7.5]
    text = ShowSys().enum(ShowSys().cpu_info())
    assert 'CPU Usage Per Core:\n\t5.0%\n\t7.5%\nTotal CPU Usage: 2.6%\n' in text


def _items(info):
    """Compare dicts including their key order, which decides the printed order."""
    return list(info.items())


def test_system_information_returns_strings(fake_machine):
    assert _items(ShowSys().system_information()) == [
        ('System', 'Linux'),
        ('Node Name', 'demo-host'),
        ('Release', '6.8.0'),
        ('Version', '#1 SMP PREEMPT_DYNAMIC'),
        ('Machine', 'x86_64'),
        ('Processor', 'x86_64'),
        ('Processor Brand', 'Example CPU 9000'),
        ('IP-Address', '192.168.1.10'),
        ('Mac-Address', 'aa:bb:cc:dd:ee:ff'),
    ]


def test_boot_time_returns_the_unpadded_date(fake_machine):
    assert ShowSys().boot_time() == {'Boot Time': '2026/1/5 3:4:5'}


def test_cpu_info_returns_counts_and_formatted_strings(fake_machine):
    assert _items(ShowSys().cpu_info()) == [
        ('Physical cores', 4),
        ('Total cores', 8),
        ('Max Frequency', '3600.00Mhz'),
        ('Min Frequency', '0.00Mhz'),
        ('Current Frequency', '2100.00Mhz'),
        ('CPU Usage Per Core', ['1.0%', '2.5%', '0.0%', '10.0%', '3.0%', '0.0%', '0.0%', '4.5%']),
        ('Total CPU Usage', '2.6%'),
    ]


def test_memory_and_swap_info_return_sizes(fake_machine):
    assert _items(ShowSys().memory_info()) == [
        ('Memory Total', '16.00GB'),
        ('Memory Available', '9.00GB'),
        ('Memory Used', '6.00GB'),
        ('Memory Percentage', '43.8%'),
    ]
    assert _items(ShowSys().swap_info()) == [
        ('Swap Total', '2.00GB'),
        ('Swap Free', '1.50GB'),
        ('Swap Used', '512.00MB'),
        ('Swap Percentage', '25.0%'),
    ]


def test_disk_info_returns_partitions_and_totals(fake_machine):
    info = ShowSys().disk_info()
    assert _items(info) == [
        ('Partitions', [{
            'Device': '/dev/sda1',
            'Mountpoint': '/',
            'File system type': 'ext4',
            'Total Size': '100.00GB',
            'Used': '40.00GB',
            'Free': '60.00GB',
            'Percentage': '40.0%',
        }]),
        ('Total read', '1.00GB'),
        ('Total write', '2.00GB'),
    ]
    assert list(info['Partitions'][0]) == [
        'Device', 'Mountpoint', 'File system type', 'Total Size', 'Used', 'Free', 'Percentage']


def test_network_info_returns_ipv4_and_mac_entries_per_interface(fake_machine):
    assert _items(ShowSys().network_info()) == [
        ('lo', [
            {'IP Address': '127.0.0.1', 'Netmask': '255.0.0.0', 'Broadcast IP': None},
            {'MAC Address': '00:00:00:00:00:00', 'Netmask': None, 'Broadcast MAC': None},
        ]),
        ('eth0', [
            {'IP Address': '192.168.1.10', 'Netmask': '255.255.255.0', 'Broadcast IP': '192.168.1.255'},
            {'MAC Address': 'aa:bb:cc:dd:ee:ff', 'Netmask': None, 'Broadcast MAC': 'ff:ff:ff:ff:ff:ff'},
        ]),
        ('Total Bytes Sent', '1.50MB'),
        ('Total Bytes Received', '20.00MB'),
    ]


@pytest.mark.parametrize('size, text', [
    (0, '0.00B'),
    (1023, '1023.00B'),
    (1024, '1.00KB'),
    (1536, '1.50KB'),
    (5 * 1024 ** 3, '5.00GB'),
    (3 * 1024 ** 5, '3.00PB'),
])
def test_get_size_formats_bytes(size, text):
    assert ShowSys().get_size(size) == text


def test_get_size_takes_a_suffix():
    assert ShowSys().get_size(2048, suffix='B/s') == '2.00KB/s'


def test_enum_formats_lists_dicts_and_values():
    text = ShowSys().enum({
        'Short list': ['a', 'b'],
        'Long list': ['1', '2', '3', '4', '5'],
        'Mapping': {'x': 1, 'y': None},
        'Value': 3.5,
    })
    assert text == ('Short list:\n\ta\n\tb\n'
                    'Long list:\n1\t2\t3\t4\n5\n'
                    'Mapping:\n\tx: 1\n\ty: None\n'
                    'Value: 3.5\n')


def test_unexpected_errors_print_a_report(fake_machine, monkeypatch, capsys):
    def broken():
        raise RuntimeError('boom')
    monkeypatch.setattr(psutil, 'virtual_memory', broken)

    out = _run(monkeypatch, capsys, '-m')

    assert out == ('An unexpected error occurred: boom\n'
                   'Here are the details:\n'
                   '==========================\n'
                   '==========================\n'
                   'Please report this issue with the full traceback.\n'
                   '-> https://github.com/NatLee/show-system-info/issues\n')
