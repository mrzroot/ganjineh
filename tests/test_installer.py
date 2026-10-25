import json
from pathlib import Path
from gonjineh import installer as I


def test_block_created_appended_idempotent(tmp_path):
    p = tmp_path / "CLAUDE.md"
    assert I.write_block(p) == "created"
    assert I.write_block(p) == "unchanged"
    p.write_text("# My rules\nbe nice\n")
    assert I.write_block(p) == "appended"
    txt = p.read_text()
    assert txt.startswith("# My rules") and txt.count(I.BEGIN) == 1
    I.write_block(p)
    assert p.read_text().count(I.BEGIN) == 1


def test_remove_block_keeps_user_text(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("# Mine\nkeep me\n")
    I.write_block(p)
    assert I.remove_block(p)
    assert p.read_text() == "# Mine\nkeep me\n"


def test_remove_block_deletes_file_we_created(tmp_path):
    p = tmp_path / "GEMINI.md"
    I.write_block(p)
    I.remove_block(p)
    assert not p.exists()


def test_claude_hooks_merge_preserves_user_hooks(tmp_path):
    s = tmp_path / ".claude" / "settings.json"
    s.parent.mkdir()
    s.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
    I.claude_hooks(tmp_path)
    I.claude_hooks(tmp_path)  # idempotent
    d = json.loads(s.read_text())
    assert d["permissions"] == {"allow": ["Bash(ls)"]}
    stop = d["hooks"]["Stop"]
    assert len(stop) == 2 and sum("gonjineh hook" in h["command"] for g in stop for h in g["hooks"]) == 1
    assert set(d["hooks"]) == {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd", "PreCompact"}
    I.remove_claude_hooks(tmp_path)
    d = json.loads(s.read_text())
    assert d["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo mine" and "SessionEnd" not in d["hooks"]


def test_hook_schema_shape_matches_claude_docs(tmp_path):
    I.claude_hooks(tmp_path)
    d = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    for ev, groups in d["hooks"].items():
        for g in groups:
            for h in g["hooks"]:
                assert h["type"] == "command" and isinstance(h["command"], str) and isinstance(h["timeout"], int)


def test_no_prompt_recall_option(tmp_path):
    I.claude_hooks(tmp_path, prompt_recall=False)
    assert "UserPromptSubmit" not in json.loads((tmp_path / ".claude" / "settings.json").read_text())["hooks"]


def test_mcp_json_variants(tmp_path):
    I.mcp_json(tmp_path / ".mcp.json")
    I.mcp_json(tmp_path / ".vscode" / "mcp.json", key="servers", vscode=True)
    a = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]["gonjineh"]
    b = json.loads((tmp_path / ".vscode" / "mcp.json").read_text())["servers"]["gonjineh"]
    assert a["args"][-1] == "mcp" and b["type"] == "stdio"


def test_mcp_json_keeps_other_servers(tmp_path):
    p = tmp_path / ".cursor" / "mcp.json"
    p.parent.mkdir()
    p.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    I.mcp_json(p)
    I.remove_mcp_json(p)
    assert json.loads(p.read_text()) == {"mcpServers": {"other": {"command": "x"}}}


def test_codex_config_notify_top_level_and_backup(tmp_path):
    c = tmp_path / "config.toml"
    c.write_text('model = "gpt-5"\n[mcp_servers.x]\ncommand = "y"\n')
    assert I.codex_config(c) == "ok"
    t = c.read_text()
    assert t.index("notify") < t.index("[mcp_servers.x]")
    assert t.count("[mcp_servers.gonjineh]") == 1 and (tmp_path / "config.toml.gonjineh.bak").exists()
    I.codex_config(c)
    assert c.read_text().count("notify =") == 1 and c.read_text().count("[mcp_servers.gonjineh]") == 1
    I.remove_codex_config(c)
    assert "gonjineh" not in c.read_text() and 'model = "gpt-5"' in c.read_text()


def test_codex_existing_notify_is_not_overwritten(tmp_path):
    c = tmp_path / "config.toml"
    c.write_text('notify = ["my-notifier"]\n')
    assert "already-set" in I.codex_config(c)
    assert c.read_text().count("notify =") == 1 and "my-notifier" in c.read_text()


def test_install_and_uninstall_project(tmp_path):
    out = I.install_project(tmp_path)
    for rel in I.INSTRUCTION_FILES:
        assert (tmp_path / rel).exists()
    assert (tmp_path / ".cursor/rules/gonjineh.mdc").read_text().startswith("---\n")
    I.uninstall_project(tmp_path)
    assert not any((tmp_path / rel).exists() for rel in I.INSTRUCTION_FILES)
    assert not (tmp_path / ".mcp.json").exists()
