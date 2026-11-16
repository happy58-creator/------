"""せいせきの履歴：これまでの記録を見る（管理者は みんなの記録）。
画面はぜんぶ JavaScript（web/history）。Python は「えらんだシートの記録を読む」「その回の結果をPDFにする」だけ。
スプレッドシートの読みこみをへらすため、シートごとの記録は60秒だけセッションにとっておく。"""
import json
import time

import streamlit as st

import auth
import common
import history
import js_page
import pdfgen
import voice_store
import web_games

common.setup_page("せいせきの履歴", ":material/assignment:")
ss = st.session_state
ADMIN_ONLY = {"ログイン", "入力チェック"}   # ログインの記録・ふざけた入力の記録は管理者だけ
HIDDEN = {"詳細", "正誤"}                    # 長いので表には出さない（詳細は PDF で見る）
admin = auth.is_admin()
me = ss.get("player_name") or ""
sheets = [s for s in history.SHEETS if s not in ADMIN_ONLY or admin]


def rows_of(sheet):
    """この人が見てよい記録（新しい順ではなく、記録した順）。60秒はとっておいたものを使う"""
    cache = ss.setdefault("hist_cache", {})
    hit = cache.get(sheet)
    if not hit or time.time() - hit[0] > 60:
        try:
            rows = history.read_history(sheet)
        except Exception:
            rows = []
        hit = cache[sheet] = (time.time(), rows)
    rows = hit[1]
    return rows if admin else [r for r in rows if str(r.get("名前")) == me]


def rec_key(r):
    try:
        return json.loads(r.get("詳細") or "").get("a") or ""
    except Exception:
        return ""


def handle(v):
    t, sheet = v.get("type"), v.get("sheet")
    if sheet not in sheets:
        return {"error": "そのシートは見られないよ"}
    if t == "load":
        if v.get("fresh"):
            ss.get("hist_cache", {}).pop(sheet, None)
        rows = rows_of(sheet)
        cols = [c for c in history.BASE_COLUMNS + history.SHEETS[sheet] if c not in HIDDEN]
        out = [{**{c: r.get(c, "") for c in cols}, "_i": i, "_pdf": bool(str(r.get("詳細") or "").strip())} for i, r in enumerate(rows)]
        res = {"sheet": sheet, "cols": cols, "rows": out}
        if sheet == "スピーキング":                    # 録音が残っている回（_rec：キー、_lock：鍵）
            keys = voice_store.keys_of(None if admin else me)
            for o, r in zip(out, rows):
                k = rec_key(r)
                if k:
                    o["_rec"], o["_lock"], o["_gone"] = (k, keys[k], False) if k in keys else ("", False, True)
            res["locks"] = sum(1 for x in keys.values() if x) if not admin else None
            res["lockMax"], res["keep"] = voice_store.LOCKS, voice_store.KEEP
        return res
    if t in ("voice", "lock"):                       # 録音を聞く・鍵をかける（自分の録音だけ。管理者はみんなの）
        key = str(v.get("key") or "")
        data = voice_store.load(key)
        if not data:
            return {"error": "この録音は もう残っていないよ（新しい10回と、鍵をかけた回だけ残ります）"}
        if not admin and data["name"] != me:
            return {"error": "この録音は 聞けないよ"}
        if t == "voice":
            return {"key": key, **data}
        ok, msg, count = voice_store.set_lock(key, bool(v.get("on")), data["name"])
        return {"key": key, "ok": ok, "msg": msg, "lock": bool(v.get("on")) if ok else data["lock"], "locks": count}
    if t == "pdf":
        rows = rows_of(sheet)
        i = int(v.get("i", -1))
        if not 0 <= i < len(rows):
            return {"error": "記録が見つからないよ。もう一度 読みこんでね"}
        pdf = pdfgen.pdf_from_history(rows[i])
        if pdf is None:
            return {"error": "この記録は 詳細が 読みこめませんでした"}
        return {"pdf": js_page.pdf_b64(pdf), "i": i}
    return {}


js_page.serve(web_games.history_view, "hist", handle, sheets=sheets, admin=admin, me=me, storage=history.storage_label())
