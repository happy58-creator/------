"""AI国語アドベンチャーの、画面に関係しない部分（学年・テーマのチェック・答え合わせ・AIの出力の確認）。

問題の構成（全10問・1問10点）
  1〜3問：漢字 → ひらがな（読みを書く）
  4〜6問：ひらがな → 漢字（漢字で書く。送りがなもみる）
  7〜10問：文章問題（3択。観点は1問ずつちがう）
"""
import random
import re
import unicodedata

# ---------------------------------------------------------------------------
# 学年（ログインしたときの年齢から決める。管理者・年齢がわからない人はえらぶ）
# ---------------------------------------------------------------------------
GRADES = ["小1", "小2", "小3", "小4", "小5", "小6", "中1", "中2", "中3", "高1", "高2", "高3"]
DEFAULT_GRADE = "小3"

GRADE_NAMES = {
    "小1": "小学1年生", "小2": "小学2年生", "小3": "小学3年生", "小4": "小学4年生", "小5": "小学5年生", "小6": "小学6年生",
    "中1": "中学1年生", "中2": "中学2年生", "中3": "中学3年生", "高1": "高校1年生", "高2": "高校2年生", "高3": "高校3年生",
}


def grade_for_age(age):
    """年齢 → 学年（6〜7さいは小1、12さいは小6、13さいは中1、18さい以上は高3）。わからなければ None"""
    try:
        age = int(age)
    except (TypeError, ValueError):
        return None
    if age <= 0:
        return None
    return GRADES[max(0, min(len(GRADES) - 1, age - 7 if age >= 7 else 0))]


def kanji_range(grade):
    """AIに伝える「使ってよい漢字」の範囲"""
    i = GRADES.index(grade)
    if i < 6:
        return f"小学{i + 1}年生までに習う漢字（学年別漢字配当表）"
    if i < 9:
        return "常用漢字のうち、中学校で読み書きできるようにする漢字"
    return "常用漢字（高校で読み書きできるようにする漢字。高校3年はやや難しい語もよい）"


def reading_level(grade):
    i = GRADES.index(grade)
    if i < 2:
        return "ひらがなを中心に、ごく短い文で。習った漢字だけを使う。"
    if i < 6:
        return "その学年の子が一人で読める文の長さと言葉づかいで。習っていない漢字はひらがなで書く。"
    if i < 9:
        return "中学生向けの文章。物語文の読解として、心情・理由・表現の効果などを問う。"
    return "高校生向けの文章。語彙はやや硬めでもよい。心情・論理・表現の工夫を問う。"


# ---------------------------------------------------------------------------
# テーマの入力チェック（長すぎる・ふざけた入力）
# ---------------------------------------------------------------------------
THEME_MAX = 15

_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890")


def theme_problem(text):
    """テーマに問題があれば ("long" | "silly" | "empty", 理由) を返す。なければ None。

    silly（ふざけた入力）は、おうちの人と相談してね、と出して記録する。
    """
    t = unicodedata.normalize("NFKC", text or "").strip()
    if not t:
        return "empty", "入力なし"
    if len(t) > THEME_MAX:
        return "long", f"{THEME_MAX}文字より長い"
    body = re.sub(r"[\s・、。,.!?！？〜~]", "", t)
    if not body or not re.search(r"[0-9A-Za-zぁ-ゖァ-ヺ\u4e00-\u9fff]", body):
        return "silly", "記号だけ"
    if re.fullmatch(r"[0-9ー]+", body):
        return "silly", "数字だけ"
    core = body.replace("ー", "")
    for p in (1, 2, 3):                      # ああああ・あいあいあ・abcabc など、短いまとまりのくり返し
        need = 3 if p == 1 else (2 * p + 1 if p == 2 else 2 * p)
        if len(core) >= need and all(core[i] == core[i - p] for i in range(p, len(core))):
            return "silly", "同じ文字のくり返し"
    if re.search(r"([^ーおあいうえっ])\1{3,}", core):   # 同じ文字が4つ以上つづく（のばす音 おおお などは ゆるす）
        return "silly", "同じ文字のくり返し"
    low = core.lower()
    if re.fullmatch(r"[a-z0-9]+", low) and len(low) >= 4:
        if any(low[i:i + 4] in row or low[i:i + 4] in row[::-1] for row in _KEYBOARD_ROWS for i in range(len(low) - 3)):
            return "silly", "キーボードをならべて打った"
        if re.fullmatch(r"[a-z]+", low) and not re.search(r"[aeiouy]", low):
            return "silly", "読めない英字"
    gojuon = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    if len(core) >= 4 and (core in gojuon or core in gojuon[::-1]):
        return "silly", "五十音をならべただけ"
    return None


# ---------------------------------------------------------------------------
# 答え合わせ
# ---------------------------------------------------------------------------
_KATA = {chr(c): chr(c - 0x60) for c in range(ord("ァ"), ord("ヶ") + 1)}


def to_hiragana(text):
    return "".join(_KATA.get(c, c) for c in text)


def clean(text):
    """全角・半角をそろえ、空白とかっこ・句読点をのぞく"""
    t = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"[\s「」『』（）()【】\[\]、。,.・]", "", t)


def is_kana(text):
    return bool(text) and bool(re.fullmatch(r"[ぁ-ゖァ-ヺー]+", text))


def has_kanji(text):
    return bool(re.search(r"[一-鿿々〆ヶ]", text or ""))


def check_reading(typed, answers):
    """漢字 → ひらがな。(結果, ひとこと)。結果は "ok" / "ng" / "retry"（採点しないで、書き直してもらう）"""
    t = to_hiragana(clean(typed))
    if not t:
        return "retry", "ひらがなで書いてね。"
    if has_kanji(t):
        return "retry", "漢字のままになっているよ。読み方を ひらがなで書いてね。"
    if t in {to_hiragana(clean(a)) for a in answers}:
        return "ok", ""
    return "ng", ""


def check_writing(typed, answers, reading=""):
    """ひらがな → 漢字。送りがなのまちがいは、それとわかるように知らせる"""
    t = clean(typed)
    if not t:
        return "retry", "漢字で書いてね。"
    if not has_kanji(t):
        if reading and to_hiragana(t) == to_hiragana(clean(reading)):
            return "retry", "ひらがなのままになっているよ。漢字に変えて書いてね。"
        return "retry", "漢字をつかって書いてね。"
    goods = [clean(a) for a in answers]
    if t in goods:
        return "ok", ""
    skeleton = lambda s: re.sub(r"[ぁ-ゖ]", "", to_hiragana(s))      # 漢字の部分だけ
    for g in goods:
        if skeleton(t) == skeleton(g) and to_hiragana(t) != to_hiragana(g):
            return "ng", "送りがなが ちがうよ。"
    return "ng", ""


# ---------------------------------------------------------------------------
# AIの出力の確認と、選択肢の並べ替え
# ---------------------------------------------------------------------------
READ_N, WRITE_N, TEXT_N = 3, 3, 4
TOTAL = READ_N + WRITE_N + TEXT_N
POINT = 100 // TOTAL


def question_kind(n):
    """n（1〜10）→ "read" / "write" / "text" """
    if n <= READ_N:
        return "read"
    if n <= READ_N + WRITE_N:
        return "write"
    return "text"


def validate(data):
    """AIの出力をたしかめ、使える形にそろえて返す。だめなら ValueError"""
    if not isinstance(data, dict):
        raise ValueError("形がちがう")
    chapters = data.get("chapters")
    qs = data.get("questions")
    if not isinstance(chapters, list) or len(chapters) != TOTAL:
        raise ValueError("お話の章が10こない")
    if not isinstance(qs, list) or len(qs) != TOTAL:
        raise ValueError("問題が10こない")
    out_ch = []
    for i, c in enumerate(chapters, 1):
        if not (isinstance(c, dict) and str(c.get("title", "")).strip() and str(c.get("story", "")).strip()):
            raise ValueError(f"第{i}章が足りない")
        out_ch.append({"title": str(c["title"]).strip(), "story": str(c["story"]).strip()})
    out_q = []
    views = set()
    for n, q in enumerate(qs, 1):
        kind = question_kind(n)
        if not isinstance(q, dict):
            raise ValueError(f"第{n}問の形がちがう")
        text = str(q.get("text", "")).strip()
        if not text:
            raise ValueError(f"第{n}問の問題文がない")
        item = {"kind": kind, "text": text, "ok": str(q.get("ok", "")).strip(), "ng": str(q.get("ng", "")).strip()}
        if kind == "read":
            word = clean(str(q.get("word", "")))
            answers = [to_hiragana(clean(a)) for a in (q.get("answers") or []) if clean(str(a))]
            if not word or not has_kanji(word) or not answers or not all(re.fullmatch(r"[ぁ-ゖー]+", a) for a in answers):
                raise ValueError(f"第{n}問（読み）の答えがおかしい")
            if word not in clean(text):
                raise ValueError(f"第{n}問の文に、読む言葉が入っていない")
            item.update(word=word, answers=answers)
        elif kind == "write":
            reading = to_hiragana(clean(str(q.get("reading", ""))))
            answers = [clean(a) for a in (q.get("answers") or []) if clean(str(a))]
            if not reading or not re.fullmatch(r"[ぁ-ゖー]+", reading) or not answers or not all(has_kanji(a) for a in answers):
                raise ValueError(f"第{n}問（書き）の答えがおかしい")
            if reading not in to_hiragana(clean(text)):
                raise ValueError(f"第{n}問の文に、書く言葉が入っていない")
            item.update(reading=reading, answers=answers)
        else:
            opts = [str(o).strip() for o in (q.get("opts") or []) if str(o).strip()]
            ans = str(q.get("ans", "")).strip()
            view = str(q.get("view", "")).strip()
            if len(opts) != 3 or len(set(opts)) != 3 or ans not in opts:
                raise ValueError(f"第{n}問の選択肢がおかしい")
            views.add(view)
            item.update(opts=opts, ans=ans, view=view or "読解")
        out_q.append(item)
    if len(views) < TEXT_N:
        raise ValueError("文章問題の観点が同じものになっている")
    return {"chapters": out_ch, "questions": out_q}


def shuffle_choices(quiz, rng=random):
    """文章問題の選択肢の順番をまぜる（正解の位置がかたよらないように）"""
    for q in quiz["questions"]:
        if q["kind"] == "text":
            rng.shuffle(q["opts"])
    return quiz
