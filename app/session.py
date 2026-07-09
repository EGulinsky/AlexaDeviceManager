from __future__ import annotations
import json
from typing import Any
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from qasync import asyncSlot, asyncClose

from .models.device import Connectivity, Device
from .models.device_group import DeviceGroup
from .models.appliance_id import ApplianceIDParser
from .models.region import AlexaRegion


class AlexaSessionError(Exception):
    pass


class InvalidResponseError(AlexaSessionError):
    pass


class HTTPError(AlexaSessionError):
    def __init__(self, status_code: int):
        super().__init__(f"HTTP error {status_code}")
        self.status_code = status_code


class GraphQLErrors(AlexaSessionError):
    def __init__(self, messages: list[str]):
        super().__init__(messages)
        self.messages = messages


class AlexaSession(QObject):
    is_logged_in = Signal(bool)
    is_loading = Signal(bool)
    last_error = Signal(str)
    current_url = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.region = AlexaRegion.candidates[0]
        self._csrf_token = ""
        self._should_check_login = False
        self._logged_in = False

        self.web_view = QWebEngineView()
        self.web_view.setFixedSize(0, 0)
        page = self.web_view.page()
        page.loadFinished.connect(self._on_load_finished)
        page.urlChanged.connect(lambda url: self.current_url.emit(url.toString()))

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    def load_sign_in_page(self) -> None:
        self.is_loading.emit(True)
        self.last_error.emit("")
        self._should_check_login = False
        self.web_view.setUrl(self.region.sign_in_url)

    def load_alexa_host(self) -> None:
        self.is_loading.emit(True)
        self.last_error.emit("")
        self._should_check_login = True
        self.web_view.setUrl(self.region.base_url)

    async def attempt_auto_login(self) -> bool:
        self._should_check_login = True
        self.is_loading.emit(True)
        self.last_error.emit("")
        self.web_view.setUrl(self.region.base_url)
        await self._wait_for_load()
        return self._logged_in

    async def check_login_status(self) -> None:
        try:
            _ = await self.fetch_devices()
            self._logged_in = True
            self.is_logged_in.emit(True)
            self.last_error.emit("")
        except AlexaSessionError as e:
            self._logged_in = False
            self.is_logged_in.emit(False)
            self.last_error.emit(str(e))

    # --- JS bridge ---

    async def evaluate(self, script: str) -> str:
        future = self._create_future()
        self.web_view.page().runJavaScript(script, self._js_callback(future))
        return await future

    def _js_callback(self, future):
        def callback(result: Any):
            if future.done():
                return
            if result is None:
                future.set_result("")
            elif isinstance(result, str):
                future.set_result(result)
            else:
                future.set_result(json.dumps(result))
        return callback

    def _create_future(self):
        import asyncio
        return asyncio.get_event_loop().create_future()

    async def _wait_for_load(self) -> None:
        future = self._create_future()
        self._load_finished_future = future
        await future

    def _on_load_finished(self, ok: bool) -> None:
        self.is_loading.emit(False)
        if hasattr(self, "_load_finished_future") and not self._load_finished_future.done():
            self._load_finished_future.set_result(None)
            del self._load_finished_future
        if self._should_check_login:
            import asyncio
            asyncio.ensure_future(self.check_login_status())

    # --- Fetch helpers ---

    @staticmethod
    def _fetch_script(path: str, method: str, json_body: str) -> str:
        return f"""
        (async () => {{
            try {{
                const res = await fetch('{path}', {{
                    method: '{method}',
                    credentials: 'include',
                    headers: {{"Content-Type": "application/json", "Accept": "application/json"}},
                    body: JSON.stringify({json_body})
                }});
                const text = await res.text();
                return JSON.stringify({{status: res.status, body: text}});
            }} catch (e) {{
                return JSON.stringify({{status: -1, body: String(e)}});
            }}
        }})()
        """

    @staticmethod
    def _js_string(value: str) -> str:
        return json.dumps(value)

    @staticmethod
    def _encode_uri_component(value: str) -> str | None:
        import urllib.parse
        return urllib.parse.quote(value, safe="-_.!~*'()")

    async def _evaluate_fetch(self, path: str, method: str, json_body: str) -> str:
        script = self._fetch_script(path, method, json_body)
        return await self.evaluate(script)

    async def _decode_envelope(self, raw: str) -> bytes:
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            raise InvalidResponseError("Invalid envelope JSON")
        status = envelope.get("status", -1)
        if status != 200:
            raise HTTPError(status)
        body = envelope.get("body")
        if body is None:
            raise InvalidResponseError("No body in envelope")
        if isinstance(body, str):
            return body.encode("utf-8")
        return json.dumps(body).encode("utf-8")

    async def _run_graphql(self, query: str) -> dict:
        body = self._js_string(query)
        raw = await self._evaluate_fetch("/nexus/v1/graphql", "POST", f"{{query: {body}}}")
        body_data = await self._decode_envelope(raw)
        try:
            json_data = json.loads(body_data)
        except json.JSONDecodeError:
            raise InvalidResponseError("Invalid JSON response")
        return json_data

    async def _run_mutation(self, query: str, success_key: str) -> bool:
        json_data = await self._run_graphql(query)
        if "data" in json_data and success_key in json_data["data"]:
            return True
        errors = json_data.get("errors", [])
        raise GraphQLErrors([e.get("message", "Unknown error") for e in errors])

    # --- Known endpoint fields ---

    _known_field_names = {"friendlyName", "legacyAppliance", "features", "manufacturer", "displayCategories", "associatedUnits", "id"}

    # --- Device listing ---

    async def fetch_devices(self) -> list[Device]:
        discovered = await self._introspect_fields()
        field_names = {f["name"] for f in discovered["fields"]}
        extra_fields = [f["name"] for f in discovered["fields"] if self._is_leaf_field(f)]
        include_features = "features" in field_names
        include_manufacturer = "manufacturer" in field_names
        include_display_categories = "displayCategories" in field_names
        include_associated_units = "associatedUnits" in field_names

        try:
            return await self._fetch_devices(
                extra_field_names=extra_fields,
                include_features=include_features,
                include_manufacturer=include_manufacturer,
                include_display_categories=include_display_categories,
                include_associated_units=include_associated_units,
            )
        except GraphQLErrors:
            return await self._fetch_devices(
                extra_field_names=[], include_features=False,
                include_manufacturer=False, include_display_categories=False,
                include_associated_units=False,
            )

    async def _fetch_devices(
        self,
        extra_field_names: list[str],
        include_features: bool,
        include_manufacturer: bool,
        include_display_categories: bool,
        include_associated_units: bool,
    ) -> list[Device]:
        base_fields = ["id", "friendlyName", "legacyAppliance { applianceId }"]
        if include_features:
            base_fields.append("features { name properties { __typename ... on Reachability { reachabilityStatusValue } } }")
        if include_manufacturer:
            base_fields.append("manufacturer { value { text } }")
        if include_display_categories:
            base_fields.append("displayCategories { primary { value } }")
        if include_associated_units:
            base_fields.append("associatedUnits { id }")
        extra = [f for f in extra_field_names if f not in self._known_field_names]
        selection = " ".join(base_fields + extra)
        query = f"query {{ endpoints {{ items {{ {selection} }} }} }}"

        json_data = await self._run_graphql(query)
        if "data" in json_data:
            data_dict = json_data["data"]
            endpoints = data_dict.get("endpoints", {})
            items = endpoints.get("items", [])
            return [self._parse_device(item) for item in items]
        errors = json_data.get("errors", [])
        raise GraphQLErrors([e.get("message", "Unknown error") for e in errors])

    def _parse_device(self, item: dict) -> Device:
        friendly_name = item.get("friendlyName", "") or ""
        legacy = item.get("legacyAppliance") or {}
        appliance_id = legacy.get("applianceId", "") or ""
        endpoint_id = item.get("id")

        manufacturer_raw = item.get("manufacturer") or {}
        manufacturer_name = None
        if isinstance(manufacturer_raw, dict):
            val = manufacturer_raw.get("value") or {}
            if isinstance(val, dict):
                manufacturer_name = val.get("text")

        display_cat_raw = item.get("displayCategories") or {}
        display_category = None
        if isinstance(display_cat_raw, dict):
            primary = display_cat_raw.get("primary") or {}
            if isinstance(primary, dict):
                display_category = primary.get("value")

        associated_units = item.get("associatedUnits") or {}
        associated_unit_id = None
        if isinstance(associated_units, dict):
            associated_unit_id = associated_units.get("id")

        features = item.get("features") or []
        connectivity_val = Device.Connectivity.UNKNOWN
        if isinstance(features, list):
            conn_feature = next((f for f in features if f.get("name") == "connectivity"), None)
            if conn_feature:
                props = conn_feature.get("properties") or []
                if isinstance(props, list):
                    reachability = next((p for p in props if p.get("__typename") == "Reachability"), None)
                    if reachability:
                        status = reachability.get("reachabilityStatusValue")
                        if status == "OK":
                            connectivity_val = Device.Connectivity.OK
                        elif status == "UNREACHABLE":
                            connectivity_val = Device.Connectivity.UNREACHABLE

        raw_fields: dict[str, str] = {}
        for key, value in item.items():
            if key not in self._known_field_names:
                raw_fields[key] = self._stringify(value)

        return Device(
            appliance_id=appliance_id,
            friendly_name=friendly_name,
            decoded=ApplianceIDParser.decode(appliance_id),
            connectivity=connectivity_val,
            manufacturer_name=manufacturer_name if manufacturer_name else None,
            display_category=display_category if display_category else None,
            endpoint_id=endpoint_id,
            associated_unit_id=associated_unit_id,
            raw_fields=raw_fields,
        )

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return "–"
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            return ", ".join(AlexaSession._stringify(v) for v in value)
        if isinstance(value, dict):
            return ", ".join(f"{k}={AlexaSession._stringify(v)}" for k, v in value.items())
        return str(value)

    # --- Group management ---

    async def fetch_device_groups(self) -> list[DeviceGroup]:
        query = """query { listDeviceGroups(listDeviceGroupsInput: {devicesPaginationParams: {disablePagination: true}}) { deviceGroups { id friendlyName { value { text } } memberDevices { items { id } } } } }"""
        json_data = await self._run_graphql(query)
        if "data" in json_data:
            data_dict = json_data["data"]
            list_response = data_dict.get("listDeviceGroups", {})
            groups = list_response.get("deviceGroups", [])
            return [self._parse_device_group(g) for g in groups]
        errors = json_data.get("errors", [])
        raise GraphQLErrors([e.get("message", "Unknown error") for e in errors])

    @staticmethod
    def _parse_device_group(item: dict) -> DeviceGroup:
        gid = item.get("id", "") or ""
        name_raw = item.get("friendlyName") or {}
        name = (name_raw.get("value") or {}).get("text") or gid
        member_items = (item.get("memberDevices") or {}).get("items") or []
        endpoint_ids = {m.get("id", "") for m in member_items if m.get("id")}
        return DeviceGroup(id=gid, name=name, member_endpoint_ids=endpoint_ids)

    async def rename_device_group(self, group_id: str, new_name: str) -> bool:
        query = f"mutation {{ updateDeviceGroup(updateDeviceGroupInput: {{deviceGroupId: {self._js_string(group_id)}, friendlyName: {self._js_string(new_name)}}}) {{ deviceGroup {{ id }} }} }}"
        return await self._run_mutation(query, "updateDeviceGroup")

    async def delete_device_group(self, group_id: str) -> bool:
        query = f"mutation {{ deleteDeviceGroup(deleteDeviceGroupInput: {{deviceGroupId: {self._js_string(group_id)}}}) {{ deviceGroupId }} }}"
        return await self._run_mutation(query, "deleteDeviceGroup")

    async def create_device_group(self, name: str, member_endpoint_ids: list[str] = []) -> DeviceGroup:
        ids_literal = "[" + ", ".join(self._js_string(eid) for eid in member_endpoint_ids) + "]"
        query = f"mutation {{ createDeviceGroup(createDeviceGroupInput: {{friendlyName: {self._js_string(name)}, memberDeviceIds: {ids_literal}}}) {{ deviceGroup {{ id friendlyName {{ value {{ text }} }} memberDevices {{ items {{ id }} }} }} }} }}"
        json_data = await self._run_graphql(query)
        if "data" in json_data:
            response = json_data["data"].get("createDeviceGroup", {})
            group = response.get("deviceGroup", {})
            return self._parse_device_group(group)
        errors = json_data.get("errors", [])
        raise GraphQLErrors([e.get("message", "Unknown error") for e in errors])

    async def update_device_group_members(self, group_id: str, endpoint_ids: list[str], operation: str) -> bool:
        ids_literal = "[" + ", ".join(self._js_string(eid) for eid in endpoint_ids) + "]"
        query = f"mutation {{ updateDeviceGroup(updateDeviceGroupInput: {{deviceGroupId: {self._js_string(group_id)}, memberDeviceIds: {ids_literal}, memberDeviceIdsUpdateOperation: {operation}}}) {{ deviceGroup {{ id }} }} }}"
        return await self._run_mutation(query, "updateDeviceGroup")

    # --- Device deletion ---

    async def delete_device(self, appliance_id: str) -> bool:
        encoded = self._encode_uri_component(appliance_id)
        if encoded is None:
            raise InvalidResponseError("Could not encode applianceId")

        extra_headers = ""
        if self._csrf_token:
            extra_headers = f', "csrf": {self._js_string(self._csrf_token)}'

        script = f"""
        (async () => {{
            try {{
                const res = await fetch('/api/phoenix/appliance/{encoded}', {{
                    method: 'DELETE',
                    credentials: 'include',
                    headers: {{ "Accept": "application/json", "Content-Type": "application/json"{extra_headers} }}
                }});
                return JSON.stringify({{status: res.status}});
            }} catch (e) {{
                return JSON.stringify({{status: -1, body: String(e)}});
            }}
        }})()
        """
        raw = await self.evaluate(script)
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            raise InvalidResponseError("Invalid envelope JSON")
        return envelope.get("status") == 200

    # --- Schema introspection ---

    @staticmethod
    def _is_leaf_field(field: dict) -> bool:
        ftype = field.get("type", {})
        kind = ftype.get("kind")
        if kind in ("SCALAR", "ENUM"):
            return True
        if kind in ("NON_NULL", "LIST"):
            of_type = ftype.get("ofType") or {}
            return of_type.get("kind") in ("SCALAR", "ENUM")
        return False

    async def _introspect_fields(self) -> dict:
        typename_query = "query { endpoints { items { __typename } } }"
        json_data = await self._run_graphql(typename_query)
        try:
            type_name = json_data["data"]["endpoints"]["items"][0]["__typename"]
        except (KeyError, IndexError):
            raise GraphQLErrors(["No __typename received"])
        details = await self._introspect_type_details(type_name)
        return {"typeName": type_name, "fields": details.get("fields", [])}

    async def _introspect_type_details(self, type_name: str) -> dict:
        query = f"""query {{ __type(name: {self._js_string(type_name)}) {{ name kind fields {{ name args {{ name type {{ name kind ofType {{ name kind }} }} }} type {{ name kind ofType {{ name kind }} }} }} inputFields {{ name type {{ name kind ofType {{ name kind }} }} }} possibleTypes {{ name }} enumValues(includeDeprecated: true) {{ name }} }} }}"""
        json_data = await self._run_graphql(query)
        type_info = json_data.get("data", {}).get("__type")
        if type_info is None:
            errors = json_data.get("errors", [])
            raise GraphQLErrors([e.get("message", "Unknown error") for e in errors])
        return type_info

    async def fetch_all_endpoint_field_names(self) -> str:
        lines: list[str] = []

        try:
            root = await self._fetch_root_type_fields()
            lines.append(root)
            lines.append("")
        except Exception:
            pass

        discovered = await self._introspect_fields()
        type_name = discovered["typeName"]
        fields = discovered["fields"]
        lines.append(f"Type: {type_name}")
        lines.append("")
        lines += self._formatted_field_lines(fields)

        visited: set[str] = {type_name}
        queue = list(self._nested_type_names(fields))
        while queue and len(visited) < 40:
            nt = queue.pop(0)
            if nt in visited:
                continue
            visited.add(nt)
            try:
                details = await self._introspect_type_details(nt)
            except Exception:
                continue
            lines.append("")
            lines.append(f"--- {nt} (kind: {details.get('kind', '?')}) ---")

            nested_fields = details.get("fields")
            if nested_fields:
                lines += self._formatted_field_lines(nested_fields)
                queue += [n for n in self._nested_type_names(nested_fields) if n not in visited]

            possible = details.get("possibleTypes")
            if possible:
                names = [p.get("name", "?") for p in possible if p.get("name")]
                lines.append("possibleTypes: " + ", ".join(names))
                queue += [n for n in names if n not in visited]

            enum_values = details.get("enumValues")
            if enum_values:
                names = [e.get("name", "?") for e in enum_values if e.get("name")]
                lines.append("enumValues: " + ", ".join(names))

        return "\n".join(lines)

    async def _fetch_root_type_fields(self) -> str:
        query = "query { __schema { queryType { name } mutationType { name } } }"
        json_data = await self._run_graphql(query)
        schema = json_data.get("data", {}).get("__schema")
        if not schema:
            errors = json_data.get("errors", [])
            raise GraphQLErrors([e.get("message", "Unknown error") for e in errors])

        lines: list[str] = []
        query_type = schema.get("queryType") or {}
        query_name = query_type.get("name")
        if query_name:
            try:
                qfields = await self._introspect_type(query_name)
                lines.append(f"=== Root Query ({query_name}) ===")
                lines += self._formatted_field_lines(qfields)
            except Exception:
                pass

        lines.append("")
        mutation_type = schema.get("mutationType") or {}
        mutation_name = mutation_type.get("name")
        if mutation_name:
            try:
                mfields = await self._introspect_type(mutation_name)
                lines.append(f"=== Root Mutation ({mutation_name}) ===")
                lines += self._formatted_field_lines(mfields)
            except Exception:
                pass
        else:
            lines.append("(no mutation root type found)")

        return "\n".join(lines)

    async def _introspect_type(self, type_name: str) -> list[dict]:
        details = await self._introspect_type_details(type_name)
        fields = details.get("fields")
        if fields is None:
            raise GraphQLErrors([f"Type '{type_name}' has no fields"])
        return fields

    def _formatted_field_lines(self, fields: list[dict]) -> list[str]:
        result: list[str] = []
        for f in sorted(fields, key=lambda x: x.get("name", "")):
            ftype = f.get("type", {})
            type_name = ftype.get("name") or (ftype.get("ofType") or {}).get("name") or ftype.get("kind", "?")
            args = f.get("args")
            if args:
                args_str = ", ".join(
                    f"{a['name']}: {a['type'].get('name') or (a['type'].get('ofType') or {}).get('name') or a['type'].get('kind', '?')}"
                    for a in args
                )
                result.append(f"{f['name']}({args_str}): {type_name}")
            else:
                result.append(f"{f['name']}: {type_name}")
        return result

    @staticmethod
    def _nested_type_names(fields: list[dict]) -> list[str]:
        names: set[str] = set()
        for f in fields:
            ftype = f.get("type", {})
            kind = ftype.get("kind")
            if kind in ("NON_NULL", "LIST"):
                kind = (ftype.get("ofType") or {}).get("kind")
            if kind in ("OBJECT", "INTERFACE", "UNION", "INPUT_OBJECT"):
                name = ftype.get("name") or (ftype.get("ofType") or {}).get("name")
                if name:
                    names.add(name)
        return sorted(names)
