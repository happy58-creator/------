"""保存のしくみ。
secrets に gcp_service_account と KAKEIBO_SPREADSHEET_ID があれば Google スプレッドシートに、
なければ手元の CSV（data フォルダ）に保存する（CSV は試す用。Streamlit Cloud では再起動で消える）。
シートは「表の名前」ごとに1枚。1行目が列見出し。"""
import csv
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st

TABLES = {
    "記録": ["ID", "日付", "種類", "金額", "カテゴリ", "メモ", "登録日時"],
    "予算": ["カテゴリ", "予算"],
    "サブスク": ["ID", "名前", "金額", "周期", "次の支払日", "支払日の日", "カテゴリ", "メモ"],
    "カテゴリ": ["種類", "名前", "アイコン"],
}
LOCAL_DIR = Path(__file__).parent / "data"


def using_sheets():
    try:
        return bool(st.secrets["gcp_service_account"]) and bool(st.secrets["KAKEIBO_SPREADSHEET_ID"])
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _book():
    import gspread
    return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"])).open_by_key(st.secrets["KAKEIBO_SPREADSHEET_ID"])


def _sheet(name):
    import gspread
    book = _book()
    try:
        return book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=100, cols=len(TABLES[name]))
        ws.update([TABLES[name]], "A1")
        return ws


@st.cache_data(ttl=300, show_spinner=False)
def load(name):
    """表の中身（dict の一覧）"""
    cols = TABLES[name]
    if using_sheets():
        rows = _sheet(name).get_all_values()
    else:
        path = LOCAL_DIR / f"{name}.csv"
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as f:
            rows = list(csv.reader(f))
    if not rows:
        return []
    head = rows[0]
    return [{c: (r[head.index(c)] if c in head and head.index(c) < len(r) else "") for c in cols} for r in rows[1:] if any(r)]


def save(name, rows):
    """表をまるごと書きかえる"""
    cols = TABLES[name]
    values = [cols] + [[("" if r.get(c) is None else str(r.get(c))) for c in cols] for r in rows]
    if using_sheets():
        ws = _sheet(name)
        ws.clear()
        ws.update(values, "A1")
    else:
        LOCAL_DIR.mkdir(exist_ok=True)
        with (LOCAL_DIR / f"{name}.csv").open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(values)
    load.clear()


def append(name, row):
    """1行たす（ID と登録日時は自動）"""
    row = dict(row)
    if "ID" in TABLES[name] and not row.get("ID"):
        row["ID"] = uuid.uuid4().hex[:10]
    if "登録日時" in TABLES[name]:
        row["登録日時"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if using_sheets():
        _sheet(name).append_row([("" if row.get(c) is None else str(row.get(c))) for c in TABLES[name]], value_input_option="RAW")
        load.clear()
    else:
        save(name, load(name) + [row])
    return row
