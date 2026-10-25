"""Loopback-only, offline reference server. Python standard library only."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import Store, Rejected

ROOT = Path(__file__).resolve().parent
FILES = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/styles.css": ("styles.css", "text/css; charset=utf-8")}


def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def json_response(self, value, status=200):
            content = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def valid_host(self):
            return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

        def do_GET(self):
            if not self.valid_host():
                return self.json_response({"error":"HOST_REFUSED"},403)
            if self.path == "/api/state":
                return self.json_response(store.summary())
            if self.path not in FILES:
                return self.json_response({"error":"NOT_FOUND"},404)
            filename, content_type = FILES[self.path]
            content = (ROOT / "web" / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(content)))
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("Content-Security-Policy","default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if not self.valid_host() or (origin and origin != "http://" + self.headers.get("Host", "")):
                return self.json_response({"error":"ORIGIN_REFUSED"},403)
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise Rejected("JSON_REQUIRED", "仅接受 JSON 请求。",415)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise Rejected("SIZE_LIMIT", "请求体为空或超出限制。",413)
                request = json.loads(self.rfile.read(length))
                if not isinstance(request,dict):
                    raise Rejected("INVALID_REQUEST", "请求必须是对象。")
                if self.path == "/api/analyze":
                    result = store.analyze(request.get("sid"),request.get("upto_seq"))
                elif self.path == "/api/feedback":
                    result = store.feedback(self.headers.get("Idempotency-Key"),request)
                else:
                    raise Rejected("NOT_FOUND", "接口不存在。",404)
                self.json_response(result)
            except Rejected as error:
                self.json_response({"error":error.code,"message":str(error)},error.status)
            except (ValueError,UnicodeError):
                self.json_response({"error":"INVALID_JSON","message":"请检查 JSON 格式。"},400)
            except Exception:
                self.json_response({"error":"LOCAL_ERROR","message":"本地服务暂不可用，请检查数据库后重试。"},503)
    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=4188)
    parser.add_argument("--db",type=Path,default=ROOT/".runtime"/"demo.sqlite")
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True,exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1",args.port),handler(Store(args.db)))
    print(f"CosmoPilot V4.0 public reference: http://127.0.0.1:{server.server_port}",flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
