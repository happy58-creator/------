"""終了後の結果PDF（賞状形式）。計算・国語・英語・プログラミングで共通。履歴からも同じPDFを作り直せる。"""
import io
import json
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT = "HeiseiKakuGo-W5"
pdfmetrics.registerFont(UnicodeCIDFont(FONT))

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


def make_record(subject, info, rows):
    """履歴に保存する詳細（JSON文字列）。rows は (問題, あなたの答え, 正しい答え, 正解か) の並び。"""
    return json.dumps(
        {"s": subject, "i": info, "r": [[q, a, c, 1 if ok else 0] for q, a, c, ok in rows]},
        ensure_ascii=False, separators=(",", ":"),
    )


def build_pdf(subject, info, name, played_at, score, rows, comment=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25,
        title=f"{subject} 結果",
    )

    def style(name_, **kw):
        base = dict(fontName=FONT, fontSize=10, leading=12, textColor=colors.HexColor("#34495E"))
        base.update(kw)
        return ParagraphStyle(name_, **base)

    title_style = style("Award_Title", fontSize=24, leading=28, alignment=1, textColor=colors.HexColor("#1A252F"))
    subtitle_style = style("Award_Subtitle", fontSize=11, leading=14, alignment=1, textColor=colors.HexColor("#7F8C8D"))
    score_style = style("Award_Score", fontSize=34, leading=38, alignment=1, textColor=colors.HexColor("#D35400"))
    msg_title_style = style("Award_MsgTitle", leading=14, textColor=colors.HexColor("#2C3E50"))
    msg_style = style("Award_Msg", fontSize=11, leading=15, textColor=colors.HexColor("#2C3E50"))
    hdr_style = style("Table_Hdr", alignment=1, textColor=colors.white)
    long_text = any(len(str(r[0])) > 18 or len(str(r[2])) > 14 for r in rows)
    cell_center = style("Table_Cell", alignment=1)
    cell_left = style("Table_CellLeft", alignment=0)

    story = [
        Paragraph("<b>表 彰 状</b>", title_style),
        Spacer(1, 4),
        Paragraph(f"ーーー {_clean(subject)}の証 ーーー", subtitle_style),
        Spacer(1, 10),
        Paragraph(f"なまえ：{_clean(name)}　　{_clean(played_at)}", subtitle_style),
        Paragraph(_clean(info), subtitle_style),
        Spacer(1, 6),
        Paragraph(f"<b>得点：{_clean(score)} / 100 点</b>", score_style),
        Spacer(1, 10),
        Paragraph("<b>【 お祝いのことば 】</b>", msg_title_style),
        Spacer(1, 2),
        Paragraph(_clean(comment or comment_for(int(float(score or 0)))), msg_style),
        Spacer(1, 12),
    ]

    table_data = [[Paragraph(f"<b>{t}</b>", hdr_style) for t in ("問題", "きみのこたえ", "正しいこたえ", "はんてい")]]
    for q, a, c, ok in rows:
        status = '<font color="#27AE60"><b>せいかい</b></font>' if ok else '<font color="#E91E63"><b>おしい！</b></font>'
        table_data.append([
            Paragraph(_clean(q), cell_left if long_text else cell_center),
            Paragraph(_clean(a), cell_center),
            Paragraph(_clean(c), cell_center),
            Paragraph(status, cell_center),
        ])
    widths = [200, 120, 120, 75] if long_text else [150, 110, 110, 110]
    table = Table(table_data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)

    def draw_border(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#2C3E50"))
        canvas.setLineWidth(1)
        canvas.rect(10, 10, doc_.pagesize[0] - 20, doc_.pagesize[1] - 20)
        canvas.setLineWidth(2.5)
        canvas.rect(14, 14, doc_.pagesize[0] - 28, doc_.pagesize[1] - 28)
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_border, onLaterPages=draw_border)
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
