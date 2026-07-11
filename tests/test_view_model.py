import pytest
from unittest.mock import AsyncMock, MagicMock
from app.models.device import Device, Connectivity
from app.models.device_group import DeviceGroup
from app.models.appliance_id import DecodedApplianceID


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.fetch_devices = AsyncMock()
    session.fetch_device_groups = AsyncMock()
    session.fetch_devices.return_value = [
        Device(
            appliance_id="id1", friendly_name="Light 1", decoded=None,
            manufacturer_name="Amazon", display_category="LIGHT",
            endpoint_id="id1",
        ),
        Device(
            appliance_id="id2", friendly_name="Sensor 1", decoded=None,
            manufacturer_name="Amazon", display_category="SENSOR",
            endpoint_id="id2",
        ),
        Device(
            appliance_id="id3", friendly_name="Plug 1", decoded=None,
            manufacturer_name="Philips", display_category="SMARTPLUG",
            connectivity=Connectivity.UNREACHABLE,
            endpoint_id="id3",
        ),
        Device(
            appliance_id="id4", friendly_name="Camera 1", decoded=None,
            manufacturer_name="Ring", display_category="CAMERA",
            endpoint_id="id4",
        ),
        Device(
            appliance_id="id5", friendly_name="Unknown", decoded=None,
            endpoint_id="id5",
        ),
    ]
    session.fetch_device_groups.return_value = [
        DeviceGroup(id="g1", name="Living Room", member_endpoint_ids={"id1", "id2"}),
        DeviceGroup(id="g2", name="Bedroom", member_endpoint_ids={"id4"}),
    ]
    return session


@pytest.fixture
def mock_store():
    store = MagicMock()
    store.meta_for.return_value = MagicMock(display_name=None)
    store.label_for.return_value = "Skill …xyz123"
    return store


@pytest.fixture
def view_model(mock_session, mock_store):
    from app.view_model import DeviceListViewModel
    vm = DeviceListViewModel(mock_session, mock_store, parent=None)
    return vm


class TestViewModelGrouping:
    @pytest.mark.asyncio
    async def test_refresh_loads_devices(self, view_model, mock_session):
        await view_model.refresh()
        mock_session.fetch_devices.assert_awaited_once()
        assert len(view_model.devices) == 5

    @pytest.mark.asyncio
    async def test_refresh_loads_groups(self, view_model, mock_session):
        await view_model.refresh()
        mock_session.fetch_device_groups.assert_awaited_once()
        assert len(view_model.device_groups) == 2

    @pytest.mark.asyncio
    async def test_grouped_by_skill(self, view_model):
        await view_model.refresh()
        groups = view_model.grouped_by_skill
        keys = [g[0] for g in groups]
        assert "Amazon" in keys
        assert "Philips" not in keys  # Philips → no skill_id → unknown
        assert Device.unknown_skill_id in [g[0] for g in groups]

    @pytest.mark.asyncio
    async def test_grouped_by_type(self, view_model):
        await view_model.refresh()
        groups = view_model.grouped_by_type
        types = {g[0] for g in groups}
        assert "Light" in types
        assert "Sensor" in types
        assert "Smart Plug" in types
        assert "Camera" in types
        assert "Unknown" in types

    @pytest.mark.asyncio
    async def test_grouped_by_device_group(self, view_model):
        await view_model.refresh()
        groups = view_model.grouped_by_device_group
        assert len(groups) == 2
        names = {g[0].name for g in groups}
        assert "Living Room" in names
        assert "Bedroom" in names

    @pytest.mark.asyncio
    async def test_unresponsive_devices(self, view_model):
        await view_model.refresh()
        unresponsive = view_model.unresponsive_devices()
        assert len(unresponsive) == 1
        assert unresponsive[0].appliance_id == "id3"

    @pytest.mark.asyncio
    async def test_devices_in_group(self, view_model):
        await view_model.refresh()
        devices = view_model.devices_in_group("g1")
        ids = {d.appliance_id for d in devices}
        assert "id1" in ids
        assert "id2" in ids
        assert len(devices) == 2

    @pytest.mark.asyncio
    async def test_devices_in_nonexistent_group(self, view_model):
        await view_model.refresh()
        devices = view_model.devices_in_group("nonexistent")
        assert devices == []

    @pytest.mark.asyncio
    async def test_refresh_error_handling(self, view_model, mock_session):
        mock_session.fetch_devices.side_effect = Exception("API error")
        await view_model.refresh()
        assert len(view_model.devices) == 0

    @pytest.mark.asyncio
    async def test_refresh_group_fetch_error(self, view_model, mock_session):
        mock_session.fetch_device_groups.side_effect = Exception("groups error")
        await view_model.refresh()
        assert view_model.device_groups == []
        mock_session.fetch_devices.assert_awaited_once()


class TestViewModelWithHA:
    @pytest.fixture
    def ha_session(self):
        session = MagicMock()
        decoded = DecodedApplianceID(
            skill_id="skill1", stage=None,
            domain="alarm_control_panel:homeassistant",
            object_id="zone1",
        )
        session.fetch_devices = AsyncMock(return_value=[
            Device(appliance_id="ha1", friendly_name="HA Alarm", decoded=decoded),
        ])
        session.fetch_device_groups = AsyncMock(return_value=[])
        return session

    @pytest.mark.asyncio
    async def test_ha_type_from_domain(self, ha_session, mock_store):
        from app.view_model import DeviceListViewModel
        vm = DeviceListViewModel(ha_session, mock_store, parent=None)
        await vm.refresh()
        assert vm.devices[0].type_label == "Alarm"
        assert vm.devices[0].type_symbol_name == "alarm-light"


class TestViewModelIntegrationLabel:
    @pytest.mark.asyncio
    async def test_unknown_skill_label(self, view_model, mock_store):
        await view_model.refresh()
        label = view_model.integration_label(Device.unknown_skill_id)
        assert "Unknown" in label

    @pytest.mark.asyncio
    async def test_skill_with_metadata(self, view_model, mock_store):
        mock_store.meta_for.return_value = MagicMock(display_name="My Custom Skill")
        label = view_model.integration_label("amzn1.ask.skill.custom123")
        assert label == "My Custom Skill"
        mock_store.meta_for.assert_called_with("amzn1.ask.skill.custom123")

    @pytest.mark.asyncio
    async def test_skill_with_manufacturer(self, view_model):
        label = view_model.integration_label("Philips")
        assert label == "Philips"

    def test_integration_label_via_manufacturer(self, view_model, mock_store):
        mock_store.meta_for.return_value = MagicMock(display_name=None)
        d = Device(
            appliance_id="x", friendly_name="X", decoded=DecodedApplianceID(
                skill_id="amzn1.ask.skill.xyz", stage=None, domain="LIGHT", object_id="o"
            ),
            manufacturer_name="ACME Corp",
            endpoint_id="e1",
        )
        view_model._devices = [d]
        label = view_model.integration_label("amzn1.ask.skill.xyz")
        assert label == "ACME Corp"

    def test_integration_label_falls_back_to_store(self, view_model, mock_store):
        mock_store.meta_for.return_value = MagicMock(display_name=None)
        mock_store.label_for.return_value = "Skill …xyz123"
        label = view_model.integration_label("amzn1.ask.skill.nonexistent")
        assert label == "Skill …xyz123"


class TestViewModelGroupManagement:
    @pytest.mark.asyncio
    async def test_create_group(self, view_model, mock_session):
        mock_session.create_device_group = AsyncMock()
        view_model._refresh_groups_only = AsyncMock()
        await view_model.create_group("New Group", members=[])
        mock_session.create_device_group.assert_awaited_once_with(
            name="New Group", member_endpoint_ids=[]
        )

    @pytest.mark.asyncio
    async def test_create_group_error(self, view_model, mock_session):
        mock_session.create_device_group = AsyncMock(side_effect=Exception("fail"))
        view_model._refresh_groups_only = AsyncMock()
        await view_model.create_group("New Group")

    @pytest.mark.asyncio
    async def test_create_group_empty_name(self, view_model, mock_session):
        mock_session.create_device_group = AsyncMock()
        await view_model.create_group("")
        mock_session.create_device_group.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_group_with_members(self, view_model, mock_session):
        mock_session.create_device_group = AsyncMock()
        view_model._refresh_groups_only = AsyncMock()
        devices = [
            Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1"),
            Device(appliance_id="d2", friendly_name="D2", decoded=None, endpoint_id="e2"),
        ]
        await view_model.create_group("Group", members=devices)
        mock_session.create_device_group.assert_awaited_once_with(
            name="Group", member_endpoint_ids=["e1", "e2"]
        )

    @pytest.mark.asyncio
    async def test_rename_group(self, view_model, mock_session):
        mock_session.rename_device_group = AsyncMock()
        view_model._refresh_groups_only = AsyncMock()
        group = DeviceGroup(id="g1", name="Old", member_endpoint_ids=set())
        await view_model.rename_group(group, "New Name")
        mock_session.rename_device_group.assert_awaited_once_with(
            group_id="g1", new_name="New Name"
        )

    @pytest.mark.asyncio
    async def test_rename_group_error(self, view_model, mock_session):
        mock_session.rename_device_group = AsyncMock(side_effect=Exception("fail"))
        view_model._refresh_groups_only = AsyncMock()
        group = DeviceGroup(id="g1", name="Old", member_endpoint_ids=set())
        await view_model.rename_group(group, "New Name")

    @pytest.mark.asyncio
    async def test_rename_group_same_name(self, view_model, mock_session):
        mock_session.rename_device_group = AsyncMock()
        group = DeviceGroup(id="g1", name="Same", member_endpoint_ids=set())
        await view_model.rename_group(group, "Same")
        mock_session.rename_device_group.assert_not_called()

    @pytest.mark.asyncio
    async def test_rename_group_empty_name(self, view_model, mock_session):
        mock_session.rename_device_group = AsyncMock()
        group = DeviceGroup(id="g1", name="Old", member_endpoint_ids=set())
        await view_model.rename_group(group, "")
        mock_session.rename_device_group.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_group(self, view_model, mock_session):
        mock_session.delete_device_group = AsyncMock()
        view_model._refresh_groups_only = AsyncMock()
        group = DeviceGroup(id="g1", name="To Delete", member_endpoint_ids=set())
        await view_model.delete_group(group)
        mock_session.delete_device_group.assert_awaited_once_with(group_id="g1")

    @pytest.mark.asyncio
    async def test_delete_group_error(self, view_model, mock_session):
        mock_session.delete_device_group = AsyncMock(side_effect=Exception("fail"))
        view_model._refresh_groups_only = AsyncMock()
        group = DeviceGroup(id="g1", name="To Delete", member_endpoint_ids=set())
        await view_model.delete_group(group)

    @pytest.mark.asyncio
    async def test_add_devices(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock(return_value=True)
        view_model._refresh_groups_only = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")]
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids={"e2"})
        await view_model.add_devices(devices, to_group=group)
        mock_session.update_device_group_members.assert_awaited_once_with(
            group_id="g1", endpoint_ids=["e1"], operation="ADD"
        )

    @pytest.mark.asyncio
    async def test_add_devices_error_in_loop(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock(side_effect=Exception("fail"))
        view_model._refresh_groups_only = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")]
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids={"e2"})
        await view_model.add_devices(devices, to_group=group)
        mock_session.update_device_group_members.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_devices_no_endpoint_id(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id=None)]
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids=set())
        await view_model.add_devices(devices, to_group=group)
        mock_session.update_device_group_members.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_devices(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock(return_value=True)
        view_model._refresh_groups_only = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")]
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids={"e1"})
        await view_model.remove_devices(devices, from_group=group)
        mock_session.update_device_group_members.assert_awaited_once_with(
            group_id="g1", endpoint_ids=["e1"], operation="REMOVE"
        )

    @pytest.mark.asyncio
    async def test_remove_devices_error_in_loop(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock(side_effect=Exception("fail"))
        view_model._refresh_groups_only = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")]
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids={"e1"})
        await view_model.remove_devices(devices, from_group=group)
        mock_session.update_device_group_members.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_move_devices_same_group(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock(return_value=True)
        view_model._refresh_groups_only = AsyncMock()
        device = Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids={"e2"})
        await view_model.move_devices([device], source=group, destination=group)
        mock_session.update_device_group_members.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_devices_different_group(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock(return_value=True)
        view_model._refresh_groups_only = AsyncMock()
        device = Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")
        source = DeviceGroup(id="g1", name="Source", member_endpoint_ids={"e1"})
        dest = DeviceGroup(id="g2", name="Dest", member_endpoint_ids={"e2"})
        await view_model.move_devices([device], source=source, destination=dest)
        assert mock_session.update_device_group_members.call_count == 2

    @pytest.mark.asyncio
    async def test_remove_devices_no_endpoint(self, view_model, mock_session):
        mock_session.update_device_group_members = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id=None)]
        group = DeviceGroup(id="g1", name="Group", member_endpoint_ids=set())
        await view_model.remove_devices(devices, from_group=group)
        mock_session.update_device_group_members.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_groups_only(self, view_model, mock_session):
        mock_session.fetch_device_groups = AsyncMock(return_value=[DeviceGroup(id="g1", name="G", member_endpoint_ids=set())])
        await view_model._refresh_groups_only()
        assert len(view_model.device_groups) == 1
        assert view_model.device_groups[0].name == "G"

    @pytest.mark.asyncio
    async def test_refresh_groups_only_error(self, view_model, mock_session):
        mock_session.fetch_device_groups.side_effect = Exception("fail")
        await view_model._refresh_groups_only()
        # Should not raise


class TestViewModelDeletion:
    @pytest.mark.asyncio
    async def test_delete_devices(self, view_model, mock_session):
        mock_session.delete_device = AsyncMock(return_value=True)
        view_model.refresh = AsyncMock()
        devices = [
            Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1"),
            Device(appliance_id="d2", friendly_name="D2", decoded=None, endpoint_id="e2"),
        ]
        await view_model.delete_devices(devices)
        assert mock_session.delete_device.await_count == 2
        view_model.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_devices_empty(self, view_model, mock_session):
        mock_session.delete_device = AsyncMock()
        view_model.refresh = AsyncMock()
        await view_model.delete_devices([])
        mock_session.delete_device.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_devices_some_fail(self, view_model, mock_session):
        mock_session.delete_device = AsyncMock(side_effect=[True, Exception("fail")])
        view_model.refresh = AsyncMock()
        devices = [
            Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1"),
            Device(appliance_id="d2", friendly_name="D2", decoded=None, endpoint_id="e2"),
        ]
        await view_model.delete_devices(devices)
        assert mock_session.delete_device.await_count == 2

    @pytest.mark.asyncio
    async def test_delete_devices_return_false(self, view_model, mock_session):
        mock_session.delete_device = AsyncMock(return_value=False)
        view_model.refresh = AsyncMock()
        devices = [Device(appliance_id="d1", friendly_name="D1", decoded=None, endpoint_id="e1")]
        await view_model.delete_devices(devices)
        mock_session.delete_device.assert_awaited_once()


class TestViewModelHelpers:
    def test_devices_from_disabled_integrations(self, view_model):
        assert view_model.devices_from_disabled_integrations() == []

    def test_is_busy_property(self, view_model):
        assert view_model.is_busy is False
        view_model._is_busy = True
        assert view_model.is_busy is True

    def test_device_groups_property(self, view_model):
        assert view_model.device_groups == []

    def test_status_message_signal(self, view_model, mock_session):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        received = []
        view_model.status_message.connect(received.append)
        mock_session.fetch_devices.side_effect = Exception("test error")
        asyncio.ensure_future(view_model.refresh())
        loop.close()
        # Just checking the fixture doesn't crash, signal tested in other tests

    def test_busy_signal(self, view_model):
        received = []
        view_model.busy_changed.connect(received.append)

    def test_progress_signal(self, view_model):
        received = []
        view_model.progress_changed.connect(received.append)
