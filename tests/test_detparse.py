"""Unlimited-OCR output parsing, using the format shown in Baidu's own demo."""

from hyperocr.document import CAPTION, FIGURE, FORMULA, HEADING, PAGE_NUMBER, TABLE, TEXT, TITLE
from hyperocr.engines import detparse

RAW = (
    "<|det|>title [114, 50, 600, 70]<|/det|>Effect of Early Mobilisation\n"
    "<|det|>paragraph_title [114, 80, 255, 95]<|/det|>5. Evaluation\n"
    "<|det|>paragraph_title [114, 100, 357, 112]<|/det|>5.1. Benchmark and Metrics\n"
    "<|det|>text [113, 120, 884, 200]<|/det|>We select OmniDocBench \\( [23] \\) as the main\n"
    "benchmark for evaluating parsing.\n"
    "<|det|>list [139, 210, 884, 300]<|/det|>\n"
    "<|det|>text [140, 210, 884, 250]<|/det|>- First item\n"
    "<|det|>image [200, 310, 800, 600]<|/det|>\n"
    "<|det|>figure_title [200, 605, 800, 620]<|/det|>Figure 1. A chart.\n"
    "<|det|>table [137, 630, 860, 800]<|/det|><table><tr><td>Model</td><td colspan=\"2\">Size</td></tr>"
    "<tr><td onclick=\"x()\">A<script>bad()</script></td><td>3B</td><td>|</td></tr></table>\n"
    "<|det|>equation [300, 810, 700, 840]<|/det|>$$E = mc^2$$\n"
    "<|det|>page_number [493, 924, 506, 936]<|/det|>8\n"
    "<PAGE><|det|>text [112, 100, 888, 182]<|/det|>Second page text\n"
)


def test_split_pages():
    pages = detparse.split_pages(RAW)
    assert len(pages) == 2
    assert "Second page" in pages[1]


def test_parse_kinds_and_order():
    blocks = detparse.parse(detparse.split_pages(RAW)[0], 2000, 3000)
    kinds = [b.kind for b in blocks]
    assert kinds == [TITLE, HEADING, HEADING, TEXT, TEXT, FIGURE, CAPTION, TABLE, FORMULA, PAGE_NUMBER]
    assert blocks[1].level == 2 and blocks[2].level == 3  # "5.1." is a sub-section


def test_boxes_scale_from_0_1000_grid():
    blocks = detparse.parse(detparse.split_pages(RAW)[0], 2000, 3000)
    x0, y0, x1, y1 = blocks[0].box
    assert (round(x0), round(y0), round(x1), round(y1)) == (228, 150, 1200, 210)


def test_text_joins_model_line_breaks_and_keeps_inline_math():
    text = detparse.parse(detparse.split_pages(RAW)[0], 1000, 1000)[3].text
    assert text == "We select OmniDocBench \\( [23] \\) as the main benchmark for evaluating parsing."


def test_table_html_is_sanitised():
    table = [b for b in detparse.parse(RAW, 1000, 1000) if b.kind == TABLE][0]
    assert "script" not in table.html and "onclick" not in table.html
    assert 'colspan="2"' in table.html
    assert table.text.splitlines()[0] == "Model Size"


def test_formula_delimiters_removed():
    formula = [b for b in detparse.parse(RAW, 1000, 1000) if b.kind == FORMULA][0]
    assert formula.text == "E = mc^2"


def test_nested_box_brackets_and_unknown_labels():
    blocks = detparse.parse("<|det|>mystery [[10, 10, 500, 60]]<|/det|>Hello", 1000, 1000)
    assert blocks[0].kind == TEXT and blocks[0].text == "Hello"
    assert blocks[0].box == (10.0, 10.0, 500.0, 60.0)


def test_no_tags_becomes_one_text_block():
    blocks = detparse.parse("Plain words only", 100, 100)
    assert len(blocks) == 1 and blocks[0].text == "Plain words only"


def test_markdown_table_content():
    html = detparse.table_to_html("| a | b |\n| --- | --- |\n| 1 | 2 |")
    assert html == "<table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>"
