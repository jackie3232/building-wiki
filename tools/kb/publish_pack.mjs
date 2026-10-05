#!/usr/bin/env node
/**
 * BUILDING.WIKI · 知识包发布器（零依赖 Node，复用 upload_instance.mjs 的 COS V5 签名器）
 * ============================================================================
 * 把本地 packs/<style>/ 的三件套（<style>.rules / <style>.type.json / dict.json）
 * 连同 build/ / src/ / CHANGELOG.md（若存在）上传到 COS，并写/更新
 *   cos:packs/manifest.json = { "<style>": { "version": "<v>", "base": "packs/<style>/<v>/" } }
 *
 * 这是「知识库动态化」的发布通道：知识改动只需跑本脚本上传 COS，
 * 不再需要 redeploy 函数（assemble.mjs 在后续阶段改为运行时按 manifest 拉取）。
 *
 * 凭据：TCB_SECRET_ID / TCB_SECRET_KEY（必填）；TCB_TOKEN（临时凭据选填）。
 * 兼容 TENCENTCLOUD_SECRETID / TENCENTCLOUD_SECRETKEY / TENCENTCLOUD_SESSIONTOKEN。
 *
 * 用法：
 *   node publish_pack.mjs --style siheyuan                       # 上传（版本=今天 YYYY.MM.DD）
 *   node publish_pack.mjs --style siheyuan --version 2026.10.05  # 指定版本
 *   node publish_pack.mjs --style siheyuan --packs /abs/packs    # 指定本地 packs 根
 *   node publish_pack.mjs --style siheyuan --dry-run             # 只校验+打印，不联网
 * 退出码非 0 = 失败（便于脚本判错）。
 */

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", ".."); // tools/kb -> repo root

// ───────────── COS V5 手搓签名器（与 upload_instance.mjs 同源，已实测） ─────────────
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
  process.stderr.write("PUBLISH_ERROR: " + msg + "\n");
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
  const httpHeaders = headerKeys
    .map((k) => `${cosQuote(k)}=${cosQuote(signed[k])}`).join("&");
  const formatStr = `${method.toLowerCase()}\n${p}\n\n${httpHeaders}\n`;
  const innerSha1 = sha1(formatStr);
  const strToSign = "sha1\n" + signTime + "\n" + innerSha1 + "\n";
  const signature = hmac(signKey, strToSign);
  const auth = "q-sign-algorithm=sha1" + "&q-ak=" + SECRET_ID +
    "&q-sign-time=" + signTime + "&q-key-time=" + signTime +
    "&q-header-list=" + headerList + "&q-url-param-list=" +
    "&q-signature=" + signature;
  return { host, auth };
}

async function cosPut(key, body) {
  const { host, auth } = buildAuthAndHost("PUT", key);
  const url = `https://${host}/${encodeURI(key)}`;
  const headers = { host, Authorization: auth, "content-type": "application/json" };
  if (TOKEN) headers["x-cos-security-token"] = TOKEN;
  const res = await fetch(url, { method: "PUT", headers, body });
  if (!res.ok) {
    let t = "";
    try { t = await res.text(); } catch { /* ignore */ }
    fail(`COS PUT 失败 ${res.status} ${res.statusText}: ${t.slice(0, 500)}`);
  }
}
async function cosGet(key) {
  const { host, auth } = buildAuthAndHost("GET", key);
  const url = `https://${host}/${encodeURI(key)}`;
  const headers = { host, Authorization: auth };
  if (TOKEN) headers["x-cos-security-token"] = TOKEN;
  const res = await fetch(url, { method: "GET", headers });
  if (res.status === 404) return null;
  if (!res.ok) {
    let t = "";
    try { t = await res.text(); } catch { /* ignore */ }
    fail(`COS GET 失败 ${res.status} ${res.statusText}: ${t.slice(0, 500)}`);
  }
  return await res.text();
}

// ───────────── 参数 ─────────────
function parseArgs(argv) {
  const out = { style: "siheyuan", version: null, packs: null, dryRun: false, verify: false };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--style") out.style = argv[++i];
    else if (argv[i] === "--version") out.version = argv[++i];
    else if (argv[i] === "--packs") out.packs = argv[++i];
    else if (argv[i] === "--dry-run") out.dryRun = true;
    else if (argv[i] === "--verify") out.verify = true;
    else fail(`publish_pack.mjs 不认识参数「${argv[i]}」（支持 --style / --version / --packs / --dry-run / --verify）`);
  }
  return out;
}

function todayVersion() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())}`;
}

function walk(dir, base, acc) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    const rel = path.join(base, e.name);
    if (e.isDirectory()) walk(full, rel, acc);
    else acc.push(rel);
  }
  return acc;
}

function contentTypeOf(rel) {
  if (rel.endsWith(".json") || rel.endsWith(".rules")) return "application/json";
  if (rel.endsWith(".md")) return "text/markdown";
  return "application/octet-stream";
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const packsRoot = args.packs ? path.resolve(args.packs) : path.join(ROOT, "packs");
  const style = args.style;
  const packDir = path.join(packsRoot, style);
  if (!fs.existsSync(packDir)) fail(`本地知识包不存在：${packDir}`);

  const required = [`${style}.rules`, `${style}.type.json`, "dict.json"];
  for (const f of required) {
    if (!fs.existsSync(path.join(packDir, f))) {
      fail(`知识包缺必需文件：${f}（应在 ${packDir}）`);
    }
  }

  const version = args.version || todayVersion();
  const base = `packs/${style}/${version}/`;
  const files = walk(packDir, "", []);
  const manifestKey = "packs/manifest.json";

  process.stdout.write(`[publish] style=${style} version=${version}\n`);
  process.stdout.write(`[publish] 本地包：${packDir}\n`);
  for (const rel of files) {
    process.stdout.write(`  -> cos:${base}${rel.replace(/\\/g, "/")}\n`);
  }
  process.stdout.write(`[publish] manifest: cos:${manifestKey}  (${style} => ${version}, base=${base})\n`);

  if (args.dryRun) {
    process.stdout.write("[publish] --dry-run：未上传，结束。\n");
    return;
  }

  if (!SECRET_ID || !SECRET_KEY) {
    fail("缺少云存储凭据：请设置 TCB_SECRET_ID / TCB_SECRET_KEY（临时凭据再补 TCB_TOKEN）。");
  }

  for (const rel of files) {
    const full = path.join(packDir, rel);
    const body = fs.readFileSync(full);
    const key = base + rel.replace(/\\/g, "/");
    const ct = contentTypeOf(rel);
    const { host, auth } = buildAuthAndHost("PUT", key);
    const url = `https://${host}/${encodeURI(key)}`;
    const headers = { host, Authorization: auth, "content-type": ct };
    if (TOKEN) headers["x-cos-security-token"] = TOKEN;
    const res = await fetch(url, { method: "PUT", headers, body });
    if (!res.ok) {
      let t = "";
      try { t = await res.text(); } catch { /* ignore */ }
      fail(`COS PUT 失败 ${res.status} ${res.statusText}: ${t.slice(0, 500)}`);
    }
    process.stdout.write(`  uploaded cos:${key}\n`);
  }

  const existing = await cosGet(manifestKey);
  const obj = existing ? JSON.parse(existing) : {};
  obj[style] = { version, base };
  await cosPut(manifestKey, JSON.stringify(obj, null, 2));

  process.stdout.write(`[publish] 完成：cos:${base} + cos:${manifestKey}\n`);

  if (args.verify) {
    process.stdout.write(`[publish] --verify：回读校验...\n`);
    const m = await cosGet(manifestKey);
    if (!m) fail(`校验失败：读不到 ${manifestKey}`);
    const mj = JSON.parse(m);
    process.stdout.write(`  manifest[${style}] = ${JSON.stringify(mj[style])}\n`);
    const sample = base + "dict.json";
    const d = await cosGet(sample);
    if (!d) fail(`校验失败：读不到样本 ${sample}`);
    const dj = JSON.parse(d);
    const keys = Object.keys(dj);
    process.stdout.write(`  样本 dict.json 回读 OK（顶层键数=${keys.length}，例如「${keys.slice(0, 3).join("、")}」）\n`);
    process.stdout.write(`[publish] 校验通过：桶 ${BUCKET} 已就位。\n`);
  }
}

main().catch((e) => fail(e && e.message ? e.message : String(e)));
