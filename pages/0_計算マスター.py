"""算数・数学マスター：練習問題（10問）と「学ぶ」。
画面はぜんぶ JavaScript（web/calc）。Python は次のことだけ：
  ・単元の一覧・学ぶの教材・学んだ ✓・ベストを画面に渡す
  ・画面から来たたのみごとにこたえる（nonce つき。同じたのみは1回だけ）
      start：10問つくる（math_units）　check：答え合わせ（math_check）・履歴・表彰状（PDF）
      ai：まちがえた問題の AI先生の解説　learned：学んだ ✓　example：数字を変えた例題"""
import base64
import random
import re
import time

import streamlit as st

import ai_explain
import auth
import common
import history
import kokugo_logic as K       # 学年（年齢 → 学年）は国語と同じ
import learn_log
import math_check as M
import math_lessons as LS
import math_units as U
import pdfgen
import web_games

common.setup_page("算数・数学マスター", "🧮")
ss = st.session_state
TOTAL_Q = 10
POINT = 100 // TOTAL_Q
MIX = "__mix__"
SUBJECT = "数学"
HIGH_COURSES = [("高1", "m1"), ("高1", "mA"), ("高2", "m2"), ("高2", "mB"), ("高2", "mC"), ("高2", "m3")]


def unit_name(uid):
    return "いろいろ（まとめ）" if uid == MIX else U.UNITS[uid][0]


def course_label(grade, course):
    return f"{K.GRADE_NAMES.get(grade, '')}・{U.COURSES[course]['name']}"


def plain(tex):
    """PDF・表用に、数式（TeX）をふつうの文字に"""
    t = tex.replace("$$", "").replace("$", "")
    t = re.sub(r"\\begin\{cases\}(.*?)\\end\{cases\}", lambda m: " ， ".join(p.strip() for p in m.group(1).split(r"\\")), t)
    for _ in range(3):
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}",
                   lambda m: "/".join(p if re.fullmatch(r"-?[\w.]+", p) else f"({p})" for p in m.groups()), t)
        t = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", t)
        t = re.sub(r"\\vec\{([^{}]*)\}", r"\1→", t)
    for a, b in ((r"\times", "×"), (r"\div", "÷"), (r"\leqq", "≦"), (r"\geqq", "≧"), (r"\cdot", "・"), (r"\infty", "∞"), (r"\to", "→"),
                 (r"\int", "∫"), (r"\sum", "Σ"), (r"\lim", "lim"), (r"\log", "log"), (r"\sin", "sin"), (r"\cos", "cos"), (r"\tan", "tan"),
                 (r"\circ", "°"), (r"\pi", "π"), (r"\left", ""), (r"\right", ""), (r"\,", " "), (r"\ ", " ")):
        t = t.replace(a, b)
    t = re.sub(r"\^\{([^{}]*)\}", lambda m: "^" + (m.group(1) if len(m.group(1)) == 1 else f"({m.group(1)})"), t)
    t = re.sub(r"_\{([^{}]*)\}", r"_\1", t)
    return t.replace("{", "").replace("}", "").replace("\\", "")


@st.cache_data
def catalog():
    """単元の一覧（学年 → 科目 → 単元）と、学ぶの目次。どれも変わらないので1回だけ作る"""
    by_grade = {}
    for g in K.GRADES:
        cs = U.courses_for(g)
        by_grade[g] = {"courses": cs, "units": {c: U.units_for(c, g) for c in cs}, "now": {c: U.current_units(c, g) for c in cs}}
    order, seen = [], set()
    for g, uids in U.SANSU.items():
        course = "sansu" if g.startswith("小") else "sugaku"
        for uid in uids:
            if uid in LS.LESSONS and uid not in seen:
                order.append([K.GRADE_NAMES[g], g, course, uid])
                seen.add(uid)
    for g, course in HIGH_COURSES:
        head = ("高校1年生" if g == "高1" else "高校2・3年生") + "・" + U.COURSES[course]["name"]
        for uid in U.COURSES[course]["units"]:
            if uid in LS.LESSONS and uid not in seen:
                order.append([head, g, course, uid])
                seen.add(uid)
    cat = {"grades": K.GRADES, "gradeNames": K.GRADE_NAMES, "byGrade": by_grade,
           "courses": {c: {"name": v["name"], "desc": v["desc"]} for c, v in U.COURSES.items()},
           "unitNames": {u: v[0] for u, v in U.UNITS.items()}}
    return cat, order, LS.LESSONS


def public(q):
    """画面に出す形（答えの形 spec は Python に残す）"""
    return {"q": q["q"], "hint": q.get("hint", ""), "unit": q["unit"]}


def one_example(uid):
    q = U.make_set([uid], random.Random(), 1)[0]
    return {"q": q["q"], "show": q["show"], "explain": q["explain"]}


def make_questions(grade, course, unit):
    units = U.current_units(course, grade) if unit == MIX else [unit]
    rng = random.Random()
    if unit == MIX:
        rng.shuffle(units)
    qs = U.make_set(units, rng, TOTAL_Q)
    sid = f"{time.time():.3f}"
    sets = ss.get("calc_sets") or {}
    sets = {k: sets[k] for k in list(sets)[-3:]}             # 古い回は3つまで残す（答え合わせ・AIの解説に使う）
    sets[sid] = {"grade": grade, "course": course, "unit": unit, "questions": qs}
    ss.calc_sets = sets
    return {"id": sid, "questions": [public(q) for q in qs]}


def check_answers(sid, answers):
    s = (ss.get("calc_sets") or {}).get(sid)
    if not s:
        return {"error": "問題が見つかりませんでした。もう一度えらんでください"}
    qs, grade, course, unit = s["questions"], s["grade"], s["course"], s["unit"]
    rows, pdf_rows, correct, blank = [], [], 0, 0
    for i, q in enumerate(qs):
        u = str(answers[i] if i < len(answers) else "").strip()
        blank += 0 if u else 1
        ok, note = M.check(q["spec"], u.replace(":", ",") if q.get("ratio") else u)
        correct += 1 if ok else 0
        rows.append({"ok": bool(ok), "note": note, "user": u, "show": q["show"], "explain": q["explain"]})
        pdf_rows.append((plain(q["q"]), u or "（未入力）", q["show"], bool(ok)))
    score = correct * POINT
    best_all = ss.setdefault("calc_best2", {})
    key = f"{grade}|{course}|{unit}"
    prev = best_all.get(key)
    best_all[key] = max(score, prev or 0)
    played_at = time.strftime("%Y-%m-%d %H:%M:%S")
    info = f"{course_label(grade, course)}（{unit_name(unit)}）"
    history.log_once("計算", f"calc-{sid}", コース=course_label(grade, course), 計算=unit_name(unit), 点数=score, 正解数=correct,
                     詳細=pdfgen.make_record("算数・数学マスター", info, pdf_rows))
    if score == 100:
        comment = "完璧です！文句なしの100点満点！この調子でどんどん挑戦しよう！"
    elif score >= 80:
        comment = "素晴らしい成績です！あともう少しで満点だったね。次は絶対パーフェクトだ！"
    else:
        comment = "最後までよく頑張りました！解き方を見直して、もう一回練習すれば絶対にできるようになるよ。応援しているよ！"
    try:
        pdf = base64.b64encode(pdfgen.build_pdf("算数・数学マスター", info, ss.get("player_name", ""), played_at, score, pdf_rows, comment)).decode("ascii")
    except Exception:
        pdf = ""
    s["rows"] = rows
    return {"rows": rows, "score": score, "correct": correct, "n": len(qs), "blank": blank, "best": best_all[key],
            "newBest": (prev is None or score > prev) and score > 0, "comment": comment, "pdf": pdf,
            "wrong": [i for i, r in enumerate(rows) if not r["ok"]]}


def ai_notes(sid):
    s = (ss.get("calc_sets") or {}).get(sid)
    if not s or not s.get("rows"):
        return None
    qs, rows = s["questions"], s["rows"]
    wrong = [i for i, r in enumerate(rows) if not r["ok"]]
    items = [{"q": plain(qs[i]["q"]), "user": rows[i]["user"] + (f"（判定メモ：{rows[i]['note']}）" if rows[i]["note"] and rows[i]["note"] != "（未入力）" else ""),
              "correct": qs[i]["show"], "hint": qs[i]["explain"]} for i in wrong]
    return ai_explain.cached_explanations(f"calc-{sid}", "算数" if s["grade"].startswith("小") else "数学",
                                          K.GRADE_NAMES.get(s["grade"], ""), items)


def handle(v):
    t = v.get("type")
    if t == "start":
        grade, course, unit = v.get("grade"), v.get("course"), v.get("unit") or MIX
        if grade not in K.GRADES or course not in U.COURSES or (unit != MIX and unit not in U.UNITS):
            return {"error": "えらび方がおかしいよ"}
        if max_grade and K.GRADES.index(grade) > K.GRADES.index(max_grade):
            return {"error": "その学年は まだ えらべないよ"}
        return make_questions(grade, course, unit)
    if t == "check":
        return check_answers(v.get("id"), v.get("answers") or [])
    if t == "ai":
        return {"notes": ai_notes(v.get("id"))}
    if t == "learned":
        uid = v.get("uid")
        if uid in U.UNITS:
            learn_log.mark(SUBJECT, v.get("grade", ""), uid, unit_name(uid))
        return {"ok": True}
    if t == "example":
        uid = v.get("uid")
        return {"ex": one_example(uid) if uid in U.UNITS else None}
    return {}


cat, order, lessons = catalog()
if "calc_examples" not in ss:                      # 学ぶの「数字を変えた例題」（単元ごとに1つ。ほかの数字はたのまれたら作る）
    ss.calc_examples = {uid: one_example(uid) for uid in lessons if uid in U.UNITS}
age_grade = K.grade_for_age(ss.get("auth_age"))
# えらべる学年：管理者・年齢がわからない人は全部。ほかの人は、いまの学年まで（maxGrade）
max_grade = None if (auth.is_admin() or age_grade is None) else age_grade
me = {"grade": age_grade or "小3", "maxGrade": max_grade, "age": ss.get("auth_age"), "band": common.age_band()}
done = ss.setdefault("calc_done", set())
val = web_games.calc_study(key="calc", cat=cat, order=order, lessons=lessons, examples=ss.calc_examples,
                           learned=sorted(learn_log.learned(SUBJECT)), best=ss.get("calc_best2") or {}, me=me, reply=ss.get("calc_reply"))
if isinstance(val, dict) and val.get("nonce") and val["nonce"] not in done:
    done.add(val["nonce"])
    try:
        out = handle(val)
    except Exception as e:                          # 画面が待ちつづけないように、かならず返事をする
        out = {"error": f"うまくいかなかったよ（{type(e).__name__}）"}
    ss.calc_reply = {**out, "nonce": val["nonce"]}
    st.rerun()
