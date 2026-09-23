#!/usr/bin/env node
/**
 * BUILDING.WIKI · 实例上传器（Agent 原生 / Node，零依赖）
 * ============================================================
 * 把 assemble.mjs 产出的 instance.json PUT 到云存储，返回 cos:<key> 引用。
 *
 * 设计约束（assemble.mjs 同源）：skill 脚本必须自包含——只依赖 Node 内置
 * （node:fs / node:path / node:crypto / node:fetch），不 require 任何外部包。
 * 因此 COS V5 签名用手搓的 HMAC-SHA1 实现，而非 @cloudbase/node-sdk。
 *
 * 与 MCP 侧 read_instance 约定对齐：
 *   - 默认桶 = storage.py 的 BW_COS_BUCKET 默认值
 *     （6275-building-wiki-d3gm9k9xwd651699f-1258039591，ap-shanghai）
 *   - 对象 key  = instances/<uuid>.json
 *   - 引用形态 = cos:instances/<uuid>.json（MCP generate_building 按此读回）
 *
 * 凭据：TCB_SECRET_ID / TCB_SECRET_KEY（必填）；TCB_TOKEN（临时凭据选填）。
 * 也兼容 TENCENTCLOUD_SECRETID / TENCENTCLOUD_SECRETKEY / TENCENTCLOUD_SESSIONTOKEN。
 *
 * 用法：
 *   node upload_instance.mjs --file instance.json          # 打印 cos:<key>
 *   node upload_instance.mjs --file instance.json --json    # 打印 {ref,key,bucket,region}
 *   node upload_instance.mjs --stdout-only ...              # 同上，仅打印裸引用（默认）
 * 退出码非 0 = 失败（便于 Agent 判错后回落）。
 */

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));

function env(name, fallback) {
  const v = process.env[name];
  return v === undefined || v === "" ? fallback : v;
}

const SECRET_ID = env("TCB_SECRET_ID") || env("TENCENTCLOUD_SECRETID");
const SECRET_KEY = env("TCB_SECRET_KEY") || env("TENCENTCLOUD_SECRETKEY");
const TOKEN = env("TCB_TOKEN") || env("TENCENTCLOUD_SESSIONTOKEN") || null;
const BUCKET = env("BW_COS_BUCKET", "6275-building-wiki-d3gm9k9xwd651699f-1258039591");
const REGION = env("BW_COS_REGION", "ap-shanghai");

function fail(msg) {
  process.stderr.write("UPLOAD_ERROR: " + msg + "\n");
  process.exit(1);
}

if (!SECRET_ID || !SECRET_KEY) {
  fail("缺少云存储凭据：请设置 TCB_SECRET_ID / TCB_SECRET_KEY（临时凭据再补 TCB_TOKEN）。本地调试可改走文件引用，不上云。");
}

function sha1(s) {
  return crypto.createHash("sha1").update(s, "utf8").digest("hex");
}
function hmac(key, s) {
  return crypto.createHmac("sha1", key).update(s, "utf8").digest("hex");
}
function uuid() {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return crypto.randomBytes(16).toString("hex");
}

/**
 * 手搓 COS V5 签名 —— 逐行对齐官方 qcloud_cos Python SDK 的 CosAuth.__call__
 * （已读 cos-python-sdk-v5==1.9.44 源码 cos_auth.py 第 73-145 行核实）：
 *   1) 待签 format_str = method + "\n" + path + "\n" + params + "\n" + headers + "\n"
 *      （path = "/" + objectKey；params 为空；headers = 仅 host [+ x-cos-security-token]）
 *   2) 内层 sha1(format_str) → str_to_sign = "sha1\n" + signTime + "\n" + sha1 + "\n"
 *   3) signKey = HMAC(SECRET_KEY, signTime)；signature = HMAC(signKey, str_to_sign)
 *   4) header 的 key/value 用 quote(v, safe="-_.~") 规范化
 *      （关键修复：原 encodeURIComponent 对 token 里的 * ! ' ( ) ` 不编码，而服务端按
 *       quote("-_.~") 编码校验 → 永久 SignatureDoesNotMatch，且随 token 变而变；现严格对齐 SDK）
 *   5) 仅 host（及临时凭据的 x-cos-security-token）参与签名；content-type 不签名。
 */
function cosQuote(s) {
  // 等价于 Python urllib.parse.quote(s, safe="-_.~")：仅 - _ . ~ 不编码；
  // encodeURIComponent 不会编码 ! ' ( ) *，故显式补上（其余字符两者一致）。
  return encodeURIComponent(String(s))
    .replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
}

function buildAuthAndHost(method, key) {
  const host = `${BUCKET}.cos.${REGION}.myqcloud.com`;
  const path = "/" + key;
  const signed = { host };
  if (TOKEN) signed["x-cos-security-token"] = TOKEN;

  const now = Math.floor(Date.now() / 1000);
  const signTime = `${now};${now + 600}`; // KeyTime == SignTime
  const signKey = hmac(SECRET_KEY, signTime);

  const headerKeys = Object.keys(signed).map((k) => k.toLowerCase()).sort();
  const headerList = headerKeys.join(";");
  // 与 qcloud_cos 一致：key/value 均 quote("-_.~") 编码后再拼 key=value
  const httpHeaders = headerKeys
    .map((k) => `${cosQuote(k)}=${cosQuote(signed[k])}`)
    .join("&");

  // format_str 含 method + path + params(空) + headers（对齐 SDK，旧版缺 path 段）
  const formatStr = `${method.toLowerCase()}\n${path}\n\n${httpHeaders}\n`;
  const innerSha1 = sha1(formatStr);
  const strToSign = "sha1\n" + signTime + "\n" + innerSha1 + "\n";
  const signature = hmac(signKey, strToSign);

  const auth =
    "q-sign-algorithm=sha1" +
    "&q-ak=" + SECRET_ID +
    "&q-sign-time=" + signTime +
    "&q-key-time=" + signTime +
    "&q-header-list=" + headerList +
    "&q-url-param-list=" +
    "&q-signature=" + signature;

  return { host, auth };
}

function parseArgs(argv) {
  const out = { file: null, key: null, json: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--file") out.file = argv[++i];
    else if (argv[i] === "--key") out.key = argv[++i];
    else if (argv[i] === "--json") out.json = true;
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const input = args.file || path.join(HERE, "instance.json");
  if (!fs.existsSync(input)) fail(`找不到实例文件：${input}`);
  const body = fs.readFileSync(input);

  const key = args.key || `oak-workspaces/instances/${uuid()}.json`;
  const { host, auth } = buildAuthAndHost("PUT", key);
  const url = `https://${host}/${encodeURI(key)}`;

  const headers = { host, Authorization: auth, "content-type": "application/json" };
  if (TOKEN) headers["x-cos-security-token"] = TOKEN;

  let res;
  try {
    res = await fetch(url, { method: "PUT", headers, body });
  } catch (e) {
    fail(`COS PUT 请求异常：${e && e.message ? e.message : String(e)}`);
  }
  if (!res.ok) {
    let text = "";
    try { text = await res.text(); } catch { /* ignore */ }
    fail(`COS PUT 失败 ${res.status} ${res.statusText}: ${text.slice(0, 500)}`);
  }

  const ref = `cos:${key}`;
  if (args.json) {
    process.stdout.write(JSON.stringify({ ref, key, bucket: BUCKET, region: REGION }) + "\n");
  } else {
    process.stdout.write(ref + "\n");
  }
}

main().catch((e) => fail(e && e.message ? e.message : String(e)));
