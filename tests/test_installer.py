"""Writing and removing ganjineh's config in each AI tool's files (ganjineh.installer).

For every file we touch: it is created, it is merged without damaging the user's own content, running it twice
changes nothing, and uninstall removes exactly what we added.
"""

import json

from ganjineh import installer


def test_block_created_appended_idempotent(tmp_path):
    p = tmp_path / "CLAUDE.md"
    assert installer.write_block(p) == "created"
    assert installer.write_block(p) == "unchanged"
    p.write_text("# My rules\nbe nice\n")
    assert installer.write_block(p) == "appended"
    txt = p.read_text()
    assert txt.startswith("# My rules") and txt.count(installer.BEGIN) == 1
    installer.write_block(p)
    assert p.read_text().count(installer.BEGIN) == 1


def test_remove_block_keeps_user_text(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("# Mine\nkeep me\n")
    installer.write_block(p)
    assert installer.remove_block(p)
    assert p.read_text() == "# Mine\nkeep me\n"


def test_remove_block_deletes_file_we_created(tmp_path):
    p = tmp_path / "GEMINI.md"
    installer.write_block(p)
    installer.remove_block(p)
    assert not p.exists()


def test_claude_hooks_merge_preserves_user_hooks(tmp_path):
    s = tmp_path / ".claude" / "settings.json"
    s.parent.mkdir()
    s.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(ls)"]},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]},
            }
        )
    )
    installer.claude_hooks(tmp_path)
    installer.claude_hooks(tmp_path)  # idempotent
    d = json.loads(s.read_text())
    assert d["permissions"] == {"allow": ["Bash(ls)"]}
    stop = d["hooks"]["Stop"]
    assert len(stop) == 2 and sum("ganjineh hook" in h["command"] for g in stop for h in g["hooks"]) == 1
    assert set(d["hooks"]) == {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd", "PreCompact"}
    installer.remove_claude_hooks(tmp_path)
    d = json.loads(s.read_text())
    assert d["hooks"]["Stop"][0]["hooks"][0]["command"] == "echo mine" and "SessionEnd" not in d["hooks"]


def test_hook_schema_shape_matches_claude_docs(tmp_path):
    installer.claude_hooks(tmp_path)
    d = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    for groups in d["hooks"].values():
        for g in groups:
            for h in g["hooks"]:
                assert h["type"] == "command" and isinstance(h["command"], str) and isinstance(h["timeout"], int)


def test_no_prompt_recall_option(tmp_path):
    installer.claude_hooks(tmp_path, prompt_recall=False)
    assert "UserPromptSubmit" not in json.loads((tmp_path / ".claude" / "settings.json").read_text())["hooks"]


def test_mcp_json_variants(tmp_path):
    installer.mcp_json(tmp_path / ".mcp.json")
    installer.mcp_json(tmp_path / ".vscode" / "mcp.json", key="servers", vscode=True)
    a = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]["ganjineh"]
    b = json.loads((tmp_path / ".vscode" / "mcp.json").read_text())["servers"]["ganjineh"]
    assert a["args"][-1] == "mcp" and b["type"] == "stdio"


def test_mcp_json_keeps_other_servers(tmp_path):
    p = tmp_path / ".cursor" / "mcp.json"
    p.parent.mkdir()
    p.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    installer.mcp_json(p)
    installer.remove_mcp_json(p)
    assert json.loads(p.read_text()) == {"mcpServers": {"other": {"command": "x"}}}


def test_codex_config_notify_top_level_and_backup(tmp_path):
    c = tmp_path / "config.toml"
    c.write_text('model = "gpt-5"\n[mcp_servers.x]\ncommand = "y"\n')
    assert installer.codex_config(c) == "ok"
    t = c.read_text()
    assert t.index("notify") < t.index("[mcp_servers.x]")
    assert t.count("[mcp_servers.ganjineh]") == 1 and (tmp_path / "config.toml.ganjineh.bak").exists()
    installer.codex_config(c)
    assert c.read_text().count("notify =") == 1 and c.read_text().count("[mcp_servers.ganjineh]") == 1
    installer.remove_codex_config(c)
    assert "ganjineh" not in c.read_text() and 'model = "gpt-5"' in c.read_text()


def test_codex_existing_notify_is_not_overwritten(tmp_path):
    c = tmp_path / "config.toml"
    c.write_text('notify = ["my-notifier"]\n')
    assert "already-set" in installer.codex_config(c)
    assert c.read_text().count("notify =") == 1 and "my-notifier" in c.read_text()


def test_install_and_uninstall_project(tmp_path):
    installer.install_project(tmp_path)
    for rel in installer.INSTRUCTION_FILES:
        assert (tmp_path / rel).exists()
    assert (tmp_path / ".cursor/rules/ganjineh.mdc").read_text().startswith("---\n")
    installer.uninstall_project(tmp_path)
    assert not any((tmp_path / rel).exists() for rel in installer.INSTRUCTION_FILES)
    assert not (tmp_path / ".mcp.json").exists()
