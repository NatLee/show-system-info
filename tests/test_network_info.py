"""network_info() must list IPv4 and MAC addresses on every Python version and OS."""
import socket
from collections import namedtuple

import psutil

from showsys import ShowSys

# Same fields as the named tuples returned by psutil.net_if_addrs().
Address = namedtuple('Address', 'family address netmask broadcast ptp')


def _all_addresses(info):
    return [address for value in info.values() if isinstance(value, list) for address in value]


def test_network_info_lists_ipv4_and_mac_addresses(monkeypatch):
    fake_interfaces = {
        'eth0': [
            Address(socket.AF_INET, '192.168.1.10', '255.255.255.0', '192.168.1.255', None),
            Address(socket.AF_INET6, 'fe80::1', 'ffff:ffff:ffff:ffff::', None, None),
            Address(psutil.AF_LINK, 'aa:bb:cc:dd:ee:ff', None, 'ff:ff:ff:ff:ff:ff', None),
        ],
    }
    monkeypatch.setattr(psutil, 'net_if_addrs', lambda: fake_interfaces)

    info = ShowSys().network_info()

    assert info['eth0'] == [
        {'IP Address': '192.168.1.10', 'Netmask': '255.255.255.0', 'Broadcast IP': '192.168.1.255'},
        {'MAC Address': 'aa:bb:cc:dd:ee:ff', 'Netmask': None, 'Broadcast MAC': 'ff:ff:ff:ff:ff:ff'},
    ]


def test_network_info_shows_the_loopback_address_of_this_machine():
    addresses = _all_addresses(ShowSys().network_info())
    assert any(address.get('IP Address') == '127.0.0.1' for address in addresses)


def test_network_info_shows_mac_addresses_of_this_machine():
    addresses = _all_addresses(ShowSys().network_info())
    assert any('MAC Address' in address for address in addresses)
