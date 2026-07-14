from __future__ import annotations
import asyncio
from typing import Callable
from PySide6.QtCore import QObject, Signal

from .session import AlexaSession
from .store import IntegrationStore
from .models.device import Device, Connectivity
from .models.device_group import DeviceGroup


class DeviceListViewModel(QObject):
    devices_changed = Signal()
    groups_changed = Signal()
    busy_changed = Signal(bool)
    status_message = Signal(str)
    progress_changed = Signal(int, int)

    def __init__(self, session: AlexaSession, store: IntegrationStore, parent: QObject | None = None):
        super().__init__(parent)
        self.session = session
        self.store = store
        self._devices: list[Device] = []
        self._device_groups: list[DeviceGroup] = []
        self._is_busy = False
        self._on_status: Callable[[str], None] | None = None

    @property
    def devices(self) -> list[Device]:
        return self._devices

    @property
    def device_groups(self) -> list[DeviceGroup]:
        return self._device_groups

    @property
    def is_busy(self) -> bool:
        return self._is_busy

    async def refresh(self) -> None:
        self._is_busy = True
        self.busy_changed.emit(True)
        try:
            self._devices = await self.session.fetch_devices()
            try:
                self._device_groups = await self.session.fetch_device_groups()
            except Exception:
                self._device_groups = []
            self.devices_changed.emit()
            self.groups_changed.emit()
            self.status_message.emit(f"{len(self._devices)} devices loaded.")
        except Exception as e:
            self.status_message.emit(f"Error loading: {e}")
        finally:
            self._is_busy = False
            self.busy_changed.emit(False)

    # --- Grouping ---

    @property
    def grouped_by_skill(self) -> list[tuple[str, list[Device]]]:
        groups: dict[str, list[Device]] = {}
        for d in self._devices:
            key = d.integration_group_key
            groups.setdefault(key, []).append(d)
        return sorted(groups.items(), key=lambda x: self.integration_label(x[0]))

    @property
    def grouped_by_type(self) -> list[tuple[str, list[Device]]]:
        groups: dict[str, list[Device]] = {}
        for d in self._devices:
            key = d.type_label
            groups.setdefault(key, []).append(d)
        return sorted(groups.items(), key=lambda x: x[0])

    @property
    def grouped_by_device_group(self) -> list[tuple[DeviceGroup, list[Device]]]:
        result: list[tuple[DeviceGroup, list[Device]]] = []
        for g in self._device_groups:
            members = [d for d in self._devices if d.endpoint_id and d.endpoint_id in g.member_endpoint_ids]
            result.append((g, members))
        result.sort(key=lambda x: x[0].name)
        return result

    def devices_in_group(self, group_id: str) -> list[Device]:
        group = next((g for g in self._device_groups if g.id == group_id), None)
        if not group:
            return []
        return [d for d in self._devices if d.endpoint_id and d.endpoint_id in group.member_endpoint_ids]

    def integration_label(self, key: str) -> str:
        if key == Device.unknown_skill_id:
            return "Unknown (no skill detected)"
        meta = self.store.meta_for(key)
        if meta.display_name:
            return meta.display_name
        if not key.startswith("amzn1.ask.skill."):
            return key
        device = next((d for d in self._devices if d.skill_id == key and d.manufacturer_name), None)
        if device and device.manufacturer_name:
            return device.manufacturer_name
        return self.store.label_for(key)

    # --- Batch filters ---

    def unresponsive_devices(self) -> list[Device]:
        return [d for d in self._devices if d.connectivity == Connectivity.UNREACHABLE]

    # --- Group management ---

    async def create_group(self, name: str, members: list[Device] | None = None) -> None:
        if not name:
            return
        endpoint_ids = [d.endpoint_id for d in (members or []) if d.endpoint_id]
        try:
            await self.session.create_device_group(name=name, member_endpoint_ids=endpoint_ids)
            self.status_message.emit(f"Group '{name}' created.")
        except Exception as e:
            self.status_message.emit(f"Error creating group: {e}")
        await self._refresh_groups_only()

    async def rename_group(self, group: DeviceGroup, new_name: str) -> None:
        if not new_name or new_name == group.name:
            return
        try:
            await self.session.rename_device_group(group_id=group.id, new_name=new_name)
            self.status_message.emit(f'Group renamed to "{new_name}".')
        except Exception as e:
            self.status_message.emit(f"Error renaming: {e}")
        await self._refresh_groups_only()

    async def delete_group(self, group: DeviceGroup) -> None:
        try:
            await self.session.delete_device_group(group_id=group.id)
            self.status_message.emit(f'Group "{group.name}" deleted.')
        except Exception as e:
            self.status_message.emit(f"Error deleting: {e}")
        await self._refresh_groups_only()

    async def add_devices(self, devices: list[Device], to_group: DeviceGroup) -> list[Device]:
        endpoint_ids = [d.endpoint_id for d in devices if d.endpoint_id]
        if not endpoint_ids:
            return []
        succeeded = 0
        added: list[Device] = []
        for eid in endpoint_ids:
            try:
                await self.session.update_device_group_members(group_id=to_group.id, endpoint_ids=[eid], operation="ADD")
                succeeded += 1
                added.extend(d for d in devices if d.endpoint_id == eid)
            except Exception:
                pass
            await asyncio.sleep(0.2)
        self.status_message.emit(f'{succeeded}/{len(endpoint_ids)} device(s) added to "{to_group.name}".')
        await self._refresh_groups_only()
        return added

    async def remove_devices(self, devices: list[Device], from_group: DeviceGroup) -> list[Device]:
        endpoint_ids = [d.endpoint_id for d in devices if d.endpoint_id]
        if not endpoint_ids:
            return []
        succeeded = 0
        removed: list[Device] = []
        for eid in endpoint_ids:
            try:
                await self.session.update_device_group_members(group_id=from_group.id, endpoint_ids=[eid], operation="REMOVE")
                succeeded += 1
                removed.extend(d for d in devices if d.endpoint_id == eid)
            except Exception:
                pass
            await asyncio.sleep(0.2)
        self.status_message.emit(f'{succeeded}/{len(endpoint_ids)} device(s) removed from "{from_group.name}".')
        await self._refresh_groups_only()
        return removed

    async def move_devices(self, devices: list[Device], source: DeviceGroup | None, destination: DeviceGroup) -> None:
        if source and source.id != destination.id:
            removed = await self.remove_devices(devices, from_group=source)
            if not removed:
                self.status_message.emit("Move cancelled: no devices were removed from the source group.")
                return []
            return await self.add_devices(removed, to_group=destination)
        return await self.add_devices(devices, to_group=destination)

    async def _refresh_groups_only(self) -> None:
        try:
            self._device_groups = await self.session.fetch_device_groups()
        except Exception:
            pass
        self.groups_changed.emit()

    # --- Deletion ---

    async def delete_devices(self, devices: list[Device]) -> None:
        if not devices:
            return
        self._is_busy = True
        self.busy_changed.emit(True)
        self.progress_changed.emit(0, len(devices))

        succeeded = 0
        failed = 0
        for i, device in enumerate(devices):
            try:
                ok = await self.session.delete_device(appliance_id=device.appliance_id)
                if ok:
                    succeeded += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
            self.progress_changed.emit(i + 1, len(devices))
            await asyncio.sleep(0.3)

        self.status_message.emit(f"{succeeded} deleted, {failed} failed.")
        self._is_busy = False
        self.busy_changed.emit(False)
        await self.refresh()
