"""AI英語スピーキング「話す」の録音を残す（履歴の画面で聞ける）。
スプレッドシートの「録音」タブに、1回（10問）を1行で入れる：キー・名前・日時・鍵・形式・文1〜10・音1〜10。
音は圧縮した録音（AAC など）の base64。セル1つに5万文字までなので、それより大きい問題の録音は入れない。
1人あたり、鍵をかけていない回は新しい10回だけ残す（古いものは消す）。鍵は1人20回まで（鍵をかけた回は消さない）。
スプレッドシートがないときは、手元の CSV（history/録音.csv）に入れる。"""
import csv
import time

import history

SHEET = "録音"
N = 10                      # 1回の問題数
KEEP = 10                   # 鍵なしで残す回数（1人あたり）
LOCKS = 20                  # 鍵をかけられる回数（1人あたり）
CELL_MAX = 48000            # スプレッドシートの1セルの上限（5万文字）より少し小さく
COLS = ["キー", "名前", "日時", "鍵", "形式"] + [f"文{i}" for i in range(1, N + 1)] + [f"音{i}" for i in range(1, N + 1)]
META = 5                    # キー・名前・日時・鍵・形式（一覧で読むのは ここまで）


# ---------------------------------------------------------------- 置き場（スプレッドシート か CSV）
def _ws():
    book = history._spreadsheet()
    if book is None:
        return None
    import gspread
    try:
        return book.worksheet(SHEET)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=SHEET, rows=200, cols=len(COLS))
        ws.append_row(COLS)
        return ws


def _csv():
    return history.LOCAL_DIR / f"{SHEET}.csv"


def _csv_rows():
    p = _csv()
    if not p.exists():
        return []
    csv.field_size_limit(10 ** 8)
    with p.open(encoding="utf-8-sig") as f:
        return [r for r in csv.reader(f)][1:]


def _csv_write(rows):
    history.LOCAL_DIR.mkdir(exist_ok=True)
    with _csv().open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)


def _metas(ws):
    """[(行番号, キー, 名前, 日時, 鍵)]。スプレッドシートは はじめの5列だけ読む（音は読まない）"""
    if ws is None:
        return [(i + 2, *(r + [""] * META)[:4]) for i, r in enumerate(_csv_rows())]
    vals = ws.get(f"A2:D{max(2, ws.row_count)}") or []
    return [(i + 2, *(list(r) + [""] * 4)[:4]) for i, r in enumerate(vals) if r and r[0]]


# ---------------------------------------------------------------- 保存
def save(key, name, texts, clips):
    """clips：[{"b64":..., "mime":...} または None]（問題の順）。古い回を消して、新しい回を入れる"""
    if not key or not any(c and c.get("b64") for c in clips):
        return False
    mime = next((c.get("mime") for c in clips if c and c.get("mime")), "audio/mp4")
    sounds = [(c.get("b64") if c and len(c.get("b64") or "") <= CELL_MAX else "") for c in clips][:N]
    row = [key, name, time.strftime("%Y-%m-%d %H:%M:%S"), "", mime] + (list(texts) + [""] * N)[:N] + (sounds + [""] * N)[:N]
    ws = _ws()
    metas = _metas(ws)
    if any(m[1] == key for m in metas):
        return True
    # この人の 鍵なしの回：新しい回を入れたあとで KEEP 回に収まるように、古い方から消す
    mine = sorted([m for m in metas if m[2] == name and not m[4]], key=lambda m: m[3])
    drop = mine[: max(0, len(mine) - (KEEP - 1))]
    if ws is None:
        gone = {m[1] for m in drop}
        _csv_write([r for r in _csv_rows() if r and r[0] not in gone] + [row])
        return True
    for m in sorted(drop, key=lambda m: -m[0]):          # 下の行から消す（行番号がずれないように）
        ws.delete_rows(m[0])
    ws.append_row(row, value_input_option="RAW")
    return True


# ---------------------------------------------------------------- 読む・鍵
def keys_of(name=None):
    """{キー: 鍵か}（name を渡すと、その人の分だけ）"""
    try:
        return {m[1]: bool(m[4]) for m in _metas(_ws()) if name is None or m[2] == name}
    except Exception:
        return {}


def load(key):
    """{"texts": [...], "mime": ..., "clips": [b64 か ""], "lock": bool, "name": ...} か None"""
    ws = _ws()
    if ws is None:
        r = next((r for r in _csv_rows() if r and r[0] == key), None)
    else:
        m = next((m for m in _metas(ws) if m[1] == key), None)
        r = ws.row_values(m[0]) if m else None
    if not r:
        return None
    r = list(r) + [""] * len(COLS)
    return {"name": r[1], "lock": bool(r[3]), "mime": r[4] or "audio/mp4",
            "texts": r[META:META + N], "clips": r[META + N:META + 2 * N]}


def set_lock(key, on, name):
    """鍵をかける・はずす。返り値 (できたか, 文, この人の鍵の数)"""
    ws = _ws()
    metas = _metas(ws)
    m = next((m for m in metas if m[1] == key), None)
    if not m:
        return False, "この録音は もう残っていないよ", 0
    owner = m[2]
    count = sum(1 for x in metas if x[2] == owner and x[4])
    if on and not m[4] and count >= LOCKS:
        return False, f"鍵は {LOCKS}回までです。ほかの回の鍵をはずしてから かけてね", count
    val = "鍵" if on else ""
    if ws is None:
        rows = _csv_rows()
        for r in rows:
            if r and r[0] == key:
                r[3] = val
        _csv_write(rows)
    else:
        ws.update_cell(m[0], 4, val)
    count += (1 if on and not m[4] else -1 if not on and m[4] else 0)
    # 鍵をはずした回は、次に録音したとき 新しい10回より古ければ消える
    return True, "鍵をかけたよ" if on else "鍵をはずしたよ", count
