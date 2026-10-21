#!/usr/bin/env node
/**
 * verify_manual_a11y.mjs —— 人工无障碍证据门（TS-9 的另一半）
 *
 * 方案 §6.8 / L916：`web/a11y-manual-v1.json` 在 Stage 0 建表，全部 `status: "not_run"`；
 * 本脚本对未签收的项**退 2（未测）**，不是绿、也不是红。
 * **Stage 7 才接进 `dev-up.sh`**；批次 0 只把它建好并接进 `npm run verify:a11y:manual`。
 *
 * 为什么未测算 2 而不是 1：这不是「做错了」，是「还没做」。
 * 把「还没做」报成红，会让人以为修一修就能绿；报成绿则是假绿（AGENTS.md §2.4.2）。
 *
 * 输出契约：`{ ok, reds[], untested[], waived[], details[] }`
 * 退出码：0 全部签收 / 1 台账结构坏了 / 2 有未签收项（未测）。
 *
 * 用法：
 *   node web/scripts/verify_manual_a11y.mjs --file web/a11y-manual-v1.json
 *   node web/scripts/verify_manual_a11y.mjs --json
 *   node web/scripts/verify_manual_a11y.mjs --selftest
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const WEB = path.resolve(HERE, "..");

function flag(n) { return process.argv.includes(`--${n}`); }
function arg(n, f) {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
}

/** 纯函数：台账 → {reds, untested, details}。反向对照直接喂样本。 */
function evaluate(doc) {
  const reds = [], untested = [], details = [];
  if (!doc || typeof doc !== "object") return { reds: ["台账不是 JSON 对象"], untested, details };
  const items = doc.items;
  if (!Array.isArray(items) || items.length === 0) {
    return { reds: ["台账没有 items —— 空清单会让「全部签收」恒真"], untested, details };
  }
  const accept = new Set(doc.accept_status || ["signed", "done"]);
  const seen = new Set();
  let signed = 0;
  for (const it of items) {
    const id = String(it.item || "").trim();
    if (!id) { reds.push("有一条没有 item 名"); continue; }
    if (seen.has(id)) reds.push(`item 重复：${id}`);
    seen.add(id);
    const missing = ["evidence", "owner", "date"].filter((k) => !String(it[k] || "").trim());
    if (!accept.has(String(it.status || ""))) {
      untested.push(`${id}（status=${it.status || "空"}）`);
      continue;
    }
    if (missing.length) {
      reds.push(`${id} 标成 ${it.status}，但缺 ${missing.join("/")} —— 签收不完整`);
      continue;
    }
    signed += 1;
  }
  details.push(`人工项 ${items.length} 条 · 已签收 ${signed} · 未签收 ${untested.length}`);
  if (!untested.length && !reds.length) details.push("全部人工项已签收（证据/owner/日期齐）");
  return { reds, untested, details };
}

function emit(reds, untested, details) {
  const payload = { ok: reds.length === 0 && untested.length === 0, reds, untested, waived: [], details };
  if (flag("json")) console.log(JSON.stringify(payload, null, 2));
  else {
    for (const d of details) console.log(`  · ${d}`);
    for (const u of untested) console.log(`  ⚠ 未测 ${u}`);
    for (const r of reds) console.log(`  ✗ ${r}`);
    console.log(payload.ok ? "✅ 人工 a11y 全部签收" : reds.length ? "❌ 台账结构有问题" : "⚠ 人工 a11y 未测");
  }
  if (reds.length) return 1;
  if (untested.length) return 2;
  return 0;
}

function main() {
  const file = path.resolve(WEB, arg("file", "a11y-manual-v1.json"));
  if (!fs.existsSync(file)) {
    return emit([], [`台账不存在：${path.relative(WEB, file)} —— 未测（不是「没有人工项」）`], []);
  }
  let doc;
  try {
    doc = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    return emit([`台账读不出：${e.message}`], [], []);
  }
  const r = evaluate(doc);
  return emit(r.reds, r.untested, r.details);
}

function selftest() {
  const base = {
    accept_status: ["signed", "done"],
    items: [
      { item: "a", status: "signed", evidence: "v.mp4", owner: "u", date: "2026-10-21" },
      { item: "b", status: "signed", evidence: "v2.mp4", owner: "u", date: "2026-10-21" },
    ],
  };
  const allSigned = evaluate(base);
  const oneNotRun = evaluate({ ...base, items: [base.items[0], { ...base.items[1], status: "not_run" }] });
  const incomplete = evaluate({ ...base, items: [base.items[0], { ...base.items[1], evidence: "" }] });
  const empty = evaluate({ accept_status: ["signed"], items: [] });
  const dup = evaluate({ ...base, items: [base.items[0], base.items[0]] });
  const cases = [
    ["MA-C1 全部签收 → 绿", allSigned.reds.length === 0 && allSigned.untested.length === 0, ""],
    ["MA-C2 一条 not_run → 未测（不是红）", oneNotRun.untested.length === 1 && oneNotRun.reds.length === 0, oneNotRun.reds.join(";")],
    ["MA-C3 标 signed 但缺 evidence → 红", incomplete.reds.length === 1, ""],
    ["MA-C4 空清单 → 红（否则「全部签收」恒真）", empty.reds.length === 1, ""],
    ["MA-C5 重复 item → 红", dup.reds.length >= 1, ""],
  ];
  let ok = true;
  for (const [label, pass, detail] of cases) {
    console.log(`${pass ? "✓" : "✗"} ${label}${pass ? "" : `  ← ${detail}`}`);
    if (!pass) ok = false;
  }
  return ok ? 0 : 1;
}

if (flag("selftest")) process.exit(selftest());
process.exit(main());
