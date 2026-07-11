import asyncio
import json
import pytest
from app.session import AlexaSession, AlexaSessionError, InvalidResponseError, HTTPError, GraphQLErrors
from app.models.device import Connectivity as _Connectivity


class TestSessionErrors:
    def test_alexa_session_error(self):
        e = AlexaSessionError("msg")
        assert str(e) == "msg"

    def test_invalid_response_error(self):
        e = InvalidResponseError("bad")
        assert isinstance(e, AlexaSessionError)

    def test_http_error(self):
        e = HTTPError(500)
        assert e.status_code == 500
        assert "500" in str(e)

    def test_graphql_errors(self):
        e = GraphQLErrors(["err1", "err2"])
        assert e.messages == ["err1", "err2"]


class TestJavascriptHelpers:
    def test_js_string_escapes_quotes(self):
        result = AlexaSession._js_string('hello "world"')
        assert '"hello \\"world\\""' == result

    def test_js_string_with_backslash(self):
        result = AlexaSession._js_string('path\\to\\file')
        assert result == '"path\\\\to\\\\file"'

    def test_js_string_simple(self):
        result = AlexaSession._js_string("hello")
        assert result == '"hello"'


class TestFetchScript:
    def test_basic_fetch(self):
        script = AlexaSession._fetch_script("/test", "GET", "null")
        assert "XMLHttpRequest" in script
        assert "xhr.open('GET', '/test', false)" in script
        assert "xhr.withCredentials = true" in script
        assert "xhr.send(JSON.stringify(null))" in script
        assert "xhr.status" in script
        assert "xhr.responseText" in script

    def test_post_with_body(self):
        script = AlexaSession._fetch_script("/api", "POST", '{"a":1}')
        assert "xhr.open('POST', '/api', false)" in script
        assert "xhr.send(JSON.stringify({\"a\":1}))" in script

    def test_error_handling(self):
        script = AlexaSession._fetch_script("/fail", "GET", "null")
        assert "catch (e)" in script
        assert 'status: -1' in script
        assert 'String(e)' in script

    def test_json_content_type(self):
        script = AlexaSession._fetch_script("/test", "POST", "null")
        assert "application/json" in script


class TestDecodeEnvelope:
    @pytest.mark.asyncio
    async def test_valid_envelope(self):
        raw = '{"status": 200, "body": "hello"}'
        result = await AlexaSession._decode_envelope(None, raw)
        assert result == b"hello"

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        from app.session import InvalidResponseError
        with pytest.raises(InvalidResponseError):
            await AlexaSession._decode_envelope(None, "not json")

    @pytest.mark.asyncio
    async def test_http_error(self):
        from app.session import HTTPError
        with pytest.raises(HTTPError):
            await AlexaSession._decode_envelope(None, '{"status": 500, "body": "error"}')

    @pytest.mark.asyncio
    async def test_missing_body(self):
        from app.session import InvalidResponseError
        with pytest.raises(InvalidResponseError):
            await AlexaSession._decode_envelope(None, '{"status": 200}')

    @pytest.mark.asyncio
    async def test_body_is_dict(self):
        raw = '{"status": 200, "body": {"key": "value"}}'
        result = await AlexaSession._decode_envelope(None, raw)
        assert b'"key"' in result

    @pytest.mark.asyncio
    async def test_empty_body(self):
        raw = '{"status": 200, "body": ""}'
        result = await AlexaSession._decode_envelope(None, raw)
        assert result == b""


class TestStringify:
    def test_none(self):
        assert AlexaSession._stringify(None) == "–"

    def test_string(self):
        assert AlexaSession._stringify("hello") == "hello"

    def test_int(self):
        assert AlexaSession._stringify(42) == "42"

    def test_float(self):
        assert AlexaSession._stringify(3.14) == "3.14"

    def test_true(self):
        assert AlexaSession._stringify(True) == "true"

    def test_false(self):
        assert AlexaSession._stringify(False) == "false"

    def test_list(self):
        assert AlexaSession._stringify(["a", "b"]) == "a, b"

    def test_dict(self):
        result = AlexaSession._stringify({"a": 1, "b": "x"})
        assert "a=1" in result
        assert "b=x" in result

    def test_nested_list(self):
        assert AlexaSession._stringify([["a", "b"], ["c"]]) == "a, b, c"

    def test_unknown_type(self):
        assert AlexaSession._stringify(b"bytes") == "b'bytes'"


class TestBoolIntParsing:
    def test_int(self):
        v = 42
        assert isinstance(v, (int, float))

    def test_float(self):
        v = 3.14
        assert isinstance(v, (int, float))

    def test_bool_is_int(self):
        assert isinstance(True, int)


class TestIsLeafField:
    def test_scalar(self):
        assert AlexaSession._is_leaf_field({"type": {"kind": "SCALAR", "name": "String"}})

    def test_enum(self):
        assert AlexaSession._is_leaf_field({"type": {"kind": "ENUM", "name": "Status"}})

    def test_non_leaf_object(self):
        assert not AlexaSession._is_leaf_field({"type": {"kind": "OBJECT", "name": "Device"}})

    def test_non_null_scalar(self):
        assert AlexaSession._is_leaf_field({
            "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "String"}}
        })

    def test_list_scalar(self):
        assert AlexaSession._is_leaf_field({
            "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}}
        })

    def test_list_object(self):
        assert not AlexaSession._is_leaf_field({
            "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Device"}}
        })

    def test_empty_type(self):
        assert not AlexaSession._is_leaf_field({"type": {}})


class TestFormattedFieldLines:
    def test_simple_field(self):
        fields = [{"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []}]
        lines = AlexaSession._formatted_field_lines(None, fields)
        assert lines == ["id: String"]

    def test_field_with_args(self):
        fields = [{
            "name": "devices",
            "type": {"kind": "LIST", "name": None, "ofType": {"kind": "OBJECT", "name": "Device"}},
            "args": [{"name": "filter", "type": {"kind": "SCALAR", "name": "String"}}],
        }]
        lines = AlexaSession._formatted_field_lines(None, fields)
        assert "devices(filter: String): Device" in lines

    def test_multiple_fields_sorted(self):
        fields = [
            {"name": "z_field", "type": {"kind": "SCALAR", "name": "Int"}, "args": []},
            {"name": "a_field", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
        ]
        lines = AlexaSession._formatted_field_lines(None, fields)
        assert lines[0].startswith("a_field")
        assert lines[1].startswith("z_field")

    def test_field_with_ofType_name(self):
        fields = [{
            "name": "items",
            "type": {"kind": "LIST", "name": None, "ofType": {"kind": "NON_NULL", "name": None, "ofType": {"kind": "OBJECT", "name": "Item"}}},
            "args": [],
        }]
        lines = AlexaSession._formatted_field_lines(None, fields)
        assert "items: LIST" in lines[0]


class TestNestedTypeNames:
    def test_object_type(self):
        fields = [{"type": {"kind": "OBJECT", "name": "Device"}}]
        assert AlexaSession._nested_type_names(fields) == ["Device"]

    def test_non_null_object(self):
        fields = [{"type": {"kind": "NON_NULL", "ofType": {"kind": "OBJECT", "name": "Device"}}}]
        assert AlexaSession._nested_type_names(fields) == ["Device"]

    def test_list_object(self):
        fields = [{"type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Device"}}}]
        assert AlexaSession._nested_type_names(fields) == ["Device"]

    def test_interface(self):
        fields = [{"type": {"kind": "INTERFACE", "name": "Node"}}]
        assert AlexaSession._nested_type_names(fields) == ["Node"]

    def test_scalar_excluded(self):
        fields = [{"type": {"kind": "SCALAR", "name": "String"}}]
        assert AlexaSession._nested_type_names(fields) == []

    def test_union(self):
        fields = [{"type": {"kind": "UNION", "name": "SearchResult"}}]
        assert AlexaSession._nested_type_names(fields) == ["SearchResult"]

    def test_input_object(self):
        fields = [{"type": {"kind": "INPUT_OBJECT", "name": "DeviceInput"}}]
        assert AlexaSession._nested_type_names(fields) == ["DeviceInput"]

    def test_empty(self):
        assert AlexaSession._nested_type_names([]) == []


class TestEncodeURIComponent:
    def test_basic(self):
        assert AlexaSession._encode_uri_component("abc") == "abc"

    def test_spaces(self):
        assert AlexaSession._encode_uri_component("a b") == "a%20b"

    def test_special_chars(self):
        assert AlexaSession._encode_uri_component("a/b?c") == "a%2Fb%3Fc"

    def test_safe_chars(self):
        safe = AlexaSession._encode_uri_component("-_.!~*'()")
        assert safe == "-_.!~*'()"

    def test_unicode(self):
        result = AlexaSession._encode_uri_component("straße")
        assert result is not None
        assert "%" in result


class TestParseDevice:
    @pytest.fixture
    def session(self, qtbot):
        from app.session import AlexaSession
        return AlexaSession()

    def test_minimal(self, session):
        item = {"friendlyName": "", "legacyAppliance": {}}
        d = AlexaSession._parse_device(session, item)
        assert d.appliance_id == ""
        assert d.friendly_name == ""
        assert d.connectivity == _Connectivity.UNKNOWN
        assert d.manufacturer_name is None
        assert d.display_category is None
        assert d.associated_unit_id is None

    def test_with_all_fields(self, session):
        item = {
            "friendlyName": "My Light",
            "legacyAppliance": {"applianceId": "abc123"},
            "id": "endpoint1",
            "manufacturer": {"value": {"text": "Philips"}},
            "displayCategories": {"primary": {"value": "LIGHT"}},
            "associatedUnits": {"id": "unit1"},
            "features": [
                {"name": "connectivity", "properties": [
                    {"__typename": "Reachability", "reachabilityStatusValue": "UNREACHABLE"}
                ]}
            ],
            "extraField": "some_value",
        }
        d = AlexaSession._parse_device(session, item)
        assert d.appliance_id == "abc123"
        assert d.friendly_name == "My Light"
        assert d.endpoint_id == "endpoint1"
        assert d.manufacturer_name == "Philips"
        assert d.display_category == "LIGHT"
        assert d.associated_unit_id == "unit1"
        assert d.connectivity == _Connectivity.UNREACHABLE
        assert "extraField" in d.raw_fields

    def test_ok_connectivity(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
            "features": [
                {"name": "connectivity", "properties": [
                    {"__typename": "Reachability", "reachabilityStatusValue": "OK"}
                ]}
            ],
        }
        d = AlexaSession._parse_device(session, item)
        assert d.connectivity == _Connectivity.OK

    def test_no_connectivity_feature(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
            "features": [{"name": "other", "properties": []}],
        }
        d = AlexaSession._parse_device(session, item)
        assert d.connectivity == _Connectivity.UNKNOWN

    def test_features_is_not_list(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
            "features": "invalid",
        }
        d = AlexaSession._parse_device(session, item)
        assert d.connectivity == _Connectivity.UNKNOWN

    def test_empty_manufacturer(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
            "manufacturer": {},
        }
        d = AlexaSession._parse_device(session, item)
        assert d.manufacturer_name is None

    def test_empty_display_categories(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
            "displayCategories": {},
        }
        d = AlexaSession._parse_device(session, item)
        assert d.display_category is None

    def test_manufacturer_not_dict(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
            "manufacturer": "not_a_dict",
        }
        d = AlexaSession._parse_device(session, item)
        assert d.manufacturer_name is None

    def test_no_appliance_id(self, session):
        item = {"friendlyName": "Test", "legacyAppliance": None}
        d = AlexaSession._parse_device(session, item)
        assert d.appliance_id == ""

    def test_raw_fields_excludes_known(self, session):
        item = {
            "friendlyName": "Test",
            "legacyAppliance": {"applianceId": "id1"},
        }
        d = AlexaSession._parse_device(session, item)
        assert "friendlyName" not in d.raw_fields
        assert "legacyAppliance" not in d.raw_fields


class TestParseDeviceGroup:
    def test_minimal(self):
        item = {}
        g = AlexaSession._parse_device_group(item)
        assert g.id == ""
        assert g.name == ""
        assert g.member_endpoint_ids == set()

    def test_with_members(self):
        item = {
            "id": "group1",
            "friendlyName": {"value": {"text": "Living Room"}},
            "memberDevices": {"items": [{"id": "e1"}, {"id": "e2"}]},
        }
        g = AlexaSession._parse_device_group(item)
        assert g.id == "group1"
        assert g.name == "Living Room"
        assert g.member_endpoint_ids == {"e1", "e2"}

    def test_no_members(self):
        item = {
            "id": "group1",
            "friendlyName": {"value": {"text": "Group"}},
            "memberDevices": {},
        }
        g = AlexaSession._parse_device_group(item)
        assert g.member_endpoint_ids == set()

    def test_uses_id_as_name_fallback(self):
        item = {
            "id": "group1",
            "friendlyName": {},
        }
        g = AlexaSession._parse_device_group(item)
        assert g.name == "group1"

    def test_friendly_name_none(self):
        item = {
            "id": "group1",
            "friendlyName": None,
        }
        g = AlexaSession._parse_device_group(item)
        assert g.name == "group1"


class TestJsCallback:
    @pytest.mark.asyncio
    async def test_string_result(self):
        future = asyncio.get_event_loop().create_future()
        cb = AlexaSession._js_callback(None, future)
        cb("hello")
        assert await future == "hello"

    @pytest.mark.asyncio
    async def test_none_result(self):
        future = asyncio.get_event_loop().create_future()
        cb = AlexaSession._js_callback(None, future)
        cb(None)
        assert await future == ""

    @pytest.mark.asyncio
    async def test_int_result(self):
        future = asyncio.get_event_loop().create_future()
        cb = AlexaSession._js_callback(None, future)
        cb(42)
        result = await future
        assert json.loads(result) == 42

    @pytest.mark.asyncio
    async def test_dict_result(self):
        future = asyncio.get_event_loop().create_future()
        cb = AlexaSession._js_callback(None, future)
        cb({"key": "val"})
        result = await future
        assert json.loads(result) == {"key": "val"}

    @pytest.mark.asyncio
    async def test_already_done_future(self):
        future = asyncio.get_event_loop().create_future()
        future.set_result("already")
        cb = AlexaSession._js_callback(None, future)
        cb("should be ignored")
        assert await future == "already"


class TestCreateFuture:
    @pytest.mark.asyncio
    async def test_creates_future(self):
        future = AlexaSession._create_future(None)
        assert not future.done()
        future.set_result("ok")
        assert await future == "ok"
