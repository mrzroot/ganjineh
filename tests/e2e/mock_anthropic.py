"""Mock of the Anthropic Messages API (port 18765) for the real Claude Code CLI.

Where this fits (see `run_e2e.sh`): Claude Code is started with `ANTHROPIC_BASE_URL` pointing here. The mock plays a
tiny two-turn conversation:

  1. First request (tools available, no tool result yet): the "model" says it will build a login endpoint and asks
     Claude Code to run the `Write` tool. The file content contains a fake API key, so the test can check that
     ganjineh's scrubber keeps it out of the shared repo.
  2. Second request (carries the tool result): the "model" says it is done and ends the turn.

Two files in `E2E_OUT` are what the test reads back:
  * `lastbody.json`      the most recent request body. run_e2e.sh greps it to prove that ganjineh's SessionStart and
                         UserPromptSubmit hook output reached the model-facing request.
  * `mock_requests.log`  one line per request: path, model, number of tools offered.

Nothing here is a real model: the replies are fixed text.
"""

import json
import os

from mock_common import OUT_DIR, MockHandler, serve, sse_event

PORT = 18765

# Fake credential planted in the file the "model" writes. Its prefix/shape matches an Anthropic key, which is exactly
# what ganjineh's scrubber must catch. run_e2e.sh greps the remote for this string (it must NOT be there).
PLANTED_SECRET = "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

PLAN_TEXT = (
    "I'll add the login endpoint. We decided to use JWT instead of server sessions because the frontend is a SPA. "
    "POST /api/login returns a token."
)
DONE_TEXT = "Done. The login endpoint POST /api/login is in backend/auth.py. TODO: add refresh tokens next step."

REQUEST_LOG = open(OUT_DIR / "mock_requests.log", "a")  # run_e2e.sh truncates it between phases


def write_tool_call():
    """The tool call the mock asks Claude Code to run: create backend/auth.py inside Alice's project."""
    project_dir = os.environ.get("E2E_PROJ", "/tmp")
    content = f"# POST /api/login\nAPI_KEY = '{PLANTED_SECRET}'\ndef login(): pass\n"
    return {
        "id": "toolu_01MOCK",
        "name": "Write",
        "input": {"file_path": os.path.join(project_dir, "backend/auth.py"), "content": content},
    }


def is_tool_result_turn(request: dict) -> bool:
    """True when the last message is Claude Code reporting a tool's output back (i.e. the second turn)."""
    messages = request.get("messages", [])
    last_content = messages[-1].get("content") if messages else None
    return isinstance(last_content, list) and any(block.get("type") == "tool_result" for block in last_content)


def plan_reply(request: dict):
    """Pick the scripted answer: returns `(content_blocks, stop_reason)`.

    A block is `("text", str)` or `("tool_use", dict)`.
    """
    if request.get("tools") and not is_tool_result_turn(request):
        return [("text", PLAN_TEXT), ("tool_use", write_tool_call())], "tool_use"
    return [("text", DONE_TEXT)], "end_turn"


def message_start(model: str) -> bytes:
    return sse_event(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": "msg_mock",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 1},
            },
        },
    )


def content_block_events(index: int, kind: str, value) -> list:
    """The start / delta / stop events that stream one content block (text, or a tool call with JSON input)."""
    if kind == "text":
        start = {"type": "text", "text": ""}
        delta = {"type": "text_delta", "text": value}
    else:
        # A tool call starts with empty input and receives the whole JSON as a single `input_json_delta`.
        start = {"type": "tool_use", "id": value["id"], "name": value["name"], "input": {}}
        delta = {"type": "input_json_delta", "partial_json": json.dumps(value["input"])}
    return [
        sse_event("content_block_start", {"type": "content_block_start", "index": index, "content_block": start}),
        sse_event("content_block_delta", {"type": "content_block_delta", "index": index, "delta": delta}),
        sse_event("content_block_stop", {"type": "content_block_stop", "index": index}),
    ]


def message_end(stop_reason: str) -> list:
    return [
        sse_event(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                "usage": {"output_tokens": 20},
            },
        ),
        sse_event("message_stop", {"type": "message_stop"}),
    ]


class AnthropicMock(MockHandler):
    def do_GET(self):
        """The models-list endpoint: an empty list is all the mock needs to answer."""
        self.send_json(b'{"data":[]}')

    def do_POST(self):
        raw_body, request = self.read_request()
        (OUT_DIR / "lastbody.json").write_bytes(raw_body)
        REQUEST_LOG.write(f"{self.path} {request.get('model')} tools={len(request.get('tools') or [])}\n")
        REQUEST_LOG.flush()

        if "count_tokens" in self.path:  # the token-counting endpoint: any number will do
            self.send_json(b'{"input_tokens": 10}')
            return

        blocks, stop_reason = plan_reply(request)
        self.start_event_stream()
        self.write_chunk(message_start(request.get("model", "claude-mock")))
        for index, (kind, value) in enumerate(blocks):
            for event in content_block_events(index, kind, value):
                self.write_chunk(event)
        for event in message_end(stop_reason):
            self.write_chunk(event)
        self.end_event_stream()


if __name__ == "__main__":
    serve(PORT, AnthropicMock)
