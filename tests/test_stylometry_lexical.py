"""Burrows' Delta（O'Sullivan 2025）与词汇多样性（Kendro 2026）的单测。"""
from __future__ import annotations

import unittest

from inksoul.lexical import hdd, lexical_indices, mattr, msttr, mtld, ttr
from inksoul.stylometry import burrows_delta

# 两个字数 ≥200 的中文片段：A 单调重复，B 用字更散
A = ("他推开门走进屋里坐在椅子上看着桌面窗外的雪越下越大他想起了那年冬天"
     "母亲在厨房里煮面条的味道很淡他没有说话只是把碗推过去") * 4
B = ("檐下的冰凌在晨光里折出细碎的亮他攥紧了袖口想起昨夜的梦梦见河流倒着流"
     "于是河床上的石头都浮了起来像一群白鸟掠过芦苇荡水声盖过了远处教堂的钟") * 4
B2 = B.replace("冰凌", "雪线").replace("白鸟", "灰鸟")


class LexicalIndicesTest(unittest.TestCase):
    def test_ttr_basic(self):
        self.assertEqual(ttr(["a", "b", "a"]), 2 / 3)
        self.assertEqual(ttr([]), 0.0)

    def test_short_text_only_ttr(self):
        out = lexical_indices(["他", "推", "门"])
        self.assertEqual(out["token_count"], 3)
        self.assertIsNone(out["mtld"])
        self.assertIsNone(out["hdd"])
        self.assertTrue(any("只报 TTR" in n for n in out["notes"]))

    def test_mattr_none_when_shorter_than_window(self):
        self.assertIsNone(mattr(["词"] * 10, window=50))

    def test_msttr_needs_segment(self):
        self.assertIsNone(msttr(["词"] * 50, segment=100))

    def test_mtld_repetitive_lower_than_varied(self):
        rep = ["他"] * 200
        varied = [f"w{i}" for i in range(200)]
        self.assertLess(mtld(rep), mtld(varied))

    def test_hdd_range(self):
        toks = B
        v = hdd(toks)
        self.assertIsNotNone(v)
        self.assertGreater(v, 0.0)
        self.assertLessEqual(v, 1.0)

    def test_hdd_length_stable(self):
        """HDD 的抽样规模固定，重复文本不应随长度大幅下滑（旧实现会）。"""
        base = ["他", "推开门", "走进", "屋里", "看着", "窗外", "的", "雪", "想起", "那年", "冬天"]
        vals = [hdd(base * (n // len(base))) for n in (220, 440, 2200)]
        self.assertLess(max(vals) - min(vals), 0.05, vals)

    def test_hdd_extremes(self):
        self.assertAlmostEqual(hdd(["词"] * 200), 1.0 / 42, places=6)
        self.assertAlmostEqual(hdd([str(i) for i in range(200)]), 1.0, places=6)

    def test_indices_structure(self):
        out = lexical_indices(B)
        for k in ("token_count", "type_count", "ttr", "mtld", "mattr", "msttr", "hdd", "params", "notes"):
            self.assertIn(k, out)
        self.assertIsNotNone(out["mtld"])
        self.assertTrue(any("AI 文本多样性反而更高" in n for n in out["notes"]))


class BurrowsDeltaTest(unittest.TestCase):
    def test_requires_two_usable_texts(self):
        with self.assertRaises(ValueError):
            burrows_delta({"a": "太短了", "b": "也短"})

    def test_identical_texts_zero_delta(self):
        rep = burrows_delta({"a": B, "b": B, "c": B})
        self.assertEqual(rep.mean_pairwise_delta, 0.0)
        self.assertIn("n_features", rep.as_dict())

    def test_similar_closer_than_different(self):
        rep = burrows_delta({"a": B, "a2": B2, "b": A})
        d_aa = [m["delta"] for m in rep.matrix if {m["a"], m["b"]} == {"a", "a2"}][0]
        d_ab = [m["delta"] for m in rep.matrix if {m["a"], m["b"]} == {"a", "b"}][0]
        self.assertLess(d_aa, d_ab)

    def test_report_fields(self):
        rep = burrows_delta({"a": A, "b": B, "c": B2})
        d = rep.as_dict()
        for k in ("n_texts", "n_usable", "n_features", "features", "mean_pairwise_delta",
                  "max_pair", "min_pair", "spread", "works", "matrix", "notes"):
            self.assertIn(k, d)
        self.assertEqual(len(d["matrix"]), 3)  # C(3,2)
        self.assertGreaterEqual(d["max_pair"]["delta"], d["min_pair"]["delta"])
        self.assertTrue(all("mean_delta" in w for w in d["works"]))


if __name__ == "__main__":
    unittest.main()
