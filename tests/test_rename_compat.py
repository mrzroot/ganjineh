"""The project was briefly spelled "gonjineh" (0.1.0). Everything written under that name must still work and migrate."""
import json
import os
import subprocess
import sys
from pathlib import Path

from ganjineh import brain, digest, installer as I
from conftest import run, SRC


def test_old_instruction_block_is_migrated_in_place(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("# Mine\n\n<!-- gonjineh:begin -->\n## Team brain (gonjineh)\nold text\n<!-- gonjineh:end -->\n\nkeep tail\n")
    assert I.write_block(p) == "migrated"
    t = p.read_text()
    assert "gonjineh" not in t and t.count(I.BEGIN) == 1 and t.startswith("# Mine") and t.rstrip().endswith("keep tail")


def test_remove_block_handles_old_markers(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("keep\n\n<!-- gonjineh:begin -->\nx\n<!-- gonjineh:end -->\n")
    assert I.remove_block(p)
    assert p.read_text() == "keep\n"


def test_init_migrates_hooks_mcp_mdc_and_project_file(tmp_path):
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / ".cursor" / "rules").mkdir(parents=True)
    (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"Stop": [
        {"hooks": [{"type": "command", "command": "python3 -m gonjineh hook claude"}]},
        {"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
    (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"gonjineh": {"command": "gonjineh", "args": ["mcp"]}, "other": {"command": "x"}}}))
    (root / ".cursor" / "rules" / "gonjineh.mdc").write_text(I.MDC_HEAD + "<!-- gonjineh:begin -->\nx\n<!-- gonjineh:end -->\n")
    (root / ".gonjineh.json").write_text(json.dumps({"schema": 1, "project": "proj", "brain": "", "areas": {}, "pii": True}))
    env = {"GANJINEH_HOME": str(tmp_path / "home")}
    r = run(["init", "--no-prompt-recall"], root, env)
    assert r.returncode == 0, r.stderr
    assert (root / ".ganjineh.json").exists() and not (root / ".gonjineh.json").exists()
    assert not (root / ".cursor" / "rules" / "gonjineh.mdc").exists() and (root / ".cursor" / "rules" / "ganjineh.mdc").exists()
    st = json.loads((root / ".claude" / "settings.json").read_text())
    cmds = [h["command"] for g in st["hooks"]["Stop"] for h in g["hooks"]]
    assert "echo mine" in cmds and not any("gonjineh" in c for c in cmds) and any("ganjineh hook claude" in c for c in cmds)
    mcp = json.loads((root / ".mcp.json").read_text())["mcpServers"]
    assert set(mcp) == {"ganjineh", "other"}


def test_legacy_project_file_alone_is_still_found(tmp_path):
    (tmp_path / ".gonjineh.json").write_text(json.dumps({"schema": 1, "project": "p"}))
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    assert brain.find_project_root(sub) == tmp_path
    assert brain.load_project(tmp_path)["project"] == "p"


def test_codex_old_block_replaced(tmp_path):
    c = tmp_path / "config.toml"
    c.write_text('# >>> gonjineh (managed) >>>\nnotify = ["gonjineh", "hook", "codex"]\n# <<< gonjineh (managed) <<<\nmodel = "x"\n'
                 '\n# >>> gonjineh (managed) >>>\n[mcp_servers.gonjineh]\ncommand = "gonjineh"\n# <<< gonjineh (managed) <<<\n')
    I.codex_config(c)
    t = c.read_text()
    assert "gonjineh" not in t.replace("config.toml.gonjineh", "") and t.count("[mcp_servers.ganjineh]") == 1 and t.count("notify =") == 1 and 'model = "x"' in t


def test_ignore_files(tmp_path):
    assert brain.IGNORE_FILES == (".ganjinehignore", ".brainignore")
