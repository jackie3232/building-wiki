"""BUILDING.WIKI · 共享云存储读写（MVP 2.0 by-reference 基础设施）
================================================

实例图谱入参、体素 BOX 出参在本项目中通过「引用」而非「值」传递，
以绕开 OAK harness 约 10KB 的工具入参上限（实测：实例图谱 ~10KB 经
工具入参通道会被截断/损坏，pydantic 拒收，Agent 反复重试 >5min）。

引用格式（instance_ref / boxes_ref）：
  - cos:<objectKey>   云端对象存储键（生产路径：Agent 写入、MCP 读取）
  - /abs/path.json    本地文件（仅调试 / 本地联调；不进生产）

出参（boxes）由 harness 自动持久化为 <persisted-output> 引用，本模块不写。
入参（instance）由 read_instance() 从 COS / 本地读取后反序列化为 dict。

凭据与桶（与 OAK Agent 运行时同源，config.ts 已证实 Agent 持 TCB_SECRET_* 并对
本桶 oak-workspaces/* 有 CAM 签名读写权）：
  - TCB_SECRET_ID / TCB_SECRET_KEY          （必填；缺则报「缺凭据」）
  - TCB_TOKEN                               （临时凭据会话令牌，可选）
  - BW_COS_BUCKET  （默认 6275-building-wiki-d3gm9k9xwd651699f-1258039591）
  - BW_COS_REGION （默认 ap-shanghai）
"""


import json
import os
import uuid


def _cos_config():
    secret_id = os.environ.get("TCB_SECRET_ID") or os.environ.get("TENCENTCLOUD_SECRETID")
    secret_key = os.environ.get("TCB_SECRET_KEY") or os.environ.get("TENCENTCLOUD_SECRETKEY")
    token = (
        os.environ.get("TCB_TOKEN")
        or os.environ.get("TENCENTCLOUD_SESSIONTOKEN")
        or None
    )
    if not (secret_id and secret_key):
        raise RuntimeError(
            "缺少云存储凭据：请在环境变量设置 TCB_SECRET_ID / TCB_SECRET_KEY"
            "（可选 TCB_TOKEN）。本地调试请改用本地文件路径引用。"
        )
    bucket = os.environ.get(
        "BW_COS_BUCKET", "6275-building-wiki-d3gm9k9xwd651699f-1258039591"
    )
    region = os.environ.get("BW_COS_REGION", "ap-shanghai")
    return secret_id, secret_key, token, bucket, region


def _read_cos(key):
    # 延迟导入：本地联调（无凭据、无 SDK）也能跑通本地路径分支
    from qcloud_cos import CosConfig, CosS3Client

    secret_id, secret_key, token, bucket, region = _cos_config()
    config = CosConfig(
        Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token
    )
    client = CosS3Client(config)
    resp = client.get_object(Bucket=bucket, Key=key)
    raw = resp["Body"].get_raw_stream().read()
    return json.loads(raw.decode("utf-8"))


def read_instance(ref):
    """引用 -> 实例图谱 dict。

    ref 支持：
      - cos:<key>     从云端对象存储读取（生产）
      - 本地文件路径   从磁盘读取（调试）
      - 裸 key         兜底当作 COS key（便于调用方不带前缀）
    """
    if ref.startswith("cos:"):
        return _read_cos(ref[len("cos:"):])
    if os.path.isfile(ref):
        with open(ref, "r", encoding="utf-8") as f:
            return json.load(f)
    return _read_cos(ref)


def new_object_key(prefix):
    """生成一个新的 COS 对象键（<prefix>/<uuid>.json）。"""
    return "%s/%s.json" % (prefix.rstrip("/"), uuid.uuid4())


def _client():
    """构造 COS 客户端 + 桶名（复用 _cos_config 的凭据/桶/区）。"""
    from qcloud_cos import CosConfig, CosS3Client

    secret_id, secret_key, token, bucket, region = _cos_config()
    config = CosConfig(
        Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token
    )
    return CosS3Client(config), bucket


def write_json(key, obj):
    """出参写入端：把对象序列化为 JSON 写入 COS，返回 cos:<key> 引用。

    与 read_instance 的引用格式对齐（cos:<objectKey>），使体素 BOX 出参
    与实例图谱入参一样走「引用」而非「值」（by-reference 对称）。
    """
    client, bucket = _client()
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    client.put_object(
        Bucket=bucket, Key=key, Body=body, ContentType="application/json"
    )
    return "cos:" + key


def presign_url(key, expires=3600):
    """为 COS 对象生成可公网 GET 的预签名 URL。

    前端拿到 URL 直接 fetch 即「去云存储取」体素，无需 SDK / 额外鉴权。
    """
    client, bucket = _client()
    return client.get_presigned_url(
        Method="GET", Bucket=bucket, Key=key, Expired=expires
    )
