#!/usr/bin/env python3
"""vocab.py —— 词表装载层（ADR-0008 / ADR-0009 的唯一装载入口）

★ 本模块存在的理由：**任何『扫一遍规则文件里的关键词』的动作都必须被消灭。**

现网三次事故是同一个病，三种表现：

  #  位置                通道由什么决定            后果
  1  `安全词` 那一行       `边界类型` 字符串          任何 SELECT 检测关键词 都取到白名单词
  2  `豁免词` 字段         无 —— 两类词混放           84 守卫 / 10 白名单词，靠词义区分
  3  `downgrade_band`     `effect` 箭头右侧字符串    一个字段承担放行与降级两条通道

白名单搬迁只解决了 #1。本模块把 #2 也变成结构：**规则文件不再持有任何词表。**

三个来源，三种语义，物理分离：

  rules-v1.json            match.keywords  —— 判险词（产生命中）
  whitelist-v1.json        exempts_rule_keys —— 词的存在**证成**主张
  context-guards-v1.json   downgrades      —— 词的存在**取消/弱化**主张

装载时按**通道**组装，每个词只走一条通道：

  放行带 (→auto_pass)     = active 白名单词，其目标规则的 effect 落点是 auto_pass
  降级带 (→manual_review) = 语境守卫词
                          ∪ 白名单表中 status=quarantined 且目标为降级带的词
                            （gentle/comfort 正是如此 —— 放行 ≠ 降级，见 ADR-0008 §2.5）

用法：
    from vocab import load_vocab, assert_channels
    V = load_vocab()
    V.down_bands["T1.1.medical-cure"]   # {'does not treat', ...}
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def landing_of(effect: str) -> str:
    """`effect` 字符串（`"A → B"`）的箭头右侧 = 落点。没有箭头就是它自己。"""
    eff = str(effect or "").strip()
    if "→" in eff:
        return eff.split("→")[-1].strip()
    return "none" if eff in ("none", "") else eff


def band_target(rule, word=None):
    """该规则的通道落点。给 `word` 时返回**那个词自己的**落点。

    ★ 为什么要按词区分（2026-09-16 · D9）：

      原来「一条规则只有一个落点」，于是「放行带」与「降级带」是二选一的 ——
      T6.1（监管状态）的落点是 auto_pass，**它的带里所有词就都是放行词**。
      但带词在语义上并不齐：`cleared`（器械层 510(k) 状态）出现，说明作者分得清
      approved 与 cleared，放行是有据的；`registered`（企业/设施层注册）出现，
      说明不了这件事 —— FDA 自己写明注册**不表示**批准或许可。两者被塞进同一个落点，
      结果是 `FDA approved device. FDA registered facility.` 判 auto_pass。

      所以落点变成**可以逐词声明**：`keyword_effect_overrides` 里给某个词单独写 effect。
      这保持了原来的分工原则（方向由规则里的字符串声明，不由代码猜），只是把粒度
      从「每条规则一个」细到「每个词一个」。法务改一个字符串就能改这个词的处置。
    """
    band = rule.get("downgrade_band") or {}
    eff = str(band.get("effect") or "").strip()
    if word is not None:
        # ★ 2026-09-16（D18 · 回答 Q12）：覆盖的键是「通道 → 词」。
        #   取不到就退回默认 —— 一个词在它**不属于**的那个通道里没有覆盖，
        #   这不是错误，是结构的本意（旧的扁平键在这里会撞上「同一个词两条覆盖」）。
        ov = band.get("keyword_effect_overrides") or {}
        lw = str(word).strip().lower()
        kind = "downgrade" if str(word).strip().lower() in {
            str(x).strip().lower() for x in (band.get("keywords") or [])} else "pass"
        for k, v in (ov.get(kind) or {}).items():
            if isinstance(v, str) and str(k).strip().lower() == lw:
                eff = v.strip()
                break
    return landing_of(eff)


class Vocab:
    __slots__ = ("rules", "match", "pass_bands", "down_bands", "targets",
                 "whitelist", "guards", "non_claims", "sources")

    def __init__(self):
        self.rules = {}
        self.match = {}        # rule_key → set(判险词)
        self.pass_bands = {}   # rule_key → set(放行词)
        self.down_bands = {}   # rule_key → set(降级词)
        self.targets = {}      # rule_key → 'auto_pass' | 'manual_review' | 'none'
        self.whitelist = []
        self.guards = []
        # ★ Q25 = 选项 A：「非主张词形」—— 它**不是**第三个通道，是**准入过滤**：
        #   这些词形不该让规则命中（详见 matcher.mask_non_claims）。默认空 = 行为不变。
        self.non_claims = []
        self.sources = []

    def downgrade_of(self, rule_key):
        return self.down_bands.get(rule_key, set())

    def pass_of(self, rule_key):
        return self.pass_bands.get(rule_key, set())


def load_vocab(skeleton_dir=None):
    d = Path(skeleton_dir) if skeleton_dir else HERE
    rules_doc = json.loads((d / "rules-v1.json").read_text())
    wl = json.loads((d / "whitelist-v1.json").read_text())
    gd = json.loads((d / "context-guards-v1.json").read_text())

    V = Vocab()
    V.rules = {r["rule_key"]: r for r in rules_doc["rules"]}
    V.targets = {k: band_target(r) for k, r in V.rules.items()}
    V.match = {k: {w.lower() for w in (r.get("match") or {}).get("keywords", [])}
               for k, r in V.rules.items()}
    V.pass_bands = {k: set() for k in V.rules}
    V.down_bands = {k: set() for k in V.rules}
    V.whitelist = wl.get("words", [])
    V.guards = [w for w in gd.get("words", []) if w.get("status") == "active"]
    # ★ Q25：非主张词形（`$non_claims.entries`）。**取全部**，不按 status 过滤 ——
    #   过滤会把「已裁定」与「研究稿」混成一个开关；要不要生效由那张表自己的 `status` 表达。
    V.non_claims = (gd.get("$non_claims") or {}).get("entries") or []
    V.sources = [
        "rules-v1.json            → match.keywords（判险词，唯一产生命中的来源）",
        "whitelist-v1.json        → exempts_rule_keys（放行；隔离词走降级）",
        "context-guards-v1.json   → downgrades（降级；绝不放行）",
        "context-guards-v1.json   → $non_claims（**准入过滤**：这些词形不让规则命中，见 Q25）",
    ]

    # ── 放行带 / 降级带：按通道组装，不按字段组装 ────────────────────
    # ★ 逐词判落点（D9）：同一个词表里，词的**通道**由「它受益的那条规则给它的落点」
    #   决定，而这个落点现在可以逐词覆盖。所以下面的判据是 `band_target(rule, w)`
    #   而不是 `band_target(rule)` —— 差这一个参数，`FDA registered` 就从放行带
    #   落到了降级带，而这正是 D9 要的全部效果。
    for e in V.whitelist:
        w = e["word"].strip().lower()
        for rk in e.get("exempts_rule_keys") or []:
            if rk not in V.rules:
                continue
            if band_target(V.rules[rk], w) == "auto_pass":
                V.pass_bands[rk].add(w)
            else:
                V.down_bands[rk].add(w)     # 降级通道：只降级，不放行

    for e in V.guards:
        w = e["word"].strip().lower()
        for rk in e.get("downgrades") or []:
            if rk in V.rules:
                V.down_bands[rk].add(w)

    return V


def assert_channels(V):
    """使用点硬断言：违反即硬失败，不降级为警告。

    从没触发过的守卫等于没有守卫 —— 所以这些检查必须在**每次装载**时跑，
    而不是只在 CI 里跑。
    """
    bad = []

    # W1 ｜ 白名单词不得进入任何判险词表（「安全」不得证明「有风险」）
    for e in V.whitelist:
        if e.get("status") != "active":
            continue
        w = e["word"].strip().lower()
        for rk, kws in V.match.items():
            if w in kws:
                bad.append(("W1", w, rk, "active 白名单词出现在判险词表"))

    # G1 ｜ 守卫词不得进入任何判险词表（否定表述本身不得被判险）
    for e in V.guards:
        w = e["word"].strip().lower()
        for rk, kws in V.match.items():
            if w in kws:
                bad.append(("G1", w, rk, "语境守卫词出现在判险词表"))

    # W3 ｜ 隔离词不得出现在放行带
    for e in V.whitelist:
        if e.get("status") != "quarantined":
            continue
        w = e["word"].strip().lower()
        for rk, ws in V.pass_bands.items():
            if w in ws:
                bad.append(("W3", w, rk, "隔离词出现在放行带"))

    # G3 ｜ 守卫词只允许落降级带；落放行带即违反
    #   ★ 逐词判（D9）：守卫词对某条 auto_pass 规则**可以**合法存在 —— 只要那条规则
    #     用 keyword_effect_overrides 给它一个 manual_review 落点。所以要问的不是
    #     「这条规则是不是放行规则」，而是「这个词在这条规则上的落点是不是放行」。
    for e in V.guards:
        w = e["word"].strip().lower()
        for rk in e.get("downgrades") or []:
            if rk in V.rules and band_target(V.rules[rk], w) == "auto_pass":
                bad.append(("G3", w, rk, "语境守卫词落在放行带（守卫绝不放行）"))

    # G4 ｜ 守卫词不得与 active 白名单词重名
    act = {e["word"].strip().lower() for e in V.whitelist if e.get("status") == "active"}
    for e in V.guards:
        w = e["word"].strip().lower()
        if w in act:
            bad.append(("G4", w, "-", "守卫词与 active 白名单词重名"))

    # ── OV 族 ｜ 逐词落点覆盖（keyword_effect_overrides）自身的自洽 ──────
    # ★ 与 W5 同一类病：**声明了但取不到**，与「没声明」在行为上完全一样。
    #   W5 抓的是「规则声明了带词、词表没登记」；OV 抓的是「覆盖声明了、但那个词
    #   根本不在带里」，以及「覆盖写了、落点和默认一样」—— 后者是伪装成改动的空改动，
    #   它比没改更坏：评审时看得见一行新配置，就会以为行为变了。
    for rk, rule in V.rules.items():
        ov = (rule.get("downgrade_band") or {}).get("keyword_effect_overrides") or {}
        if not ov:
            continue
        declared = {str(k).strip().lower()
                    for k in (rule.get("downgrade_band") or {}).get("keywords", [])}
        pass_declared = {str(w).strip().lower() for w in V.pass_bands.get(rk, set())}
        default_target = band_target(rule)
        # ★ 2026-09-16（D18）：键是「通道 → 词」。旧形状（值直接是字符串）
        #   在这里必须显形为错误，而不是被当成空覆盖静默跳过 ——
        #   跳过的话，一次未完成的迁移会表现为「覆盖全部失效但检查全绿」。
        for kind, words in ov.items():
            if not isinstance(words, dict):
                bad.append(("OV0", kind, rk,
                            f"覆盖的键必须是通道名（downgrade / pass），实得 {kind!r} → "
                            f"{type(words).__name__}（D18 之后是两层结构）"))
                continue
            for k, v in words.items():
                kw = str(k).strip().lower()
                if kind == "downgrade" and kw not in declared:
                    bad.append(("OV1", k, rk,
                                "逐词覆盖的词不在 downgrade_band.keywords 里（死覆盖：永不参与判定）"))
                if kind == "pass" and kw not in pass_declared:
                    bad.append(("OV1", k, rk,
                                "放行通道的逐词覆盖不在放行带里（死覆盖：永不参与判定）"))
                if kind == "downgrade" and landing_of(v) == default_target:
                    bad.append(("OV2", k, rk,
                                f"逐词覆盖的落点与规则默认落点相同（{default_target}）——空改动"))
                if landing_of(v) not in ("auto_pass", "manual_review", "auto_reject",
                                         "auto_pass_with_note", "none"):
                    bad.append(("OV3", k, rk, f"逐词覆盖写出了非法落点 {landing_of(v)!r}"))

    # OV4 ｜ 同一个词不得同时进入同一条规则的放行带与降级带
    #   `load_vocab` 的 if/else 结构天然排除了它，但**跨表**可以撞上：
    #   白名单把词送进放行带，守卫表把同一个词送进降级带。它们来自两个文件，
    #   任一个文件单独看都自洽 —— 只有在这里并起来才看得出。
    for rk in V.rules:
        both = V.pass_bands[rk] & V.down_bands[rk]
        for w in sorted(both):
            bad.append(("OV4", w, rk, "同一个词同时进了放行带与降级带（谁生效取决于代码次序）"))

    if not bad:
        return True
    print("\n" + "!" * 82)
    print("❌ 词表通道不变量被违反 —— 本次评测结论不可用")
    for code, w, rk, why in bad:
        print(f"    {code}  {w:<24} {rk:<28} {why}")
    print("    三个来源必须物理分离：判险词 / 放行词 / 降级词。")
    print("    修法：检查是否有一条读取路径绕过了 vocab.load_vocab()。")
    print("!" * 82)
    raise SystemExit(3)
