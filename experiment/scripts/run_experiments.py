#!/usr/bin/env python3
"""InkSoul 实验管道：A 句法分布 / B 复用率 / D 代理相关性 / E 修辞误判 / F 修订前后。

诚实性约定
----------
1. 真实模型样本需要 API Key，本机没有；`--full` 会在拿到 Key 后补跑实验 C。
2. 实验 D 目前用「标签代理变量」而不是人工评分，只能演示相关性计算方式。
3. 实验 F 的「修订后」文本是**人工改写**，不是模型修订；标签里写清楚。
4. 所有阈值未标定；结果只用于验证管线与暴露误报，不用于给作品打分。

用法：
    PYTHONPATH=src python3 experiment/scripts/run_experiments.py --dry-run
    PYTHONPATH=src python3 experiment/scripts/run_experiments.py --full
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "experiment" / "data"
RESULTS = ROOT / "experiment" / "results"

sys.path.insert(0, str(ROOT / "src"))

from inksoul.analyzer import Analyzer          # noqa: E402
from inksoul.config import InkSoulConfig       # noqa: E402

METRICS = [
    "reuse_rate",
    "pattern_entropy_norm",
    "adjacent_similarity_mean",
    "adjacent_high_similarity_share",
    "paragraph_internal_repeat_rate",
    "ttr",
    "mtld_like",
    "sentence_len_cv",
    "dialogue_ratio",
]


def _load_corpus() -> list[dict]:
    items: list[dict] = []
    human_dir = DATA / "raw_sources"
    manifest = {}
    if (human_dir / "manifest.json").exists():
        for row in json.loads((human_dir / "manifest.json").read_text(encoding="utf-8")):
            manifest[row.get("file") or row.get("key")] = row
    for p in sorted(human_dir.glob("*.txt")):
        row = manifest.get(p.name) or manifest.get(p.stem) or {}
        items.append({"id": f"h_{p.stem}", "corpus": "人类", "genre": row.get("genre", "未知"),
                      "path": p, "note": f"{row.get('author','')}《{row.get('title','')}》{row.get('year','')}"})
    for p in sorted((DATA / "generated").glob("t_mock_*.txt")):
        if "_edited" in p.name:
            continue
        items.append({"id": f"t_{p.stem}", "corpus": "模板拼接", "genre": "小说", "path": p,
                      "note": "模板拼接基线（非模型输出）"})
    return items


def _metrics(rep) -> dict:
    fp, dv, st = rep.fingerprint, rep.diversity, rep.style
    lens = st.sentence_length_stats.get("mean") and None
    return {
        "clauses": fp.clause_count,
        "distinct": fp.distinct_patterns,
        "reuse_rate": round(fp.reuse_rate, 3),
        "pattern_entropy_norm": round(dv.pattern_entropy_norm, 3),
        "adjacent_similarity_mean": round(dv.adjacent_similarity_mean, 3),
        "adjacent_high_similarity_share": round(dv.adjacent_high_similarity_share, 3),
        "paragraph_internal_repeat_rate": round(dv.paragraph_internal_repeat_rate, 3),
        "ttr": round(st.ttr, 3),
        "mtld_like": round(st.mtld_like, 2),
        "sentence_len_cv": round(_cv(st), 3),
        "dialogue_ratio": round(st.dialogue_ratio, 3),
        "suspects": len(fp.suspects),
        "blocking": len(rep.review.blocking) if rep.review else 0,
        "exempted": len(rep.review.exempted) if rep.review else 0,
    }, lens


def _cv(style) -> float:
    stats = style.sentence_length_stats or {}
    mean = stats.get("mean") or 0.0
    std = stats.get("std") or 0.0
    return (std / mean) if mean else 0.0


def _describe(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
    }


def exp_a_b(rows: list[dict]) -> dict:
    by_corpus: dict[str, dict] = {}
    for corpus in sorted({r["corpus"] for r in rows}):
        subset = [r for r in rows if r["corpus"] == corpus]
        by_corpus[corpus] = {m: _describe([r[m] for r in subset if m in r])
                             for m in METRICS + ["suspects", "blocking", "exempted", "clauses"]}
        by_corpus[corpus]["n_texts"] = len(subset)
    return {"by_corpus": by_corpus, "per_text": rows}


def exp_e() -> dict:
    labels = json.loads((DATA / "rhetoric" / "labels.json").read_text(encoding="utf-8"))
    az = Analyzer(InkSoulConfig())
    out = []
    for row in labels:
        text = (DATA / "rhetoric" / row["file"]).read_text(encoding="utf-8")
        rep = az.analyze(text)
        out.append({
            "file": row["file"], "label": row["label"], "desc": row["desc"],
            "suspects": len(rep.fingerprint.suspects),
            "blocking": len(rep.review.blocking),
            "exempted": len(rep.review.exempted),
            "reuse_rate": round(rep.fingerprint.reuse_rate, 3),
        })
    flags = [r for r in out if r["label"] == "机械"]
    rhet = [r for r in out if r["label"] == "修辞性"]
    hit = sum(1 for r in flags if r["blocking"] > 0 or r["suspects"] > 0)
    fp_rate = sum(1 for r in rhet if r["blocking"] > 0 or r["suspects"] > 0)
    return {
        "rows": out,
        "detection_rate_mechanical": round(hit / len(flags), 3) if flags else None,
        "false_positive_rate_rhetorical": round(fp_rate / len(rhet), 3) if rhet else None,
        "n_mechanical": len(flags), "n_rhetorical": len(rhet),
    }


def exp_f() -> dict:
    az = Analyzer(InkSoulConfig())
    before = (DATA / "generated" / "t_mock_01.txt").read_text(encoding="utf-8")
    after = (DATA / "generated" / "t_mock_01_edited.txt").read_text(encoding="utf-8")
    rb = az.analyze(before)
    ra = az.analyze(after)
    def snap(rep):
        return {
            "reuse_rate": round(rep.fingerprint.reuse_rate, 3),
            "pattern_entropy_norm": round(rep.diversity.pattern_entropy_norm, 3),
            "suspects": len(rep.fingerprint.suspects),
            "blocking": len(rep.review.blocking),
        }
    return {"before": snap(rb), "after": snap(ra),
            "note": "「修订后」为人工改写（非模型修订），用于验证指标是否朝期望方向移动"}


def exp_d(rows: list[dict]) -> dict:
    """代理相关性：用 corpus 标签当机械感代理（模板拼接=1，人类=0）。"""
    labeled = [r for r in rows if r["corpus"] in ("人类", "模板拼接")]
    if len({r["corpus"] for r in labeled}) < 2:
        return {"skipped": True, "reason": "缺少对照语料"}
    y = [1 if r["corpus"] == "模板拼接" else 0 for r in labeled]
    out = {}
    for m in METRICS:
        xs = [r[m] for r in labeled]
        out[m] = {"point_biserial": round(_point_biserial(xs, y), 3),
                  "auc": round(_auc(xs, y), 3)}
    return {
        "rows": out,
        "labels": "corpus 标签代理（模板拼接=机械 1 / 人类 0）",
        "caveat": "不是人工机械感评分；只验证统计管线，不能当作效度证据",
    }


def _point_biserial(xs: list[float], ys: list[int]) -> float:
    m1 = [x for x, y in zip(xs, ys) if y == 1]
    m0 = [x for x, y in zip(xs, ys) if y == 0]
    if len(m1) < 2 or len(m0) < 2:
        return 0.0
    sx = statistics.stdev(xs) if len(xs) > 1 else 0.0
    if sx == 0:
        return 0.0
    p = len(m1) / len(xs)
    q = 1 - p
    return (statistics.fmean(m1) - statistics.fmean(m0)) / sx * (p * q) ** 0.5


def _auc(xs: list[float], ys: list[int]) -> float:
    pos = [x for x, y in zip(xs, ys) if y == 1]
    neg = [x for x, y in zip(xs, ys) if y == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for a in pos:
        for b in neg:
            wins += 1.0 if a > b else 0.5 if a == b else 0.0
    return wins / (len(pos) * len(neg))


def write_summary(payload: dict, path: Path) -> None:
    a = payload["A_B"]["by_corpus"]
    lines = ["# InkSoul 实验结果（自动生成）", "",
             f"生成时间：{payload['meta']['generated_at']}｜模式：{payload['meta']['mode']}", "",
             "> 所有阈值未标定；模板拼接样本不是模型输出；实验 D 使用代理标签。", "",
             "## A/B 各语料指标（均值）", "",
             "| 语料 | 篇数 | 复用率 | 模式熵(归一) | 相邻相似度 | 段内重复 | TTR | 长句变异系数 | 阻断问题 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for corpus, m in a.items():
        lines.append(
            f"| {corpus} | {m['n_texts']} | {m['reuse_rate'].get('mean')} | "
            f"{m['pattern_entropy_norm'].get('mean')} | {m['adjacent_similarity_mean'].get('mean')} | "
            f"{m['paragraph_internal_repeat_rate'].get('mean')} | {m['ttr'].get('mean')} | "
            f"{m['sentence_len_cv'].get('mean')} | {m['blocking'].get('mean')} |")
    e = payload["E"]
    lines += ["", "## E 修辞性重复误判", "",
              f"- 机械样本检出率：{e['detection_rate_mechanical']}（n={e['n_mechanical']}）",
              f"- 修辞样本误报率：{e['false_positive_rate_rhetorical']}（n={e['n_rhetorical']}）", "",
              "| 文件 | 标签 | 复用率 | 嫌疑簇 | 阻断问题 | 豁免 |", "|---|---|---|---|---|---|"]
    for r in e["rows"]:
        lines.append(f"| {r['file']} | {r['label']} | {r['reuse_rate']} | {r['suspects']} | "
                     f"{r['blocking']} | {r['exempted']} |")
    d = payload["D"]
    if not d.get("skipped"):
        lines += ["", "## D 代理相关性（AUC，越大越能区分机械样本）", "", "| 指标 | 点二列相关 | AUC |", "|---|---|---|"]
        for m, v in d["rows"].items():
            lines.append(f"| {m} | {v['point_biserial']} | {v['auc']} |")
        lines += ["", f"注意：{d['caveat']}"]
    f = payload["F"]
    lines += ["", "## F 修订前后（人工改写对照）", "",
              "| 阶段 | 复用率 | 模式熵 | 嫌疑簇 | 阻断问题 |", "|---|---|---|---|---|",
              f"| 修订前 | {f['before']['reuse_rate']} | {f['before']['pattern_entropy_norm']} | "
              f"{f['before']['suspects']} | {f['before']['blocking']} |",
              f"| 修订后 | {f['after']['reuse_rate']} | {f['after']['pattern_entropy_norm']} | "
              f"{f['after']['suspects']} | {f['after']['blocking']} |",
              "", f"注意：{f['note']}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="InkSoul 实验管道")
    ap.add_argument("--dry-run", action="store_true", help="只跑不需要模型的部分（默认）")
    ap.add_argument("--full", action="store_true", help="额外跑需要 API 的实验 C（当前未实现）")
    args = ap.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    az = Analyzer(InkSoulConfig())
    rows = []
    for item in _load_corpus():
        text = item["path"].read_text(encoding="utf-8")
        try:
            rep = az.analyze(text)
        except Exception as exc:  # noqa: BLE001 - 坏样本记下来继续
            rows.append({**{k: item[k] for k in ("id", "corpus", "genre", "note")},
                         "error": str(exc)})
            continue
        met, _ = _metrics(rep)
        rows.append({**{k: item[k] for k in ("id", "corpus", "genre", "note")}, **met})

    payload = {
        "meta": {"mode": "full" if args.full else "dry-run",
                 "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                 "n_texts": len(rows),
                 "norms_version": InkSoulConfig().analysis.norm_table_version},
        "A_B": exp_a_b(rows),
        "D": exp_d(rows),
        "E": exp_e(),
        "F": exp_f(),
    }
    if args.full:
        payload["C"] = {"skipped": True,
                        "reason": "需要可用的模型 API Key；请配置后运行 gen_model_samples.py 再重跑"}

    (RESULTS / "all.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(payload, RESULTS / "summary.md")
    print(f"语料 {len(rows)} 篇；结果写入 {RESULTS/'all.json'} 与 summary.md")
    print(f"E：机械检出 {payload['E']['detection_rate_mechanical']}，"
          f"修辞误报 {payload['E']['false_positive_rate_rhetorical']}")
    print(f"F：复用率 {payload['F']['before']['reuse_rate']} → {payload['F']['after']['reuse_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
