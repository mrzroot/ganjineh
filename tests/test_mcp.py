import json

from ganjineh import core, mcp


class FakeCtx:
    pass


def test_initialize_negotiates_known_version():
    r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}, None)
    assert r["result"]["protocolVersion"] == "2024-11-05" and "tools" in r["result"]["capabilities"]
    r = mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1999"}}, None)
    assert r["result"]["protocolVersion"] == mcp.PROTOCOLS[0]


def test_tools_list_has_required_tools():
    r = mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, None)
    names = {t["name"] for t in r["result"]["tools"]}
    assert names == {"search_memory", "read_entry", "add_note", "who_knows_about", "recent"}
    for t in r["result"]["tools"]:
        assert t["inputSchema"]["type"] == "object"


def test_notification_gets_no_response_and_unknown_method_errors():
    assert mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, None) is None
    r = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"}, None)
    assert r["error"]["code"] == -32601


def test_tool_call_outside_project_reports_error_not_crash(tmp_path):
    def factory():
        raise core.NoProject("no project")
    r = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search_memory", "arguments": {"query": "x"}}}, factory)
    assert r["result"]["isError"] is True


def test_unknown_tool():
    r = mcp.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "zzz"}}, lambda: None)
    assert r["error"]["code"] == -32602


def test_serve_handles_garbage_line():
    import io
    out = io.StringIO()
    mcp.serve("/tmp", io.StringIO("garbage\n" + json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"), out)
    lines = [json.loads(l) for l in out.getvalue().splitlines()]
    assert lines[0]["error"]["code"] == -32700 and lines[1]["result"] == {}
