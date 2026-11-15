"""基本情報技術者試験（大人向け）：科目A・科目Bの解説・問題演習・本番形式の模試・用語カード。
画面はぜんぶ JavaScript（web/fe。ITパスポートと同じつくり。問題と解説は web/fe/data.js）。
Python は「スプレッドシートの記録を画面に渡す」「1回分の結果を記録する」「AIの解説を作る」だけ。"""
import json

import streamlit as st

import ai_explain
import common
import history
import web_games

common.setup_page("基本情報技術者", "🧑‍💻")
ss = st.session_state
SHEET = "基本情報"
me = ss.get("player_name") or ""


def my_rows():
    """この人の記録（ページを開いたときに1回だけ読む。スプレッドシートへの問い合わせをへらす）"""
    if ss.get("fe_rows_for") != me:
        try:
            rows = [r for r in history.read_history(SHEET) if str(r.get("名前")) == me]
        except Exception:
            rows = []
        ss.fe_rows, ss.fe_rows_for = rows, me
    return ss.fe_rows


def stats_from(rows):
    """1問ごとの成績 {id: {n, c, last, t}} と、模試の記録"""
    stats, sessions = {}, []
    for k, r in enumerate(rows):
        try:
            data = json.loads(r.get("正誤") or "[]")
        except Exception:
            data = []
        items = data.get("r", []) if isinstance(data, dict) else data        # {"k": 回のID, "r": [[問題ID, 正解なら1], ...]}
        run_key = data.get("k") if isinstance(data, dict) else None
        for item in items:
            if not isinstance(item, list) or len(item) != 2:
                continue
            qid, ok = str(item[0]), bool(item[1])
            s = stats.setdefault(qid, {"n": 0, "c": 0, "last": 0, "t": k})
            s["n"] += 1
            s["c"] += 1 if ok else 0
            s["last"], s["t"] = (1 if ok else 0), k
        if r.get("モード") in EXAM_MODES:
            sessions.append({"key": run_key or f"{r.get('日時')}-{r.get('モード')}", "date": str(r.get("日時"))[:16], "mode": r.get("モード"),
                             "title": r.get("内容"), "total": r.get("点数"), "pass": r.get("合否") == "合格ライン",
                             "c": r.get("正解数"), "n": r.get("問題数")})
    return stats, sessions


EXAM_MODES = ("A", "B", "miniA", "miniB")      # 模試（科目A・科目B・それぞれのミニ）


def ask_ai(v):
    """問題について、AIにくわしく説明してもらう"""
    if not ai_explain.ai_available():
        return "AIのカギ（GEMINI_API_KEY）が設定されていないので、AIの解説は使えません。"
    kana = ["ア", "イ", "ウ", "エ", "オ", "カ", "キ", "ク", "ケ", "コ", "サ", "シ"]
    choices = "\n".join(f"{kana[i]}：{c}" for i, c in enumerate(v.get("choices") or []))
    mine = v.get("mine")
    mine_text = f"受験者の答え：{kana[mine]}" if isinstance(mine, int) and 0 <= mine < len(kana) else "受験者は未回答"
    prompt = f"""あなたは基本情報技術者試験の、わかりやすい講師です。次の問題について、受験者（ITパスポート合格レベルの社会人）に解説してください。

【問題】
{v.get('q', '')}

【選択肢】
{choices}

正解：{kana[v.get('answer', 0)]}（これが正しい。ちがう答えを正解として書かないこと）
{mine_text}
教材の解説：{v.get('exp', '')}
{('受験者からの希望：' + v['extra']) if v.get('extra') else ''}

書きかた：
- 最初に、この問題で問われているポイントを1文で。
- 受験者がまちがえていたら、その選択肢がなぜ誤りか、どう勘違いしやすいかを書く。
- 身近な例えを1つ使って、正解の考え方を説明する（計算問題なら式を順番に。擬似言語のプログラムなら、変数の値がどう変わるかを表のように順番に追う）。
- 最後に「覚え方」か「試験でのひっかけ」を1つ。
- 全体で500字くらいまで（プログラムのトレースは少し長くてよい）。です・ます調。強調したい語は **語** の形で。"""
    try:
        from google.genai import types
        client = common.get_gemini_client()
        res = client.models.generate_content(model=common.GEMINI_MODEL, contents=prompt,
                                             config=types.GenerateContentConfig(temperature=0.4))
        return (res.text or "").strip() or "うまく作れませんでした。もう一度ためしてください。"
    except Exception as e:
        return f"AIの解説を作れませんでした（{e}）。少し時間をおいて、もう一度ためしてください。"


rows = my_rows()
stats, sessions = stats_from(rows)
done = ss.setdefault("fe_done", set())
val = web_games.fe_study(key="fe", user=me, stats=stats, sessions=sessions, ai=ss.get("fe_ai"))

if isinstance(val, dict) and val.get("nonce") and val["nonce"] not in done:
    done.add(val["nonce"])
    if val.get("type") == "log":
        per = val.get("per") or {}
        fields = {
            "モード": val.get("mode"), "内容": val.get("title"), "点数": val.get("total") if val.get("mode") in EXAM_MODES else "",
            "正解数": val.get("c"), "問題数": val.get("n"), "時間秒": val.get("secs"),
            "合否": ("合格ライン" if val.get("pass") else "不合格ライン") if val.get("pass") is not None else "",
            "正誤": json.dumps({"k": val.get("key"), "r": val.get("rows") or []}, separators=(",", ":")),
        }
        history.log_once(SHEET, val.get("key") or val["nonce"], **fields)
        # 読みなおさずに、手元の記録にも足しておく（スプレッドシートへの問い合わせをへらす）
        ss.fe_rows = rows + [{"日時": __import__("time").strftime("%Y-%m-%d %H:%M:%S"), "名前": me, **fields}]
    elif val.get("type") == "ask":
        ss.fe_ai = {"nonce": val["nonce"], "id": val.get("id"), "text": ask_ai(val)}
        st.rerun()
