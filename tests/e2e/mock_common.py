"""Plumbing shared by the two mock model servers (`mock_anthropic.py`, `mock_openai.py`).

Where this fits: `run_e2e.sh` starts one mock per vendor on localhost and points the REAL Claude Code / Codex CLI
at it. The CLI talks to the mock exactly as it would to the vendor's API (JSON request, streamed answer), which lets
the test inspect what ganjineh's hooks put into the request without needing a model or an API key.

Both vendors stream their answer as Server-Sent Events over a chunked HTTP/1.1 response. That framing is
vendor-neutral, so it lives here; the vendor-specific event shapes stay in the mock files.
"""
import http.server
import json
import os
from pathlib import Path

# Everything the mocks record (request bodies, logs) goes here; run_e2e.sh reads it back.
OUT_DIR = Path(os.environ.get("E2E_OUT", "/tmp/ganjineh-e2e"))
OUT_DIR.mkdir(parents=True, exist_ok=True)

HOST = "127.0.0.1"


def sse_event(event: str, data: dict) -> bytes:
    """One Server-Sent Event: an `event:` line, a JSON `data:` line, and a blank line."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


class MockHandler(http.server.BaseHTTPRequestHandler):
    """Base class with the HTTP details every mock needs. Subclasses implement `do_POST`."""

    # Streaming with `transfer-encoding: chunked` is only valid in HTTP/1.1.
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        """Keep stderr quiet; the mocks write their own log files instead."""

    def read_request(self):
        """Return `(raw_body, parsed_json)`. Unparseable or empty bodies give `{}` rather than an error."""
        length = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = {}
        return raw, parsed

    def send_json(self, body: bytes):
        """Reply with a small, fixed JSON document (no streaming)."""
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def start_event_stream(self):
        """Send the response headers of a streamed (SSE) answer; follow with `write_chunk` calls."""
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()

    def write_chunk(self, payload: bytes):
        """Write one HTTP chunk: its size in hex, CRLF, the bytes, CRLF. Flushed so the client sees it at once."""
        self.wfile.write(f"{len(payload):x}\r\n".encode() + payload + b"\r\n")
        self.wfile.flush()

    def end_event_stream(self):
        """The zero-length chunk that terminates a chunked response."""
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()


class ThreadingServer(http.server.ThreadingHTTPServer):
    # Do not keep the process alive for open connections when run_e2e.sh kills the mock.
    daemon_threads = True


def serve(port: int, handler_class: type) -> None:
    """Run the mock until the process is killed."""
    ThreadingServer((HOST, port), handler_class).serve_forever()
