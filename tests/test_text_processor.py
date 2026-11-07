"""文本预处理测试：切分、句长、边界与异常。"""
import unittest

from inksoul.text_processor import process
from inksoul.errors import InkSoulError


class TestProcess(unittest.TestCase):
    def test_basic_structure(self):
        doc = process("他推开门。她关上窗。")
        self.assertEqual(len(doc.paragraphs), 1)
        self.assertEqual(len(doc.paragraphs[0].sentences), 2)
        self.assertTrue(any(c.clauses for c in doc.paragraphs[0].sentences))

    def test_paragraphs_split_on_blank_line(self):
        doc = process("第一段。\n\n第二段。\n\n\n第三段。")
        self.assertEqual(len(doc.paragraphs), 3)

    def test_clause_split_on_comma(self):
        doc = process("桌面很干净，什么也没有。")
        clauses = doc.clauses
        self.assertGreaterEqual(len(clauses), 2, [c.text for c in clauses])

    def test_empty_input_raises(self):
        with self.assertRaises(InkSoulError):
            process("   ")

    def test_english_mixed(self):
        doc = process("他说 OK，然后走了。")
        self.assertGreaterEqual(len(doc.clauses), 2)

    def test_clause_ids_unique(self):
        doc = process("甲，乙，丙。丁，戊。")
        ids = [c.id for c in doc.clauses]
        self.assertEqual(len(ids), len(set(ids)))

    def test_whitespace_inside_text(self):
        doc = process("他   推开   门。")
        self.assertGreaterEqual(len(doc.clauses), 1)


if __name__ == "__main__":
    unittest.main()
