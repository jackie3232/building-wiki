"""
① 智能化层 · 装配器（intelligent-layer assembly）
------------------------------------------------
build_instance / assemble_instance / _finish / _plan_by_jin 等：
把「知识包（packs/<style>/）」+「声明式骨架（LLM 出）」装配成自包含实例图谱。
纯机械推导（查表 + 拓扑），零推理；属 ① 理解层后处理，不是 ④⑤ 自动化层。

运行时：Agent 侧 skill 的 assemble.mjs 是实时装配路径；本模块是引擎侧
基线 / 落库 / 闭合自测用的同契约 Python 实现（与 assemble.mjs 零漂移）。
"""
import re

from .geometry import (
    _norms_get,
    _role_height,
    _occupancy_rules,
    _occupancy_of,
    _load_knowledge,
    _role_of,
)


def _room(role, norms, type_doc=None):
    """一栋建筑的声明：role + 尺度 + 该栋自身的属性（等级 / 材质 / 高度 / 台明）。

    属性来源：规则库 norms.<role>（height / taiming）+ 类型图谱 roles.<role>
    （level / material）。属性「长在建筑上」而不只挂在 role 上——图谱是「这一座」的
    差量，同一 role 的不同栋可有不同取值；④ 读建筑自带的 height / taiming。
    """
    n = norms.get(role, {}) or {}
    t = ((type_doc or {}).get("roles") or {}).get(role, {}) or {}
    r = {"role": role,
         "miankuo": n.get("miankuo", 5),
         "jinshen": n.get("jinshen", 3),
         # 朝院门洞：各房门窗均向院内开辟，门在明间(正中开间)。
         # **开向不进图谱**——它由房屋所在侧推得（北房朝南、南房朝北、东厢朝西、西厢朝东），
         # 属几何事实；写进图谱就变成引擎级动作了。动线(liantong)据此声明「院↔房」可通。
         "door": {"at": "mingjian"}}
    for k in ("height", "taiming"):
        if n.get(k) is not None:
            r[k] = n[k]
    for k in ("level", "material"):
        if t.get(k) is not None:
            r[k] = t[k]
    return r




def _cy(seq, name, bei=None, nan=None, dong=None, xi=None,
        beimen=None, nanmen=None, peripheral=None, perimeter=False):
    enc = {"relation": "weihe"}
    if bei: enc["bei"] = bei
    if nan: enc["nan"] = nan
    if dong: enc["dong"] = dong
    if xi: enc["xi"] = xi
    if beimen: enc["beimen"] = beimen
    if nanmen: enc["nanmen"] = nanmen
    c = {"id": f"cy{seq}", "name": name, "sequence": seq,
         "enclosure": enc, "center": {"role": "tingyuan"}}
    if perimeter:
        c["perimeter"] = True
    if peripheral:
        c["peripheral"] = peripheral
    return c


# ④ 实际消费的 norms 路径前缀：appliedRules 只保留这些前缀下的整棵子树，其余裁掉。
# 来源：grep 全文件 _norms_get(norms, (...)) 与 norms.get(...) 汇总——
#   modus / courtDepthRatio（整体）
#   room.{thickness,taimingOutset,heightDefault} / door.{width,height}
#   zhaimen.{gateSpan,height,eastMargin} / houmen.{gateSpan,westMargin} / layout.xiangfang
#   chuihuamen.{gateSpan,height,depth} / peripheral.{youlang,yingbi} / wall.{height,thickness}
#   逐角色：zhengfang/xiangfang/daozuofang/houzhaofang 的 height & taiming
#           （zhaimen/chuihuamen 的 height 经 _role_height 回落读取，一并保留其整棵子树）
_NORMS_KEEP_PREFIXES = [
    ("modus",), ("courtDepthRatio",),
    ("room",), ("door",), ("zhaimen",), ("houmen",), ("layout",), ("chuihuamen",),
    ("peripheral",), ("wall",),
    ("zhengfang",), ("xiangfang",), ("daozuofang",), ("houzhaofang",),
]




def _keep_subtree(src, prefix):
    """从 norms 取 prefix 路径下的整棵子树；任一节点缺失则返回 None（该前缀本就不被此院用到）。"""
    cur = src
    for k in prefix:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur




def _snapshot_rules(rules_doc):
    """规则库 -> appliedRules 快照：只保留 ④ 实际消费的 norms 子树，无关词条全裁。

    仍是深拷贝，instance 自包含、可脱离知识中心独立复现；但不再夹带 orientation / position /
    usage / sequence / wall 等 ④ 不读的整段规制与文字说明。裁错路径会被 _norms_get 的「缺失即报错」
    立刻暴露，所以裁剪是零风险 + 可验证的（每次改完跑零漂移复核）。
    """
    rules = rules_doc if isinstance(rules_doc, dict) else json.loads(json.dumps(rules_doc))
    full = rules.get("norms", {})
    if not isinstance(full, dict) or "modus" not in full:
        raise ValueError("图谱缺陷：siheyuan.rules 缺少 norms.modus")
    trimmed = {}
    for prefix in _NORMS_KEEP_PREFIXES:
        sub = _keep_subtree(full, prefix)
        if sub is None:
            continue
        d = trimmed
        for k in prefix[:-1]:
            d = d.setdefault(k, {})
        d[prefix[-1]] = sub
    return {"norms": trimmed}




def _jin_cond_ok(cond, jin):
    """规则库里 `when` 条件的求值（如 "jin>=4" / "jin==2" / None=恒真）。

    条件写在图谱里（业务语义），④ 只做通用求值，不把「四进院才有过厅」这类知识
    硬编码进代码。
    """
    if not cond:
        return True
    m = re.match(r"^\s*jin\s*(>=|<=|==|>|<)\s*(\d+)\s*$", str(cond))
    if not m:
        raise ValueError(f"图谱缺陷：rules 中无法求值的 when 条件「{cond}」")
    op, n = m.group(1), int(m.group(2))
    return {">=": jin >= n, "<=": jin <= n, "==": jin == n,
            ">": jin > n, "<": jin < n}[op]




def _used_terms(*docs):
    """收集若干图谱块里出现过的全部标量字符串值（用于裁剪命名字典：只带用到的词）。"""
    used = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            used.add(o)

    for d in docs:
        walk(d)
    return used




def _extract_dict(dict_doc, *docs):
    """命名字典子集：只保留被用到的词条（按类别裁剪）。

    判据同「附属只带用到的」——删掉任一条，图谱里就有解释不通的词。
    meta 段是类别说明、不是词条，整段保留。
    """
    if not dict_doc:
        return None
    used = _used_terms(*docs)
    out = {}
    for cat, entries in dict_doc.items():
        if cat == "meta" or not isinstance(entries, dict):
            out[cat] = entries
            continue
        keep = {k: v for k, v in entries.items() if k in used}
        if keep:
            out[cat] = keep
    return out




def _wrap(jin, courtyards, rules_doc, dict_doc=None, style="siheyuan"):
    """instance = data（实例图谱）+ appliedDict / appliedRules（用到的附属知识）。

    两个附属块都是知识中心的**按需子集**：只带解释本实例用得到的部分，无关的不带。
    - appliedRules：只保留 ④ 实际消费的 norms 子树（见 _snapshot_rules）。
    - appliedDict：只保留被用到的词条（见 _extract_dict）。
    类型图谱(appliedType) 已移除——它的信息（每角色 level/material）在 build_instance 阶段
    已落到 data 建筑自带属性上，④ 不再读类型图谱，故 instance 不必再携带它。
    仍为深拷贝，使 instance 自包含、可脱离知识中心独立复现。

    style 即知识包标识（packs/<style>/），写进 instance 供 ④⑤ / 校验器按包取知识。
    """
    data = {"type": style, "jin": jin, "courtyards": courtyards}
    rules_snap = _snapshot_rules(rules_doc)
    inst = {
        "style": style,
        "meta": {
            "type": style,
            "desc": f"{style} {jin}进实例（由类型图谱+规则库合成，工程文件·自包含）",
            "generatedBy": "build_instance (① placeholder)",
            "zeroCoord": True,
        },
        "data": data,
        "appliedRules": rules_snap,
    }
    if dict_doc is not None:
        # 裁剪输入 = 主内容 + 附属 rules 快照（它们引用的词同样算「用到了」）
        inst["appliedDict"] = _extract_dict(dict_doc, data, rules_snap)
    return inst




def _court_namer(rules_doc, dict_doc):
    """院名解析器：返回 court_name(k, jin) -> 中文院名。

    院名唯一事实源 = siheyuan.rules:sequence.naming（图谱驱动）。本层只做「按序求值、首个命中者胜出」，
    不硬编码院名映射；规则里的 name 是命名字典 key，中文名一律由字典 label 给出（字典是命名权威）。
    """
    _naming = (rules_doc.get("sequence") or {}).get("naming") or {}
    _naming_rules = _naming.get("rules") or []
    _naming_fallback = _naming.get("fallback") or {}
    if not _naming_rules or not _naming_fallback:
        raise ValueError("图谱缺陷：siheyuan.rules 缺少 sequence.naming.rules / .fallback")
    CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
              6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}

    def _lbl(key):
        """院名 key -> 字典 label。取不到即报错：缺词条是图谱缺陷，不静默兜底。"""
        for cat in ("院落", "空间角色"):
            v = (dict_doc.get(cat) or {}).get(key)
            if isinstance(v, dict) and isinstance(v.get("label"), str):
                return v["label"]
        raise ValueError("图谱缺陷：院名 key「%s」在命名字典「院落/空间角色」中无 label" % key)

    def court_name(k, jin):
        """第 k 进（共 jin 进）的院名。规则逐条见 siheyuan.rules:sequence.naming（含各条 why）。"""
        for r in _naming_rules:
            at = r.get("at")
            if at == "last":
                if k != jin:
                    continue
            elif at != k:
                continue
            if "jinEq" in r and jin != r["jinEq"]:
                continue
            if "jinGte" in r and jin < r["jinGte"]:
                continue
            return _lbl(r["name"])
        n = k - _naming_fallback.get("ordinalFrom", 2)
        if n < 2:
            # fallback 只服务「同类多次出现」的次院（序数≥2）。落到这里说明规则表有洞：
            # 该进既无规则命中、又不属于次院 —— 是图谱缺陷，报错而不吐「内院·0」这种假名。
            raise ValueError("图谱缺陷：第 %d 进（共 %d 进）在 sequence.naming 中无规则命中，"
                             "且不满足 fallback 序数（序数算出为 %d）" % (k, jin, n))
        return "%s·%s" % (_lbl(_naming_fallback["name"]), CN_NUM.get(n, str(n)))

    return court_name




def _plan_by_jin(jin, norms, type_doc, court_name, rules_doc):
    """① 确定性生成器：按进数合成 courtyards。

    角色与四至**一律取自 rules.occupancy（院落四至默认构成）**——本函数不含任何角色硬编，
    只做「读表 → 查 norms / 类型图谱补数值 → 交给 _finish」。规则改则生成随之改，不可能两处漂移。

    它同时是确定性基线（build_instance）的生成段，供验证与落库使用。

    其他已知点（原散在本函数的注释，现归位）：
      - 游廊暂不生成：抄手游廊是内院环形通道的细部做法，留待「加细节」阶段单独讨论其形制与归属
        （类型图谱 peripheral.youlang 亦标【当前不启用】）。
      - 后门（houmen）是**条件性**构件，不属「每进默认构成」——仅当用户明确提到「宅后临街 / 开后门」
        才在图谱里加，见 siheyuan.rules:position.houmen（用户 2026-09-20 定：默认不设）。
      - 穿堂是正房的一种**做法**（明间南北贯通），随正房归属本院，**不是门**（故图谱记 ring.nan.thru，不记 gate）。
    """
    occ_rules = _occupancy_rules(rules_doc)

    courtyards = []
    for k in range(1, jin + 1):
        rule = _occupancy_of(k, jin, occ_rules)
        sides = rule.get("sides") or {}
        kwargs = {}
        for side in ("bei", "nan", "dong", "xi"):
            spec = sides.get(side)
            if not spec:
                continue              # 该侧无建筑：院墙环自动补独立院墙（yuanqiang）
            room = _room(spec["role"], norms, type_doc)
            for dk in _ROOM_DECL_KEYS:   # gate / chuantang —— 骨架允许的建筑级声明，原样合上
                if dk in spec:
                    room[dk] = spec[dk]
            kwargs[side] = room
        beimen = rule.get("beimen")
        peripheral = rule.get("peripheral") or []
        courtyards.append(_cy(
            k, court_name(k, jin),
            beimen={"role": beimen["role"]} if beimen else None,
            peripheral=[{"role": p["role"]} for p in peripheral] if peripheral else None,
            perimeter=bool(rule.get("perimeter")),
            **kwargs))
    return courtyards




def _finish(jin, courtyards, rules_doc, dict_doc, omit=None, style="siheyuan"):
    """装配收尾：omit 裁剪 -> usage 标注 -> 院角色判定 -> ring 声明 -> 打包附属知识。

    纯机械推导（查表 + 拓扑），零推理。确定性生成器（_plan_by_jin）与 LLM 骨架（assemble_instance）
    共用此段，因此两条路产出的 instance 形状必然一致。
    """
    # 应用 omit：去掉指定侧的建筑（模拟"去掉某厢房"等变体，验证"去掉建筑→外墙自动补上"）。
    # 纯图谱层声明变更，几何层零改动——这正是 boundarySegmentRealization（院墙环分段实现）模型内禀性质。
    omit = set(omit or [])
    for c in courtyards:
        enc = c.get("enclosure", {})
        for side in ("bei", "nan", "dong", "xi"):
            role = _role_of(enc.get(side), None)
            if role and f"{role}_{side}" in omit:
                enc[side] = None

    # 用途(usage)：图谱声明「某角色在某情形下作何用途」——如四进院第二进院正位房作过厅。
    # role 不变、只多一个用途语义（可逆：usage=guoting ⇄「过厅」）。
    # ④ 不自行判断谁是过厅，只按 rules.usage 落字段（图谱驱动）。
    # 必须在 role 标注之前执行——否则主院判定看不到过厅标记，会把「前堂」误当主院。
    for u in (rules_doc.get("usage") or []):
        u_role, u_use, u_at, u_cond = u.get("role"), u.get("usage"), u.get("at"), u.get("when")
        if not u_role or not u_use or not u_at or not _jin_cond_ok(u_cond, jin):
            continue
        if u_at == "erjinyuan_zhengwei":
            target = (courtyards[1].get("enclosure") or {}) if len(courtyards) > 1 else {}
            nm = target.get("bei")
            if nm and nm.get("role") == u_role:
                nm["usage"] = u_use

    # 标注每进角色(waiyuan/neiyuan/houzhaoyuan)，对齐自然语言「外院/内院/后罩院」层级描述
    # neiyuan = 正房所在的主院（后寝）：取最靠南的正房院，但**跳过作过厅的那一进**——
    #       过厅是「前堂」，其正位房虽仍 role=zhengfang，却非后寝主院（前堂后寝，据 rules.usage）。
    # neiyuan 之前=waiyuan（外院/厅房院），之后=houzhaoyuan（后罩院及其前的次院）
    neiyuan_idx = None
    for i, c in enumerate(courtyards):
        enc = c.get("enclosure", {}) or {}
        bei = enc.get("bei") or {}
        if bei.get("role") == "zhengfang" and bei.get("usage") != "guoting":
            neiyuan_idx = i
            break
    for i, c in enumerate(courtyards):
        # 一进院（唯一一进）既是入口院又是主院，无独立院名（就叫「庭院」）→ 角色随院名取
        # tingyuan；多进时正房所在的主院才叫内院 neiyuan（定：一进不叫内院）。
        if neiyuan_idx is None or i == neiyuan_idx:
            c["role"] = "tingyuan" if len(courtyards) == 1 else "neiyuan"
        elif i < neiyuan_idx:
            bei = (c.get("enclosure") or {}).get("bei") or {}
            # 作过厅的那一进是「前堂」(厅房院)，进深介于外院与主院之间，故单列 tingfangyuan
            c["role"] = "tingfangyuan" if bei.get("usage") == "guoting" else "waiyuan"
        else:
            c["role"] = "houzhaoyuan"

    # 图谱层显式声明 ring：每侧墙基底(默认存在) + provider(被谁后檐墙分段实现) + gate（零坐标·语义·可逆）。
    # 几何层只消费此声明，不再自行判断 wallSharing——"先有墙、建筑分段实现替换"由此唯一驱动。
    for i, c in enumerate(courtyards):
        enc = c.get("enclosure", {})
        nr = _role_of(enc.get("bei"), None)
        sr = _role_of(enc.get("nan"), None)
        er = _role_of(enc.get("dong"), None)
        wr = _role_of(enc.get("xi"), None)
        prev_enc = courtyards[i - 1].get("enclosure", {}) if i > 0 else {}
        prev_nr = _role_of(prev_enc.get("bei"), None)
        # bei 侧
        if enc.get("beimen"):
            n_prov, n_kind, n_gate = None, "kaziqiang", "chuihuamen"
        else:
            # bei.gate = 嵌在本院北房上的对外门（后门），与首院 nan.gate=宅门 对称：
            # 它不是独立门屋，而是「把后罩房西北角那间改成门道」，故 provider 仍是该建筑。
            ngate = ((enc.get("bei") or {}).get("gate") or {}).get("role")
            n_prov, n_kind, n_gate = nr, ("houyanqiang" if nr else "weiqiang"), ngate
        # nan 侧：idx0=倒座后檐墙；否则上一进北墙承担（门洞随上一进对齐）
        if i == 0:
            s_prov, s_kind, s_gate, s_thru = sr, ("houyanqiang" if sr else "weiqiang"), (
                "zhaimen" if (enc.get("nan") or {}).get("gate") else None), None
        else:
            s_prov, s_kind = prev_nr, ("houyanqiang" if prev_nr else "weiqiang")
            if prev_enc.get("beimen"):
                s_gate, s_thru = "chuihuamen", None
            elif (prev_enc.get("bei") or {}).get("chuantang"):
                # 穿堂**不是门**：它是上一进北房「明间前后贯通」的做法，属于那座正房、
                # 随正房归属上一进院（有明确归属，不立门实体）。
                # 故 gate=Null，另记 thru：只声明「经何物进入本院」，供联通视图与巡游读取。
                s_gate, s_thru = None, {"via": "chuantang", "of": prev_nr,
                                        "courtyard": courtyards[i - 1].get("name")}
            else:
                s_gate, s_thru = None, None
        c["ring"] = {
            "bei": {"provider": n_prov, "kind": n_kind, "gate": n_gate},
            # nan.gate = 真正的门（宅门/垂花门）；nan.thru = 经上一进正房明间穿堂进入（不是门）。
            "nan": {"provider": s_prov, "kind": s_kind, "gate": s_gate, "thru": s_thru},
            "dong":  {"provider": er, "kind": "houyanqiang" if er else "weiqiang"},
            "xi":  {"provider": wr, "kind": "houyanqiang" if wr else "weiqiang"},
        }

    return _wrap(jin, courtyards, rules_doc, dict_doc, style=style)




def build_instance(jin, omit=None, style="siheyuan"):
    """① 确定性基线：按进数合成自包含 instance（读知识中心 type+rules）。

    与 LLM 路径共用 _finish 装配段，故两者产出形状一致；omit 用于模拟"去掉某侧建筑"的变体。
    style 选定知识包（packs/<style>/）；默认 siheyuan 保持向后兼容。
    """
    rules_doc, type_doc, dict_doc = _load_knowledge(style)
    norms = rules_doc.get("norms", {})
    court_name = _court_namer(rules_doc, dict_doc)
    return _finish(jin, _plan_by_jin(jin, norms, type_doc, court_name, rules_doc),
                   rules_doc, dict_doc, omit=omit, style=style)


# 骨架里允许出现的「建筑级声明」字段：声明性的（门 / 穿堂）+ 业务量（面阔…）。
# 业务量的**值域**由 rules.paramRanges 约束（校验在 Agent 侧 skill 的装配器 validatePlan 里），
# 本常量只管「可声明」。
_ROOM_DECL_KEYS = ("gate", "chuantang", "miankuo")




def _expand_room(spec, norms, type_doc):
    """骨架里的建筑声明 -> 完整建筑：role 查表补全尺度/等级/材质，声明字段原样合上。

    LLM 只写 role（+ 门/穿堂等声明），尺度数值由本函数从知识中心查表补；
    唯一例外是**业务量**（如 miankuo 面阔）——可由骨架声明，但取值须落在
    rules.paramRanges 声明的值域内（红线只禁坐标/几何量，不禁业务量；§13.4 #1）。
    """
    if not isinstance(spec, dict) or not spec.get("role"):
        raise ValueError("图谱缺陷：骨架中的建筑声明缺 role：%r" % (spec,))
    r = _room(spec["role"], norms, type_doc)
    for k in _ROOM_DECL_KEYS:
        if k in spec:
            r[k] = spec[k]
    return r




def assemble_instance(plan, style="siheyuan"):
    """① LLM 骨架 -> 自包含 instance（装配 = 查表 + 拓扑，零推理）。

    style 选定知识包（packs/<style>/）；默认 siheyuan 保持向后兼容。

    plan 形状（= 实例图谱 data 块的声明式压缩）：
      {"jin": 3,
       "courtyards": [
         {"sequence": 1,
          "enclosure": {"nan": {"role": "daozuofang", "gate": {"role": "zhaimen"}},
                        "beimen": {"role": "chuihuamen"}},
          "peripheral": [{"role": "yingbi"}], "perimeter": true},
         ...]}

    - 尺度数值（面阔/进深/高/台明/等级/材质）由 _expand_room 查知识中心补；
      业务量可在骨架声明（值域受 rules.paramRanges 约束）。
    - 院名不取自骨架，由 sequence.naming 规则推导（命名权归图谱，不归 LLM）。
    - 收尾与 build_instance 共用 _finish，故形状必然一致（零漂移）。
    """
    rules_doc, type_doc, dict_doc = _load_knowledge(style)
    norms = rules_doc.get("norms", {})
    court_name = _court_namer(rules_doc, dict_doc)

    if not isinstance(plan, dict):
        raise ValueError("图谱缺陷：理解层产物不是对象")
    specs = plan.get("courtyards") or []
    jin = int(plan.get("jin") or len(specs))
    if jin < 1 or len(specs) != jin:
        raise ValueError("图谱缺陷：jin=%s 与 courtyards 数量 %d 不符" % (plan.get("jin"), len(specs)))

    courtyards = []
    for i, spec in enumerate(specs):
        if not isinstance(spec, dict):
            raise ValueError("图谱缺陷：courtyards[%d] 不是对象" % i)
        seq = int(spec.get("sequence") or (i + 1))
        enc_in = spec.get("enclosure") or {}
        enc = {"relation": enc_in.get("relation") or "weihe"}
        for side in ("bei", "nan", "dong", "xi"):
            if isinstance(enc_in.get(side), dict):
                enc[side] = _expand_room(enc_in[side], norms, type_doc)
        # beimen / nanmen 是「门本体」声明（垂花门等），与 _cy 同形：只带 role，不带数值。
        for k in ("beimen", "nanmen"):
            if isinstance(enc_in.get(k), dict):
                enc[k] = {"role": enc_in[k]["role"]}
        c = {"id": "cy%d" % seq, "name": court_name(seq, jin), "sequence": seq,
             "enclosure": enc, "center": {"role": "tingyuan"}}
        if spec.get("perimeter"):
            c["perimeter"] = True
        if spec.get("peripheral"):
            # 与 _cy 一致：附属只记 role（其尺度由 ④ 按 rules.peripheral 取）。
            c["peripheral"] = [{"role": p.get("role")} for p in spec["peripheral"]
                               if isinstance(p, dict)]
        courtyards.append(c)

    return _finish(jin, courtyards, rules_doc, dict_doc, style=style)




def skeleton_of(courtyards):
    """装配态 courtyards -> 声明式骨架（剥离全部数值）—— assemble_instance 的逆。

    用途：① 闭合性自测（骨架 -> assemble_instance 应逐字节还原）；
          ② 与 Agent 侧 JS 装配器（skill 内 assemble.mjs）做零漂移比对
             （见 docs/cloudbase-agent-oak/_verify_port.py）。

    与 assemble_instance 互逆，故与它同处一模块，并**共用 _ROOM_DECL_KEYS**：
    骨架允许的声明字段只保留一处真源（此前 understanding.py 另立 _DECL_KEYS，
    漏了 miankuo，构成"同一事实两处表达"）。
    """
    out = []
    for c in courtyards:
        enc_in = c.get("enclosure") or {}
        enc = {"relation": enc_in.get("relation") or "weihe"}
        for side in ("bei", "nan", "dong", "xi"):
            r = enc_in.get(side)
            if isinstance(r, dict) and r.get("role"):
                spec = {"role": r["role"]}
                for k in _ROOM_DECL_KEYS:
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


# ---------------- ④ 几何计算：instance -> 构件列表（连续几何, 绝对坐标, 米, Y-up） ----------------


# 骨架里允许出现的「建筑级声明」字段：声明性的（门 / 穿堂）+ 业务量（面阔…）。
# 业务量的**值域**由 rules.paramRanges 约束（校验在 Agent 侧 skill 的装配器 validatePlan 里），
# 本常量只管「可声明」。
_ROOM_DECL_KEYS = ("gate", "chuantang", "miankuo")
