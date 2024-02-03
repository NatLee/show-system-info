import pytest
from systeminfo.systeminfo import SystemInfo

@pytest.fixture
def cleanup():
    # Cleanup files before and after tests
    yield  # This allows the test to run in between the setup and teardown

def test_systeminfo(cleanup):
    sysinfo = SystemInfo()
    assert sysinfo.system_information() is not None
    assert sysinfo.boot_time() is not None
    assert sysinfo.cpu_info() is not None
    assert sysinfo.memory_info() is not None
    assert sysinfo.swap_info() is not None
    assert sysinfo.network_info() is not None
    assert sysinfo.detail_info() is not None
    assert sysinfo.info() is not None

def test_systeminfo_enum(cleanup):
    sysinfo = SystemInfo()
    assert sysinfo.enum(sysinfo.system_information()) is not None
    assert sysinfo.enum(sysinfo.boot_time()) is not None
    assert sysinfo.enum(sysinfo.cpu_info()) is not None
    assert sysinfo.enum(sysinfo.memory_info()) is not None
    assert sysinfo.enum(sysinfo.swap_info()) is not None
    assert sysinfo.enum(sysinfo.network_info()) is not None
    assert sysinfo.enum(sysinfo.detail_info()) is not None
    assert sysinfo.enum(sysinfo.info()) is not None
