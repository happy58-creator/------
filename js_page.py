"""JavaScript の画面（web/ のカスタムコンポーネント）と Python のやりとりを、どのページでも同じ形にする小物。

画面 → Python：たのみごと {"type": ..., "nonce": ...}（同じ nonce は1回だけ受けとる）
Python → 画面：返事を args の reply に入れて、もう一度画面をかく（reply.nonce で、どのたのみごとの返事かわかる）"""
import streamlit as st


def serve(component, key, handle, **args):
    """component（web_games の関数）を出して、たのみごとを handle(たのみごと) → 返事の dict で受ける"""
    ss = st.session_state
    done = ss.setdefault(f"{key}_done", set())
    val = component(key=key, reply=ss.get(f"{key}_reply"), **args)
    if isinstance(val, dict) and val.get("nonce") and val["nonce"] not in done:
        done.add(val["nonce"])
        try:
            out = handle(val) or {}
        except Exception as e:                       # 画面が待ちつづけないように、かならず返事をする
            out = {"error": str(e) if isinstance(e, RuntimeError) else f"うまくいかなかったよ（{type(e).__name__}）"}     # RuntimeError はそのまま見せる文
        ss[f"{key}_reply"] = {**out, "nonce": val["nonce"]}
        st.rerun()
    return val


def pdf_b64(pdf_bytes):
    import base64
    return base64.b64encode(pdf_bytes).decode("ascii") if pdf_bytes else ""
