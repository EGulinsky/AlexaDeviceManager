import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from app.models.device import Device, Connectivity
from app.models.device_group import DeviceGroup
from app.models.appliance_id import DecodedApplianceID


@pytest.fixture
def sample_device() -> Device:
    return Device(
        appliance_id="id1",
        friendly_name="Light 1",
        decoded=None,
        manufacturer_name="Amazon",
        display_category="LIGHT",
        endpoint_id="id1",
    )


@pytest.fixture
def sample_devices() -> list[Device]:
    decoded = DecodedApplianceID(
        skill_id="amzn1.ask.skill.abc123",
        stage=None,
        domain="LIGHT",
        object_id="device1",
    )
    return [
        Device(
            appliance_id="id1", friendly_name="Light 1",
            decoded=decoded, manufacturer_name="Amazon",
            display_category="LIGHT", endpoint_id="id1",
            connectivity=Connectivity.OK,
        ),
        Device(
            appliance_id="id2", friendly_name="Sensor 1",
            decoded=None, manufacturer_name="Amazon",
            display_category="SENSOR", endpoint_id="id2",
        ),
        Device(
            appliance_id="id3", friendly_name="Plug 1",
            decoded=decoded, manufacturer_name="Philips",
            display_category="SMARTPLUG", endpoint_id="id3",
            connectivity=Connectivity.UNREACHABLE,
        ),
        Device(
            appliance_id="id4", friendly_name="Camera 1",
            decoded=None, manufacturer_name="Ring",
            display_category="CAMERA", endpoint_id="id4",
        ),
        Device(
            appliance_id="id5", friendly_name="Unknown",
            decoded=None, endpoint_id="id5",
        ),
    ]


@pytest.fixture
def sample_groups() -> list[DeviceGroup]:
    return [
        DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={"id1", "id2"}),
        DeviceGroup(id="g2", name="Bedroom", member_endpoint_ids={"id4"}),
    ]


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.meta_for.return_value = MagicMock(display_name=None)
    store.label_for.return_value = "Skill …xyz123"
    return store


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.fetch_devices = AsyncMock()
    session.fetch_device_groups = AsyncMock()
    session.fetch_devices.return_value = [
        Device(appliance_id="id1", friendly_name="Light 1", decoded=None,
               manufacturer_name="Amazon", display_category="LIGHT", endpoint_id="id1"),
        Device(appliance_id="id2", friendly_name="Sensor 1", decoded=None,
               manufacturer_name="Amazon", display_category="SENSOR", endpoint_id="id2"),
        Device(appliance_id="id3", friendly_name="Plug 1", decoded=None,
               manufacturer_name="Philips", display_category="SMARTPLUG",
               connectivity=Connectivity.UNREACHABLE, endpoint_id="id3"),
        Device(appliance_id="id4", friendly_name="Camera 1", decoded=None,
               manufacturer_name="Ring", display_category="CAMERA", endpoint_id="id4"),
        Device(appliance_id="id5", friendly_name="Unknown", decoded=None, endpoint_id="id5"),
    ]
    session.fetch_device_groups.return_value = [
        DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={"id1", "id2"}),
        DeviceGroup(id="g2", name="Bedroom", member_endpoint_ids={"id4"}),
    ]
    return session


@pytest.fixture
def view_model(mock_session, mock_store):
    from app.view_model import DeviceListViewModel
    vm = DeviceListViewModel(mock_session, mock_store, parent=None)
    return vm
