#!/usr/bin/env python3
"""生成实验用的「模板拼接」对照样本。

为什么要有这个脚本
------------------
真实模型样本需要 API Key，本机没有。为了先验证实验管线（而不是伪造模型输出），
这里用**显式模板拼接**生成一组「机械复用」文本：句式从固定模板池里抽，词汇从固定词表里抽。
它不是任何模型的作品，只代表「无意识模板复用」这一端的上界。

真实模型样本的生成方式见 `gen_model_samples.py`（需要配置 api_key）。
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "generated"

SUBJ = ["他", "她"]
ADV = ["慢慢地", "轻轻地", "缓缓地", "悄悄地"]
VERB = ["推开", "关上", "拿起", "放下"]
OBJ = ["房门", "窗户", "杯子", "书"]
LOC = ["屋里", "窗边", "桌前", "门口"]
MOOD = ["没有回答", "没有说话", "沉默了一会儿", "叹了一口气"]

TEMPLATES = [
    "{s}{adv}{v}了{obj}，走进了{loc}。",
    "{s}{adv}{v}了{obj}，又{adv}{v}了{obj}。",
    "{s}看着{loc}，{mood}。",
    "{loc}很安静，什么也没有。",
]


def make_paragraph(rng: random.Random, n: int = 4) -> str:
    lines = []
    for _ in range(n):
        t = rng.choice(TEMPLATES)
        lines.append(t.format(s=rng.choice(SUBJ), adv=rng.choice(ADV), v=rng.choice(VERB),
                              obj=rng.choice(OBJ), loc=rng.choice(LOC), mood=rng.choice(MOOD)))
    return "".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成模板拼接对照样本")
    ap.add_argument("--n", type=int, default=6, help="样本数")
    ap.add_argument("--paras", type=int, default=6, help="每篇段数")
    ap.add_argument("--seed", type=int, default=20261031)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    manifest = []
    for i in range(args.n):
        text = "\n\n".join(make_paragraph(rng) for _ in range(args.paras))
        name = f"t_mock_{i + 1:02d}.txt"
        (OUT / name).write_text(text, encoding="utf-8")
        manifest.append({"file": name, "chars": len(text), "source": "template-concat",
                         "seed": args.seed, "note": "模板拼接基线，非模型输出"})
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成 {len(manifest)} 篇 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
