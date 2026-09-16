"""
BUILDING.WIKI · MVP 服务（重构版）
------------------------------------------------
取代旧 OCCT/STL 链路。新链路：

  实例图谱(数据中心)
      │
      │  POST /api/command  {text} 或 {graph}
      ▼
  [① 理解层 MVP 占位] text -> 种子实例（后续替换为混元 LLM 原生生成）
      ▼
  ④ 几何计算引擎（server/engine/geometry.py）
      │   实例图谱 -> 相对位置清单（米, Y-up）
      ▼
  ⑤ 几何造型引擎 BOX 出口
      │   -> 体素 BOX 清单
      ▼
  JSON {action:"model", boxes:[...]}  ──▶  前端 Three.js 体素渲染

零依赖（仅 Python 标准库 http.server），可直接 `python server/app.py` 本地跑，
也可在 CloudBase CloudRun 以 $PORT 启动（已兼容）。
"""
import json
import os
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.geometry import instance_to_boxes, text_to_instance  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")


class Handler(BaseHTTPRequestHandler):
    timeout = 15                      # 半开/闲置连接不占死线程（单线程版曾因此卡死）

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, fp, ctype):
        try:
            with open(fp, "rb") as f:
                self._send(200, f.read(), ctype)
        except Exception as e:
            self._send(404, json.dumps({"error": str(e)}, ensure_ascii=False))

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", ""):
            return self._serve_file(os.path.join(STATIC, "index.html"), "text/html; charset=utf-8")
        if p.startswith("/static/"):
            fp = os.path.normpath(os.path.join(STATIC, p[len("/static/"):]))
            if fp.startswith(STATIC) and os.path.isfile(fp):
                if fp.endswith(".js"):
                    ctype = "application/javascript; charset=utf-8"
                elif fp.endswith(".css"):
                    ctype = "text/css; charset=utf-8"
                else:
                    ctype = "application/octet-stream"
                return self._serve_file(fp, ctype)
        self._send(404, json.dumps({"error": "not found"}, ensure_ascii=False))

    def do_POST(self):
        p = urlparse(self.path).path
        if p != "/api/command":
            return self._send(404, json.dumps({"error": "not found"}, ensure_ascii=False))
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            body = {}

        if "graph" in body:
            inst = body["graph"]
        else:
            inst = text_to_instance(body.get("text", ""))

        try:
            boxes = instance_to_boxes(inst)
        except Exception as e:
            return self._send(200, json.dumps(
                {"action": "clear", "source": "error", "error": str(e)}, ensure_ascii=False))
        self._send(200, json.dumps({"action": "model", "boxes": boxes}, ensure_ascii=False))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[BUILDING.WIKI] MVP server on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
