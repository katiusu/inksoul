"""论文驱动新增指标的回归测试：句长离散度、语料同质度、依存弧分布。

对应来源：
- 句长离散度 / 中等长度堆积：Munoz-Ortiz et al. 2024, AI Review 57:265
- 跨作品相似度（集体多样性）：Doshi & Hauser 2024, Science Advances
- 依存弧长/左右弧/树深：同 Munoz-Ortiz 2024
"""
import unittest

from inksoul import corpus as cp
from inksoul import dependency as dp
from inksoul.diversity import analyze_diversity, length_dispersion
from inksoul.errors import AnalysisError
from inksoul.nlp.backend import Token
from inksoul.text_processor import Document, Paragraph, Sentence, process

LONG = (
    "雨停在傍晚，屋檐还在滴水。"
    "他推开门，风把桌上的纸吹得满地都是。"
    "她没有说话，只是站在门口，看了很久很久。"
    "远处有狗在叫，一声长，一声短，像是谁在提醒什么。"
    "灯亮起来的时候，他才发现窗台上的花已经枯了。"
) * 5


def _fake_doc() -> Document:
    s1 = Sentence(id=0, para_id=0, text="我推门", tokens=[
        Token(0, "我", pos="PRON", head=1, deprel="nsubj"),
        Token(1, "推", pos="VERB", head=1, deprel="root"),
        Token(2, "门", pos="NOUN", head=1, deprel="obj"),
    ])
    s2 = Sentence(id=1, para_id=0, text="他很累了", tokens=[
        Token(0, "他", pos="PRON", head=2, deprel="nsubj"),
        Token(1, "很", pos="ADV", head=2, deprel="advmod"),
        Token(2, "累", pos="ADJ", head=2, deprel="root"),
        Token(3, "了", pos="PART", head=2, deprel="discourse:sp"),
    ])
    return Document(text="我推门。他很累了。", has_dependency=True,
                    paragraphs=[Paragraph(id=0, text="我推门。他很累了。", sentences=[s1, s2])])


class TestLengthDispersion(unittest.TestCase):
    def test_empty(self):
        d = length_dispersion([])
        self.assertEqual(d["n"], 0)
        self.assertEqual(d["cv"], 0.0)

    def test_single_value(self):
        d = length_dispersion([12, 12, 12])
        self.assertEqual(d["cv"], 0.0)
        self.assertEqual(d["mid_share"], 1.0)

    def test_more_scattered_has_higher_cv(self):
        tight = length_dispersion([20] * 10)
        loose = length_dispersion([3, 45, 8, 60, 12, 33, 5, 70, 19, 27])
        self.assertGreater(loose["cv"], tight["cv"])
        self.assertEqual(tight["mid_share"], 1.0)   # 全在 10-30 字带
        self.assertLess(loose["mid_share"], tight["mid_share"])

    def test_report_includes_field(self):
        rep = analyze_diversity(process(LONG))
        data = rep.as_dict()
        self.assertIn("length_dispersion", data)
        self.assertIn("mid_share", data["length_dispersion"])
        self.assertGreater(data["length_dispersion"]["n"], 0)


class TestDependency(unittest.TestCase):
    def test_needs_dependency_backend(self):
        doc = process("他推开门。")
        self.assertFalse(doc.has_dependency)
        with self.assertRaises(AnalysisError):
            dp.analyze_dependency(doc)

    def test_arc_stats(self):
        rep = dp.analyze_dependency(_fake_doc())
        self.assertEqual(rep.arc_count, 5)          # 2 + 3 条弧（根不算弧）
        self.assertAlmostEqual(rep.left_arc_share, 3 / 5, places=3)
        self.assertAlmostEqual(rep.arc_len_mean, 1.2, places=3)
        self.assertEqual(rep.deprel_shares["nsubj"], 0.4)
        self.assertGreaterEqual(rep.mean_tree_depth, 1.0)
        self.assertTrue(any("Ω" in n for n in rep.notes))

    def test_analyzer_degrades_to_placeholder(self):
        from inksoul.analyzer import analyze_text

        data = analyze_text("他推开门，屋里没有人。")["dependency"] if False else analyze_text(
            "他推开门，屋里没有人。").as_dict()["dependency"]
        self.assertIn("unavailable", data)
        self.assertIn("依存", data["reason"])


class TestCorpus(unittest.TestCase):
    def test_identical_works_are_near_identical(self):
        rep = cp.analyze_corpus({"a": LONG, "b": LONG})
        self.assertGreater(rep.mean_pairwise_similarity, 0.99)
        self.assertTrue(rep.max_pair["near_identical"])
        self.assertEqual(rep.n_compared, 2)

    def test_similarity_range_and_matrix(self):
        other = ("黄昏的时候，河面像一块旧铁。天边压着云，风从西边来。"
                 "她把伞收了，抖掉水珠，慢慢往桥上走。") * 5
        rep = cp.analyze_corpus({"a": LONG, "b": LONG, "c": other})
        d = rep.as_dict()
        self.assertEqual(d["n_compared"], 3)
        self.assertEqual(len(d["matrix"]), 3)       # C(3,2)
        for row in d["matrix"]:
            self.assertGreaterEqual(row["similarity"], 0.0)
            self.assertLessEqual(row["similarity"], 1.0)
        self.assertEqual(len(d["works"]), 3)
        # works 按「与同侪平均相似度」降序
        sims = [w["mean_similarity_to_others"] for w in d["works"]]
        self.assertEqual(sims, sorted(sims, reverse=True))

    def test_rejects_single_work(self):
        with self.assertRaises(AnalysisError):
            cp.analyze_corpus({"only": LONG})

    def test_rejects_too_short(self):
        with self.assertRaises(AnalysisError):
            cp.analyze_corpus({"a": "他推门。", "b": "她关窗。"})


if __name__ == "__main__":
    unittest.main()
