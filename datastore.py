"""小さな表（スプレッドシートのタブ）を 読み書きする道具。スプレッドシートが ないときは 手元の CSV（history/タブ名.csv）。
問題の保存・とめはねの記録・レポートなど、いろいろな ページで 使う。
- read(tab, cols)：行の一覧（dict）。少しのあいだ（TTL 秒）は 読みなおさない
- append(tab, cols, rows)：行を 足す
- put(tab, cols, key_col, row)：key_col が 同じ行が あれば 書きかえ、なければ 足す"""
import csv
import time

import history

TTL = 90
_cache = {}          # tab → (読んだ時刻, rows)


def _ws(tab, cols):
    book = history._spreadsheet()
    if book is None:
        return None
    import gspread
    try:
        ws = book.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=tab, rows=500, cols=max(len(cols), 4))
        ws.append_row(cols)
    return ws


def _csv(tab):
    return history.LOCAL_DIR / f"{tab}.csv"


def _csv_read(tab, cols):
    p = _csv(tab)
    if not p.exists():
        return []
    csv.field_size_limit(10 ** 8)
    with p.open(encoding="utf-8-sig") as f:
        r = csv.reader(f)
        head = next(r, cols)
        return [dict(zip(head, row)) for row in r]


def _csv_write(tab, cols, rows):
    history.LOCAL_DIR.mkdir(exist_ok=True)
    with _csv(tab).open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([[str(r.get(c, "")) for c in cols] for r in rows])


def read(tab, cols, fresh=False):
    hit = _cache.get(tab)
    if hit and not fresh and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        ws = _ws(tab, cols)
        if ws is None:
            rows = _csv_read(tab, cols)
        else:
            vals = ws.get_all_values()
            head = vals[0] if vals else cols
            rows = [dict(zip(head, v)) for v in vals[1:] if any(v)]
    except Exception as e:
        print(f"[datastore] {tab} を 読めない: {type(e).__name__}: {e}", flush=True)
        rows = hit[1] if hit else []
    _cache[tab] = (time.time(), rows)
    return rows


def append(tab, cols, rows):
    rows = [r for r in rows if r]
    if not rows:
        return
    try:
        ws = _ws(tab, cols)
        if ws is None:
            _csv_write(tab, cols, _csv_read(tab, cols) + rows)
        else:
            ws.append_rows([[str(r.get(c, "")) for c in cols] for r in rows], value_input_option="RAW")
        hit = _cache.get(tab)
        if hit:
            _cache[tab] = (hit[0], hit[1] + rows)
    except Exception as e:
        print(f"[datastore] {tab} に 書けない: {type(e).__name__}: {e}", flush=True)


def put(tab, cols, key_col, row):
    """key_col の値が 同じ行を 書きかえる（なければ 足す）"""
    try:
        ws = _ws(tab, cols)
        if ws is None:
            rows = _csv_read(tab, cols)
            rows = [r for r in rows if r.get(key_col) != row.get(key_col)] + [row]
            _csv_write(tab, cols, rows)
        else:
            keys = ws.col_values(cols.index(key_col) + 1)
            line = [str(row.get(c, "")) for c in cols]
            if row.get(key_col) in keys[1:]:
                n = keys.index(row.get(key_col)) + 1
                ws.update(range_name=f"A{n}", values=[line], value_input_option="RAW")
            else:
                ws.append_row(line, value_input_option="RAW")
        _cache.pop(tab, None)
    except Exception as e:
        print(f"[datastore] {tab} に 書けない: {type(e).__name__}: {e}", flush=True)


def delete(tab, cols, key_col, keys):
    """key_col の値が keys に入っている行を 消す"""
    keys = set(keys)
    if not keys:
        return
    try:
        ws = _ws(tab, cols)
        if ws is None:
            _csv_write(tab, cols, [r for r in _csv_read(tab, cols) if r.get(key_col) not in keys])
        else:
            col = ws.col_values(cols.index(key_col) + 1)
            for n in sorted((i + 1 for i, k in enumerate(col) if i and k in keys), reverse=True):
                ws.delete_rows(n)
        _cache.pop(tab, None)
    except Exception as e:
        print(f"[datastore] {tab} から 消せない: {type(e).__name__}: {e}", flush=True)


def my_history(sheet, name=None, days=None):
    """その人の 記録（新しい順）。days を渡すと その日数ぶんだけ"""
    import streamlit as st
    name = name or st.session_state.get("player_name") or ""
    rows = [r for r in history.read_history(sheet) if str(r.get("名前")) == name]
    if days:
        since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - days * 86400))
        rows = [r for r in rows if str(r.get("日時")) >= since]
    return sorted(rows, key=lambda r: str(r.get("日時")), reverse=True)
