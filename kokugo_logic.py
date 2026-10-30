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
# 科目（学年ごとにえらべる科目と、10問の内訳）
#   read  : 漢字の読み（書いて答える）     write : 漢字の書き取り（書いて答える）
#   text  : 本文の読解（3択）             essay : 自分で書く（AIが採点・目安）
#   kana  : 古典の歴史的かなづかい → 現代かなづかい（書いて答える）
#   classic: 古典の読解（3択）
# ---------------------------------------------------------------------------
TOTAL = 10
POINT = 10

VIEWS_STORY = ["登場人物の気持ち", "行動の理由", "言葉や表現の意味", "場面の様子", "心の変化", "話の順序やつながり", "指示語がさすもの"]
VIEWS_ESSAY = ["筆者の主張", "理由・根拠", "具体と抽象", "対比", "指示語がさすもの", "段落の役割", "要旨", "言葉の意味"]
VIEWS_NOVEL = ["心情", "表現の効果", "比喩・象徴", "人物像", "語り手の視点", "主題", "場面の転換"]
VIEWS_EXPR = ["文章の構成", "表現の工夫", "相手や目的に合った伝え方", "敬語の使い方", "要約", "根拠の示し方", "言葉の選び方"]
VIEWS_CLASSIC = ["現代語訳", "古語の意味", "主語・登場人物", "内容・理由", "作者の考え・主題", "表現・修辞", "文法（助動詞・係り結び・敬語など）", "漢文の句法・書き下し"]

KANBUN_LIKE = ("kanbun", "kanshi")


def _plan(*parts):
    out = []
    for kind, n in parts:
        out += [kind] * n
    return out


COURSES = {
    "sho": {"name": "国語", "grades": GRADES[:6], "genre": "story", "plan": _plan(("read", 3), ("write", 3), ("text", 4)),
            "desc": "お話を読んで、漢字の読み書きと読解"},
    "chu1": {"name": "国語", "grades": ["中1"], "genre": "story", "plan": _plan(("read", 2), ("write", 2), ("text", 3), ("kana", 1), ("classic", 2)),
             "classic": ("中", ("kobun", "kanbun", "kanshi", "waka")), "desc": "お話の読解と、古典の入門"},
    "chu_gendai": {"name": "現代文中心", "grades": ["中2", "中3"], "genre": "story", "plan": _plan(("read", 2), ("write", 2), ("text", 6)),
                   "desc": "物語を読んで、漢字と読解をしっかり"},
    "chu_koten": {"name": "古典中心", "grades": ["中2", "中3"], "genre": "guide", "plan": _plan(("read", 2), ("write", 2), ("kana", 1), ("classic", 5)),
                  "classic": ("中", ("kobun", "kanbun", "kanshi", "waka")), "desc": "古文・漢文・和歌を読む"},
    "gendai_kokugo": {"name": "現代の国語", "grades": ["高1"], "genre": "essay", "plan": _plan(("read", 2), ("write", 2), ("text", 6)),
                      "desc": "説明文・論説文で、主張と根拠を読み取る"},
    "gengo_bunka": {"name": "言語文化", "grades": ["高1"], "genre": "guide", "plan": _plan(("read", 2), ("write", 2), ("kana", 1), ("classic", 5)),
                    "classic": ("高", ("kobun", "kanbun", "kanshi", "waka", "kindai")), "desc": "古文・漢文・近代文学を読む"},
    "ronri": {"name": "論理国語", "grades": ["高2", "高3"], "genre": "critique", "plan": _plan(("read", 2), ("write", 2), ("text", 6)),
              "desc": "評論文で、論の進め方を読み解く"},
    "bungaku": {"name": "文学国語", "grades": ["高2", "高3"], "genre": "novel", "plan": _plan(("read", 2), ("write", 2), ("text", 6)),
                "desc": "小説を読んで、心情や表現を味わう"},
    "hyogen": {"name": "国語表現", "grades": ["高2", "高3"], "genre": "expression", "plan": _plan(("read", 2), ("write", 2), ("text", 4), ("essay", 2)),
               "desc": "伝わる文章を考えて、自分でも書く（AIが採点・目安）"},
    "koten_tankyu": {"name": "古典探究", "grades": ["高2", "高3"], "genre": "guide", "plan": _plan(("read", 2), ("write", 2), ("kana", 1), ("classic", 5)),
                     "classic": ("高", ("kobun", "kanbun", "kanshi", "waka")), "desc": "古文・漢文を、文法までふかく読む"},
}

GENRES = {
    "story": ("物語", "お話", VIEWS_STORY),
    "guide": ("古典への案内", "案内の文章", VIEWS_STORY),
    "essay": ("説明文・論説文", "文章", VIEWS_ESSAY),
    "critique": ("評論文", "文章", VIEWS_ESSAY),
    "novel": ("小説", "小説", VIEWS_NOVEL),
    "expression": ("スピーチ原稿・意見文などの実用的な文章", "文章", VIEWS_EXPR),
}


def courses_for(grade):
    return [cid for cid, c in COURSES.items() if grade in c["grades"]]


def course_plan(course_id, passage=None):
    """10問の種類。近代文学（歴史的かなづかいがない）のときは、かなづかいの問題を読解にする"""
    plan = list(COURSES[course_id]["plan"])
    if passage is not None and passage["kind"] == "kindai":
        plan = ["classic" if k == "kana" else k for k in plan]
    return plan


def section_count(plan):
    """お話（文章）の章の数＝古典以外の問題の数"""
    return sum(1 for k in plan if k not in ("kana", "classic"))


KIND_NAMES = {"read": "漢字の読み", "write": "漢字の書き取り", "text": "読解", "essay": "自分で書く",
              "kana": "古典のかなづかい", "classic": "古典の読解"}


# ---------------------------------------------------------------------------
# AIの出力の確認と、選択肢の並べ替え
# ---------------------------------------------------------------------------
def _hira_list(values):
    return [to_hiragana(clean(str(a))) for a in (values or []) if clean(str(a))]


def validate(data, plan, passage=None):
    """AIの出力をたしかめ、使える形にそろえて返す。だめなら ValueError"""
    if not isinstance(data, dict):
        raise ValueError("形がちがう")
    n_sec = section_count(plan)
    chapters = data.get("chapters")
    qs = data.get("questions")
    if not isinstance(chapters, list) or len(chapters) != n_sec:
        raise ValueError(f"文章の章が{n_sec}こない")
    if not isinstance(qs, list) or len(qs) != len(plan):
        raise ValueError(f"問題が{len(plan)}こない")
    out_ch = []
    for i, c in enumerate(chapters, 1):
        if not (isinstance(c, dict) and str(c.get("title", "")).strip() and str(c.get("story", "")).strip()):
            raise ValueError(f"第{i}章が足りない")
        out_ch.append({"title": str(c["title"]).strip(), "story": str(c["story"]).strip()})
    out_q, views, cviews = [], [], []
    sec = 0
    for n, (q, kind) in enumerate(zip(qs, plan), 1):
        if not isinstance(q, dict):
            raise ValueError(f"第{n}問の形がちがう")
        text = str(q.get("text", "")).strip()
        if not text:
            raise ValueError(f"第{n}問の問題文がない")
        item = {"kind": kind, "text": text, "ok": str(q.get("ok", "")).strip(), "ng": str(q.get("ng", "")).strip()}
        if kind in ("kana", "classic"):
            item["section"] = None
        else:
            item["section"] = sec
            sec += 1
        if kind == "read":
            word = clean(str(q.get("word", "")))
            answers = _hira_list(q.get("answers"))
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
        elif kind == "kana":
            word = clean(str(q.get("word", "")))
            answers = _hira_list(q.get("answers"))
            if not passage or not word or word not in clean(passage["text"]) or not answers \
                    or not all(re.fullmatch(r"[ぁ-ゖー]+", a) for a in answers):
                raise ValueError(f"第{n}問（かなづかい）がおかしい")
            item.update(word=word, answers=answers)
        elif kind == "essay":
            rubric = [str(r).strip() for r in (q.get("rubric") or []) if str(r).strip()]
            limit = q.get("limit") or [100, 200]
            try:
                lo, hi = int(limit[0]), int(limit[1])
            except Exception:
                lo, hi = 100, 200
            if len(rubric) < 2:
                raise ValueError(f"第{n}問（自分で書く）の採点の観点がない")
            item.update(rubric=rubric[:4], limit=[max(20, lo), max(lo + 20, hi)])
        else:   # text / classic：3択
            opts = [str(o).strip() for o in (q.get("opts") or []) if str(o).strip()]
            ans = str(q.get("ans", "")).strip()
            view = str(q.get("view", "")).strip() or "読解"
            if len(opts) != 3 or len(set(opts)) != 3 or ans not in opts:
                raise ValueError(f"第{n}問の選択肢がおかしい")
            (cviews if kind == "classic" else views).append(view)
            item.update(opts=opts, ans=ans, view=view)
        out_q.append(item)
    for vs, label in ((views, "読解"), (cviews, "古典")):
        if len(vs) >= 2 and len(set(vs)) < min(len(vs), 4):
            raise ValueError(f"{label}の問題の観点が同じものばかりになっている")
    return {"chapters": out_ch, "questions": out_q}


def shuffle_choices(quiz, rng=random):
    """3択の選択肢の順番をまぜる（正解の位置がかたよらないように）"""
    for q in quiz["questions"]:
        if q["kind"] in ("text", "classic"):
            rng.shuffle(q["opts"])
    return quiz


def essay_score(data):
    """AIの採点（0〜10点）をたしかめて返す"""
    try:
        score = int(round(float(data.get("score"))))
    except Exception:
        raise ValueError("点数がない")
    return max(0, min(10, score)), str(data.get("good", "")).strip(), str(data.get("advice", "")).strip()
