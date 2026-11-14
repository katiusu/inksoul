# -*- coding: utf-8 -*-
"""molds 层测试：22 项模具目录、基线一致性、段级复合 z、短文本门槛、JSON 与 CLI 接线。

0.6.2 起 molds 从「16 项单阈值双边否决」改为「段级复合 z」：
单项只报 z（诊断，不单独判死刑），复合偏离超人类段 p95 才判 DRIFT；
下限项只报「本段未出现」，不进否决——按 p10 硬补会把文写平。
"""
from __future__ import annotations

import json
import re
from argparse import Namespace
from pathlib import Path

import pytest

from inksoul.molds import (
    JUDGED,
    MIN_TEXT_HAN,
    MOLDS,
    MOLD_MAP,
    WINDOW_CHARS,
    analyze_molds,
    baseline,
    gate_text,
    han_count,
    threshold,
)

ROOT = Path(__file__).resolve().parent.parent
HUMAN = ROOT / "experiment" / "corpus" / "human"

#: 典型「坐标化」段落：空间坐标 + 轨迹 + 时间刻度 + 把字句 + 序列副词 + 一就
COORD_UNIT = (
    "她把发带从腰头绕到第三遍，鞋尖对着墙根，左手按在领口上，"
    "再从肩胛挪到后颈，一抬手就把袖口翻过来，先压平，再抹顺，最后提起来看了第三遍。"
)
COORD = COORD_UNIT * 12


def test_catalog_shape():
    keys = [m.key for m in MOLDS]
    assert len(keys) == len(set(keys)), "模具 key 不能重复"
    assert {m.direction for m in MOLDS} <= {"over", "under", "neutral"}
    assert sum(m.direction == "over" for m in MOLDS) == 14
    assert sum(m.direction == "under" for m in MOLDS) == 5
    assert sum(m.direction == "neutral" for m in MOLDS) == 3
    assert len(MOLDS) == 22
    assert set(MOLD_MAP) == set(keys)


def test_every_mold_pattern_compiles():
    for m in MOLDS:
        assert m.pattern, m.key
        re.compile(m.pattern, re.M)
        assert m.name.strip(), m.key


def test_baseline_covers_judged_items():
    base = baseline()
    items = base.get("items") or {}
    assert items, "基线缺失：src/inksoul/data/molds_baseline.json"
    for m in JUDGED:
        st = items.get(m.key)
        assert st is not None, "基线缺 %s" % m.key
        q = [float(st.get(k, 0.0)) for k in ("p10", "p50", "p90", "p95", "p99")]
        assert q == sorted(q), "%s 分位不单调：%s" % (m.key, q)
        assert float(st.get("mean", 0.0)) >= 0.0
        assert float(st.get("sd", 0.0)) >= 0.0


def test_threshold_in_sane_range():
    thr = threshold()
    assert 0.2 <= thr <= 2.0, thr


def test_empty_text_raises():
    with pytest.raises(ValueError):
        analyze_molds("   \n\n  ")


def test_short_text_is_insufficient():
    short = "她走了两步，停下。" * 20
    assert han_count(short) < MIN_TEXT_HAN
    rep = analyze_molds(short)
    assert rep.insufficient is True
    assert rep.verdict == "INSUFFICIENT"
    assert rep.windows == []
    assert rep.rows == []
    assert "不足" in rep.as_text()


def test_coordinate_heavy_text_drifts():
    assert han_count(COORD) >= MIN_TEXT_HAN
    rep = analyze_molds(COORD)
    assert rep.insufficient is False
    assert rep.composite_score > rep.threshold, (rep.composite_score, rep.threshold)
    assert rep.verdict == "DRIFT"
    top = {r.key for r in rep.diagnostics_top(6)}
    assert {"LOC", "BA", "SEQ"} & top, "坐标化段落应在 LOC/BA/SEQ 上有贡献"


def test_rows_cover_every_mold_and_carry_z():
    rep = analyze_molds(COORD)
    assert len(rep.rows) == len(MOLDS)
    for r in rep.rows:
        assert r.contribution >= 0.0
        if r.direction == "neutral":
            assert r.contribution == 0.0, "neutral 不进复合分"


def test_under_items_reported_as_missing_not_veto():
    # 全句号、无问号/感叹号/省略号/引号/叠词：下限项应全部「本段未出现」
    flat = "她把杯子放在桌上然后坐下看着窗外很久没有说一句话。" * 40
    rep = analyze_molds(flat)
    miss = {r.key for r in rep.under_missing()}
    assert {"EXCL", "ELLIP", "QUES", "QUOTE"} <= miss
    for r in rep.rows:
        if r.direction == "under":
            assert r.contribution == 0.0 or r.z < 0
    assert rep.verdict in {"PASS", "DRIFT"}, "下限缺失不得产生 UNDER 否决"


def test_report_dict_shape():
    rep = analyze_molds(COORD)
    d = rep.as_dict()
    for k in ("n_chars", "verdict", "composite", "composite_threshold",
              "pass_rate", "windows", "worst_window", "rows", "under_missing"):
        assert k in d, k
    assert d["n_chars"] == han_count(COORD)
    assert isinstance(d["windows"], list) and d["windows"]
    assert len(d["rows"]) == len(MOLDS)
    assert json.dumps(d, ensure_ascii=False)


def test_gate_text_returns_verdict_and_report():
    verdict, text = gate_text(COORD)
    assert verdict in {"PASS", "DRIFT", "INSUFFICIENT"}
    assert "VERDICT" in text or "不足" in text


@pytest.mark.skipif(not HUMAN.is_dir(), reason="人类样本目录不存在")
def test_human_window_less_deviant_than_coordinate_text():
    books = sorted(HUMAN.glob("*.txt"))
    if not books:
        pytest.skip("人类样本为空")
    human = books[0].read_text(encoding="utf-8", errors="ignore")[:2500]
    if han_count(human) < MIN_TEXT_HAN:
        pytest.skip("人类样本过短")
    h = analyze_molds(human)
    c = analyze_molds(COORD)
    assert c.composite_score > h.composite_score, (
        "坐标化文本应比人类样本更偏离：coord=%.2f human=%.2f" % (c.composite_score, h.composite_score)
    )


def test_cli_molds_json(tmp_path, capsys):
    from inksoul.cli import cmd_molds

    p = tmp_path / "coord.txt"
    p.write_text(COORD, encoding="utf-8")
    code = cmd_molds(Namespace(target=str(p), json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["file"] == "coord.txt"
    assert payload["verdict"] in {"PASS", "DRIFT"}
    assert code == 0, "--json 分支固定返回 0（裁决看 JSON 里的 verdict）"
    assert payload["composite_threshold"] == pytest.approx(threshold(), abs=0.01)


def test_cli_molds_missing_file(tmp_path, capsys):
    from inksoul.cli import cmd_molds

    code = cmd_molds(Namespace(target=str(tmp_path / "nope.txt"), json=False))
    assert code == 2
    assert "找不到文件" in capsys.readouterr().err
