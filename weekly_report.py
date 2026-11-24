"""週ごとの 学習レポート（おうちの人向け）。1人ずつ、7日ぶんの 記録を まとめて、AI（2.5 → 3.5 Lite）が 短く 書く。
- 数字（回数・平均点・苦手）は アプリが 記録から 数える（正確）。AI は それを 読みやすい 文に するだけ
- 作った レポートは「週レポート」タブに 保存（同じ人・同じ週は 作りなおすまで 回数を 使わない）"""
import json
import time
from datetime import date, datetime, timedelta

import common
import datastore
import history

TAB, COLS = "週レポート", ["キー", "名前", "週", "レポート", "日時"]
SUBJECTS = ["計算", "国語", "漢字", "英語", "スピーキング", "タイピング", "プログラミング", "ITパスポート", "基本情報", "学習"]


def week_range(offset=0):
    """offset=0：今週（月曜〜今日）、1：先週（月〜日）。(はじめ, おわり) の 日付"""
    today = date.today()
    mon = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
    return mon, (today if offset == 0 else mon + timedelta(days=6))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def facts_of(name, start, end):
    """その人・その期間の 教科ごとの まとめ（AI に わたす 正確な データ）"""
    a, b = start.strftime("%Y-%m-%d"), (end + timedelta(days=1)).strftime("%Y-%m-%d")
    out, days = [], set()
    for sheet in SUBJECTS:
        rows = [r for r in history.read_history(sheet) if str(r.get("名前")) == name and a <= str(r.get("日時")) < b]
        if not rows:
            continue
        days |= {str(r.get("日時"))[:10] for r in rows}
        sc = [v for v in (_num(r.get("点数")) for r in rows) if v is not None]
        f = {"教科": sheet, "回数": len(rows)}
        if sc:
            f["平均点"] = round(sum(sc) / len(sc), 1)
            f["最高点"] = max(sc)
        miss, good = [], []
        for r in rows:
            try:
                rec = json.loads(r.get("詳細") or "{}")
            except ValueError:
                rec = {}
            for x in (rec.get("r") or []) if isinstance(rec, dict) else []:
                if len(x) >= 4:
                    (good if x[3] else miss).append(str(x[0]).split("\n")[0][:30])
        if miss:
            f["まちがえた問題の例"] = list(dict.fromkeys(miss))[:6]
            f["正答率"] = f"{round(len(good) * 100 / (len(good) + len(miss)))}%"
        if sheet == "漢字":
            f["書き方"] = sorted({str(r.get("モード")) for r in rows})
        if sheet in ("ITパスポート", "基本情報"):
            c, n = sum(int(_num(r.get("正解数")) or 0) for r in rows), sum(int(_num(r.get("問題数")) or 0) for r in rows)
            if n:
                f["正答率"] = f"{round(c * 100 / n)}%（{c}/{n}問）"
        if sheet == "学習":
            f["まなんだ単元"] = list(dict.fromkeys(str(r.get("単元名") or r.get("単元")) for r in rows))[:6]
        if sheet in ("英語", "スピーキング", "国語", "プログラミング"):
            kinds = [str(r.get("コース") or r.get("テーマ") or r.get("言語") or "") for r in rows]
            f["内容"] = list(dict.fromkeys(k for k in kinds if k))[:5]
        out.append(f)
    return out, sorted(days)


def make(name, offset=0, remake=False):
    """{"week": "11/23〜11/29", "facts": [...], "days": n, "report": {...} or None, "made": 日時}"""
    start, end = week_range(offset)
    label = f"{start.month}/{start.day}〜{end.month}/{end.day}"
    key = f"{name}|{start.isoformat()}"
    facts, days = facts_of(name, start, end)
    res = {"week": label, "facts": facts, "days": len(days), "report": None, "made": ""}
    old = next((r for r in datastore.read(TAB, COLS, fresh=True) if r.get("キー") == key), None)
    if old and not remake:
        try:
            res["report"], res["made"] = json.loads(old.get("レポート") or ""), old.get("日時", "")
            return res
        except ValueError:
            pass
    if not facts:
        return res
    if not remake and offset == 0 and not old:
        return res                              # 今週は「作る」を 押したときだけ 作る（回数の 節約）
    res["report"] = _ai(name, label, facts, len(days))
    res["made"] = time.strftime("%Y-%m-%d %H:%M:%S")
    datastore.put(TAB, COLS, "キー", {"キー": key, "名前": name, "週": label, "レポート": json.dumps(res["report"], ensure_ascii=False), "日時": res["made"]})
    return res


def _ai(name, label, facts, days):
    from google.genai import types
    prompt = f"""あなたは 家庭学習を 見守る、あたたかくて 具体的な 先生です。{name}さんの {label} の 学習記録を、おうちの人向けに まとめてください。
次の データは アプリの 記録から 数えた 正確な 値です。データに ない ことは 書かない。数字は データの とおりに 使う。

学習した日数：{days}日
{json.dumps(facts, ensure_ascii=False, indent=1)}

次の JSON だけで 答えてください：
{{"summary": "1週間の ようすを 2〜3文で（何を どれくらい がんばったか、のびた所）",
  "good": ["よかった点（具体的に。教科名と 数字を 入れる）", "…（2〜3個）"],
  "next": ["来週の おすすめ（苦手や まちがえた問題から。アプリの どの練習を するか まで）", "…（1〜3個）"],
  "praise": "{name}さん本人への ひとこと（ひらがな多め、1文）"}}"""
    res = common.get_gemini_client().models.generate_content(
        model=getattr(common, "GEMINI_CHEAP", common.GEMINI_MODEL), contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4))
    d = json.loads(res.text)
    return {"summary": str(d.get("summary") or ""), "good": [str(x) for x in (d.get("good") or [])][:3],
            "next": [str(x) for x in (d.get("next") or [])][:3], "praise": str(d.get("praise") or "")}
