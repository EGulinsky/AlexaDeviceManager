import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage
from app.session import AlexaSession, AlexaSessionError, AlexaWebEnginePage, HTTPError, InvalidResponseError, GraphQLErrors


def _make_envelope(status=200, body="{}"):
    return json.dumps({"status": status, "body": body})


@pytest.fixture
def session(qtbot):
    sess = AlexaSession()
    sess.evaluate = AsyncMock()
    return sess


class TestRunGraphQL:
    @pytest.mark.asyncio
    async def test_success(self, session):
        session.evaluate.return_value = _make_envelope(body=json.dumps({"data": {"endpoints": {"items": []}}}))
        result = await session._run_graphql("{ endpoints { items { id } } }")
        assert "data" in result
        call_args = session.evaluate.call_args
        script = call_args.args[0]
        assert "XMLHttpRequest" in script

    @pytest.mark.asyncio
    async def test_invalid_envelope(self, session):
        session.evaluate.return_value = "not json"
        with pytest.raises(InvalidResponseError):
            await session._run_graphql("{ test }")

    @pytest.mark.asyncio
    async def test_http_error(self, session):
        session.evaluate.return_value = _make_envelope(status=500, body="error")
        with pytest.raises(HTTPError):
            await session._run_graphql("{ test }")

    @pytest.mark.asyncio
    async def test_invalid_json_body(self, session):
        session.evaluate.return_value = _make_envelope(body="not valid json{{{")
        with pytest.raises(InvalidResponseError):
            await session._run_graphql("{ test }")

    @pytest.mark.asyncio
    async def test_graphql_errors(self, session):
        resp = json.dumps({"errors": [{"message": "Field not found"}]})
        session.evaluate.return_value = _make_envelope(body=resp)
        result = await session._run_graphql("{ test }")
        assert "errors" in result


class TestRunMutation:
    @pytest.mark.asyncio
    async def test_success(self, session):
        resp = json.dumps({"data": {"updateDeviceGroup": {"deviceGroup": {"id": "g1"}}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        result = await session._run_mutation("mutation {}", "updateDeviceGroup")
        assert result is True

    @pytest.mark.asyncio
    async def test_failure(self, session):
        resp = json.dumps({"errors": [{"message": "Not authorized"}]})
        session.evaluate.return_value = _make_envelope(body=resp)
        with pytest.raises(GraphQLErrors) as exc:
            await session._run_mutation("mutation {}", "successKey")
        assert "Not authorized" in str(exc.value)


class TestIntrospectFields:
    @pytest.mark.asyncio
    async def test_success(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [{"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []}],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
        ]
        result = await session._introspect_fields()
        assert result["typeName"] == "Endpoint"
        assert len(result["fields"]) == 1

    @pytest.mark.asyncio
    async def test_no_typename(self, session):
        session.evaluate.return_value = _make_envelope(body=json.dumps({
            "data": {"endpoints": {"items": [{}]}}
        }))
        with pytest.raises(GraphQLErrors):
            await session._introspect_fields()


class TestFetchDevices:
    @pytest.mark.asyncio
    async def test_empty(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "friendlyName", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "legacyAppliance", "type": {"kind": "OBJECT", "name": "LegacyAppliance"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({"data": {"endpoints": {"items": []}}})),
        ]
        devices = await session.fetch_devices()
        assert devices == []

    @pytest.mark.asyncio
    async def test_with_devices(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "friendlyName", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "legacyAppliance", "type": {"kind": "OBJECT", "name": "LegacyAppliance"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [
                    {"friendlyName": "Light", "legacyAppliance": {"applianceId": "id1"}, "id": "e1"}
                ]}}
            })),
        ]
        devices = await session.fetch_devices()
        assert len(devices) == 1
        assert devices[0].friendly_name == "Light"
        assert devices[0].appliance_id == "id1"

    @pytest.mark.asyncio
    async def test_graphql_error_fallback(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "friendlyName", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "features", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "manufacturer", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "displayCategories", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "associatedUnits", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                        {"name": "legacyAppliance", "type": {"kind": "OBJECT", "name": "LegacyAppliance"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({"errors": [{"message": "Field not found"}]})),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [
                    {"friendlyName": "Fallback", "legacyAppliance": {"applianceId": "f1"}, "id": "fe1"}
                ]}}
            })),
        ]
        devices = await session.fetch_devices()
        assert len(devices) == 1
        assert devices[0].friendly_name == "Fallback"


class TestFetchDeviceGroups:
    @pytest.mark.asyncio
    async def test_empty(self, session):
        resp = json.dumps({"data": {"listDeviceGroups": {"deviceGroups": []}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        groups = await session.fetch_device_groups()
        assert groups == []

    @pytest.mark.asyncio
    async def test_with_groups(self, session):
        resp = json.dumps({"data": {"listDeviceGroups": {"deviceGroups": [
            {"id": "g1", "friendlyName": {"value": {"text": "Group 1"}},
             "memberDevices": {"items": [{"id": "e1"}, {"id": "e2"}]}},
        ]}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        groups = await session.fetch_device_groups()
        assert len(groups) == 1
        assert groups[0].name == "Group 1"
        assert groups[0].member_endpoint_ids == {"e1", "e2"}

    @pytest.mark.asyncio
    async def test_error(self, session):
        resp = json.dumps({"errors": [{"message": "Query failed"}]})
        session.evaluate.return_value = _make_envelope(body=resp)
        with pytest.raises(GraphQLErrors):
            await session.fetch_device_groups()


class TestGroupMutations:
    @pytest.mark.asyncio
    async def test_rename(self, session):
        resp = json.dumps({"data": {"updateDeviceGroup": {"deviceGroup": {"id": "g1"}}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        result = await session.rename_device_group("g1", "New Name")
        assert result is True

    @pytest.mark.asyncio
    async def test_rename_error(self, session):
        resp = json.dumps({"errors": [{"message": "Not found"}]})
        session.evaluate.return_value = _make_envelope(body=resp)
        with pytest.raises(GraphQLErrors):
            await session.rename_device_group("g1", "New Name")

    @pytest.mark.asyncio
    async def test_delete(self, session):
        resp = json.dumps({"data": {"deleteDeviceGroup": {"deviceGroupId": "g1"}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        result = await session.delete_device_group("g1")
        assert result is True

    @pytest.mark.asyncio
    async def test_create(self, session):
        resp = json.dumps({"data": {"createDeviceGroup": {"deviceGroup": {
            "id": "g1", "friendlyName": {"value": {"text": "New Group"}},
            "memberDevices": {"items": []},
        }}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        group = await session.create_device_group("New Group")
        assert group.name == "New Group"
        assert group.id == "g1"

    @pytest.mark.asyncio
    async def test_create_error(self, session):
        resp = json.dumps({"errors": [{"message": "Failed"}]})
        session.evaluate.return_value = _make_envelope(body=resp)
        with pytest.raises(GraphQLErrors):
            await session.create_device_group("New Group")

    @pytest.mark.asyncio
    async def test_update_members(self, session):
        resp = json.dumps({"data": {"updateDeviceGroup": {"deviceGroup": {"id": "g1"}}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        result = await session.update_device_group_members("g1", ["e1", "e2"], "ADD")
        assert result is True


class TestDeleteDevice:
    @pytest.mark.asyncio
    async def test_success(self, session):
        session.evaluate.return_value = json.dumps({"status": 200})
        result = await session.delete_device("test_id")
        assert result is True

    @pytest.mark.asyncio
    async def test_failure(self, session):
        session.evaluate.return_value = json.dumps({"status": 404})
        result = await session.delete_device("test_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_envelope(self, session):
        session.evaluate.return_value = "not json"
        with pytest.raises(InvalidResponseError):
            await session.delete_device("test_id")

    @pytest.mark.asyncio
    async def test_with_csrf(self, session):
        session._csrf_token = "token123"
        session.evaluate.return_value = json.dumps({"status": 200})
        result = await session.delete_device("test_id")
        assert result is True
        script = session.evaluate.call_args.args[0]
        assert "token123" in script


class TestFetchAllFieldNames:
    @pytest.mark.asyncio
    async def test_basic(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"}}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Query", "kind": "OBJECT", "fields": [
                    {"name": "endpoints", "type": {"kind": "OBJECT", "name": "EndpointsConnection"}, "args": []},
                ], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Mutation", "kind": "OBJECT", "fields": [
                    {"name": "updateDeviceGroup", "type": {"kind": "OBJECT", "name": "UpdateDeviceGroupPayload"}, "args": []},
                ], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Endpoint", "kind": "OBJECT", "fields": [
                    {"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                ], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "Root Query" in text
        assert "Root Mutation" in text

    @pytest.mark.asyncio
    async def test_root_query_error(self, session):
        """Root query fetch fails gracefully."""
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": {"name": "Mutation"}}}
            })),
            _make_envelope(body=json.dumps({
                "errors": [{"message": "Type not found"}]
            })),
            _make_envelope(body=json.dumps({
                "errors": [{"message": "Type not found"}]
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Endpoint", "kind": "OBJECT", "fields": [], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "Endpoint" in text

    @pytest.mark.asyncio
    async def test_with_nested_types_and_enums(self, session):
        """Test traversal of nested types, possibleTypes, and enumValues."""
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Query", "kind": "OBJECT", "fields": [], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "connection", "type": {"kind": "INTERFACE", "name": "Connection"}, "args": []},
                    ],
                    "inputFields": None,
                    "possibleTypes": None,
                    "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Connection", "kind": "INTERFACE",
                    "fields": [],
                    "inputFields": None,
                    "possibleTypes": [{"name": "WifiConnection"}, {"name": "EthernetConnection"}],
                    "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "WifiConnection", "kind": "OBJECT",
                    "fields": [{"name": "ssid", "type": {"kind": "SCALAR", "name": "String"}, "args": []}],
                    "inputFields": None,
                    "possibleTypes": None,
                    "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "EthernetConnection", "kind": "OBJECT",
                    "fields": [],
                    "inputFields": None,
                    "possibleTypes": None,
                    "enumValues": None,
                }}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "possibleTypes: WifiConnection, EthernetConnection" in text
        assert "ssid: String" in text

    @pytest.mark.asyncio
    async def test_no_mutation_type(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Query", "kind": "OBJECT", "fields": [], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Endpoint", "kind": "OBJECT", "fields": [], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "no mutation root type" in text


class TestCheckLoginStatus:
    @pytest.mark.asyncio
    async def test_success(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Endpoint", "kind": "OBJECT", "fields": [
                    {"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []},
                    {"name": "legacyAppliance", "type": {"kind": "OBJECT", "name": "LegacyAppliance"}, "args": []},
                ], "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({"data": {"endpoints": {"items": []}}})),
        ]
        await session.check_login_status()
        assert session._logged_in is True

    @pytest.mark.asyncio
    async def test_failure(self, session):
        session.evaluate.return_value = _make_envelope(status=500, body="error")
        await session.check_login_status()
        assert session._logged_in is False


class TestIntrospectTypeDetails:
    @pytest.mark.asyncio
    async def test_success(self, session):
        resp = json.dumps({"data": {"__type": {"name": "Endpoint", "kind": "OBJECT", "fields": [], "inputFields": None, "possibleTypes": None, "enumValues": None}}})
        session.evaluate.return_value = _make_envelope(body=resp)
        result = await session._introspect_type_details("Endpoint")
        assert result["name"] == "Endpoint"

    @pytest.mark.asyncio
    async def test_error(self, session):
        resp = json.dumps({"errors": [{"message": "Type not found"}]})
        session.evaluate.return_value = _make_envelope(body=resp)
        with pytest.raises(GraphQLErrors):
            await session._introspect_type_details("Invalid")


class TestAlexaWebEnginePage:
    def test_block_external_nav_different_host(self, session):
        page = session._page
        page._block_external_nav = True
        with patch.object(page, 'url', return_value=QUrl("https://alexa.amazon.com")):
            result = page.acceptNavigationRequest(
                QUrl("https://evil.com"), QWebEnginePage.NavigationTypeLinkClicked, True
            )
        assert result is False

    def test_block_external_nav_same_host(self, session):
        page = session._page
        page._block_external_nav = True
        with patch.object(page, 'url', return_value=QUrl("https://alexa.amazon.com")):
            result = page.acceptNavigationRequest(
                QUrl("https://alexa.amazon.com/somepage"),
                QWebEnginePage.NavigationTypeLinkClicked,
                True,
            )
        assert result is True

    def test_block_external_nav_not_blocking(self, session):
        page = session._page
        page._block_external_nav = False
        with patch.object(page, 'url', return_value=QUrl("https://alexa.amazon.com")):
            result = page.acceptNavigationRequest(
                QUrl("https://evil.com"), QWebEnginePage.NavigationTypeLinkClicked, True
            )
        assert result is True

    def test_block_external_nav_sub_frame(self, session):
        page = session._page
        page._block_external_nav = True
        with patch.object(page, 'url', return_value=QUrl("https://alexa.amazon.com")):
            result = page.acceptNavigationRequest(
                QUrl("https://evil.com"), QWebEnginePage.NavigationTypeLinkClicked, False
            )
        assert result is True


class TestLoggedInProperty:
    def test_logged_in_property(self, session):
        assert session.logged_in is False
        session._logged_in = True
        assert session.logged_in is True


class TestLoadSignInPage:
    def test_load_sign_in_page(self, session, qtbot):
        signals = []
        session.is_loading.connect(lambda v: signals.append(("is_loading", v)))
        session.last_error.connect(lambda v: signals.append(("last_error", v)))
        session.load_sign_in_page()
        assert session._should_check_login is False
        assert ("is_loading", True) in signals
        assert ("last_error", "") in signals


class TestLoadAlexaHost:
    def test_load_alexa_host(self, session, qtbot):
        signals = []
        session.is_loading.connect(lambda v: signals.append(("is_loading", v)))
        session.last_error.connect(lambda v: signals.append(("last_error", v)))
        session.load_alexa_host()
        assert session._should_check_login is True
        assert ("is_loading", True) in signals
        assert ("last_error", "") in signals


class TestEvaluate:
    @pytest.fixture
    def sess(self, qtbot):
        return AlexaSession()

    @pytest.mark.asyncio
    async def test_success(self, sess):
        sess.web_view.page().runJavaScript = lambda script, cb: cb("hello")
        result = await sess.evaluate("1+1")
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_timeout(self, sess):
        sess.web_view.page().runJavaScript = lambda script, cb: None
        with pytest.raises(AlexaSessionError, match="timed out"):
            await sess.evaluate("1+1", timeout_ms=100)


class TestAttemptAutoLogin:
    @pytest.mark.asyncio
    async def test_success(self, session):
        session._wait_for_load = AsyncMock()
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Endpoint", "kind": "OBJECT",
                                    "fields": [{"name": "id", "type": {"kind": "SCALAR", "name": "String"}, "args": []}],
                                    "inputFields": None, "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({"data": {"endpoints": {"items": []}}})),
        ]
        result = await session.attempt_auto_login()
        assert result is True
        assert session._logged_in is True

    @pytest.mark.asyncio
    async def test_failure(self, session):
        session._wait_for_load = AsyncMock()
        session.fetch_devices = AsyncMock(side_effect=HTTPError(500))
        result = await session.attempt_auto_login()
        assert result is False
        assert session._logged_in is False

    @pytest.mark.asyncio
    async def test_block_external_nav_restored(self, session):
        session._wait_for_load = AsyncMock()
        session.fetch_devices = AsyncMock(side_effect=HTTPError(500))
        assert session._page._block_external_nav is False
        await session.attempt_auto_login()
        assert session._page._block_external_nav is False


class TestOnLoadFinished:
    @pytest.mark.asyncio
    async def test_resolves_future(self, session):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        session._load_finished_future = future
        session._on_load_finished(True)
        assert future.done()
        assert not hasattr(session, '_load_finished_future')

    def test_no_future(self, session):
        session._on_load_finished(True)

    @pytest.mark.asyncio
    async def test_triggers_settled_check(self, session):
        session._should_check_login = True
        session._on_load_finished(True)
        assert session._should_check_login is False
        assert session._page._block_external_nav is True

    @pytest.mark.asyncio
    async def test_already_done_future(self, session):
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        future.set_result(None)
        session._load_finished_future = future
        session._on_load_finished(True)
        assert future.done()
        assert hasattr(session, '_load_finished_future')

    def test_emits_is_loading_false(self, session, qtbot):
        signals = []
        session.is_loading.connect(lambda v: signals.append(v))
        session._on_load_finished(True)
        assert False in signals


class TestAutoCheckAfterSettle:
    @pytest.mark.asyncio
    async def test_calls_check_login_status(self, session, monkeypatch):
        monkeypatch.setattr(asyncio, 'sleep', AsyncMock())
        session.check_login_status = AsyncMock()
        session._page._block_external_nav = True
        await session._auto_check_after_settle()
        assert session._page._block_external_nav is False
        session.check_login_status.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_block_nav_restored_on_error(self, session, monkeypatch):
        monkeypatch.setattr(asyncio, 'sleep', AsyncMock())
        session.check_login_status = AsyncMock(side_effect=Exception("boom"))
        session._page._block_external_nav = True
        with pytest.raises(Exception, match="boom"):
            await session._auto_check_after_settle()
        assert session._page._block_external_nav is False


class TestStartSettledCheck:
    @pytest.mark.asyncio
    async def test_forwards_to_auto_check(self, session, monkeypatch):
        called = False

        async def fake_check():
            nonlocal called
            called = True
        monkeypatch.setattr(session, '_auto_check_after_settle', fake_check)
        session._start_settled_check()
        await asyncio.sleep(0.05)
        assert called


class TestWaitForLoad:
    @pytest.mark.asyncio
    async def test_waits_for_load(self, session):
        async def resolve_after_delay():
            await asyncio.sleep(0.05)
            session._on_load_finished(True)

        task = asyncio.ensure_future(resolve_after_delay())
        await session._wait_for_load()
        assert not hasattr(session, '_load_finished_future')
        await task


class TestDeleteDeviceEncodeError:
    @pytest.mark.asyncio
    async def test_encode_error(self, session):
        with patch.object(AlexaSession, '_encode_uri_component', return_value=None):
            with pytest.raises(InvalidResponseError, match="Could not encode"):
                await session.delete_device("test_id")


class TestFetchRootTypeFieldsNoSchema:
    @pytest.mark.asyncio
    async def test_no_schema(self, session):
        session.evaluate.return_value = _make_envelope(body=json.dumps({"data": {}}))
        with pytest.raises(GraphQLErrors):
            await session._fetch_root_type_fields()


class TestIntrospectType:
    @pytest.mark.asyncio
    async def test_no_fields(self, session):
        session.evaluate.return_value = _make_envelope(body=json.dumps({
            "data": {"__type": {"name": "Foo", "kind": "OBJECT"}}
        }))
        with pytest.raises(GraphQLErrors):
            await session._introspect_type("Foo")


class TestFetchAllFieldNamesAdvanced:
    @pytest.mark.asyncio
    async def test_root_raises_exception(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({"data": {}})),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Endpoint", "kind": "OBJECT",
                                    "fields": [], "inputFields": None,
                                    "possibleTypes": None, "enumValues": None}}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "Endpoint" in text

    @pytest.mark.asyncio
    async def test_visited_continue(self, session):
        evaluate_calls = []

        def tracking_side_effect(*args):
            evaluate_calls.append(args)
            return _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Dummy", "kind": "OBJECT",
                                    "fields": [], "inputFields": None,
                                    "possibleTypes": None, "enumValues": None}}
            }))

        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Query", "kind": "OBJECT",
                                    "fields": [], "inputFields": None,
                                    "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "a", "type": {"kind": "OBJECT", "name": "TypeA"}, "args": []},
                        {"name": "b", "type": {"kind": "OBJECT", "name": "TypeB"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "TypeA", "kind": "OBJECT",
                    "fields": [
                        {"name": "b", "type": {"kind": "OBJECT", "name": "TypeB"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "TypeB", "kind": "OBJECT",
                    "fields": [],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "TypeA" in text
        assert "TypeB" in text

    @pytest.mark.asyncio
    async def test_introspect_type_details_error(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Query", "kind": "OBJECT",
                                    "fields": [], "inputFields": None,
                                    "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "broken", "type": {"kind": "OBJECT", "name": "BrokenType"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({"errors": [{"message": "Not found"}]})),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "Endpoint" in text

    @pytest.mark.asyncio
    async def test_enum_values_displayed(self, session):
        session.evaluate.side_effect = [
            _make_envelope(body=json.dumps({
                "data": {"__schema": {"queryType": {"name": "Query"}, "mutationType": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {"name": "Query", "kind": "OBJECT",
                                    "fields": [], "inputFields": None,
                                    "possibleTypes": None, "enumValues": None}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"endpoints": {"items": [{"__typename": "Endpoint"}]}}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Endpoint", "kind": "OBJECT",
                    "fields": [
                        {"name": "connection", "type": {"kind": "OBJECT", "name": "Connection"}, "args": []},
                    ],
                    "inputFields": None, "possibleTypes": None, "enumValues": None,
                }}
            })),
            _make_envelope(body=json.dumps({
                "data": {"__type": {
                    "name": "Connection", "kind": "OBJECT",
                    "fields": None, "inputFields": None, "possibleTypes": None,
                    "enumValues": [{"name": "ACTIVE"}, {"name": "INACTIVE"}],
                }}
            })),
        ]
        text = await session.fetch_all_endpoint_field_names()
        assert "--- Connection" in text
        assert "enumValues: ACTIVE, INACTIVE" in text
