import random
import time

import pandas as pd
import streamlit as st

import common
import history
import pdfgen

common.setup_page("計算マスター", "🧮")

TOTAL_Q = 25
DEFAULTS = {
    "calc_step": "setup",  # setup, playing, result
    "calc_questions": [],
    "calc_user_answers": {},
    "calc_mode": "ノーマル",
    "calc_best": {},
    "calc_game_id": 0,
}
common.init_state(DEFAULTS)


# --- 問題自動生成関数（選択された演算を順番通りに25問作成） ---
def generate_questions(mode, selected_ops):
    q_list = []
    used_pairs = set()  # 重複検知用セット
    
    if not selected_ops:
        return []
        
    # 選ばれた演算の種類数で25問をなるべく均等に分ける
    base_count = TOTAL_Q // len(selected_ops)
    remainder = TOTAL_Q % len(selected_ops)
    
    # ユーザーがチェックを入れた通りの順番で並べる（シャッフルなし）
    ops_config = []
    for i, op in enumerate(selected_ops):
        count = base_count + (1 if i < remainder else 0)
        ops_config.append({"type": op, "count": count})
    
    all_op_questions = []
    
    for config in ops_config:
        op = config["type"]
        count = 0
        attempts = 0
        
        while count < config["count"] and attempts < 400:
            attempts += 1
            
            if op == "足し算 (＋)":
                sign = "＋"
                if mode == "ノーマル":
                    a, b = random.randint(10, 99), random.randint(10, 99)
                else:
                    a, b = random.randint(1000, 9999), random.randint(1000, 9999)
                ans = a + b
                
            elif op == "引き算 (－)":
                sign = "－"
                if mode == "ノーマル":
                    a = random.randint(10, 99)
                    b = random.randint(10, a)
                else:
                    a = random.randint(1000, 9999)
                    b = random.randint(1000, a)
                ans = a - b
                
            elif op == "掛け算 (×)":
                sign = "×"
                if mode == "ノーマル":
                    a, b = random.randint(1, 9), random.randint(1, 9)
                else:
                    a, b = random.randint(10, 99), random.randint(1, 9)
                ans = a * b
                
            elif op == "割り算 (÷)":
                sign = "÷"
                if mode == "ノーマル":
                    b = random.randint(1, 9)
                    ans = random.randint(1, 9)
                    a = b * ans
                else:
                    b = random.randint(2, 9) 
                    ans = random.randint(10, 99) 
                    a = b * ans
            
            pair_key = (a, sign, b)
            if pair_key not in used_pairs:
                used_pairs.add(pair_key)
                all_op_questions.append({"num1": a, "op": sign, "num2": b, "correct": ans})
                count += 1
                
    return all_op_questions[:TOTAL_Q]


# --- 画面描画ロジック ---
common.hero("🧮 カスタム計算マスター", "コースと計算の種類を選んで、25問のチャレンジに挑戦しよう！")

# 1. 初期設定画面
if st.session_state.calc_step == "setup":
    with st.container(border=True):
        st.subheader("① コースを選ぼう")
        mode = st.radio(
            "難しさ", ["ノーマル", "挑戦（激ムズ）"], horizontal=True, label_visibility="collapsed"
        )
        st.caption("ノーマル：取り組みやすい問題  ・  挑戦（激ムズ）：大きな数の問題")

    operation_options = ["足し算 (＋)", "引き算 (－)", "掛け算 (×)"]
    if mode != "ノーマル":
        operation_options.append("割り算 (÷)")

    with st.container(border=True):
        st.subheader("② 計算の種類を1つ選ぼう")
        selected_op = st.radio(
            "計算の種類", operation_options, horizontal=True,
            key=f"calc_operation_{mode}", label_visibility="collapsed",
        )

    best = st.session_state.calc_best.get((mode, selected_op))
    if best is not None:
        st.caption(f"🏆 このコースのベスト：{best} 点")
    st.info(f"全部で{TOTAL_Q}問出題されるよ。準備ができたらスタート！", icon="💡")
    if st.button("🏁 この内容でスタート！", type="primary", use_container_width=True):
        st.session_state.calc_mode = mode
        st.session_state.calc_op = selected_op
        st.session_state.calc_questions = generate_questions(mode, [selected_op])
        st.session_state.calc_game_id = time.time()
        st.session_state.calc_user_answers = {}
        for i in range(TOTAL_Q):
            st.session_state.pop(f"calc_q_{i}", None)
        st.session_state.calc_step = "playing"
        st.rerun()

# 2. 問題回答画面
elif st.session_state.calc_step == "playing":
    st.subheader(f"✏️ 計算チャレンジ中！ （{st.session_state.calc_mode} ・ {st.session_state.calc_op}）")
    st.caption("わからない問題は空らんのままでもOK。全部できたら一番下の「答えあわせ」を押してね。")

    with st.form(key="calc_form"):
        for i, q in enumerate(st.session_state.calc_questions):
            st.number_input(
                f"問 {i + 1}：　{q['num1']} {q['op']} {q['num2']} ＝",
                key=f"calc_q_{i}", value=None, step=1,
            )
        submitted = st.form_submit_button("🚨 答えあわせをする！", type="primary", use_container_width=True)

    if submitted:
        answers = {}
        for i in range(len(st.session_state.calc_questions)):
            value = st.session_state.get(f"calc_q_{i}")
            if value is not None:
                answers[i] = int(value)
        st.session_state.calc_user_answers = answers
        st.session_state.calc_step = "result"
        st.rerun()

    if st.button("やめてトップにもどる"):
        st.session_state.calc_step = "setup"
        st.rerun()

# 3. 結果表示＆PDF出力画面
elif st.session_state.calc_step == "result":
    st.header("🏆 チャレンジお疲れ様でした！")

    correct_count = 0
    unanswered = 0
    records = []
    for i, q in enumerate(st.session_state.calc_questions):
        u_ans = st.session_state.calc_user_answers.get(i)
        if u_ans is None:
            unanswered += 1
        is_correct = u_ans == q["correct"]
        correct_count += is_correct
        records.append({
            "問題": f"{q['num1']} {q['op']} {q['num2']}",
            "あなたの解答": u_ans if u_ans is not None else "（未入力）",
            "正しい答え": q["correct"],
            "判定": "⭕" if is_correct else "❌",
        })

    total_score = correct_count * 4
    best_key = (st.session_state.calc_mode, st.session_state.calc_op)
    previous_best = st.session_state.calc_best.get(best_key)
    is_new_best = previous_best is None or total_score > previous_best
    st.session_state.calc_best[best_key] = max(total_score, previous_best or 0)

    game_id = st.session_state.calc_game_id
    if st.session_state.get("calc_played_id") != game_id:  # 同じ結果画面の再描画で日時が変わらないようにする
        st.session_state.calc_played_id = game_id
        st.session_state.calc_played_at = time.strftime("%Y-%m-%d %H:%M:%S")
    pdf_info = f"チャレンジコース：{st.session_state.calc_mode}（{st.session_state.calc_op}）"
    pdf_rows = [(r["問題"], r["あなたの解答"], r["正しい答え"], r["判定"] == "⭕") for r in records]
    history.log_once(
        "計算", f"calc-{game_id}",
        コース=st.session_state.calc_mode, 計算=st.session_state.calc_op,
        点数=total_score, 正解数=correct_count,
        詳細=pdfgen.make_record("計算チャレンジマスター", pdf_info, pdf_rows),
    )

    if total_score == 100:
        comment = "完璧です！文句なしの100点満点、天才計算マスターだね！この調子でどんどん挑戦しよう！"
        st.balloons()
    elif total_score >= 80:
        comment = "素晴らしい成績です！あともう少しで満点だったね。次は絶対パーフェクトだ！"
    else:
        comment = "最後までよく頑張りました！間違えたところを見直して、もう一回練習すれば絶対にできるようになるよ。応援しているよ！"

    c1, c2, c3 = st.columns(3)
    c1.metric("🎯 今回の点数", f"{total_score} / 100 点")
    c2.metric("✅ 正解数", f"{correct_count} / {TOTAL_Q} 問")
    c3.metric("🏆 ベスト", f"{st.session_state.calc_best[best_key]} 点")
    if is_new_best and total_score > 0:
        st.success("🎉 ベストスコア更新！")
    if unanswered:
        st.caption(f"未入力の問題が {unanswered} 問あったよ。")

    (st.warning if total_score < 80 else st.success)(f"💬 {comment}")

    df_results = pd.DataFrame(records)
    wrong_df = df_results[df_results["判定"] == "❌"]
    if not wrong_df.empty:
        with st.expander(f"👀 まちがえた問題を見なおす（{len(wrong_df)}問）", expanded=True):
            st.dataframe(wrong_df, use_container_width=True, hide_index=True)
    with st.expander("📊 全部の結果を見る"):
        st.dataframe(df_results, use_container_width=True, hide_index=True)

    st.download_button(
        label="📥 がんばり結果をPDFで保存する（印刷もできるよ！）",
        data=pdfgen.build_pdf(
            "計算チャレンジマスター", pdf_info, st.session_state.get("player_name", ""),
            st.session_state.calc_played_at, total_score, pdf_rows, comment,
        ),
        file_name=f"けいさん結果_{st.session_state.calc_mode}.pdf",
        mime="application/pdf",
        use_container_width=True,
        type="primary",
    )

    st.divider()
    col_again, col_menu = st.columns(2)
    with col_again:
        if st.button("🔁 同じコースでもう一度", use_container_width=True):
            st.session_state.calc_questions = generate_questions(
                st.session_state.calc_mode, [st.session_state.calc_op]
            )
            st.session_state.calc_game_id = time.time()
            st.session_state.calc_user_answers = {}
            for i in range(TOTAL_Q):
                st.session_state.pop(f"calc_q_{i}", None)
            st.session_state.calc_step = "playing"
            st.rerun()
    with col_menu:
        if st.button("🔄 コースを選びなおす", use_container_width=True):
            st.session_state.calc_step = "setup"
            st.rerun()
