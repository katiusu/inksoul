# -*- coding: utf-8 -*-
"""molds 层测试：双边判据、短段门槛、JSON 结构与 CLI 接线。"""
from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from inksoul.molds import MOLDS, analyze_molds, han_count

ROOT = Path(__file__).resolve().parent.parent
HUMAN = ROOT / "experiment" / "corpus" / "human"

#: 典型「坐标化」段落：空间坐标 + 轨迹 + 时间刻度 + 把字句 + 序列副词 + 一就
COORD = (
    "她把发带从腰头绕到第三遍，鞋尖对着墙根，左手按在领口上，"
    "再从肩胛挪到后颈，一抬手就把袖口翻过来，先压平，再抹顺，最后提起来看了第三遍。"
) * 5


def test_catalog_shape():
    keys = [m.key for m in MOLDS]
    assert len(keys) == len(set(keys))
    assert {m.direction for m in MOLDS} <= {"over", "under", "neutral"}
    assert sum(m.direction == "over" for m in MOLDS) == 16
    assert sum(m.direction == "under" for m in MOLDS) == 5


def test_baseline_ordering():
    for m in MOLDS:
        assert m.p10 <= m.mean <= m.p90, m.key
        assert m.pattern, m.key


def test_empty_text_raises():
    with pytest.raises(ValueError):
        analyze_molds("   \n\n  ")


def test_coordinate_heavy_text_reports_over():
    rep = analyze_molds(COORD)
    assert han_count(COORD) > 100
    assert rep.verdict == "OVER"
    keys = {r.key for r in rep.over}
    assert {"LOC", "BA", "SEQ"} & keys


def test_short_text_skips_under_bounds():
    rep = analyze_molds(COORD[:120])
    if han_count(COORD[:120]) < 600:
        assert rep.excluded, "短段应跳过下限判定"
        assert not any(r.status == "UNDER" for r in rep.rows)
        assert rep.verdict != "UNDER"


@pytest.mark.skipif(not HUMAN.is_dir(), reason="人类样本目录不存在")
def test_human_book_not_massively_over():
    books = sorted(HUMAN.glob("*.txt"))
    if not books:
        pytest.skip("no human corpus")
    text = books[0].read_text(encoding="utf-8", errors="ignore")
    if han_count(text) < 5000:
        pytest.skip("sample too small")
    rep = analyze_molds(text)
    assert len(rep.over) <= 5, [r.key for r in rep.over]


def test_report_dict_shape():
    rep = analyze_molds(COORD)
    d = rep.as_dict()
    assert d["n_chars"] == rep.n_chars
    assert d["verdict"] in {"PASS", "OVER", "UNDER"}
    assert isinstance(d["rows"], list) and len(d["rows"]) == len(MOLDS)
    assert {"key", "status", "count", "per_1000", "mean", "ref"} <= set(d["rows"][0])


def test_cli_molds(tmp_path, capsys):
    from inksoul.cli import cmd_molds

    f = tmp_path / "seg.md"
    f.write_text(COORD, encoding="utf-8")
    rc = cmd_molds(Namespace(target=str(f), json=False, min_chars=600))
    out = capsys.readouterr().out
    assert "模具报告" in out
    assert rc == 1  # OVER 退出码 1

    rc2 = cmd_molds(Namespace(target=str(f), json=True, min_chars=600))
    out2 = capsys.readouterr().out
    assert '"verdict"' in out2 and rc2 == 0
