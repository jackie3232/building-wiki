"""
① 理解层 · LLM 原生（零依赖，仅标准库 urllib）
====================================================================
职责：NL -> 实例图谱【骨架】（= data 块的声明式压缩）。只做「模糊 -> 结构」的映射。

与 ④⑤ 的边界（架构设计总览.md §13.4 / §14.1 锁定）：
- 本层只产骨架：院 + 每院四至的 role / 门 / 穿堂 / 附属声明。
- **一个数字都不产** —— 面阔/进深/高度/台明/等级/材质由装配器
  （geometry.assemble_instance -> _expand_room）查知识中心补。
  数值若出自 LLM 即幻觉源，正是 §13.4 #1「确定性活不给 LLM」要挡的。
- 院名不产 —— 由 siheyuan.rules:sequence.naming 推导（命名权归图谱，不归 LLM）。

词表约束（§13.2）：dict.json 的 key 是唯一合法词表；输出中任何 role / gate.role
不在词表内即判非法，整单作废（geometry.text_to_instance 随即回落确定性基线）。
这样「幻觉出非法节点」从根上被挡住。

凭据与环境：全部来自环境变量（可选 cloudbaserc.json 取 envId），不落盘、不进代码。
  TCB_AI_KEY        API Key（必填；缺失 -> 直接抛错 -> 回落确定性基线）
  TCB_ENV_ID        环境 ID（缺省读 server/cloudbaserc.json 的 envId）
  TCB_AI_PROVIDER   模型分组，默认 cloudbase（也可 hunyuan-v3）
  TCB_AI_MODEL      具体模型，默认 hy3（hy3-preview 官方已公告将下线）
  TCB_AI_BASE       整体覆盖网关 base；默认 https://{envId}.api.tcloudbasegateway.com/v1/ai/{provider}
  TCB_AI_AUTH_STYLE Bearer（默认）| raw —— 网关两种 APIKey 传法，实测二选一
  TCB_AI_TIMEOUT    秒，默认 55（网关非流式 60s 上限，留余量）

接口：understand(text) -> plan dict。失败一律抛异常，由调用方决定回落。
"""
import json
import os
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # server/

# 骨架里允许出现在「建筑声明」上的字段（与 geometry._ROOM_DECL_KEYS 同义，此处只读不改）。
_DECL_KEYS = ("gate", "chuantang")
_SIDES = ("bei", "nan", "dong", "xi")


def _env_id():
    v = os.environ.get("TCB_ENV_ID")
    if v:
        return v.strip()
    try:
        with open(os.path.join(BASE, "cloudbaserc.json"), encoding="utf-8") as f:
            return (json.load(f) or {}).get("envId")
    except Exception:
        return None


def _cfg():
    """网关调用配置。缺 key / 缺 envId 即抛错（不静默）。"""
    key = (os.environ.get("TCB_AI_KEY") or "").strip()
    if not key:
        raise RuntimeError("① 未配置 TCB_AI_KEY：理解层不可用（回落确定性基线）")
    provider = (os.environ.get("TCB_AI_PROVIDER") or "cloudbase").strip()
    base = (os.environ.get("TCB_AI_BASE") or "").strip()
    if not base:
        env_id = _env_id()
        if not env_id:
            raise RuntimeError("① 无法确定环境 ID：请设 TCB_ENV_ID 或 TCB_AI_BASE")
        base = "https://%s.api.tcloudbasegateway.com/v1/ai/%s" % (env_id, provider)
    style = (os.environ.get("TCB_AI_AUTH_STYLE") or "bearer").strip().lower()
    return {
        "url": base.rstrip("/") + "/chat/completions",
        "auth": key if style == "raw" else ("Bearer " + key),
        "model": (os.environ.get("TCB_AI_MODEL") or "hy3").strip(),
        "timeout": int(os.environ.get("TCB_AI_TIMEOUT") or 55),
    }


# ---------------------------------------------------------------- 词表 / 上下文
def skeleton_of(courtyards):
    """装配态 courtyards -> 声明式骨架（剥离全部数值）。

    两个用途：① 生成 prompt 里的 few-shot 示例（来自 build_instance，与装配器同源，
    永不漂移）；② 闭合性自测（骨架 -> assemble_instance 应逐字节还原）。
    """
    out = []
    for c in courtyards:
        enc_in = c.get("enclosure") or {}
        enc = {"relation": enc_in.get("relation") or "weihe"}
        for side in _SIDES:
            r = enc_in.get(side)
            if isinstance(r, dict) and r.get("role"):
                spec = {"role": r["role"]}
                for k in _DECL_KEYS:
                    if k in r:
                        spec[k] = r[k]
                enc[side] = spec
        for k in ("beimen", "nanmen"):
            r = enc_in.get(k)
            if isinstance(r, dict) and r.get("role"):
                enc[k] = {"role": r["role"]}
        spec = {"sequence": c.get("sequence"), "enclosure": enc}
        if c.get("perimeter"):
            spec["perimeter"] = True
        if c.get("peripheral"):
            spec["peripheral"] = [{"role": p["role"]} for p in c["peripheral"]
                                  if isinstance(p, dict) and p.get("role")]
        out.append(spec)
    return {"jin": len(courtyards), "courtyards": out}


def _vocab_block(dict_doc):
    """合法词表：只列「空间角色」（骨架里只会出现这一类 key）。"""
    items = (dict_doc.get("空间角色") or {})
    return "、".join("%s=%s" % (k, (v or {}).get("label", k)) for k, v in items.items())


def _rule_hints(rules_doc, dict_doc):
    """规制要点：从 siheyuan.rules 的 position / orientation 生成可读提示。

    事实源仍是规则库（这里只做投影），因此规则一改，提示随之改，不会两处漂移。
    """
    labels = {}
    for cat, items in (dict_doc or {}).items():
        if isinstance(items, dict):
            for k, v in items.items():
                if isinstance(v, dict) and isinstance(v.get("label"), str):
                    labels[k] = v["label"]
    lines = []
    for r in (rules_doc.get("position") or []):
        role = r.get("role")
        if role:
            lines.append("- %s：%s" % (labels.get(role, role), (r.get("desc") or "").strip()))
    for r in (rules_doc.get("orientation") or []):
        role = r.get("role")
        if role:
            lines.append("- %s：%s" % (labels.get(role, role), (r.get("desc") or "").strip()))
    return "\n".join(lines)


def _system_prompt(dict_doc, rules_doc):
    from engine.geometry import build_instance
    examples = []
    for jin in (1, 3):
        sk = skeleton_of(build_instance(jin)["data"]["courtyards"])
        examples.append("【示例：%d 进】\n%s" % (jin, json.dumps(sk, ensure_ascii=False, indent=2)))
    return """你是「北京四合院实例图谱」生成器。把用户的自然语言需求，翻译成一张**【实例图谱骨架】**。

## 输出格式（严格 JSON，不要 markdown 代码围栏，不要任何解释文字）
{
  "jin": <整数，院落进数，1-10>,
  "courtyards": [
    {
      "sequence": <整数，第几进，最南为 1，向北递增>,
      "enclosure": {
        "bei":  {"role": "<词表key>", "gate": {"role": "<词表key>"}},   // 北侧建筑；gate=嵌在它身上的门（后门，默认不设，见规制要点）
        "nan":  {"role": "<词表key>", "gate": {"role": "<词表key>"}},   // 南侧建筑；gate=嵌在它身上的门（宅门）
        "dong": {"role": "<词表key>"},                      // 东侧建筑
        "xi":   {"role": "<词表key>"},                      // 西侧建筑
        "beimen": {"role": "<词表key>"}                     // 该院北墙上的门（垂花门）
      },
      "perimeter": true,                          // 该院有院墙（通常为 true）
      "peripheral": [{"role": "<词表key>"}]       // 附属物（影壁等），可选
    }
  ]
}

## 硬约束（违反即作废）
1. 只输出 JSON。不要解释、不要 ``` 围栏、不要注释。
2. role 与 gate.role **只能取下方词表里的 key**，不得自造、不得写中文、不得写拼音以外的任何形式。
3. **绝对不要输出任何尺寸数字**（面阔、进深、高度、台明、等级、材质）——你只声明"哪一侧有什么建筑、门开在哪"，尺寸由引擎查知识中心自动补齐。
4. 不要输出坐标、方向向量、镜像等几何动作。
5. **不要写院名**（外院/内院/后罩院…）——由系统按进数规则推导。你只给 sequence。
6. courtyards 的条目数必须正好等于 jin，sequence 从 1 连续到 jin。
7. 只输出 JSON 对象本身，第一个字符必须是 {。

## 合法词表（空间角色）
%s

## 规制要点（源自规则库，必须遵守）
%s

%s
""" % (_vocab_block(dict_doc), _rule_hints(rules_doc, dict_doc), "\n\n".join(examples))


# ---------------------------------------------------------------- 调用 / 解析 / 校验
def _chat(messages, cfg):
    body = json.dumps({"model": cfg["model"], "stream": False,
                       "temperature": 0, "messages": messages}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(cfg["url"], data=body, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": cfg["auth"],
    })
    try:
        with urllib.request.urlopen(req, timeout=cfg["timeout"]) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError("① 网关 %s：%s" % (e.code, detail)) from None
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("① 网关无 choices：%s" % json.dumps(data, ensure_ascii=False)[:300])
    return (choices[0].get("message") or {}).get("content") or ""


def _extract_json(text):
    """从模型输出里取出 JSON 对象（容错剥 ``` 围栏与前后缀）。"""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("① 产物中找不到 JSON 对象：%r" % (text or "")[:200])
    return json.loads(s[i:j + 1])


def _legal_roles(dict_doc, type_doc):
    """合法 role 集 = 类型图谱 roles ∪ 命名字典「空间角色」。"""
    roles = set((type_doc.get("roles") or {}).keys())
    roles |= set((dict_doc.get("空间角色") or {}).keys())
    return roles


def _check_room(spec, roles, where):
    if not isinstance(spec, dict):
        raise ValueError("① 产物非法：%s 不是对象" % where)
    role = spec.get("role")
    if role not in roles:
        raise ValueError("① 产物非法：%s 的 role=%r 不在合法词表（幻觉节点）" % (where, role))
    gate = spec.get("gate")
    if gate is not None:
        if not isinstance(gate, dict) or gate.get("role") not in roles:
            raise ValueError("① 产物非法：%s 的 gate.role 不在合法词表" % where)


def _validate(plan, roles):
    """词表 + 结构校验。任一项不过 -> 抛错 -> 调用方回落确定性基线。"""
    if not isinstance(plan, dict):
        raise ValueError("① 产物非法：不是 JSON 对象")
    specs = plan.get("courtyards")
    if not isinstance(specs, list) or not specs:
        raise ValueError("① 产物非法：courtyards 缺失或为空")
    try:
        jin = int(plan.get("jin"))
    except Exception:
        raise ValueError("① 产物非法：jin 不是整数：%r" % (plan.get("jin"),)) from None
    if jin < 1 or jin > 10:
        raise ValueError("① 产物非法：jin=%d 超出 1-10" % jin)
    if len(specs) != jin:
        raise ValueError("① 产物非法：jin=%d 但 courtyards 有 %d 项" % (jin, len(specs)))
    seen = set()
    for i, spec in enumerate(specs):
        if not isinstance(spec, dict):
            raise ValueError("① 产物非法：courtyards[%d] 不是对象" % i)
        seq = spec.get("sequence")
        if not isinstance(seq, int) or not (1 <= seq <= jin):
            raise ValueError("① 产物非法：courtyards[%d].sequence=%r 非法" % (i, seq))
        if seq in seen:
            raise ValueError("① 产物非法：sequence %d 重复" % seq)
        seen.add(seq)
        enc = spec.get("enclosure")
        if not isinstance(enc, dict):
            raise ValueError("① 产物非法：courtyards[%d].enclosure 缺失" % i)
        for side in _SIDES:
            if side in enc and enc[side] is not None:
                _check_room(enc[side], roles, "courtyards[%d].enclosure.%s" % (i, side))
        for k in ("beimen", "nanmen"):
            if isinstance(enc.get(k), dict):
                _check_room(enc[k], roles, "courtyards[%d].enclosure.%s" % (i, k))
        for j, p in enumerate(spec.get("peripheral") or []):
            _check_room(p, roles, "courtyards[%d].peripheral[%d]" % (i, j))
    if seen != set(range(1, jin + 1)):
        raise ValueError("① 产物非法：sequence 未覆盖 1..%d" % jin)
    return plan


def understand(text):
    """NL -> 实例图谱骨架。任何失败（无凭据 / 网络 / 非法产物）都抛异常。"""
    from engine.geometry import _load_knowledge
    rules_doc, type_doc, dict_doc = _load_knowledge()
    cfg = _cfg()
    messages = [
        {"role": "system", "content": _system_prompt(dict_doc, rules_doc)},
        {"role": "user", "content": (text or "").strip() or "建一座标准三进四合院"},
    ]
    raw = _chat(messages, cfg)
    return _validate(_extract_json(raw), _legal_roles(dict_doc, type_doc))
