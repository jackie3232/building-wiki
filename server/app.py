# -*- coding: utf-8 -*-
r"""
工程数据发动机 · MVP 骨架
本地单服务：Flask serve 前端静态页 + POST /api/command（意图 → 渲染数据）

渲染数据来源（【实时】调用建模引擎）：
  每次收到 build 请求，服务端实时调用 OCCT 建模引擎（n1/modelling），把空间图谱
  编译成真实墙/板几何并导出 STL：
      引擎 <图谱.json> <shapes.json>      # 同时写出同名 .stl
  引擎是同一份源码（D:\sourcecodes\n1，经 server/engine/sync_from_n1.sh 镜像到
  server/engine/），在两个平台各编一份：
      Windows：voxelcli\main.exe（MSVC + modelling.lib + OCCT）。若 main.cpp 比
               main.exe 新（或 exe 缺失），本服务先用 MSVC 重新编译再运行——
               「需要什么编译就重新编译」。
      Linux  ：bin/voxelcli（容器构建期由 Dockerfile 的 engine-builder 阶段用
               g++/CMake 编出 ELF），直接运行，无编译步骤。
  本服务【不做】任何几何推导，只把 STL 产物交给前端渲染。
  接口契约：只返回 STL 文件名（外加 action/source/realtime 等控制字段），
  【不回传】boxes 等中间格式。

  两平台引擎都不存在时退化为「预生成产物」模式：取随包的
  data/shapes_case6.json 里的 STL 文件名返回，此时【不消费】上传图谱
  （传什么都一样）——仅兜底，正常部署（本机或容器）都有引擎，走不到该分支。
"""
import glob
import json
import os
import subprocess
import time

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATA_DIR = os.path.join(BASE_DIR, "data")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")

CLEAR_WORDS = ("清空", "清除", "清理", "移除全部")

# ---- 建模引擎（n1 modelling 原生 exe）路径 ----
IS_WINDOWS = (os.name == "nt")
N1_DIR = r"D:\sourcecodes\n1"
VOXELCLI_DIR = os.path.join(N1_DIR, "voxelcli")
MAIN_CPP = os.path.join(VOXELCLI_DIR, "main.cpp")
MAIN_EXE = os.path.join(VOXELCLI_DIR, "main.exe")
BIN_DIR = os.path.join(N1_DIR, r"bin\x64\Release")
# Linux：Docker 构建期编出的原生引擎（见 Dockerfile 的 engine-builder 阶段）
ENGINE_BIN_LINUX = os.path.join(BASE_DIR, "bin", "voxelcli")
# 默认图谱：四合院（一进四合院-东厢房开门问题.json，已落到 case_6.json）
GRAPH_PATH = os.path.join(DATA_DIR, "case_6.json")
SHAPES_PATH = os.path.join(DATA_DIR, "shapes_case6.json")
RUN_LOG = os.path.join(DATA_DIR, "modelling_run.log")

# 按平台选引擎：Windows 用 main.exe，Linux 用 bin/voxelcli。
# 二者都不存在时 ENGINE_AVAILABLE=False，退化为「预生成产物」模式（不消费图谱，仅演示）。
ENGINE_BIN = (MAIN_EXE if os.path.exists(MAIN_EXE) else None) if IS_WINDOWS \
             else (ENGINE_BIN_LINUX if os.path.exists(ENGINE_BIN_LINUX) else None)
ENGINE_AVAILABLE = ENGINE_BIN is not None


def _log_run(entry: dict) -> None:
    try:
        with open(RUN_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _needs_rebuild() -> bool:
    """main.cpp 比 main.exe 新（或 exe 缺失）则需要重编译。"""
    if not os.path.exists(MAIN_EXE):
        return True
    try:
        return os.path.getmtime(MAIN_CPP) > os.path.getmtime(MAIN_EXE)
    except OSError:
        return True


def _msvc_env():
    """构造 MSVC 编译所需 INCLUDE/LIB/PATH（用环境变量而非 /I\"含空格\"，避免被 shell 引号破坏）。"""
    vs = r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise"
    sdk = r"C:\Program Files (x86)\Windows Kits\10"
    sdkver = "10.0.22621.0"
    n1 = N1_DIR
    # OCCT 完整 inc（n1Package 版，含全部 .lxx/.hxx，STL/STEP 等导出头才能编译通过；
    # n1/occ/inc 是被裁剪版，缺 Message_Msg.lxx 等，导出代码编不过）
    occ_inc = r"D:\sourcecodes\n1Package\occt\occt_vc14-64\inc"
    includes = [
        occ_inc,
        os.path.join(n1, r"inc\modelling"),
        os.path.join(n1, r"rapidjson-1.1.0"),
        os.path.join(n1, r"cgal-5.6.1\inc"),
        os.path.join(n1, r"boost-1.6.6\inc"),
        os.path.join(sdk, f"Include\\{sdkver}\\ucrt"),
        os.path.join(sdk, f"Include\\{sdkver}\\um"),
        os.path.join(sdk, f"Include\\{sdkver}\\shared"),
    ]
    libs = [
        os.path.join(n1, r"occ\lib\x64\release"),
        BIN_DIR,
        os.path.join(sdk, f"Lib\\{sdkver}\\ucrt\\x64"),
        os.path.join(sdk, f"Lib\\{sdkver}\\um\\x64"),
    ]
    cl_glob = glob.glob(os.path.join(vs, r"VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe"))
    cl_path = cl_glob[0] if cl_glob else "cl"
    cl_dir = os.path.dirname(cl_path)
    # VC 自带标准库 include / lib（cl.exe 所在目录往上三层）：
    #   bin\Hostx64\x64 -> VC\Tools\MSVC\<ver>\include 与 lib\x64
    # 显式加入，否则手动设 INCLUDE 时 cl 不会自动补 VC 标准路径（iostream 找不到）。
    vc_include = os.path.normpath(os.path.join(cl_dir, "..", "..", "..", "include"))
    vc_lib = os.path.normpath(os.path.join(cl_dir, "..", "..", "..", "lib", "x64"))
    includes = [vc_include] + includes
    libs = [vc_lib] + libs
    env = os.environ.copy()
    env["INCLUDE"] = ";".join(includes)
    env["LIB"] = ";".join(libs)
    env["PATH"] = cl_dir + ";" + BIN_DIR + ";" + env.get("PATH", "")
    return env, cl_path


def _compile_main():
    """用 MSVC 重新编译 main.cpp → main.exe（仅当源码变更时由调用方触发）。"""
    if not os.path.exists(MAIN_CPP):
        raise FileNotFoundError("main.cpp 缺失：" + MAIN_CPP)
    env, cl_path = _msvc_env()
    libs = ("modelling.lib TKernel.lib TKMath.lib TKGeomBase.lib TKTopAlgo.lib TKPrim.lib "
            "TKBRep.lib TKGeomAlgo.lib TKG2d.lib TKBO.lib TKService.lib TKG3d.lib TKV3d.lib "
            "TKShHealing.lib TKMesh.lib TKSTL.lib TKIGES.lib TKLCAF.lib TKXCAF.lib TKXSBase.lib "
            "TKSTEP.lib TKSTEPBase.lib TKSTEPAttr.lib")
    cmd = [cl_path, "/nologo", "/O2", "/MD", "/EHsc", "/utf-8", "/std:c++17",
           "/D", "NDEBUG", "/D", "_CONSOLE", "/D", "_CRT_SECURE_NO_WARNINGS",
           "/D", "WIN32", "/D", "_WIN64",
           "main.cpp", "/link", *libs.split()]
    # 建模引擎/编译器产物可能含非 UTF-8 字节（如 name() 缓冲区脏字节），故按字节捕获、按需 replace 解码
    r = subprocess.run(cmd, cwd=VOXELCLI_DIR, env=env,
                       capture_output=True, timeout=300)
    if r.returncode != 0:
        out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError("编译 main.cpp 失败 (rc=%d):\n%s" % (r.returncode, out[-2000:]))
    if not os.path.exists(MAIN_EXE):
        raise RuntimeError("编译完成但未生成 main.exe")
    return MAIN_EXE


def _run_modelling(graph_path, out_path):
    """实时调用建模引擎生成 shapes JSON。

    返回：本次是否发生了重新编译（Linux 侧编译在容器构建期完成，恒为 False）。
    """
    # ---- Linux（容器）：引擎是构建期编好的 ELF，直接调用 --------------------
    # 无编译步骤、无 DLL 同目录依赖，故不走 _needs_rebuild()/_compile_main()/_msvc_env()。
    if not IS_WINDOWS:
        r = subprocess.run([ENGINE_BIN, graph_path, out_path],
                           capture_output=True, timeout=120)
        if r.returncode != 0:
            out = (r.stdout or b"").decode("utf-8", "replace") + \
                  (r.stderr or b"").decode("utf-8", "replace")
            raise RuntimeError("建模引擎运行失败 (rc=%d):\n%s" % (r.returncode, out[-2000:]))
        return False

    # ---- Windows（本机）：main.exe 缺失或源码更新时先重编，再运行 ----------
    recompiled = False
    if _needs_rebuild():
        try:
            _compile_main()
            recompiled = True
        except Exception as exc:  # noqa: BLE001
            # 重编失败但已有可用 exe：降级为运行旧 exe，并在日志标记
            if os.path.exists(MAIN_EXE):
                _log_run({"ts": time.time(), "event": "recompile_failed_fallback",
                          "error": str(exc)[:300]})
            else:
                raise
    if not os.path.exists(MAIN_EXE):
        raise FileNotFoundError("main.exe 缺失且编译失败")

    # 运行目录必须是 voxelcli（modelling.dll / api-ms / TK*.dll 同目录）
    env = os.environ.copy()
    env["PATH"] = BIN_DIR + ";" + VOXELCLI_DIR + ";" + env.get("PATH", "")
    r = subprocess.run([MAIN_EXE, graph_path, out_path],
                       cwd=VOXELCLI_DIR, env=env,
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
        raise RuntimeError("建模引擎运行失败 (rc=%d):\n%s" % (r.returncode, out[-2000:]))
    return recompiled


def _load_shapes() -> dict:
    with open(SHAPES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/asset/<path:filename>")
def asset(filename):
    """导出产物（真实几何 STL 等）落盘在 data/，浏览器需经此路由取回。"""
    return send_from_directory(DATA_DIR, filename)


def _is_graph(obj) -> bool:
    """图谱合法性初检：必须是含非空 buildings 数组的 dict。"""
    return isinstance(obj, dict) and isinstance(obj.get("buildings"), list) and len(obj["buildings"]) > 0


def _save_upload_graph(graph) -> str:
    """把前端上传/粘贴的图谱 JSON 落盘到 data/_up_<ts>.json，返回路径。"""
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(DATA_DIR, f"_up_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False)
    return path


def _build_from_graph(graph_path, source):
    """按图谱实时生成 STL；本机/容器有建模引擎则现场跑，否则回退随包预生成产物的 STL。

    接口契约：只返回 STL 文件名 + action/source/realtime 等控制字段，
    【不回传】boxes 等中间格式（shapes json 仍落盘 data/ 供服务端自己用）。
    """
    t0 = time.time()

    # 无任何平台引擎时（纯前端演示环境）：返回随包预生成产物的 STL 文件名。
    # 注意：此分支【不消费】graph_path，传任何图谱结果都一样——仅兜底，正常部署不会走到。
    if not ENGINE_AVAILABLE:
        try:
            shapes = _load_shapes()
        except Exception as e:  # noqa: BLE001
            return jsonify({"action": "clear", "source": "error",
                            "error": "预生成产物缺失：" + str(e)[:400]})
        _log_run({"ts": t0, "event": "build", "source": source, "realtime": False,
                  "stl": shapes.get("stl"),
                  "ms": round((time.time() - t0) * 1000)})
        return jsonify({"action": "build", "source": source, "realtime": False,
                        "recompiled": False, "stl": shapes.get("stl")})

    try:
        recompiled = _run_modelling(graph_path, SHAPES_PATH)
        shapes = _load_shapes()
        elapsed = round((time.time() - t0) * 1000)
        _log_run({"ts": t0, "event": "build", "source": source, "recompiled": recompiled,
                  "walls": shapes.get("stats", {}).get("walls"),
                  "slabs": shapes.get("stats", {}).get("slabs"),
                  "doors": shapes.get("stats", {}).get("doors"),
                  "stl": shapes.get("stl"),
                  "ms": elapsed})
        return jsonify({"action": "build", "source": source, "realtime": True,
                        "recompiled": recompiled, "stl": shapes.get("stl")})
    except Exception as e:  # noqa: BLE001 —— 异常时清空兜底，保证前端不卡死
        return jsonify({"action": "clear", "source": "error", "error": str(e)[:500]})


@app.post("/api/command")
def command():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    graph = body.get("graph")

    # 1) 上传/粘贴的图谱 JSON：落盘后实时跑建模引擎生成
    if graph is not None:
        if isinstance(graph, str):
            try:
                graph = json.loads(graph)
            except Exception:
                return jsonify({"action": "clear", "source": "error",
                                "error": "graph 不是合法 JSON 字符串"}), 400
        if not _is_graph(graph):
            return jsonify({"action": "clear", "source": "error",
                            "error": "图谱格式不正确：需含非空 buildings 数组"}), 400
        graph_path = _save_upload_graph(graph)
        return _build_from_graph(graph_path, source="uploaded")

    if not text:
        return jsonify({"error": "text 不能为空"}), 400

    # 2) 清空指令
    if any(k in text for k in CLEAR_WORDS):
        return jsonify({"action": "clear", "source": "mock"})

    # 3) 其余：用默认图谱（case_6.json）实时生成
    return _build_from_graph(GRAPH_PATH, source="case_6")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
