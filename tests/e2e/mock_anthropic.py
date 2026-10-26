import json, os, sys, http.server, threading
OUT = os.environ.get("E2E_OUT", "/tmp/ganjineh-e2e")
os.makedirs(OUT, exist_ok=True)
LOG = open(OUT + "/mock_requests.log", "a")
def sse(ev, data): return f"event: {ev}\ndata: {json.dumps(data)}\n\n".encode()
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("content-type","application/json"); b=b'{"data":[]}'; self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get("content-length", 0)); body = self.rfile.read(n)
        try: req = json.loads(body)
        except Exception: req = {}
        open(OUT + "/lastbody.json","wb").write(body)
        LOG.write(self.path + " " + str(req.get("model")) + " tools=" + str(len(req.get("tools") or [])) + "\n"); LOG.flush()
        if "count_tokens" in self.path:
            b = b'{"input_tokens": 10}'; self.send_response(200); self.send_header("content-type","application/json"); self.send_header("content-length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        msgs = req.get("messages", [])
        last = msgs[-1] if msgs else {}
        has_result = isinstance(last.get("content"), list) and any(b.get("type") == "tool_result" for b in last["content"])
        has_tools = bool(req.get("tools"))
        blocks = []
        if has_tools and not has_result:
            blocks = [("text", "I'll add the login endpoint. We decided to use JWT instead of server sessions because the frontend is a SPA. POST /api/login returns a token."),
                      ("tool_use", {"id": "toolu_01MOCK", "name": "Write", "input": {"file_path": os.path.join(os.environ.get("E2E_PROJ", "/tmp"), "backend/auth.py"), "content": "# POST /api/login\nAPI_KEY = 'sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'\ndef login(): pass\n"}})]
            stop = "tool_use"
        else:
            blocks = [("text", "Done. The login endpoint POST /api/login is in backend/auth.py. TODO: add refresh tokens next step.")]
            stop = "end_turn"
        self.send_response(200); self.send_header("content-type", "text/event-stream"); self.send_header("cache-control","no-cache"); self.send_header("transfer-encoding", "chunked"); self.end_headers()
        def w(b): self.wfile.write(f"{len(b):x}\r\n".encode() + b + b"\r\n"); self.wfile.flush()
        w(sse("message_start", {"type":"message_start","message":{"id":"msg_mock","type":"message","role":"assistant","model":req.get("model","claude-mock"),"content":[],"stop_reason":None,"stop_sequence":None,"usage":{"input_tokens":10,"output_tokens":1}}}))
        for i,(k,v) in enumerate(blocks):
            if k == "text":
                w(sse("content_block_start", {"type":"content_block_start","index":i,"content_block":{"type":"text","text":""}}))
                w(sse("content_block_delta", {"type":"content_block_delta","index":i,"delta":{"type":"text_delta","text":v}}))
            else:
                w(sse("content_block_start", {"type":"content_block_start","index":i,"content_block":{"type":"tool_use","id":v["id"],"name":v["name"],"input":{}}}))
                w(sse("content_block_delta", {"type":"content_block_delta","index":i,"delta":{"type":"input_json_delta","partial_json":json.dumps(v["input"])}}))
            w(sse("content_block_stop", {"type":"content_block_stop","index":i}))
        w(sse("message_delta", {"type":"message_delta","delta":{"stop_reason":stop,"stop_sequence":None},"usage":{"output_tokens":20}}))
        w(sse("message_stop", {"type":"message_stop"}))
        self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
class S(http.server.ThreadingHTTPServer): daemon_threads = True
S(("127.0.0.1", 18765), H).serve_forever()
