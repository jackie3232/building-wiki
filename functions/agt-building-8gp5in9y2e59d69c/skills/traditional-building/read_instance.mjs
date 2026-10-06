#!/usr/bin/env node
/**
 * BUILDING.WIKI · 实例读取器（Agent 原生 / Node，零依赖）
 * ============================================================
 * 把 upload_instance.mjs 写出的 instance.json 从云存储读回（GET），打印 JSON。
 * 与 upload_instance.mjs 共用同一套手搓 COS V5 签名器（已对齐 qcloud_cos SDK）。
 *
 * 引用形态对齐 MCP 侧：cos:instances/<uuid>.json（也可传裸 key 或本地路径）。
 *
 * 凭据：TCB_SECRET_ID / TCB_SECRET_KEY（必填）；TCB_TOKEN（临时凭据选填）。
 * 也兼容 TENCENTCLOUD_SECRETID / TENCENTCLOUD_SECRETKEY / TENCENTCLOUD_SESSIONTOKEN。
 *
 * 用法：
 *   node read_instance.mjs --ref cos:instances/<uuid>.json        # 打印实例 JSON
 *   node read_instance.mjs --ref cos:instances/<uuid>.json --key  # 仅打印对象 key
 *   node read_instance.mjs --file instance.json                    # 读本地文件透传
 * 退出码非 0 = 失败（便于 Agent 判错）。
 */

import fs from "node:fs";
import crypto from "node:crypto";

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
  process.stderr.write("READ_ERROR: " + msg + "\n");
  process.exit(1);
}

function sha1(s) { return crypto.createHash("sha1").update(s, "utf8").digest("hex"); }
function hmac(key, s) { return crypto.createHmac("sha1", key).update(s, "utf8").digest("hex"); }

function cosQuote(s) {
  return encodeURIComponent(String(s))
    .replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
}

function buildAuthAndHost(method, key) {
  const host = `${BUCKET}.cos.${REGION}.myqcloud.com`;
  const p = "/" + key;
  const signed = { host };
  if (TOKEN) signed["x-cos-security-token"] = TOKEN;
  const now = Math.floor(Date.now() / 1000);
  const signTime = `${now};${now + 600}`;
  const signKey = hmac(SECRET_KEY, signTime);
  const headerKeys = Object.keys(signed).map((k) => k.toLowerCase()).sort();
  const headerList = headerKeys.join(";");
  const httpHeaders = headerKeys.map((k) => `${cosQuote(k)}=${cosQuote(signed[k])}`).join("&");
  const formatStr = `${method.toLowerCase()}\n${p}\n\n${httpHeaders}\n`;
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
  const out = { ref: null, file: null, key: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--ref") out.ref = argv[++i];
    else if (argv[i] === "--file") out.file = argv[++i];
    else if (argv[i] === "--key") out.key = true;
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.file) {
    // 本地文件透传（便于离线检视 / 调试）。
    if (!fs.existsSync(args.file)) fail(`找不到实例文件：${args.file}`);
    const txt = fs.readFileSync(args.file, "utf-8");
    if (args.key) {
      process.stdout.write(args.file + "\n");
    } else {
      process.stdout.write(txt);
    }
    return;
  }
  if (!args.ref) fail("缺少 --ref（cos:instances/<uuid>.json）或 --file（本地路径）");
  if (!SECRET_ID || !SECRET_KEY) {
    fail("缺少云存储凭据：请设置 TCB_SECRET_ID / TCB_SECRET_KEY（临时凭据再补 TCB_TOKEN）");
  }
  const key = args.ref.startsWith("cos:") ? args.ref.slice(4) : args.ref;
  if (args.key) {
    process.stdout.write(key + "\n");
    return;
  }
  const { host, auth } = buildAuthAndHost("GET", key);
  const url = `https://${host}/${encodeURI(key)}`;
  const headers = { host, Authorization: auth };
  if (TOKEN) headers["x-cos-security-token"] = TOKEN;
  let res;
  try {
    res = await fetch(url, { method: "GET", headers });
  } catch (e) {
    fail(`COS GET 请求异常：${e && e.message ? e.message : String(e)}`);
  }
  if (res.status === 404) fail(`COS 上找不到实例 ${args.ref}`);
  if (!res.ok) {
    let t = "";
    try { t = await res.text(); } catch { /* ignore */ }
    fail(`COS GET 失败 ${res.status} ${res.statusText}: ${t.slice(0, 500)}`);
  }
  const txt = await res.text();
  process.stdout.write(txt);
}

main().catch((e) => fail(e && e.message ? e.message : String(e)));
