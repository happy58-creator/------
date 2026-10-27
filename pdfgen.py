"""終了後の結果PDF（表彰状）。計算・国語・英語・タイピング・プログラミングで共通。履歴からも同じPDFを作り直せる。

1ページ目が表彰状、2ページ目からが「こたえあわせ」の表。
"""
import io
import json
import math
import re
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

GOTHIC = "HeiseiKakuGo-W5"
MINCHO = "HeiseiMin-W3"
pdfmetrics.registerFont(UnicodeCIDFont(GOTHIC))
pdfmetrics.registerFont(UnicodeCIDFont(MINCHO))

NAVY = colors.HexColor("#1F2A44")
GOLD = colors.HexColor("#C9A227")
GOLD_DARK = colors.HexColor("#9C7A12")
GOLD_LIGHT = colors.HexColor("#F3E3A3")
CREAM = colors.HexColor("#FFFCF2")
RED = colors.HexColor("#C0392B")
INK = colors.HexColor("#2C3A4F")

# PDFのフォントに絵文字は入っていないので取り除く
_EMOJI = re.compile("[\U0001F000-\U0001FFFF☀-➿⬀-⯿️‍⃣]")


def comment_for(score):
    if score >= 100:
        return "完璧です！文句なしの100点満点、天才だね！この調子でどんどん挑戦しよう！"
    if score >= 80:
        return "素晴らしい成績です！あともう少しで満点だったね。次は絶対パーフェクトだ！"
    return "最後までよく頑張りました！間違えたところを見直して、もう一回練習すれば絶対にできるようになるよ。応援しているよ！"


def _clean(text):
    return escape(_EMOJI.sub("", str(text if text is not None else ""))).replace("\n", "<br/>")


def _japanese_date(played_at):
    try:
        d = datetime.strptime(str(played_at)[:10], "%Y-%m-%d")
        return f"{d.year}年{d.month}月{d.day}日"
    except ValueError:
        return str(played_at or "")


def make_record(subject, info, rows):
    """履歴に保存する詳細（JSON文字列）。rows は (問題, あなたの答え, 正しい答え, 正解か) の並び。"""
    return json.dumps(
        {"s": subject, "i": info, "r": [[q, a, c, 1 if ok else 0] for q, a, c, ok in rows]},
        ensure_ascii=False, separators=(",", ":"),
    )


# ---------------------------------------------------------------- 飾り（図形）
def _star(canv, cx, cy, r, fill):
    pts = []
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    path = canv.beginPath()
    path.moveTo(*pts[0])
    for p in pts[1:]:
        path.lineTo(*p)
    path.close()
    canv.setFillColor(fill)
    canv.setStrokeColor(GOLD_DARK if fill == GOLD else colors.HexColor("#CFCFCF"))
    canv.setLineWidth(0.6)
    canv.drawPath(path, fill=1, stroke=1)


class Stars(Flowable):
    """5つ星。点数に応じて金色にする。"""

    def __init__(self, score, size=13):
        super().__init__()
        self.count = max(0, min(5, round(score / 20)))
        self.size = size
        self.width, self.height = 5 * size * 2.4, size * 2.2

    def draw(self):
        gap = self.size * 2.4
        for i in range(5):
            _star(self.canv, gap / 2 + i * gap, self.height / 2, self.size, GOLD if i < self.count else colors.HexColor("#E6E6E6"))


class Medal(Flowable):
    """金のメダル（点数入り）。"""

    def __init__(self, score):
        super().__init__()
        self.score = score
        self.scale = 1.12
        self.width, self.height = 150 * self.scale, 150 * self.scale

    def draw(self):
        c = self.canv
        c.scale(self.scale, self.scale)
        cx, cy = 75, 84
        # リボンの足
        for dx, col in ((-22, RED), (22, colors.HexColor("#A93226"))):
            p = c.beginPath()
            x = cx + dx
            p.moveTo(x - 17, cy - 24)
            p.lineTo(x + 17, cy - 24)
            p.lineTo(x + 17 + (8 if dx > 0 else -8), cy - 74)
            p.lineTo(x, cy - 62)
            p.lineTo(x - 17 + (8 if dx > 0 else -8), cy - 74)
            p.close()
            c.setFillColor(col)
            c.setStrokeColor(colors.HexColor("#7B241C"))
            c.setLineWidth(0.6)
            c.drawPath(p, fill=1, stroke=1)
        # メダル本体（ぎざぎざの縁 → 金 → 内側の輪）
        c.setFillColor(GOLD_DARK)
        c.setStrokeColor(GOLD_DARK)
        teeth = 36
        for i in range(teeth):
            ang = 2 * math.pi * i / teeth
            c.circle(cx + 58 * math.cos(ang), cy + 58 * math.sin(ang), 3.4, fill=1, stroke=0)
        c.setFillColor(GOLD)
        c.circle(cx, cy, 58, fill=1, stroke=0)
        c.setStrokeColor(GOLD_DARK)
        c.setLineWidth(1.4)
        c.circle(cx, cy, 58, fill=0, stroke=1)
        c.setFillColor(CREAM)
        c.circle(cx, cy, 46, fill=1, stroke=0)
        c.setStrokeColor(GOLD)
        c.setLineWidth(1.2)
        c.circle(cx, cy, 46, fill=0, stroke=1)
        c.circle(cx, cy, 42, fill=0, stroke=1)
        # 点数
        text = f"{self.score:g}" if isinstance(self.score, (int, float)) else str(self.score)
        size = 44 if len(text) <= 2 else 36
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", size)
        c.drawCentredString(cx, cy - size * 0.18, text)
        c.setFont(MINCHO, 11)
        c.setFillColor(GOLD_DARK)
        c.drawCentredString(cx, cy - 33, "/ 100 点")


class Seal(Flowable):
    """赤い角印（「賞」）。"""

    def __init__(self, size=46):
        super().__init__()
        self.width = self.height = size

    def draw(self):
        c, s = self.canv, self.width
        c.saveState()
        c.setFillColor(RED)
        c.roundRect(2, 2, s - 4, s - 4, 5, fill=1, stroke=0)
        c.setStrokeColor(colors.white)
        c.setLineWidth(1)
        c.roundRect(5, 5, s - 10, s - 10, 3, fill=0, stroke=1)
        c.setFillColor(colors.white)
        c.setFont(MINCHO, s * 0.55)
        c.drawCentredString(s / 2, s * 0.28, "賞")
        c.restoreState()


class Rule(Flowable):
    """金色の飾り線（中央に菱形）。"""

    def __init__(self, width=300):
        super().__init__()
        self.width, self.height = width, 10
        self.hAlign = "CENTER"

    def draw(self):
        c, w = self.canv, self.width
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.line(0, 5, w / 2 - 12, 5)
        c.line(w / 2 + 12, 5, w, 5)
        c.setFillColor(GOLD)
        d = c.beginPath()
        d.moveTo(w / 2, 10)
        d.lineTo(w / 2 + 6, 5)
        d.lineTo(w / 2, 0)
        d.lineTo(w / 2 - 6, 5)
        d.close()
        c.drawPath(d, fill=1, stroke=0)


def _page_frame(canvas, doc):
    """全ページ共通：クリーム色の地 + 紺と金の二重の枠 + 四隅の飾り。"""
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(CREAM)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(4)
    canvas.rect(20, 20, w - 40, h - 40)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1.4)
    canvas.rect(29, 29, w - 58, h - 58)
    canvas.setLineWidth(0.5)
    canvas.rect(34, 34, w - 68, h - 68)
    # 四隅：金の菱形 + 小さな円
    for x, y in ((29, 29), (w - 29, 29), (29, h - 29), (w - 29, h - 29)):
        canvas.setFillColor(GOLD)
        d = canvas.beginPath()
        d.moveTo(x, y + 11)
        d.lineTo(x + 11, y)
        d.lineTo(x, y - 11)
        d.lineTo(x - 11, y)
        d.close()
        canvas.drawPath(d, fill=1, stroke=0)
        canvas.setFillColor(NAVY)
        canvas.circle(x, y, 3.2, fill=1, stroke=0)
    canvas.restoreState()


def _style(name, **kw):
    base = dict(fontName=GOTHIC, fontSize=10, leading=13, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


def build_pdf(subject, info, name, played_at, score, rows, comment=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=58, leftMargin=58, topMargin=62, bottomMargin=58,
        title=f"{subject} 表彰状",
    )
    score_num = int(float(score or 0))
    comment = comment or comment_for(score_num)
    who = _clean(name) or "あなた"

    subject_style = _style("subject", fontName=MINCHO, fontSize=15, leading=20, alignment=1, textColor=GOLD_DARK)
    info_style = _style("info", fontSize=9.5, leading=13, alignment=1, textColor=colors.HexColor("#6B7385"))
    title_style = _style("title", fontName=MINCHO, fontSize=56, leading=64, alignment=1, textColor=NAVY)
    name_style = _style("name", fontName=MINCHO, fontSize=34, leading=42, alignment=1, textColor=NAVY)
    body_style = _style("body", fontName=MINCHO, fontSize=16, leading=29, alignment=1, textColor=INK)
    comment_style = _style("comment", fontSize=10.5, leading=16, alignment=1, textColor=colors.HexColor("#5B6578"))
    foot_style = _style("foot", fontName=MINCHO, fontSize=12, leading=18, textColor=INK)
    foot_right = _style("footr", fontName=MINCHO, fontSize=12, leading=18, textColor=INK, alignment=2)

    story = [
        Paragraph(f"ーー　{_clean(subject)}　ーー", subject_style),
        Paragraph(_clean(info), info_style),
        Spacer(1, 20),
        Paragraph("表　彰　状", title_style),
        Spacer(1, 4),
        Rule(340),
        Spacer(1, 26),
        Paragraph(f"<u>　{who}　</u>　殿", name_style),
        Spacer(1, 22),
        Paragraph(
            f"あなたは「{_clean(subject)}」で<br/>"
            f"100点満点中　<font color='#C0392B'><b>{score_num}点</b></font>　をとり、<br/>"
            "さいごまで よくがんばりました。<br/>"
            "よって ここに ひょうしょうします。",
            body_style,
        ),
        Spacer(1, 14),
        Table([[Medal(score_num)]], colWidths=[400], rowHeights=[170], style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])),
        Table([[Stars(score_num)]], colWidths=[400], style=TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")])),
        Spacer(1, 6),
        Paragraph(_clean(comment), comment_style),
        Spacer(1, 26),
        Table(
            [[Paragraph(_japanese_date(played_at), foot_style), Seal(54), Paragraph("きょうざい・ゲームひろば", foot_right)]],
            colWidths=[160, 70, 180], style=TableStyle([
                ("ALIGN", (1, 0), (1, 0), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        ),
        PageBreak(),
        # --- 2ページ目：こたえあわせ ---
        Paragraph("こたえあわせ ひょう", _style("h2", fontName=MINCHO, fontSize=22, leading=28, alignment=1, textColor=NAVY)),
        Spacer(1, 2),
        Rule(240),
        Spacer(1, 8),
        Paragraph(f"{who}　／　{_clean(subject)}　／　{_clean(played_at)}", info_style),
        Paragraph(_clean(info), info_style),
        Spacer(1, 4),
        Paragraph(
            f"せいかい　<b>{sum(1 for r in rows if r[3])} / {len(rows)}</b> もん　　とくてん　<b>{score_num} / 100</b> 点",
            _style("sum", fontSize=11, leading=16, alignment=1, textColor=NAVY),
        ),
        Spacer(1, 10),
    ]

    hdr = _style("hdr", alignment=1, textColor=colors.white)
    long_text = any(len(str(r[0])) > 18 or len(str(r[2])) > 14 for r in rows)
    cell_center = _style("cell", alignment=1)
    cell_left = _style("cellL", alignment=0)
    table_data = [[Paragraph(f"<b>{t}</b>", hdr) for t in ("もんだい", "きみのこたえ", "正しいこたえ", "はんてい")]]
    for q, a, c, ok in rows:
        mark = '<font color="#1E8449"><b>◎ せいかい</b></font>' if ok else '<font color="#C0392B"><b>△ おしい！</b></font>'
        table_data.append([
            Paragraph(_clean(q), cell_left if long_text else cell_center),
            Paragraph(_clean(a), cell_center),
            Paragraph(_clean(c), cell_center),
            Paragraph(mark, cell_center),
        ])
    widths = [200, 105, 105, 75] if long_text else [140, 100, 100, 100]
    table = Table(table_data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F1DA")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 1, GOLD),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, GOLD_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame)
    return buffer.getvalue()


def pdf_from_history(record):
    """履歴の1行（辞書）から、そのときのPDFを作り直す。詳細が無い古い記録は None。"""
    try:
        detail = json.loads(record.get("詳細") or "")
        rows = [(q, a, c, bool(ok)) for q, a, c, ok in detail["r"]]
    except Exception:
        return None
    return build_pdf(
        detail["s"], detail["i"], record.get("名前", ""), record.get("日時", ""),
        record.get("点数", 0), rows,
    )
