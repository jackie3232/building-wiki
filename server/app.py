# -*- coding: utf-8 -*-
"""
工程数据发动机 · MVP 骨架
本地单服务：Flask serve 前端静态页 + POST /api/command（NL → 意图 JSON）

LLM 双通道：
  - 环境变量 CLOUDBASE_API_KEY 存在 → 走 CloudBase AI 网关（hy3-preview，OpenAI 兼容）
  - 无 Key / 网络异常 / 解析失败   → 降级 mock 规则解析（demo 不中断）
"""
import json
import os
import re

import requests
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

ENV_ID = os.environ.get("CLOUDBASE_ENV_ID", "building-wiki-d3gm9k9xwd651699f")
API_KEY = os.environ.get("CLOUDBASE_API_KEY", "")
MODEL = "hy3-preview"
AI_URL = f"https://{ENV_ID}.api.tcloudbasegateway.com/v1/ai/cloudbase/chat/completions"

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

SYSTEM_PROMPT = (
    "你是建筑空间体素生成引擎的意图解析器。用户用自然语言描述想在 3D 场景里做什么。"
    '你只输出一个 JSON 对象，禁止输出任何其他文字、注释或代码块标记。格式：'
    '{"action":"create_box","count":N} 表示创建 N 个体素方块'
    '（N 从用户描述提取，1-30 的整数；没说数量默认 5；超过 30 取 30）；'
    '{"action":"clear"} 表示清空场景。'
    '例句：用户说"帮我创建 6 个 Box"→ 输出 {"action":"create_box","count":6}；'
    '用户说"清空"→ 输出 {"action":"clear"}。'
)


def call_llm(text: str) -> dict:
    """调 CloudBase AI 网关，返回意图 dict。"""
    resp = requests.post(
        AI_URL,
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "max_tokens": 100,
            "stream": False,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"LLM 未返回 JSON: {content[:200]}")
    return json.loads(content[start:end + 1])


CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
          "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def mock_parse(text: str) -> dict:
    """无 LLM 时的规则兜底：提取数字 + 清空关键词。"""
    t = text.strip()
    if any(k in t for k in ("清空", "清除", "清理", "移除全部")):
        return {"action": "clear"}
    n = 5
    m = re.search(r"\d+", t)
    if m:
        n = int(m.group())
    else:
        for ch in t:
            if ch in CN_NUM:
                n = CN_NUM[ch]
                break
    return {"action": "create_box", "count": _clamp(n)}


def _clamp(n) -> int:
    try:
        return max(1, min(30, int(n)))
    except (TypeError, ValueError):
        return 5


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.post("/api/command")
def command():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text 不能为空"}), 400

    # 优先 LLM，任何异常降级 mock（保证 demo 不中断）
    if API_KEY:
        try:
            intent = call_llm(text)
            if intent.get("action") == "clear":
                return jsonify({"action": "clear", "source": "llm"})
            return jsonify({"action": "create_box",
                            "count": _clamp(intent.get("count", 5)),
                            "source": "llm"})
        except Exception as e:  # noqa: BLE001 —— 兜底路径，捕获一切异常降级
            intent = mock_parse(text)
            intent["source"] = "fallback"
            intent["error"] = str(e)[:200]
            return jsonify(intent)

    intent = mock_parse(text)
    intent["source"] = "mock"
    return jsonify(intent)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
