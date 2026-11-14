#!/usr/bin/env python3
"""Q6b：条件化 vs 统计指标 vs 裸生成 —— 三臂，同温度、同模型、每次只生成一篇。

每臂只差 user prompt 里那一段：
  C = 裸生成   ：只给题材与体裁
  P = 具体条件 ：给视角／时间窗／禁写项，不含任何统计指标
  D = 统计指标 ：给人类池 p10–p90 目标表（现行 pipeline 的规划块）

三臂同温度 0.9、同 system、同目标字数；每篇只调用一次，不选稿、不改稿。
盲评：每组三篇随机排成 甲/乙/丙，映射只写进 manifest。
"""
from __future__ import annotations

import argparse
import html
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, "/sdcard/Project/InkSoul/src")

from inksoul.config import load_config
from inksoul.generation import (CreationBrief, SYSTEM_PROMPT, _clean_output,
                                _system, build_plan)
from inksoul.llm import LLMClient

TARGET = 900
TEMP = 0.9
OUT = Path("/tmp/q6b")
SEED = 20261114

BRIEFS = [
    {"theme": "深夜便利店，店员在补货，一个客人进来只买了一颗茶叶蛋，付完钱却没走。",
     "cond": "只从店员视角写；场景限定在客人进店到走出自动门这几分钟；禁止写任何心理活动，情绪只能靠动作和对话透出来。"},
    {"theme": "城中村理发店，老板娘给一个老主顾剪头发，那人下周就要搬走了。",
     "cond": "只写剪刀响的这十几分钟；禁止回忆、禁止交代两人以往交情；两人都不说“舍不得”这三个字。"},
    {"theme": "早班公交，售票员提醒一个缩在车门边打瞌睡的学生。",
     "cond": "只写这一站到下一站之间的两分钟；禁止写学生的过去和家庭；对话不超过六句。"},
    {"theme": "小区快递柜前，保安教一个不会扫码的老太太取件。",
     "cond": "只写扫码这一件事从头到尾；禁止外貌描写；老太太始终没搞懂，最后是保安替她按的。"},
    {"theme": "夜市收摊，卖炒粉的两口子为收尾的钱吵了两句，又一块儿推车回家。",
     "cond": "只写收摊这十分钟；吵的那两句必须很短；和好用动作收，不许写一句和解的话。"},
]


def call(client, system, user):
    last = None
    for attempt in range(3):
        try:
            resp = client.chat([{"role": "system", "content": system},
                                {"role": "user", "content": user}],
                               temperature=TEMP,
                               max_tokens=max(512, int(TARGET * 2.0)))
            return _clean_output(resp.text)
        except Exception as exc:  # noqa: BLE001
            last = exc
            print("  重试:", exc, flush=True)
            time.sleep(2 + 2 * attempt)
    raise RuntimeError(f"三次调用均失败：{last}")


def build_html(manifest):
    parts = []
    for it in manifest["items"]:
        parts.append('<section><h2>第 %d 组</h2><div class="brief">%s</div>'
                     % (it["idx"] + 1, html.escape(it["brief"])))
        for label in ["甲", "乙", "丙"]:
            p = Path(it["files"][label])
            if not p.exists():
                continue
            paras = [x.strip() for x in p.read_text(encoding="utf-8").split("\n\n") if x.strip()]
            body = "".join("<p>%s</p>" % html.escape(x) for x in paras)
            parts.append('<article><h3>%s</h3>%s</article>' % (label, body))
        parts.append("</section>")
    css = """
body{max-width:44em;margin:0 auto;padding:1.2em 1.1em 6em;font:17px/1.85 "Songti SC","Noto Serif CJK SC",serif;color:#1b1b1b;background:#fbfaf7}
h1{font-size:1.15em;font-weight:600;border-bottom:1px solid #ddd;padding-bottom:.6em}
h2{font-size:.9em;font-weight:600;color:#8a6a3a;margin:3em 0 .3em;letter-spacing:.05em}
.brief{font-size:.85em;color:#6f6a5f;line-height:1.7;margin:0 0 1.6em;padding-left:.6em;border-left:2px solid #e0dbcf}
h3{font-size:1em;font-weight:600;color:#444;margin:2em 0 .7em;padding:.2em .55em;background:#efece5;border-radius:4px;display:inline-block}
article{border-left:2px solid #e6e2d8;padding-left:1em}
p{margin:0 0 .9em;text-indent:2em}
.note{font-size:.86em;color:#8b8477;line-height:1.7;margin-bottom:2em}
"""
    doc = ("<!doctype html><html lang=zh><meta charset=utf-8>"
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           "<title>Q6b 三版对照</title><style>" + css + "</style>"
           "<h1>Q6b · 同题三版对照</h1>"
           '<div class="note">每组三篇写同一个题、同一个设定，条件不同。'
           "读完在每组里排个序（如「丙 &gt; 甲 &gt; 乙」），再挑一篇说一句为什么。"
           "不要猜哪版是谁，只看文字。</div>" + "".join(parts) + "</html>")
    (OUT / "q6b_review.html").write_text(doc, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reveal", action="store_true")
    args = ap.parse_args()

    if args.reveal:
        man = json.loads((OUT / "q6b_manifest.json").read_text(encoding="utf-8"))
        for it in man["items"]:
            print("第 %d 组  " % (it["idx"] + 1) + "  ".join(
                "%s=%s" % (k, v) for k, v in it["mapping"].items()))
        print("\nC=裸生成  P=具体条件  D=统计指标")
        return

    cfg = load_config()
    cfg.generation.target_chars = TARGET
    client = None if args.dry_run else LLMClient(cfg.model)
    system = _system(SYSTEM_PROMPT, "")
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    manifest = {"target": TARGET, "temperature": TEMP,
                "model": cfg.model.model, "items": []}

    for idx, spec in enumerate(BRIEFS[: args.limit]):
        brief = CreationBrief(theme=spec["theme"], genre="小说", target_chars=TARGET)
        plan = build_plan(brief, cfg, client=client, use_llm=not args.dry_run)
        base = brief.prompt_block()
        tail = "请直接写出正文，约 %d 字。" % TARGET
        prompts = {
            "C": base + "\n\n" + tail,
            "P": base + "\n\n【本次写作条件】\n" + spec["cond"] + "\n\n" + tail,
            "D": base + "\n\n" + plan.as_prompt() + "\n\n" + tail,
        }
        labels = ["甲", "乙", "丙"]
        arms = ["C", "P", "D"]
        rng.shuffle(arms)
        mapping = dict(zip(labels, arms))
        item = {"idx": idx, "brief": spec["theme"], "files": {}, "mapping": mapping}
        for label, arm in mapping.items():
            p = OUT / ("%02d_%s.txt" % (idx, label))
            if p.exists() and p.stat().st_size > 200:
                print("[%d] %s 已存在，复用" % (idx, label), flush=True)
                item["files"][label] = str(p)
                continue
            if args.dry_run:
                text = "[dry-run %s]\n\n%s" % (arm, prompts[arm])
            else:
                text = call(client, system, prompts[arm])
            p.write_text(text, encoding="utf-8")
            item["files"][label] = str(p)
            print("[%d] %s <- %s  %d 字" % (idx, label, arm, len(text)), flush=True)
        manifest["items"].append(item)

    (OUT / "q6b_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    build_html(manifest)
    print("完成。审完用 --reveal 揭盲。")


if __name__ == "__main__":
    main()
