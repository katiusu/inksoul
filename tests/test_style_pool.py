"""人类池距离：把「像不像人」做成到人类池中心的相对距离。"""
import json
import unittest
from unittest import mock

from inksoul import style_pool as sp
from inksoul.agent import RoundRecord


POOL = {"genres": {"网文": {"chunks": 4, "dims": {
    "reuse_rate": {"mean": 0.2, "std": 0.1, "p10": 0.1, "p90": 0.3},
    "mean_pairwise_similarity": {"mean": 0.45, "std": 0.02, "p10": 0.43, "p90": 0.47},
    "conj_per_kchar": {"mean": 14.0, "std": 5.0, "p10": 9.0, "p90": 19.0},
    "long_sentence_share": {"mean": 0.63, "std": 0.16, "p10": 0.45, "p90": 0.8},
    "dialogue_ratio": {"mean": 0.23, "std": 0.16, "p10": 0.05, "p90": 0.44},
    "information_density_mean": {"mean": 3.2, "std": 0.42, "p10": 2.8, "p90": 3.7},
}}}}


def vec(**over):
    base = {"reuse_rate": 0.2, "mean_pairwise_similarity": 0.45, "conj_per_kchar": 14.0,
            "long_sentence_share": 0.63, "dialogue_ratio": 0.23, "information_density_mean": 3.2}
    base.update(over)
    return base


class TestDistance(unittest.TestCase):
    def test_center_is_zero(self):
        self.assertAlmostEqual(sp.distance(vec(), POOL), 0.0, places=3)

    def test_farther_is_larger(self):
        near = sp.distance(vec(conj_per_kchar=19.0), POOL)
        far = sp.distance(vec(conj_per_kchar=6.0, reuse_rate=0.35), POOL)
        self.assertLess(near, far)

    def test_missing_dims_downweight(self):
        partial = {"reuse_rate": 0.3}
        self.assertIsNotNone(sp.distance(partial, POOL))

    def test_no_pool_returns_none(self):
        self.assertIsNone(sp.distance(vec(), {}))
        self.assertIsNone(sp.distance(vec(), {"genres": {}}))

    def test_metrics_from_dict(self):
        data = {"style": {"conj_per_kchar": 12.0, "long_sentence_share": 0.5},
                "narrative": {"dialogue_ratio": 0.1, "information_density_mean": 3.0},
                "fingerprint": {"reuse_rate": 0.25, "mean_pairwise_similarity": 0.44}}
        got = sp.metrics_from_dict(data)
        self.assertEqual(got["conj_per_kchar"], 12.0)
        self.assertEqual(got["dialogue_ratio"], 0.1)
        self.assertEqual(len(got), 6)

    def test_dim_report_sorted_by_abs_z(self):
        rows = sp.dim_report(vec(conj_per_kchar=4.0), POOL)
        self.assertEqual(rows[0]["dim"], "conj_per_kchar")
        self.assertLess(rows[0]["z"], -1.0)


class TestRankTieBreak(unittest.TestCase):
    def test_distance_breaks_ties(self):
        a = RoundRecord(label="a", round=1, chars=900, blocking=1, issues=2, style_distance=1.9)
        b = RoundRecord(label="b", round=2, chars=900, blocking=1, issues=2, style_distance=1.1)
        self.assertLess(b.rank(), a.rank())

    def test_missing_distance_sorts_last(self):
        a = RoundRecord(label="a", round=1, chars=900, blocking=1, issues=2)
        b = RoundRecord(label="b", round=2, chars=900, blocking=1, issues=2, style_distance=5.0)
        self.assertLess(b.rank(), a.rank())

    def test_gate_and_blocking_still_dominate(self):
        bad = RoundRecord(label="bad", round=1, chars=900, blocking=0, issues=0, style_distance=0.1)
        bad.gate_status = "fail"
        ok = RoundRecord(label="ok", round=2, chars=900, blocking=9, issues=9, style_distance=3.0)
        self.assertLess(ok.rank(), bad.rank())


class TestShippedPool(unittest.TestCase):
    def test_pool_file_loads(self):
        pool = sp.load_pool()
        self.assertTrue(pool, "data/human_style_zh.json 缺失")
        genre = pool["genres"]["网文"]
        self.assertGreaterEqual(genre["chunks"], 100)
        self.assertEqual(len(genre["books"]), 2)
        for k in sp.DIMS:
            self.assertIn(k, genre["dims"])
            self.assertGreater(genre["dims"][k]["std"], 0.0)

    def test_human_like_scores_lower_than_stiff(self):
        pool = sp.load_pool()
        human = vec(reuse_rate=0.19, mean_pairwise_similarity=0.446, conj_per_kchar=14.2,
                    long_sentence_share=0.63, dialogue_ratio=0.23, information_density_mean=3.2)
        ai = vec(reuse_rate=0.31, mean_pairwise_similarity=0.49, conj_per_kchar=6.0,
                 long_sentence_share=0.30, dialogue_ratio=0.13, information_density_mean=2.6)
        self.assertLess(sp.distance(human, pool), sp.distance(ai, pool) - 0.5)


if __name__ == "__main__":
    unittest.main()

class TestAnalyzerWiring(unittest.TestCase):
    def test_analyze_reports_pool_distance(self):
        from inksoul.analyzer import Analyzer
        from inksoul.config import InkSoulConfig

        text = ("他推开门，风把桌上的纸吹散了。她把外套挂好，没说话。" * 20)
        rep = Analyzer(InkSoulConfig()).analyze(text)
        self.assertIsNotNone(rep.style_pool)
        self.assertGreater(rep.style_pool["distance"], 0.0)
        self.assertTrue(rep.style_pool["dims"])
        self.assertIn("style_pool", rep.as_dict())

