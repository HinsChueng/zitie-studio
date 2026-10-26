"""文本清洗、中文断行（避头尾禁则）、以及练习行的编排。

这里刻意和渲染分开：编排只产出「每一行有哪些格子、每格写什么、用什么样式」，
渲染层拿到的就是一张纯数据表，便于单独测试。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# 不能出现在行首的字符（避头）
NO_START = set("。，、；：？！）］｝〉》」』】”’…—·％‰℃,.;:?!)]}>")
# 不能出现在行尾的字符（避尾）
NO_END = set("（［｛〈《「『【“‘([{<")

FULL_PUNCT = set("，。、；：？！“”‘’（）【】《》〈〉「」『』…—·～％‰")
# 适合断行的句读标点
PUNCT_BREAK = set("。！？，、；：")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _to_traditional(text: str) -> str:
    try:
        from zhconv import convert

        return convert(text, "zh-hant")
    except Exception:  # 没装 zhconv 时降级为原文
        return text


def normalize(text: str, keep_punct: bool = True, traditional: bool = False) -> str:
    """统一换行符，按需保留标点与数字，其余字符丢弃。"""
    if traditional:
        text = _to_traditional(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    out: list[str] = []
    for ch in text:
        if ch == "\n":
            out.append("\n")
        elif CJK.match(ch) or ch in FULL_PUNCT:
            out.append(ch)
        elif ch.isalnum():          # 数字、英文字母保留，便于练数字或英文
            out.append(ch)
        elif keep_punct and ch in ",.;:?!":
            out.append(ch)
        # 其余（空白、emoji、其他符号）丢弃
    return "".join(out)


def wrap(paragraph: str, cols: int, rule: bool = True, break_at_punct: bool = False) -> list[str]:
    """把一段文字按每行 cols 格切行，并处理避头尾禁则。

    break_at_punct=True 时优先在标点后断行（诗句、文句更符合字帖习惯），
    只有当所有句子都能放进一行时才这么做，否则退回硬切。
    """
    if cols <= 0:
        raise ValueError("cols 必须为正数")

    if break_at_punct:
        segs = _split_after_punct(paragraph)
        if segs and max(len(s) for s in segs) <= cols:
            out: list[str] = []
            for seg in segs:
                out.extend(_hard_wrap(seg, cols, rule))
            return out

    return _hard_wrap(paragraph, cols, rule)


def _split_after_punct(text: str) -> list[str]:
    """在句末标点后切开，标点留在前一句末尾"""
    segs: list[str] = []
    cur = ""
    for ch in text:
        cur += ch
        if ch in PUNCT_BREAK:
            segs.append(cur)
            cur = ""
    if cur:
        segs.append(cur)

    # 一两个字的碎片并回上一句，避免出现孤零零的短行
    merged: list[str] = []
    for seg in segs:
        if merged and len(seg) <= 2:
            merged[-1] += seg
        else:
            merged.append(seg)
    return merged


def _hard_wrap(paragraph: str, cols: int, rule: bool = True) -> list[str]:
    lines: list[str] = []
    cur: list[str] = []
    total = len(paragraph)

    for i, ch in enumerate(paragraph):
        cur.append(ch)
        if len(cur) < cols:
            continue

        # 已经是最后一个字，不必为禁则腾位置，直接收行
        if i == total - 1:
            lines.append("".join(cur))
            cur = []
        elif rule and ch in NO_START and len(cur) > 1:
            # 标点被顶到行首：把标点和它前一个字一起挪到下一行
            punct = cur.pop()
            carry = cur.pop()
            lines.append("".join(cur))
            cur = [carry, punct]
        elif rule and len(cur) > 1 and cur[-1] in NO_END:
            # 行尾悬着开引号 / 左括号：一起挪下去
            carry = cur.pop()
            lines.append("".join(cur))
            cur = [carry]
        else:
            lines.append("".join(cur))
            cur = []

    if cur:
        lines.append("".join(cur))
    return lines


def paragraphs(text: str, cols: int, rule: bool = True, break_at_punct: bool = False) -> list[str]:
    """按原始换行分段，再逐段断行；保留用户手动换行。"""
    out: list[str] = []
    for para in text.split("\n"):
        if para:
            out.extend(wrap(para, cols, rule, break_at_punct))
    return out


@dataclass(frozen=True)
class Slot:
    """一个格子：写哪个字、用什么样式（blank 用 None 表示空格）"""

    char: str
    style: str  # demo | trace


def compose_rows(p) -> list[list[Slot | None]]:
    """按练习模式把正文编排成「行 → 格子」的结构。

    demo  : 每字一遍实心示范
    trace : 每字一遍描红
    mixed : 行内分段，前 demo_cells 格实心、中 trace_cells 格描红、其余留空
    rotate: 三行一组，示范行 → 描红行 → 空白行（经典诗文帖排法）
    """
    lines = paragraphs(normalize(p.text, p.keep_punct, p.traditional), p.columns,
                       p.line_break_rule, p.break_at_punct)
    rows: list[list[Slot | None]] = []
    cols = p.columns

    if p.mode in ("demo", "trace"):
        style = "demo" if p.mode == "demo" else "trace"
        for line in lines:
            rows.append([Slot(ch, style) for ch in line])

    elif p.mode == "mixed":
        span = max(1, p.demo_cells + p.trace_cells)
        if p.repeat:
            # 单字重复练习：一行只练一个字；标点不进单字练习
            for line in lines:
                for ch in line:
                    if ch in FULL_PUNCT or ch in ",.;:?!":
                        continue
                    row = []
                    for i in range(cols):
                        if i < p.demo_cells:
                            row.append(Slot(ch, "demo"))
                        elif i < p.demo_cells + p.trace_cells:
                            row.append(Slot(ch, "trace"))
                        else:
                            row.append(None)
                    rows.append(row)
        else:
            # 整句连排：一行内按段分配样式
            for line in lines:
                for start in range(0, len(line), span):
                    chunk = line[start:start + span]
                    row = []
                    for i in range(cols):
                        if i < len(chunk):
                            style = "demo" if i < p.demo_cells else "trace"
                            row.append(Slot(chunk[i], style))
                        else:
                            row.append(None)
                    rows.append(row)

    else:  # rotate
        blank_row: list[Slot | None] = []
        for line in lines:
            slots = [Slot(ch, "demo") for ch in line]
            slots_t = [Slot(ch, "trace") for ch in line]
            for _ in range(p.cycle_demo):
                rows.append(list(slots))
            for _ in range(p.cycle_trace):
                rows.append(list(slots_t))
            for _ in range(p.cycle_blank):
                rows.append(list(blank_row))

    return rows


def paginate(rows: list[list[Slot | None]], rows_per_page: int) -> list[list[list[Slot | None]]]:
    """按每页行数切页；行数恰好整除时不额外产生空页。"""
    if not rows:
        return [[]]
    return [rows[i:i + rows_per_page] for i in range(0, len(rows), rows_per_page)]
