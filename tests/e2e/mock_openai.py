import json, os, http.server
OUT = os.environ.get("E2E_OUT", "/tmp/ganjineh-e2e")
os.makedirs(OUT, exist_ok=True)
def sse(ev, data): return f"event: {ev}\ndata: {json.dumps(data)}\n\n".encode()
class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("content-length", 0)); body = self.rfile.read(n)
        req = json.loads(body) if body else {}
        open(OUT + "/codex_lastbody.json","wb").write(body)
        tools = [t.get("name") or t.get("type") for t in req.get("tools", [])]
        open(OUT + "/codex_tools.log","a").write(self.path+" "+str(tools)+"\n")
        inp = req.get("input", [])
        has_out = any(i.get("type") in ("function_call_output","custom_tool_call_output") for i in inp)
        items=[]
        if not has_out:
            shell = next((t for t in tools if t in ("shell","shell_command","exec_command")), None)
            if shell == "exec_command":
                args = {"cmd":"mkdir -p frontend && printf '// calls POST /api/login\\nexport const LoginForm = () => null\\n' > frontend/LoginForm.tsx"}
            elif shell == "shell":
                args = {"command":["bash","-lc","mkdir -p frontend && printf '// calls POST /api/login\\nexport const LoginForm = () => null\\n' > frontend/LoginForm.tsx"]}
            else:
                args = {"command":"mkdir -p frontend && printf '// calls POST /api/login\\nexport const LoginForm = () => null\\n' > frontend/LoginForm.tsx"}
            items=[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Starting the login form. We chose React state instead of a form library because it is tiny."}]},
                   {"type":"function_call","name":shell or "shell","arguments":json.dumps(args),"call_id":"call_mock1"}]
        else:
            items=[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"Done: frontend/LoginForm.tsx posts to POST /api/login. TODO: show server errors next step."}]}]
        self.send_response(200); self.send_header("content-type","text/event-stream"); self.send_header("transfer-encoding","chunked"); self.end_headers()
        def w(b): self.wfile.write(f"{len(b):x}\r\n".encode()+b+b"\r\n"); self.wfile.flush()
        w(sse("response.created",{"type":"response.created","response":{"id":"resp_mock"}}))
        for it in items: w(sse("response.output_item.done",{"type":"response.output_item.done","item":it}))
        w(sse("response.completed",{"type":"response.completed","response":{"id":"resp_mock","usage":{"input_tokens":1,"input_tokens_details":None,"output_tokens":1,"output_tokens_details":None,"total_tokens":2}}}))
        self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
class S(http.server.ThreadingHTTPServer): daemon_threads=True
S(("127.0.0.1",18766),H).serve_forever()
