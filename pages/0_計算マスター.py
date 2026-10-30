import random
import re
import time

import pandas as pd
import streamlit as st

import auth
import common
import history
import kokugo_logic as K       # 学年（年齢 → 学年）は国語と同じ
import learn_log
import math_check as M
import math_lessons as LS
import math_units as U
import pdfgen

common.setup_page("算数・数学マスター", "🧮")

TOTAL_Q = 10
POINT = 100 // TOTAL_Q
MIX = "__mix__"
DEFAULTS = {
    "calc_step": "setup",  # setup, learn（まなぶ）, playing, result
    "calc_questions": [],
    "calc_user_answers": {},
    "calc_grade": "",
    "calc_course": "",
    "calc_unit": "",
    "calc_best": {},
    "calc_game_id": 0,
}
common.init_state(DEFAULTS)

HOWTO = """
- **分数**：`3/4`　**帯分数**：`2と1/3`　**小数**：`0.25`
- **ルート**：`√3`、`2√3`、`√(x+1)`（ルートの中は いちばん小さく、分母は有理化）
- **円周率**：`π`　**累乗**：`x^2` または `x²`　**かけ算**：`2x`、`3(x+1)`
- **答えが2つ**：`x=2, -3` や `x=±√3`　**連立方程式**：`x=1, y=2`　**座標**：`(2, -3)`
- **不等式**：`x>3`、`x≧-1/2`（`>=` でもOK）　**複素数**：`3+2i`
- 全角で打っても、単位（cm・度・通り など）をつけてもOK
"""


SUBJECT = "数学"
LEARN_PAGES = ["ポイント", "例題", "もう1問", "やってみよう", "まとめ"]


def unit_name(uid):
    return "いろいろ（まとめ）" if uid == MIX else U.UNITS[uid][0]


def unit_label(uid):
    """単元えらびの表示（まなんだ単元には ✓）"""
    if uid == MIX:
        return unit_name(uid)
    return ("✓ " if uid in learn_log.learned(SUBJECT) else "") + unit_name(uid)


def start_learn():
    ss = st.session_state
    ss.calc_step = "learn"
    ss.calc_lpage = 0
    ss.calc_lstep = 0            # 例題の手順を何行まで見せたか
    new_example()
    ss.calc_ltry = U.make_set([ss.calc_unit], random.Random(), 2)
    ss.calc_ltry_checked = False
    for i in range(2):
        ss.pop(f"calc_try_{i}", None)


def new_example():
    st.session_state.calc_lex = U.make_set([st.session_state.calc_unit], random.Random(), 1)[0]
    st.session_state.calc_lex_open = False


def course_label():
    return f"{K.GRADE_NAMES.get(st.session_state.calc_grade, '')}・{U.COURSES[st.session_state.calc_course]['name']}"


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


def new_questions():
    uid = st.session_state.calc_unit
    units = U.current_units(st.session_state.calc_course, st.session_state.calc_grade) if uid == MIX else [uid]
    rng = random.Random()
    if uid == MIX:
        rng.shuffle(units)
    st.session_state.calc_questions = U.make_set(units, rng, TOTAL_Q)
    st.session_state.calc_game_id = time.time()
    st.session_state.calc_user_answers = {}
    for i in range(TOTAL_Q):
        st.session_state.pop(f"calc_q_{i}", None)
    st.session_state.calc_step = "playing"


common.hero(*{"小": ("🧮 算数マスター", "学年と たんげんを えらんで、10問のチャレンジに ちょうせんしよう！"),
              "中": ("🧮 数学マスター", "学年と単元を選んで、10問のチャレンジに挑戦しよう！"),
              "高": ("🧮 数学マスター", "科目と単元を選んで、10問の演習に取り組もう。")}[common.age_band()])

# 1. 初期設定画面
if st.session_state.calc_step == "setup":
    age_grade = K.grade_for_age(st.session_state.get("auth_age"))
    with st.container(border=True):
        st.subheader("① 学年")
        if auth.is_admin() or age_grade is None:
            default = st.session_state.get("calc_grade_pick") or age_grade or "小3"
            grade = st.selectbox("学年をえらんでね", K.GRADES, index=K.GRADES.index(default),
                                 format_func=lambda g: K.GRADE_NAMES[g], key="calc_grade_pick")
        else:
            grade = age_grade
            st.markdown(f"**{K.GRADE_NAMES[grade]}** の問題が出るよ（{st.session_state.auth_age}さい）")

        course_ids = U.courses_for(grade)
        if len(course_ids) > 1:
            st.subheader("② 科目")
            course_id = st.radio("科目", course_ids, key=f"calc_course_pick_{grade}", label_visibility="collapsed",
                                 format_func=lambda c: f"{U.COURSES[c]['name']}　―　{U.COURSES[c]['desc']}")
        else:
            course_id = course_ids[0]
            st.caption(f"📚 {U.COURSES[course_id]['name']}：{U.COURSES[course_id]['desc']}")

    units = U.units_for(course_id, grade)
    with st.container(border=True):
        st.subheader(f"{'③' if len(course_ids) > 1 else '②'} 単元")
        st.caption("前の学年の単元も、ふくしゅうで入っているよ。" if U.COURSES[course_id].get("units") is None and grade not in ("小1", "中1") else "")
        unit = st.radio("単元", [MIX] + units, key=f"calc_unit_pick_{grade}_{course_id}", label_visibility="collapsed",
                        format_func=unit_label, horizontal=True)
        done = sum(1 for u in units if u in learn_log.learned(SUBJECT))
        st.caption(f"📖 まなんだ単元：{done} / {len(units)}（✓ がついているよ）")

    best = st.session_state.calc_best.get((grade, course_id, unit))
    if best is not None:
        st.caption(f"🏆 この単元のベスト：{best} 点")
    has_lesson = unit in LS.LESSONS
    if has_lesson:
        st.info("📖「まなぶ」で説明と例題を見てから、🏁「練習する」で10問に挑戦しよう！", icon="💡")
    else:
        st.info(f"全部で{TOTAL_Q}問出題されるよ。準備ができたらスタート！" +
                ("（「いろいろ」には まなぶ画面はないよ。単元を1つえらぶと まなべるよ）" if unit == MIX else ""), icon="💡")
    col_learn, col_go = st.columns(2)
    if col_learn.button("📖 まなぶ", use_container_width=True, disabled=not has_lesson):
        st.session_state.calc_grade, st.session_state.calc_course, st.session_state.calc_unit = grade, course_id, unit
        start_learn()
        st.rerun()
    if col_go.button("🏁 練習する（10問）", type="primary", use_container_width=True):
        st.session_state.calc_grade, st.session_state.calc_course, st.session_state.calc_unit = grade, course_id, unit
        new_questions()
        st.rerun()

# 1.5 まなぶ画面（ポイント → 例題 → もう1問 → やってみよう → まとめ）
elif st.session_state.calc_step == "learn":
    ss = st.session_state
    uid = ss.calc_unit
    lesson = LS.LESSONS[uid]
    page = ss.calc_lpage
    st.subheader(f"📖 {unit_name(uid)}")
    st.caption(f"{course_label()}　／　{page + 1} / {len(LEARN_PAGES)}：{LEARN_PAGES[page]}" + ("　✓ まなんだ" if uid in learn_log.learned(SUBJECT) else ""))
    st.progress((page + 1) / len(LEARN_PAGES))

    with st.container(border=True):
        if page == 0:
            st.markdown(f"#### 💡 {lesson['intro']}")
            st.markdown("**おぼえよう**")
            st.markdown("\n".join(f"- {p}" for p in lesson["points"]))
            if lesson.get("caution"):
                st.warning("⚠️ " + lesson["caution"])
        elif page == 1:
            ex = lesson["example"]
            st.markdown("#### ✏️ 例題")
            st.markdown(ex["q"])
            for i, step_text in enumerate(ex["steps"][: ss.calc_lstep]):
                st.markdown(f"**{i + 1}.** {step_text}")
            if ss.calc_lstep < len(ex["steps"]):
                if st.button("▶ 次の手順を見る", key="calc_lnext"):
                    ss.calc_lstep += 1
                    st.rerun()
            else:
                st.success(f"答え：**{ex['answer']}**")
        elif page == 2:
            q = ss.calc_lex
            st.markdown("#### 🔁 もう1問（数字を変えた例題）")
            st.markdown(q["q"])
            if ss.calc_lex_open:
                st.success(f"答え：**{q['show']}**")
                st.info("📝 解き方：" + q["explain"])
            elif st.button("👀 答えと解き方を見る", key="calc_lopen"):
                ss.calc_lex_open = True
                st.rerun()
            if st.button("🔄 べつの例題にする", key="calc_lnew"):
                new_example()
                st.rerun()
        elif page == 3:
            st.markdown("#### 🙋 やってみよう（点数はつかないよ）")
            with st.expander("✍️ 答えの書き方"):
                st.markdown(HOWTO)
            with st.form("calc_try_form"):
                for i, q in enumerate(ss.calc_ltry):
                    st.markdown(f"**{i + 1}.** {q['q']}")
                    if q.get("hint"):
                        st.caption(q["hint"])
                    st.text_input("答え", key=f"calc_try_{i}", label_visibility="collapsed", placeholder="答えを入力")
                if st.form_submit_button("答えを たしかめる", type="primary"):
                    ss.calc_ltry_checked = True
            if ss.calc_ltry_checked:
                for i, q in enumerate(ss.calc_ltry):
                    typed = ss.get(f"calc_try_{i}", "")
                    ok, note = M.check(q["spec"], typed.replace(":", ",") if q.get("ratio") else typed)
                    if ok:
                        st.success(f"{i + 1}. ⭕ せいかい！（{q['show']}）")
                    else:
                        st.error(f"{i + 1}. ❌ 答えは **{q['show']}**" + (f"（{note}）" if note and note != "（未入力）" else ""))
                        st.caption("📝 " + q["explain"])
            if st.button("🔄 ちがう問題で もう一度", key="calc_try_new"):
                ss.calc_ltry = U.make_set([uid], random.Random(), 2)
                ss.calc_ltry_checked = False
                for i in range(2):
                    ss.pop(f"calc_try_{i}", None)
                st.rerun()
        else:
            st.markdown("#### 🎓 まとめ")
            st.markdown("\n".join(f"- {p}" for p in lesson["points"]))
            if uid in learn_log.learned(SUBJECT):
                st.success("✓ この単元は まなんだよ！")
            elif st.button("✅ まなんだ！（記録する）", type="primary", use_container_width=True):
                learn_log.mark(SUBJECT, ss.calc_grade, uid, unit_name(uid))
                st.balloons()
                st.rerun()
            if st.button("🏁 この単元を 練習する（10問）", use_container_width=True):
                new_questions()
                st.rerun()

    col_prev, col_next = st.columns(2)
    if page > 0 and col_prev.button("◀ 前へ", use_container_width=True):
        ss.calc_lpage -= 1
        st.rerun()
    if page < len(LEARN_PAGES) - 1 and col_next.button("次へ ▶", type="primary", use_container_width=True):
        ss.calc_lpage += 1
        st.rerun()
    if st.button("↩ 単元えらびに もどる"):
        ss.calc_step = "setup"
        st.rerun()

# 2. 問題回答画面
elif st.session_state.calc_step == "playing":
    st.subheader(f"✏️ チャレンジ中！（{course_label()}・{unit_name(st.session_state.calc_unit)}）")
    st.caption("わからない問題は空らんのままでもOK。全部できたら一番下の「答えあわせ」を押してね。")
    with st.expander("✍️ 答えの書き方"):
        st.markdown(HOWTO)

    with st.form(key="calc_form"):
        for i, q in enumerate(st.session_state.calc_questions):
            with st.container(border=True):
                st.markdown(f"**問 {i + 1}**　<small>{U.UNITS[q['unit']][0]}</small>", unsafe_allow_html=True)
                st.markdown(q["q"])
                if q.get("hint"):
                    st.caption(q["hint"])
                st.text_input("答え", key=f"calc_q_{i}", label_visibility="collapsed", placeholder="答えを入力")
        submitted = st.form_submit_button("🚨 答えあわせをする！", type="primary", use_container_width=True)

    if submitted:
        st.session_state.calc_user_answers = {i: st.session_state.get(f"calc_q_{i}", "") for i in range(len(st.session_state.calc_questions))}
        st.session_state.calc_step = "result"
        st.rerun()

    if st.button("やめて選びなおす"):
        st.session_state.calc_step = "setup"
        st.rerun()

# 3. 結果表示＆PDF出力画面
elif st.session_state.calc_step == "result":
    st.header("🏆 チャレンジお疲れ様でした！")

    correct_count = 0
    unanswered = 0
    records, checks = [], []
    for i, q in enumerate(st.session_state.calc_questions):
        u_ans = (st.session_state.calc_user_answers.get(i) or "").strip()
        if not u_ans:
            unanswered += 1
        ok, note = M.check(q["spec"], u_ans.replace(":", ",") if q.get("ratio") else u_ans)
        correct_count += ok
        checks.append((ok, note))
        records.append({
            "問題": plain(q["q"]),
            "あなたの解答": u_ans or "（未入力）",
            "正しい答え": q["show"],
            "判定": "⭕" if ok else "❌",
        })

    total_score = correct_count * POINT
    best_key = (st.session_state.calc_grade, st.session_state.calc_course, st.session_state.calc_unit)
    previous_best = st.session_state.calc_best.get(best_key)
    is_new_best = previous_best is None or total_score > previous_best
    st.session_state.calc_best[best_key] = max(total_score, previous_best or 0)

    game_id = st.session_state.calc_game_id
    if st.session_state.get("calc_played_id") != game_id:  # 同じ結果画面の再描画で日時が変わらないようにする
        st.session_state.calc_played_id = game_id
        st.session_state.calc_played_at = time.strftime("%Y-%m-%d %H:%M:%S")
    pdf_info = f"{course_label()}（{unit_name(st.session_state.calc_unit)}）"
    pdf_rows = [(r["問題"], r["あなたの解答"], r["正しい答え"], r["判定"] == "⭕") for r in records]
    history.log_once(
        "計算", f"calc-{game_id}",
        コース=course_label(), 計算=unit_name(st.session_state.calc_unit),
        点数=total_score, 正解数=correct_count,
        詳細=pdfgen.make_record("算数・数学マスター", pdf_info, pdf_rows),
    )

    if total_score == 100:
        comment = "完璧です！文句なしの100点満点！この調子でどんどん挑戦しよう！"
        st.balloons()
    elif total_score >= 80:
        comment = "素晴らしい成績です！あともう少しで満点だったね。次は絶対パーフェクトだ！"
    else:
        comment = "最後までよく頑張りました！解き方を見直して、もう一回練習すれば絶対にできるようになるよ。応援しているよ！"

    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 今回の点数", f"{total_score} / 100 点")
    c2.metric("✅ 正解数", f"{correct_count} / {TOTAL_Q} 問")
    c3.metric("🏆 ベスト", f"{st.session_state.calc_best[best_key]} 点")
    if is_new_best and total_score > 0:
        st.success("🎉 ベストスコア更新！")
    if unanswered:
        st.caption(f"未入力の問題が {unanswered} 問あったよ。")

    (st.warning if total_score < 80 else st.success)(f"💬 {comment}")

    wrong = [i for i, (ok, _) in enumerate(checks) if not ok]
    if wrong:
        st.subheader(f"👀 まちがえた問題を見なおそう（{len(wrong)}問）")
        for i in wrong:
            q = st.session_state.calc_questions[i]
            with st.container(border=True):
                st.markdown(f"**問 {i + 1}**　{q['q']}")
                st.markdown(f"あなたの答え：`{records[i]['あなたの解答']}`　→　正しい答え：**{q['show']}**")
                if checks[i][1] and checks[i][1] != "（未入力）":
                    st.caption("💡 " + checks[i][1])
                st.info("📝 解き方：" + q["explain"])
    with st.expander("📊 全部の結果を見る"):
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)

    common.pdf_preview_button(
        pdfgen.build_pdf(
            "算数・数学マスター", pdf_info, st.session_state.get("player_name", ""),
            st.session_state.calc_played_at, total_score, pdf_rows, comment,
        ),
    )

    st.divider()
    col_again, col_menu = st.columns(2)
    with col_again:
        if st.button("🔁 同じ単元でもう一度", use_container_width=True):
            new_questions()
            st.rerun()
    with col_menu:
        if st.button("🔄 単元を選びなおす", use_container_width=True):
            st.session_state.calc_step = "setup"
            st.rerun()
