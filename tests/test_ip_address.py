"""The IP address comes from the network interfaces, chosen by the rule in primary_address()."""
import socket

import psutil
import pytest

import showsys
from showsys import collectors

from .fakes import Address, NetStats

# Addresses below are from the documentation ranges (RFC 5737, RFC 3849) or the
# loopback and link-local ranges, so no test depends on a real network.
LAN = '192.168.1.10'      # eth0 of the fake machine
VPN = '10.8.0.6'
APIPA = '169.254.7.7'     # IPv4 link-local
GLOBAL_V6 = '2001:db8::42'


def _iface(*addresses, family=socket.AF_INET):
    return [Address(family, address, None, None, None) for address in addresses]


def test_the_interface_with_the_default_route_wins(fake_machine):
    # The routed interface is listed second: the order of interfaces must not matter.
    fake_machine.interfaces = {'tun0': _iface(VPN), **fake_machine.interfaces}
    assert showsys.get_system().ip_address == LAN
    fake_machine.routes[socket.AF_INET] = VPN
    assert showsys.get_system().ip_address == VPN


def test_asking_the_route_sends_nothing(fake_machine):
    showsys.get_system()
    probes = [s for s in fake_machine.sockets if s.source]
    assert probes, 'the routing table was not asked'
    # A documentation address (RFC 5737), never a real host; FakeSocket fails any send.
    assert probes[0].destination[0].startswith('192.0.2.')


def test_without_a_route_the_first_usable_address_is_used(fake_machine):
    fake_machine.routes[socket.AF_INET] = None
    fake_machine.interfaces = {
        'lo': _iface('127.0.0.1'),
        'eth1': _iface(APIPA),
        'wlan0': _iface(VPN),
        **fake_machine.interfaces,
    }
    assert showsys.get_system().ip_address == VPN


def test_a_routed_address_that_is_not_on_an_interface_is_ignored(fake_machine):
    fake_machine.routes[socket.AF_INET] = '203.0.113.9'
    assert showsys.get_system().ip_address == LAN


def test_interfaces_that_are_down_are_skipped(fake_machine):
    fake_machine.routes[socket.AF_INET] = None
    fake_machine.interfaces = {'wlan0': _iface(VPN), **fake_machine.interfaces}
    fake_machine.interface_stats['wlan0'] = NetStats(isup=False, duplex=0, speed=0, mtu=1500)
    assert showsys.get_system().ip_address == LAN


def test_unknown_link_state_counts_as_up(fake_machine, monkeypatch):
    def broken():
        raise OSError('No such device')
    monkeypatch.setattr(psutil, 'net_if_stats', broken)
    assert showsys.get_system().ip_address == LAN


@pytest.mark.parametrize('addresses', [
    {'lo': _iface('127.0.0.1')},
    {'lo': _iface('127.0.0.1'), 'eth0': _iface(APIPA)},
    {'eth0': _iface('fe80::1%eth0', family=socket.AF_INET6)},
    {},
], ids=['loopback only', 'link-local only', 'IPv6 link-local only', 'no interfaces'])
def test_na_only_when_no_interface_has_a_usable_address(fake_machine, capsys, addresses):
    fake_machine.interfaces = addresses
    assert showsys.get_system().ip_address is None
    assert showsys.ShowSys().system_information()['IP-Address'] == 'N/A'


def test_ipv6_is_used_only_without_a_usable_ipv4_address(fake_machine):
    fake_machine.interfaces = {
        'lo': _iface('127.0.0.1'),
        'eth0': _iface('fe80::1%eth0', GLOBAL_V6, family=socket.AF_INET6),
    }
    assert showsys.get_system().ip_address == GLOBAL_V6
    fake_machine.routes[socket.AF_INET6] = GLOBAL_V6
    assert showsys.get_system().ip_address == GLOBAL_V6


def test_the_address_on_this_machine_is_one_of_its_interface_addresses():
    interfaces = collectors.get_network().interfaces
    address = showsys.get_system().ip_address
    if address is None:
        pytest.skip('this machine has no usable address')
    listed = {a.address for i in interfaces.values() for a in i.addresses}
    assert address in listed
