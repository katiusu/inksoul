"""词性归一测试：把 jieba 的错标纠正回结构可用的骨架符号。"""
import unittest

from inksoul.nlp.backend import build_backend
from inksoul.text_processor import process


def skel(text):
    doc = process(text)
    out = []
    for cl in doc.clauses:
        out.extend(cl.skel)
    return out


class TestNormalizer(unittest.TestCase):
    def test_negation_word(self):
        self.assertIn("ADV_NEG", skel("他没有回答。"))

    def test_negation_as_verb_when_clause_final(self):
        # 「什么也没有。」里的「没有」是谓词，不是否定状语
        self.assertIn("V", skel("什么也没有。"))
        self.assertNotIn("ADV_NEG", skel("什么也没有。"))

    def test_ba_construction(self):
        self.assertIn("PREP_BA", skel("她把窗户关上了。"))

    def test_bei_construction(self):
        self.assertIn("PREP_BEI", skel("门被他推开了。"))

    def test_de_adverbial(self):
        ns = skel("他慢慢地走过来。")
        self.assertIn("DE_ADV", ns)

    def test_punctuation_marked(self):
        self.assertEqual(skel("他走了。")[-1], "P")

    def test_parallel_clauses_same_skeleton(self):
        a = process("他慢慢地推开了房门。").clauses[0].skel
        b = process("她轻轻地关上了窗户。").clauses[0].skel
        from inksoul import fingerprint as fp
        self.assertGreaterEqual(fp.similarity(a, b), 0.6, (a, b))


class TestBackend(unittest.TestCase):
    def test_jieba_exists(self):
        be = build_backend("jieba")
        self.assertIsNotNone(be)
        self.assertEqual(be.name, "jieba")

    def test_token_shape(self):
        be = build_backend("jieba")
        toks = be.analyze("他推开门。")
        self.assertTrue(toks)
        t = toks[0]
        for attr in ("word", "pos", "start", "end", "norm"):
            self.assertTrue(hasattr(t, attr), attr)
        self.assertEqual(toks[-1].word, "。")
        self.assertTrue(toks[-1].is_punct)


if __name__ == "__main__":
    unittest.main()
