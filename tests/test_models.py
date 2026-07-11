import pytest
from app.models.device import Device, Connectivity
from app.models.device_group import DeviceGroup
from app.models.appliance_id import ApplianceIDParser, DecodedApplianceID
from app.models.region import AlexaRegion
from app.models.filter import DeviceFilter, BatchAction


class TestConnectivity:
    def test_enum_values(self):
        assert Connectivity.OK.value == "ok"
        assert Connectivity.UNREACHABLE.value == "unreachable"
        assert Connectivity.UNKNOWN.value == "unknown"


class TestDevice:
    def test_device_id_property(self):
        d = Device(appliance_id="id1", friendly_name="Test", decoded=None)
        assert d.id == "id1"

    def test_device_type_symbol_fallback(self):
        d = Device(appliance_id="id1", friendly_name="Test", decoded=None)
        assert d.type_symbol_name == "questionmark-circle"

    def test_minimal_device(self):
        d = Device(appliance_id="id1", friendly_name="Test", decoded=None)
        assert d.appliance_id == "id1"
        assert d.friendly_name == "Test"
        assert d.connectivity == Connectivity.UNKNOWN
        assert d.skill_id is None
        assert d.integration_group_key == Device.unknown_skill_id
        assert d.type_label == "Unknown"

    def test_device_with_skill_id(self):
        decoded = DecodedApplianceID(
            skill_id="amzn1.ask.skill.abc123",
            stage="live",
            domain="Light",
            object_id="obj1",
        )
        d = Device(appliance_id="id2", friendly_name="Lamp", decoded=decoded)
        assert d.skill_id == "amzn1.ask.skill.abc123"
        assert d.integration_group_key == "amzn1.ask.skill.abc123"

    def test_device_amazon_manufacturer(self):
        d = Device(
            appliance_id="id3", friendly_name="Echo", decoded=None,
            manufacturer_name="Amazon",
        )
        assert d.integration_group_key == "Amazon"

    def test_device_connectivity_ok(self):
        d = Device(
            appliance_id="id4", friendly_name="Plug", decoded=None,
            connectivity=Connectivity.OK,
        )
        assert d.connectivity == Connectivity.OK

    def test_device_with_endpoint_id(self):
        d = Device(
            appliance_id="id5", friendly_name="Sensor", decoded=None,
            endpoint_id="ep1",
        )
        assert d.endpoint_id == "ep1"

    def test_device_type_label_from_display_category(self):
        d = Device(
            appliance_id="id6", friendly_name="Main Light", decoded=None,
            display_category="LIGHT",
        )
        assert d.type_label == "Light"
        assert d.type_symbol_name == "lightbulb"

    def test_device_unknown_display_category(self):
        d = Device(
            appliance_id="id7", friendly_name="Unknown", decoded=None,
            display_category="NONEXISTENT_CAT",
        )
        assert d.type_label == "NONEXISTENT_CAT"
        assert d.type_symbol_name == "questionmark-circle"

    def test_device_type_from_ha_domain(self):
        decoded = DecodedApplianceID(
            skill_id="skill1", stage=None,
            domain="alarm_control_panel:homeassistant",
            object_id="obj1",
        )
        d = Device(appliance_id="id8", friendly_name="Alarm", decoded=decoded)
        assert d.type_label == "Alarm"
        assert d.type_symbol_name == "alarm-light"

    def test_device_raw_fields(self):
        d = Device(
            appliance_id="id9", friendly_name="Raw", decoded=None,
            raw_fields={"key1": "val1", "key2": "val2"},
        )
        assert d.raw_fields["key1"] == "val1"
        assert d.raw_fields["key2"] == "val2"

    def test_device_associated_unit_id(self):
        d = Device(
            appliance_id="id10", friendly_name="Multi", decoded=None,
            associated_unit_id="unit1",
        )
        assert d.associated_unit_id == "unit1"


class TestApplianceIDParser:
    def test_valid_decode(self):
        # base64 of {"skillId":"amzn1.ask.skill.abc","stage":"live"}
        b64 = "eyJza2lsbElkIjoiYW16bjEuYXNrLnNraWxsLmFiYyIsInN0YWdlIjoibGl2ZSJ9"
        result = ApplianceIDParser.decode(f"SKILL_{b64}_Light#obj1")
        assert result is not None
        assert result.skill_id == "amzn1.ask.skill.abc"
        assert result.stage == "live"
        assert result.domain == "Light"
        assert result.object_id == "obj1"

    def test_valid_decode_no_object_id(self):
        b64 = "eyJza2lsbElkIjoiYW16bjEuYXNrLnNraWxsLnh5eiJ9"
        result = ApplianceIDParser.decode(f"SKILL_{b64}_Switch")
        assert result is not None
        assert result.skill_id == "amzn1.ask.skill.xyz"
        assert result.object_id == ""

    def test_valid_decode_no_stage(self):
        b64 = "eyJza2lsbElkIjoiYW16bjEuYXNrLnNraWxsLmRlZiJ9"
        result = ApplianceIDParser.decode(f"SKILL_{b64}_Lock#door1")
        assert result is not None
        assert result.skill_id == "amzn1.ask.skill.def"
        assert result.stage is None

    def test_invalid_format(self):
        result = ApplianceIDParser.decode("not_a_valid_format")
        assert result is None

    def test_empty_string(self):
        result = ApplianceIDParser.decode("")
        assert result is None

    def test_invalid_base64(self):
        result = ApplianceIDParser.decode("SKILL_!!!invalid!!!_Domain#obj")
        assert result is None

    def test_invalid_json_in_base64(self):
        import base64
        b64 = base64.b64encode(b"not json").decode()
        result = ApplianceIDParser.decode(f"SKILL_{b64}_Domain")
        assert result is None

    def test_base64_decode_invalid_bytes(self):
        import base64
        b64 = base64.b64encode(b"\xff\xfe\xfa").decode()
        result = ApplianceIDParser.decode(f"SKILL_{b64}_Domain")
        assert result is None

    def test_missing_skill_id_in_payload(self):
        # valid base64 but no skillId field
        b64 = "eyJmb28iOiJiYXIifQ=="  # {"foo":"bar"}
        result = ApplianceIDParser.decode(f"SKILL_{b64}_Domain#obj")
        assert result is None

    def test_complex_domain(self):
        b64 = "eyJza2lsbElkIjoic2tpbGwxIn0="  # {"skillId":"skill1"}
        result = ApplianceIDParser.decode(f"SKILL_{b64}_alarm_control_panel:homeassistant#zone1")
        assert result is not None
        assert result.domain == "alarm_control_panel:homeassistant"
        assert result.object_id == "zone1"


class TestDeviceGroup:
    def test_minimal_group(self):
        g = DeviceGroup(id="g1", name="Living Room")
        assert g.id == "g1"
        assert g.name == "Living Room"
        assert g.member_endpoint_ids == set()

    def test_group_with_members(self):
        g = DeviceGroup(id="g2", name="Bedroom", member_endpoint_ids={"ep1", "ep2"})
        assert g.member_endpoint_ids == {"ep1", "ep2"}

    def test_group_eq_by_id(self):
        g1 = DeviceGroup(id="g1", name="Living Room")
        g2 = DeviceGroup(id="g1", name="Living Room")
        assert g1 == g2


class TestAlexaRegion:
    def test_base_url(self):
        r = AlexaRegion(id="alexa.amazon.de", label="DE", retail_domain="amazon.de")
        assert r.base_url == "https://alexa.amazon.de"

    def test_sign_in_url(self):
        r = AlexaRegion(id="alexa.amazon.de", label="DE", retail_domain="amazon.de")
        assert r.sign_in_url == "https://www.amazon.de/"

    def test_candidates_exist(self):
        assert len(AlexaRegion.candidates) >= 4
        domains = {r.id for r in AlexaRegion.candidates}
        assert "alexa.amazon.de" in domains
        assert "alexa.amazon.com" in domains
        assert "pitangui.amazon.com" in domains
        assert "layla.amazon.com" in domains

    def test_region_immutable(self):
        r = AlexaRegion(id="test", label="Test", retail_domain="test.com")
        with pytest.raises(Exception):
            r.id = "changed"


class TestDeviceFilter:
    def test_all(self):
        f = DeviceFilter.all()
        assert f.kind == "all"
        assert f.value is None

    def test_skill(self):
        f = DeviceFilter.skill("amzn1.ask.skill.abc")
        assert f.kind == "skill"
        assert f.value == "amzn1.ask.skill.abc"

    def test_type(self):
        f = DeviceFilter.type_("Light")
        assert f.kind == "type"
        assert f.value == "Light"

    def test_group(self):
        f = DeviceFilter.group("g1")
        assert f.kind == "group"
        assert f.value == "g1"

    def test_unresponsive(self):
        f = DeviceFilter.unresponsive()
        assert f.kind == "unresponsive"
        assert f.value is None

    def test_disabled_integrations(self):
        f = DeviceFilter.disabled_integrations()
        assert f.kind == "disabledIntegrations"

    def test_equality(self):
        assert DeviceFilter.all() == DeviceFilter.all()
        assert DeviceFilter.skill("abc") == DeviceFilter.skill("abc")
        assert DeviceFilter.all() != DeviceFilter.unresponsive()

    def test_equality_with_non_filter(self):
        assert DeviceFilter.all().__eq__("not a filter") is NotImplemented

    def test_hashable(self):
        s = {DeviceFilter.all(), DeviceFilter.skill("abc")}
        assert len(s) == 2


class TestBatchAction:
    def test_selected(self):
        devices = [Device(appliance_id="a1", friendly_name="A", decoded=None)]
        a = BatchAction.selected(devices)
        assert a.kind == "selected"
        assert len(a.devices) == 1

    def test_unresponsive(self):
        a = BatchAction.unresponsive()
        assert a.kind == "unresponsive"

    def test_disabled_integrations(self):
        a = BatchAction.disabled_integrations()
        assert a.kind == "disabledIntegrations"

    def test_all(self):
        a = BatchAction.all()
        assert a.kind == "all"


class TestLookupTables:
    def test_alexa_display_category_label(self):
        from app.models.lookup_tables import alexa_display_category_label
        assert alexa_display_category_label("LIGHT") == "Light"
        assert alexa_display_category_label("NONEXISTENT") == "NONEXISTENT"

    def test_alexa_display_category_symbol(self):
        from app.models.lookup_tables import alexa_display_category_symbol
        assert alexa_display_category_symbol("LIGHT") == "lightbulb"
        assert alexa_display_category_symbol("NONEXISTENT") == "questionmark-circle"

    def test_home_assistant_domain_label(self):
        from app.models.lookup_tables import home_assistant_domain_label
        assert home_assistant_domain_label("light") == "Light"
        assert home_assistant_domain_label("nonexistent") == "nonexistent"

    def test_home_assistant_domain_symbol(self):
        from app.models.lookup_tables import home_assistant_domain_symbol
        assert home_assistant_domain_symbol("light") == "lightbulb"
        assert home_assistant_domain_symbol("nonexistent") == "questionmark-circle"
