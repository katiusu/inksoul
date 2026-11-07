"""句法指纹测试：相似度、并簇、复用率、基线。"""
import unittest

from inksoul import fingerprint as fp
from inksoul.text_processor import process

PAIR_A = "他慢慢地推开了房门。"
PAIR_B = "她轻轻地关上了窗户。"


def skel(text):
    return process(text).clauses[0].skel


class TestSimilarity(unittest.TestCase):
    def test_parallel_pair_is_similar(self):
        sim = fp.similarity(skel(PAIR_A), skel(PAIR_B))
        self.assertGreaterEqual(sim, 0.6, (skel(PAIR_A), skel(PAIR_B)))

    def test_unrelated_is_not_similar(self):
        sim = fp.similarity(skel("桌面很干净。"), skel(PAIR_A))
        self.assertLess(sim, 0.6)

    def test_identical_is_one(self):
        self.assertAlmostEqual(fp.similarity(skel(PAIR_A), skel(PAIR_A)), 1.0)

    def test_zero_subject_not_merged(self):
        a = skel("推开了房门。")
        b = skel("他推开了房门。")
        self.assertFalse(fp._anchor_compatible(a, b), (a, b))

    def test_ba_vs_normal_not_merged(self):
        a = skel("她把窗户关上了。")
        b = skel("她关上了窗户。")
        self.assertFalse(fp._anchor_compatible(a, b), (a, b))

    def test_edit_distance_symmetric(self):
        a, b = skel(PAIR_A), skel(PAIR_B)
        self.assertEqual(fp.weighted_edit_distance(a, b), fp.weighted_edit_distance(b, a))


class TestReport(unittest.TestCase):
    def test_reuse_bounds(self):
        doc = process(PAIR_A + PAIR_B)
        r = fp.FingerprintEngine().analyze(doc)
        self.assertGreaterEqual(r.reuse_rate, 0.0)
        self.assertLessEqual(r.reuse_rate, 1.0)
        self.assertGreater(r.pattern_entropy, 0.0)
        self.assertLessEqual(r.distinct_patterns, r.clause_count)

    def test_suspect_needs_cross_paragraph(self):
        one_para = process("他走进屋里。他走进屋里。他走进屋里。")
        r1 = fp.FingerprintEngine().analyze(one_para)
        self.assertEqual(len(r1.suspects), 0, "同段重复不应算跨段机械复用")

    def test_suspect_detected_across_paragraphs(self):
        text = "\n\n".join(["他走进屋里。"] * 3)
        r = fp.FingerprintEngine().analyze(process(text))
        self.assertGreaterEqual(len(r.suspects), 1)

    def test_single_word_doc_has_no_patterns(self):
        r = fp.FingerprintEngine().analyze(process("嗯。"))
        self.assertEqual(r.clause_count, 0)
        self.assertEqual(r.distinct_patterns, 0)


class TestBaseline(unittest.TestCase):
    def test_coverage_and_novelty(self):
        human = "\n\n".join([PAIR_A, PAIR_B, "桌面很干净，什么也没有。"])
        base = fp.build_baseline([human], genre="小说")
        cov = base.coverage(process(human))
        self.assertGreaterEqual(cov["coverage"], 0.0)
        self.assertLessEqual(cov["coverage"], 1.0)
        self.assertAlmostEqual(cov["novelty"], 1.0 - cov["coverage"])

    def test_empty_baseline_build_raises(self):
        from inksoul.errors import InkSoulError
        with self.assertRaises(InkSoulError):
            fp.build_baseline([], genre="小说")

    def test_baseline_from_dict_roundtrip(self):
        human = "\n\n".join([PAIR_A, PAIR_B, "桌面很干净，什么也没有。"])
        base = fp.build_baseline([human], genre="小说")
        restored = fp.Baseline.from_dict(base.as_dict())
        self.assertEqual(restored.genre, "小说")
        self.assertGreater(len(restored.patterns), 0)
        self.assertAlmostEqual(base.coverage(process(human))["coverage"],
                               restored.coverage(process(human))["coverage"], places=6)

    def test_baseline_from_dict_falls_back_to_top_patterns(self):
        data = {"genre": "小说", "tau": 1.5, "top_patterns": [{"signature": "V N", "count": 2}]}
        base = fp.Baseline.from_dict(data)
        self.assertEqual(base.patterns[("V", "N")], 2)
        self.assertEqual(base.tau, 1.5)


class TestQuadraticGuards(unittest.TestCase):
    def test_many_clauses_reports_pairwise_sampling(self):
        text = "\n\n".join(["他把门推开。雨顺着屋檐落下来。" for _ in range(450)])
        r = fp.FingerprintEngine().analyze(process(text))
        self.assertGreater(r.clause_count, fp.PAIR_SAMPLE_CLAUSES)
        self.assertTrue(any("等距抽样" in n for n in r.notes), r.notes)

    def test_big_cluster_samples_variation(self):
        text = "\n\n".join(["他把门推开。" for _ in range(120)])
        r = fp.FingerprintEngine().analyze(process(text))
        self.assertTrue(any("簇内变异" in n for n in r.notes), r.notes)


if __name__ == "__main__":
    unittest.main()
