"""Mock of the OpenAI Responses API (port 18766) for the real Codex CLI.

Where this fits (see `run_e2e.sh`): Codex is configured with a `[model_providers.mock]` entry whose `base_url` points
here. Like the Anthropic mock, it plays a tiny two-turn conversation:

  1. First request (no tool output yet): the "model" announces a login form and calls Codex's shell tool to create
     `frontend/LoginForm.tsx`. That file mentions `POST /api/login`, which is how the test later finds the session
     when Bob searches for work related to Alice's login endpoint.
  2. Second request (carries the tool output): the "model" says it is done.

Files written to `E2E_OUT`:
  * `codex_lastbody.json`  the most recent request body.
  * `codex_tools.log`      one line per request listing the tool names Codex offered. run_e2e.sh greps it for
                           `mcp__ganjineh...` to prove Codex loaded ganjineh's MCP server.

Nothing here is a real model: the replies are fixed text.
"""

import json

from mock_common import OUT_DIR, MockHandler, serve, sse_event

PORT = 18766

PLAN_TEXT = "Starting the login form. We chose React state instead of a form library because it is tiny."
DONE_TEXT = "Done: frontend/LoginForm.tsx posts to POST /api/login. TODO: show server errors next step."

SHELL_COMMAND = "mkdir -p frontend && printf '// calls POST /api/login\\nexport const LoginForm = () => null\\n' > frontend/LoginForm.tsx"

# Codex versions expose the shell under different tool names with different argument shapes.
SHELL_TOOL_NAMES = ("shell", "shell_command", "exec_command")
TOOL_OUTPUT_TYPES = ("function_call_output", "custom_tool_call_output")


def tool_names(request: dict) -> list:
    """Names of the tools Codex offered; some tools have no name and are identified by `type` instead."""
    return [tool.get("name") or tool.get("type") for tool in request.get("tools", [])]


def shell_call_arguments(shell_tool: str) -> dict:
    """The arguments object matching the shell tool this Codex version offers."""
    if shell_tool == "exec_command":
        return {"cmd": SHELL_COMMAND}
    if shell_tool == "shell":
        return {"command": ["bash", "-lc", SHELL_COMMAND]}
    return {"command": SHELL_COMMAND}  # "shell_command"


def assistant_message(text: str) -> dict:
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}


def plan_reply(request: dict) -> list:
    """The scripted output items for this request (a message, plus a shell call on the first turn)."""
    already_ran_tool = any(item.get("type") in TOOL_OUTPUT_TYPES for item in request.get("input", []))
    if already_ran_tool:
        return [assistant_message(DONE_TEXT)]
    shell_tool = next((name for name in tool_names(request) if name in SHELL_TOOL_NAMES), "shell")
    shell_call = {
        "type": "function_call",
        "name": shell_tool,
        "arguments": json.dumps(shell_call_arguments(shell_tool)),
        "call_id": "call_mock1",
    }
    return [assistant_message(PLAN_TEXT), shell_call]


# Placeholder token counts: the `response.completed` event carries a usage block, so the mock includes one.
COMPLETED_USAGE = {
    "input_tokens": 1,
    "input_tokens_details": None,
    "output_tokens": 1,
    "output_tokens_details": None,
    "total_tokens": 2,
}


class OpenAIMock(MockHandler):
    def do_POST(self):
        raw_body, request = self.read_request()
        (OUT_DIR / "codex_lastbody.json").write_bytes(raw_body)
        with open(OUT_DIR / "codex_tools.log", "a") as log:
            log.write(f"{self.path} {tool_names(request)}\n")

        self.start_event_stream()
        self.write_chunk(sse_event("response.created", {"type": "response.created", "response": {"id": "resp_mock"}}))
        for item in plan_reply(request):
            self.write_chunk(
                sse_event("response.output_item.done", {"type": "response.output_item.done", "item": item})
            )
        self.write_chunk(
            sse_event(
                "response.completed",
                {
                    "type": "response.completed",
                    "response": {"id": "resp_mock", "usage": COMPLETED_USAGE},
                },
            )
        )
        self.end_event_stream()


if __name__ == "__main__":
    serve(PORT, OpenAIMock)
