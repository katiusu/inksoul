#!/usr/bin/env python3
"""Q6 对照实验：生成期控制 vs 后编辑。

三臂（同模型、同 brief、同目标字数、同修订机制）：
  C  裸生成    一次调用，无文体规划、无修订                 —— 地板
  B  仅后编辑  裸生成 → review → revise(max_rounds=2)      —— 现有「修补」路径
  A  生成期控制 plan(LLM) → 3 候选 → 选阻断最少 → revise    —— 本项目主张

跑之前把预注册写进 q6_prereg.md；评分表不出现「AI 味」三个字，只问四个具体问题。

用法：
  python3 experiment/scripts/q6_ab.py --dry-run     # 计划、调用数、余额、成本估计
  python3 experiment/scripts/q6_ab.py               # 正式跑（断点续跑，已有文件跳过）
  python3 experiment/scripts/q6_ab.py --show        # 评分时揭盲对照
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from inksoul.analyzer import Analyzer
from inksoul.config import load_config
from inksoul.generation import CreationBrief, build_plan, generate, revise

OUT = Path(os.environ.get("Q6_OUT", "/tmp/q6"))
TARGET = 800
MAX_ITEMS = 4
MAX_ROUNDS = 2

BARE_SYSTEM = (
    "你是一位中文小说作者。按用户要求写一段小说正文。"
    "只输出正文本身：不要标题、不要分节说明、不要任何解释。"
)

BRIEFS = [
    "末班地铁已经走了，值班员要锁站厅的卷帘门，一个乘客还在闸机外面翻包找卡。两人从僵持到一起走了一段路。",
    "老式居民楼，夜里电梯坏了，六楼住户下楼取外卖，跟外卖员一起爬上来。",
    "县城医院走廊，凌晨三点，陪床的女儿睡不着，去开水房打水时遇到一位陌生老人。",
    "南方小城，台风来的前夜，修表铺老板在关窗，一个学生来取修好的表。",
    "冬天早市，豆腐摊刚开张，摊主和每天第一个来的老太太。",
    "长途大巴上，司机从后视镜里注意到后座有个女人一直没下车。",
    "废弃的小学操场，一个中年人回来看旧教室，遇到留守的门卫。",
    "城郊废品站，收废品的男人在分拣，一个高中生来卖一箱旧书。",
    "年三十的网吧，网管在数烟灰缸，一个高三男生包了夜。",
    "老式照相馆，老板在冲洗胶卷，一个年轻人来补拍证件照。",
]

PRE_REG = """# Q6 预注册（跑之前写死）

假设 H：A（生成期控制）在盲评中**优于** B（仅后编辑）。
零假设 H0：A 与 B 无差异。

判据（跑之前先写，跑完不改）：
- 每对 A/B 由评审二选一：更具体 / 有更想记住的句子 / 更像某个具体的人在写。
- n=10 对，不做显著性检验、不宣称等价（TOST 需要 n≥30 起）。
  只报原始票数、平票数，并保留每一对的文字理由。
- C 臂是地板：若 B 与 C 已无差异，说明「后编辑」这一整套本身就没用，
  A/B 之争失去前提——先处理这一条。
- 评分只看原始文本，**不看任何指标输出**（用闸门评 A 就是循环论证）。

已知不公：A 臂在设计上花了更多 token，成本不对等；实验只回答「值不值这个钱」，
不回答「同等成本下谁更好」。
"""


# ---------------------------------------------------------------- 计费与工具
def balance() -> float | None:
    key = os.environ.get("DEEPSEEK_KEY") or ""
    if not key:
        cfg_file = Path.home() / ".dsh" / "inksoul" / "config.json"
        try:
            key = json.loads(cfg_file.read_text())["model"]["api_key"]
        except Exception:
            return None
    req = urllib.request.Request(
        "https://api.deepseek.com/user/balance",
        headers={"Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
        for b in data.get("balance_infos", []):
            if b.get("currency") == "CNY":
                return float(b.get("total_balance", 0))
    except Exception:
        return None
    return None


def bare_generate(client, brief: CreationBrief) -> str:
    resp = client.chat(
        [{"role": "system", "content": BARE_SYSTEM},
         {"role": "user", "content": f"{brief.prompt_block()}\n\n请直接写出正文，约 {TARGET} 字。"}],
        temperature=0.9,
        max_tokens=int(TARGET * 2.2),
    )
    return (resp.text or "").strip()


def arm_c(cfg, client, analyzer, brief):
    text = bare_generate(client, brief)
    return {"text": text, "calls": 1, "notes": ["裸生成"]}


def arm_b(cfg, client, analyzer, brief):
    neutral = build_plan(brief, cfg, client=None, use_llm=False)
    text = bare_generate(client, brief)
    rep = analyzer.analyze(text, with_review=True)
    rev = revise(text, rep.review, client, neutral, cfg=cfg,
                 max_rounds=MAX_ROUNDS, max_items=MAX_ITEMS)
    return {"text": rev.text, "calls": 1 + rev.applied + rev.skipped,
            "notes": [f"后编辑 应用{rev.applied} 跳过{rev.skipped}"]}


def arm_a(cfg, client, analyzer, brief):
    plan = build_plan(brief, cfg, client=client, use_llm=True)
    n = max(1, plan.candidates or 3)
    drafts, reports = [], []
    for i in range(n):
        d = generate(brief, plan, client, candidate_id=i)
        drafts.append(d)
        reports.append(analyzer.analyze(d.text, with_review=True))
    best = min(range(n), key=lambda i: (len(reports[i].review.blocking), i))
    rev = revise(drafts[best].text, reports[best].review, client, plan, cfg=cfg,
                 max_rounds=MAX_ROUNDS, max_items=MAX_ITEMS)
    return {"text": rev.text, "calls": 1 + n + rev.applied + rev.skipped,
            "notes": [f"候选{n} 选#{best}", f"后编辑 应用{rev.applied} 跳过{rev.skipped}"]}


ARMS = {"C": arm_c, "B": arm_b, "A": arm_a}


# ---------------------------------------------------------------- 评分表
def write_sheet(manifest: dict, path: Path) -> None:
    lines = [
        "# Q6 盲评表",
        "",
        "规则：每对只读文本，不看其他任何输出。每题三选一，实在分不出就写「平」。",
        "不要数句子、不要找 AI 味——只回答下面四个问题。",
        "",
    ]
    for item in manifest["items"]:
        lines.append(f"## 第 {item['idx'] + 1} 组：{item['brief'][:24]}…")
        lines.append("")
        for code, arm in sorted(item["blind"].items()):
            body = item["files"][arm]
            lines.append(f"### 【{code}】")
            lines.append("")
            try:
                lines.append(Path(body).read_text(encoding="utf-8").strip())
            except Exception as exc:
                lines.append(f"（读取失败：{exc}）")
            lines.append("")
        codes = "/".join(sorted(item["blind"]))
        lines += [
            f"**1 具体**（哪篇的细节让你看得见东西）：{codes} / 平",
            f"**2 记忆点**（哪篇有你想再读一遍的句子）：{codes} / 平",
            f"**3 人**（哪篇最像某个具体的人在写，而不是某种写法）：{codes} / 平",
            "**4 一句话理由**：",
            "",
            "---",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", action="store_true", help="揭盲：打印 code→arm")
    ap.add_argument("--arms", default="CA", help="CA=生成期控制 vs 裸生成；B 在真实输出上 revise 零命中，故默认不含")
    ap.add_argument("--limit", type=int, default=len(BRIEFS))
    ap.add_argument("--max-cny", type=float, default=4.0)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    man_path = OUT / "q6_manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {"items": [], "seed": None}
    if args.show:
        for item in manifest["items"]:
            print(f"[{item['idx'] + 1}] " + "  ".join(f"{c}={a}" for c, a in sorted(item["blind"].items())))
        return 0

    before = balance()
    print(f"余额前：{before}")

    if args.dry_run:
        calls = sum({"C": 1, "B": 1 + MAX_ROUNDS * MAX_ITEMS, "A": 4 + MAX_ROUNDS * MAX_ITEMS}[a]
                    for a in args.arms) * min(args.limit, len(BRIEFS))
        print(f"臂={args.arms} 组数={min(args.limit, len(BRIEFS))} 目标{TARGET}字 "
              f"最多调用≈{calls} 次 上限¥{args.max_cny}")
        return 0

    cfg = load_config()
    if not cfg.model.api_key:
        print("没有可用 api_key：先 inksoul config --init")
        return 2
    cfg.generation.target_chars = TARGET
    from inksoul.llm import LLMClient
    client = LLMClient(cfg.model)
    analyzer = Analyzer(cfg)

    seed = args.seed if args.seed is not None else (manifest.get("seed") or int(time.time()))
    manifest["seed"] = seed
    rng = random.Random(seed)
    prereg = OUT / "q6_prereg.md"
    if not prereg.exists():
        prereg.write_text(PRE_REG, encoding="utf-8")
        print(f"预注册已写：{prereg}")

    done = {it["idx"] for it in manifest["items"] if len(it.get("files", {})) == len(args.arms)}
    for idx, brief_text in enumerate(BRIEFS[: args.limit]):
        if idx in done:
            print(f"[{idx + 1}] 跳过（已完成）")
            continue
        brief = CreationBrief(theme=brief_text, genre="小说", target_chars=TARGET)
        arms = [a for a in args.arms]
        rng.shuffle(arms)
        blind = {chr(ord("k") + i): a for i, a in enumerate(arms)}
        files, used = {}, 0
        t0 = time.time()
        for code, arm in blind.items():
            if arm == "C" and "B" in blind.values() and False:
                pass
            try:
                res = ARMS[arm](cfg, client, analyzer, brief)
            except Exception as exc:
                print(f"[{idx + 1}] {code}/{arm} 失败：{exc}")
                res = {"text": f"（{arm} 臂失败：{exc}）", "calls": 0, "notes": [str(exc)]}
            used += res["calls"]
            p = OUT / f"{idx:02d}_{code}.txt"
            p.write_text(res["text"], encoding="utf-8")
            files[arm] = str(p)
            print(f"[{idx + 1}] {code} {len(res['text'])}字 {' / '.join(res['notes'])}  # 盲：不打印臂名")
        manifest["items"] = [it for it in manifest["items"] if it["idx"] != idx]
        manifest["items"].append({"idx": idx, "brief": brief_text, "blind": blind,
                                  "files": files, "calls": used,
                                  "seconds": round(time.time() - t0, 1)})
        manifest["items"].sort(key=lambda it: it["idx"])
        man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        now = balance()
        if before is not None and now is not None:
            spent = before - now
            print(f"    累计花费 ¥{spent:.3f}")
            if spent > args.max_cny:
                print(f"超过上限 ¥{args.max_cny}，停止")
                break

    write_sheet(manifest, OUT / "q6_sheet.md")
    after = balance()
    print(f"\n余额后：{after}  花费：{None if before is None or after is None else round(before - after, 3)}")
    print(f"评分表：{OUT / 'q6_sheet.md'}（盲；评分时用 --show 揭盲）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
