"""家計簿の計算（画面や保存には関係しない、ただの計算）"""
import calendar
from datetime import date, timedelta

EXPENSE, INCOME = "支出", "収入"
MONTHLY, YEARLY = "月払い", "年払い"


def to_date(v):
    """"2026-11-06" などの文字列・date を date に（読めなければ None）"""
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def to_int(v):
    try:
        return int(round(float(str(v).replace(",", "").strip() or 0)))
    except ValueError:
        return 0


def ym(d):
    """date → "2026-11\""""
    return f"{d.year:04d}-{d.month:02d}"


def shift_month(month, n):
    """"2026-11" を n か月ずらす"""
    y, m = int(month[:4]), int(month[5:7])
    k = y * 12 + (m - 1) + n
    return f"{k // 12:04d}-{k % 12 + 1:02d}"


def in_month(records, month):
    return [r for r in records if str(r.get("日付", ""))[:7] == month]


def totals(records):
    """収入・支出・収支"""
    inc = sum(to_int(r["金額"]) for r in records if r.get("種類") == INCOME)
    exp = sum(to_int(r["金額"]) for r in records if r.get("種類") == EXPENSE)
    return {"収入": inc, "支出": exp, "収支": inc - exp}


def by_category(records, kind=EXPENSE):
    """カテゴリごとの合計（多い順）"""
    out = {}
    for r in records:
        if r.get("種類") == kind:
            out[r.get("カテゴリ") or "その他"] = out.get(r.get("カテゴリ") or "その他", 0) + to_int(r["金額"])
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def trend(records, end_month, months=12):
    """end_month までの months か月ぶんの、月ごとの収入・支出"""
    out = []
    for i in range(months - 1, -1, -1):
        m = shift_month(end_month, -i)
        t = totals(in_month(records, m))
        out.append({"月": m, "収入": t["収入"], "支出": t["支出"]})
    return out


def budget_status(month_records, budgets):
    """カテゴリごとの予算・使った額・残り（予算を入れたカテゴリだけ）"""
    used = by_category(month_records, EXPENSE)
    out = []
    for b in budgets:
        amount = to_int(b.get("予算"))
        if amount <= 0:
            continue
        u = used.get(b.get("カテゴリ"), 0)
        out.append({"カテゴリ": b.get("カテゴリ"), "予算": amount, "使った": u, "残り": amount - u, "割合": u / amount})
    return out


def add_cycle(d, cycle, day=None):
    """次の支払日：月払いは1か月後、年払いは1年後（月末をこえる日は、その月の最後の日）。
    day は本来の支払日（31日払いなどで、短い月のあとも31日にもどすため）"""
    day = day or d.day
    if cycle == YEARLY:
        y, m = d.year + 1, d.month
    else:
        y, m = (d.year + (d.month // 12), d.month % 12 + 1)
    return date(y, m, min(day, calendar.monthrange(y, m)[1]))


def sub_monthly(sub):
    """サブスクの、1か月あたりの金額（年払いは12で割る）"""
    a = to_int(sub.get("金額"))
    return a / 12 if sub.get("周期") == YEARLY else a


def sub_totals(subs):
    m = sum(sub_monthly(s) for s in subs)
    return {"月あたり": round(m), "年あたり": round(m * 12)}


def upcoming(subs, today, days=30):
    """支払日が近い（または過ぎた）サブスク。[{...sub, "あと何日": n}] 近い順"""
    out = []
    for s in subs:
        d = to_date(s.get("次の支払日"))
        if not d:
            continue
        left = (d - today).days
        if left <= days:
            out.append({**s, "あと何日": left})
    return sorted(out, key=lambda s: s["あと何日"])


def pay_sub(sub, today):
    """「支払った」：家計簿に入れる記録と、次の支払日を進めたサブスクを返す"""
    d = to_date(sub.get("次の支払日")) or today
    record = {"日付": d.isoformat(), "種類": EXPENSE, "金額": to_int(sub.get("金額")),
              "カテゴリ": sub.get("カテゴリ") or "サブスク", "メモ": f"{sub.get('名前', '')}（{sub.get('周期', MONTHLY)}）"}
    day = to_int(sub.get("支払日の日")) or d.day
    nxt = add_cycle(d, sub.get("周期", MONTHLY), day)
    return record, {**sub, "次の支払日": nxt.isoformat(), "支払日の日": day}
