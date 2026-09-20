"""
BUILDING.WIKI · MVP 服务（重构版）
------------------------------------------------
取代旧 OCCT/STL 链路。新链路：

  实例图谱(数据中心)
      │
      │  POST /api/command  {text} / {graph} / {graph, tour:true}
      ▼
  [① 理解层] text -> LLM 生成实例图谱骨架 -> 装配器补全为自包含 instance（无凭据/非法产物时回落确定性基线）
      ▼
  ④ 几何计算引擎（server/engine/geometry.py）
      │   实例图谱 -> 相对位置清单（米, Y-up）
      ▼
  ⑤ 几何造型引擎 BOX 出口
      │   -> 体素 BOX 清单
      ▼
  JSON {action:"model", boxes:[...], graph:{...}}
  游览（body.tour=true）时额外附 route:[{x,y,z,label,pause,look}]（由图谱+④坐标实时派生，不落盘）
  响应回传的 graph = 本次场景所依据的实例图谱；前端下次游览原样带回，保证 route 与 BOX 同源。
  同一张 graph 也是「查看图谱」视图的数据源（前端渲染成节点-边关系图，纯展示、不落盘）。

  GET /api/dict  -> 命名字典（role -> 中文名/释义），图谱视图据此显示标签，前端不硬编词表。

零依赖（仅 Python 标准库 http.server），可直接 `python server/app.py` 本地跑，
也可在 CloudBase CloudRun 以 $PORT 启动（已兼容）。
"""
import json
import os
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.geometry import (  # noqa: E402
    build_tour_path, compute_geometry, geometry_to_boxes, text_to_instance,
)

BASE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(BASE, "static")
KNOWLEDGE = os.path.join(BASE, "knowledge")


class Handler(BaseHTTPRequestHandler):
    timeout = 15                      # 半开/闲置连接不占死线程（单线程版曾因此卡死）

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, (bytes, bytearray)) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, fp, ctype):
        try:
            with open(fp, "rb") as f:
                # 本地开发期静态资源禁缓存：避免「代码已改、浏览器仍跑旧版」的假象
                self._send(200, f.read(), ctype, {"Cache-Control": "no-store, must-revalidate"})
        except Exception as e:
            self._send(404, json.dumps({"error": str(e)}, ensure_ascii=False))

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", ""):
            return self._serve_file(os.path.join(STATIC, "index.html"), "text/html; charset=utf-8")
        if p == "/api/dict":
            # 命名字典（role -> 中文名/释义）：LLM 的唯一合法词表，也供图谱视图取标签。
            # 刻意不由前端硬编 —— 词表属图谱模块，随图谱一起演进，两处维护必然漂移。
            return self._serve_file(os.path.join(KNOWLEDGE, "dict.json"),
                                    "application/json; charset=utf-8")
        if p.startswith("/static/"):
            fp = os.path.normpath(os.path.join(STATIC, p[len("/static/"):]))
            if fp.startswith(STATIC) and os.path.isfile(fp):
                if fp.endswith(".js"):
                    ctype = "application/javascript; charset=utf-8"
                elif fp.endswith(".css"):
                    ctype = "text/css; charset=utf-8"
                elif fp.endswith(".png"):
                    ctype = "image/png"
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

        text = body.get("text", "")
        if "graph" in body:
            # 显式图谱：上传/粘贴的工程文件，或前端回传的「当前场上场景」图谱
            inst = body["graph"]
        else:
            inst = text_to_instance(text)

        try:
            geo = compute_geometry(inst)          # ④ 几何计算（构件列表）
            boxes = geometry_to_boxes(geo)        # ⑤ 造型出口（体素 BOX）
        except Exception as e:
            return self._send(200, json.dumps(
                {"action": "clear", "source": "error", "error": str(e)}, ensure_ascii=False))
        # 游览意图由前端判定（属 UI 语义），后端只按 tour 标记附路线，不重复维护关键词表。
        # 响应回传 graph —— 前端把它作为「当前场景」存下，下次游览原样带回，
        # 保证 route 与场上 BOX 出自同一张图谱（否则「游览」二字会被重新解析成默认进数）。
        action = "tour" if body.get("tour") else "model"
        resp = {"action": action, "boxes": boxes, "graph": inst}
        if action == "tour":
            # 游览路线 = 由实例图谱 + ④ 实算坐标实时派生（DATA，非文件、非预生成）
            try:
                resp["route"] = build_tour_path(inst, geo)
            except Exception as e:
                resp["route"] = []
                resp["routeError"] = str(e)
        self._send(200, json.dumps(resp, ensure_ascii=False))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[BUILDING.WIKI] MVP server on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
