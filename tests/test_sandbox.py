from __future__ import annotations

import ipaddress

import pytest

from sandbox import sandbox

OPTIONS = sandbox.options
DENY_LIST = OPTIONS["proxy_config"]["access_control"]["deny_list"]

# Addresses the browser must never reach: loopback, private, link-local/metadata, CGNAT.
BLOCKED_ADDRESSES = [
    "127.0.0.1",
    "10.1.2.3",
    "172.16.5.5",
    "192.168.1.1",
    "169.254.169.254",
    "100.64.0.1",
    "::1",
    "fc00::1",
    "fe80::1",
]


def _networks():
    nets = []
    for entry in DENY_LIST:
        try:
            nets.append(ipaddress.ip_network(entry))
        except ValueError:
            pass  # hostnames such as "localhost"
    return nets


@pytest.mark.parametrize("addr", BLOCKED_ADDRESSES)
def test_internal_address_is_denied(addr):
    ip = ipaddress.ip_address(addr)
    assert any(ip in net for net in _networks() if net.version == ip.version)


def test_localhost_is_denied():
    assert "localhost" in DENY_LIST


@pytest.mark.parametrize("addr", ["8.8.8.8", "93.184.216.34", "2606:4700::1111"])
def test_public_address_is_not_denied(addr):
    ip = ipaddress.ip_address(addr)
    assert not any(ip in net for net in _networks() if net.version == ip.version)


def test_default_timeout_within_cap():
    assert 0 < OPTIONS["default_timeout"] <= 120


@pytest.mark.parametrize("key", ["idle_ttl_seconds", "delete_after_stop_seconds"])
def test_ttls_are_multiples_of_60(key):
    assert OPTIONS[key] > 0 and OPTIONS[key] % 60 == 0
