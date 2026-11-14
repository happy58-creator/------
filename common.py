"""全ページ共通の見た目・ヘルパー。"""
import copy
import os
import unicodedata

import streamlit as st

GEMINI_MODEL = "gemini-3.6-flash"
HOME_PAGE = "home.py"

# (名前, ファイル, サイドバーの表示名, アイコン, URLの末尾)。URLは半角英数字にして、
# ファイル名の文字の形（Mac の濁点の分かれ方）に左右されないようにする。
PAGE_DEFS = [
    ("home", "home.py", "トップ", "🏠", ""),
    ("calc", "pages/0_計算マスター.py", "算数・数学", "🧮", "calc"),
    ("kokugo", "pages/1_国語.py", "AI国語", "🧙‍♂️", "kokugo"),
    ("english", "pages/2_英語.py", "AI英語", "🔤", "english"),
    ("speaking", "pages/14_英語スピーキング.py", "AI英語スピーキング", "🎤", "speaking"),
    ("kanji", "pages/10_漢字.py", "漢字", "✍️", "kanji"),
    ("typing", "pages/3_タイピング.py", "AIタイピング", "⌨️", "typing"),
    ("programming", "pages/4_プログラミング.py", "AIプログラミング", "💻", "programming"),
    ("lottery", "pages/5_くじ引き・じゅんばん決めゲーム.py", "くじ引き", "🎉", "lottery"),
    ("janken", "pages/6_じゃんけんゲーム.py", "じゃんけん", "✊", "janken"),
    ("chess", "pages/7_チェスVS.py", "チェス", "♟️", "chess"),
    ("rapid", "pages/8_限界突破ゲーム.py", "連打ゲーム", "⚡", "rapid"),
    ("story", "pages/11_ストーリーモード.py", "ストーリーモード", "⚔️", "story"),
    ("itpass", "pages/12_ITパスポート.py", "ITパスポート", "🖥️", "itpass"),
    ("fe", "pages/13_基本情報.py", "基本情報技術者", "🧑‍💻", "fe"),
    ("history", "pages/9_履歴.py", "せいせきの履歴", "📒", "history"),
]
SECTIONS = {
    "": ["home"],
    "べんきょう": ["calc", "kokugo", "english", "speaking", "kanji", "typing", "programming", "itpass", "fe"],
    "ゲーム": ["lottery", "janken", "chess", "rapid", "story"],
    "きろく": ["history"],
}
PAGES = {}  # 名前 -> st.Page（教材.py が毎回つくる）

# 年齢で変える表記（小学生 / 中学生 / 高校生以上）。サイドバーのメニュー名と見出し
BAND_PAGE_TITLES = {
    "中": {"calc": "数学", "history": "成績の履歴"},
    "高": {"calc": "数学", "history": "成績の履歴"},
}
BAND_SECTIONS = {
    "中": {"べんきょう": "学習", "きろく": "記録"},
    "高": {"べんきょう": "学習", "きろく": "記録"},
}


def age_band():
    """ログイン中の人の年齢から "小"（12さいまで・年齢がわからない）/ "中"（13〜15さい）/ "高"（16さい以上・管理者）"""
    import auth

    ss = st.session_state
    age, admin = ss.get("auth_age"), ss.get("auth_admin")
    if "auth_age" not in ss:              # ページを開き直した直後は、保存してあるログイン情報から読む
        try:
            token = auth._stored_token()
            entry = auth.read_token(token) if token else None
            if entry:
                age, admin = entry.get("age"), entry.get("admin")
        except Exception:
            pass
    try:
        age = int(age)
    except (TypeError, ValueError):
        return "高" if admin else "小"
    return "小" if age <= 12 else ("中" if age <= 15 else "高")

# Streamlit Cloud がアプリの外側の画面に出す「王冠マーク」と「作った人のアカウント表示」を消す。
# アプリと外側の画面は同じドメイン（〜.streamlit.app）なので、JavaScript から触れる。
_HIDE_CLOUD_BADGES_JS = """
<script>
(() => {
  const SELECTORS = [
    '[class*="viewerBadge"]', '[class*="profileContainer"]', '[class*="profilePreview"]',
    '[data-testid="stToolbarActions"]', '[data-testid="stMainMenu"]', '.stAppDeployButton',
  ];
  const hide = (doc) => {
    for (const sel of SELECTORS) {
      doc.querySelectorAll(sel).forEach((el) => el.style.setProperty("display", "none", "important"));
    }
    // 見えない部品（CSS や JavaScript だけの st.markdown / st.html）が作るすき間をつめる。
    // 中に style・script があるか、st.html の空の箱で、高さ0・画像やボタンなどが無いものだけ（あとで中身が入る場所はさわらない）
    doc.querySelectorAll('[data-testid="stElementContainer"], .element-container').forEach((el) => {
      if (el.dataset.kzGap) return;
      if (el.querySelector("iframe,img,button,input,textarea,select,a,canvas,svg,video,audio,table,[data-testid=stIconMaterial]")) return;
      const invisible = el.querySelector("style,script") || el.querySelector('[data-testid="stHtml"]');
      if (!invisible || el.getBoundingClientRect().height > 1) return;
      el.dataset.kzGap = "1";
      el.style.setProperty("display", "none", "important");
    });
  };
  const docs = [document];
  try { if (window.parent !== window) docs.push(window.parent.document); } catch (e) {}
  for (const doc of docs) {
    hide(doc);
    if (doc.defaultView.__kyouzaiBadgeObserver) continue;  // 監視は1画面に1つだけ
    let queued = false;
    const observer = new MutationObserver(() => {
      if (queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; hide(doc); });
    });
    observer.observe(doc.body, { childList: true, subtree: true });
    doc.defaultView.__kyouzaiBadgeObserver = observer;
  }
})();
</script>
"""

# PDFを、アプリの画面の上に「ビューア」として表示するスクリプト（ファイルを保存しない）。
# ボタンの data-pdf に PDF の中身(base64)が入っていて、クリックされたら pdf.js で1ページずつ描いて見せる。
# 別タブ(blob URL)は、スマホのブラウザーでは開けないことが多いので、同じ画面の中で表示する。
_PDF_OPEN_JS = """
<script>
(() => {
  const w = window;
  if (w.__kyouzaiPdfOpen) return;  // 登録は1回だけ
  w.__kyouzaiPdfOpen = true;
  const CDN = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/";

  const loadPdfJs = () => w.pdfjsLib ? Promise.resolve(w.pdfjsLib) : new Promise((ok, ng) => {
    const s = document.createElement("script");
    s.src = CDN + "pdf.min.js";
    s.onload = () => { w.pdfjsLib.GlobalWorkerOptions.workerSrc = CDN + "pdf.worker.min.js"; ok(w.pdfjsLib); };
    s.onerror = () => ng(new Error("pdf.js を よみこめなかったよ"));
    document.head.appendChild(s);
  });
  const toBytes = (b64) => {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  };

  async function openViewer(b64) {
    const bytes = toBytes(b64);
    // 注意：st.html は、スクリプトの中に HTML の文字列があると、そのスクリプトを捨ててしまう。部品は createElement で作る。
    const el = (tag, cls, text) => {
      const e = document.createElement(tag);
      if (cls) e.className = cls;
      if (text) e.textContent = text;
      return e;
    };
    const ov = el("div", "kz-pdf-overlay");
    const bar = el("div", "kz-pdf-bar");
    const saveBtn = el("button", "", "💾 ほぞん・いんさつ");
    const closeBtn = el("button", "kz-close", "✕ とじる");
    saveBtn.type = closeBtn.type = "button";
    const buttons = el("span");
    buttons.append(saveBtn, closeBtn);
    bar.append(el("b", "", "📄 表彰状"), buttons);
    const body = el("div", "kz-pdf-body");
    body.append(el("div", "kz-pdf-msg", "よみこみ中…"));
    ov.append(bar, body);
    document.body.appendChild(ov);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const close = () => { ov.remove(); document.body.style.overflow = prevOverflow; document.removeEventListener("keydown", onKey); };
    const onKey = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    closeBtn.onclick = close;
    saveBtn.onclick = () => {
      // 保存・印刷：ブラウザーの機能にまかせる（保存は、ここを押したときだけ）
      const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = "ひょうしょうじょう.pdf"; a.target = "_blank"; a.rel = "noopener";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 600000);
    };
    try {
      const lib = await loadPdfJs();
      const doc = await lib.getDocument({ data: bytes.slice() }).promise;
      body.replaceChildren();
      const dpr = Math.min(w.devicePixelRatio || 1, 3);
      const width = Math.min(body.clientWidth - 16, 820);
      for (let n = 1; n <= doc.numPages; n++) {
        const page = await doc.getPage(n);
        const base = page.getViewport({ scale: 1 });
        const viewport = page.getViewport({ scale: (width / base.width) * dpr });
        const canvas = document.createElement("canvas");
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);
        canvas.style.width = width + "px";
        canvas.style.height = Math.floor(viewport.height / dpr) + "px";
        body.appendChild(canvas);
        await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      }
    } catch (err) {
      body.replaceChildren(el("div", "kz-pdf-msg", "ここでは うまく ひらけなかったよ。「ほぞん・いんさつ」ボタンを おしてね。"));
    }
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-pdf]");
    if (btn) openViewer(btn.dataset.pdf);
  });
})();
</script>
"""

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@400;700;900&display=swap');
/* アイコン（stIconMaterial）はアイコン用フォントのままにする。上書きすると「arrow_right」などの文字が出てしまう */
html, body, [class*="st-"]:not([data-testid="stIconMaterial"]), .stApp { font-family: 'Zen Maru Gothic', sans-serif; }
.block-container { max-width: 900px; padding-top: 2rem; padding-bottom: 4rem; }
/* 上のバー（中身はかくしてある）を消して、ページの上の空白をつめる */
header[data-testid="stHeader"], [data-testid="stHeader"] { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: .8rem !important; }
/* 右上のツールバーのボタン（Fork・GitHub・メニュー）をかくす。
   サイドバーを開くボタンも stToolbar の中にあるので、stToolbar ごと消さない */
[data-testid="stToolbarActions"], [data-testid="stToolbarActionButton"], [data-testid="stMainMenu"],
.stAppDeployButton, [data-testid="stDecoration"] { display: none !important; }
/* サイドバーは使わない（開くボタンもかくす） */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"], [data-testid="stSidebarNav"] { display: none !important; }
/* ページの上の「トップにもどる」：小さめのボタンに */
.st-key-kz-back { width: fit-content; margin-bottom: -.4rem; }
.st-key-kz-back a { background: #fff; border: 1px solid rgba(84,43,105,.18); border-radius: 999px; padding: .15rem .9rem; }
/* 家計簿（/kakeibo）と買い物リスト（/kaimono）のページは、メニューに出さない */
[data-testid="stSidebarNav"] a[href$="/kakeibo"], [data-testid="stSidebarNavLink"][href$="/kakeibo"],
[data-testid="stSidebarNav"] a[href$="/kaimono"], [data-testid="stSidebarNavLink"][href$="/kaimono"] { display: none !important; }
[data-testid="stHeader"] { background: transparent; }

/* トップのカード全体をクリックで開く：リンクの当たり判定をカード全体に広げる */
[class*="st-key-appcard-"] { position: relative; cursor: pointer; transition: transform .1s ease; }
[class*="st-key-appcard-"]:hover { transform: translateY(-3px); }
[class*="st-key-appcard-"]:hover .topic-card { box-shadow: 0 8px 20px rgba(120, 80, 60, .18); }
[class*="st-key-appcard-"] [data-testid="stElementContainer"],
[class*="st-key-appcard-"] [data-testid="stPageLink"] { position: static !important; }
[class*="st-key-appcard-"] [data-testid="stPageLink-NavLink"]::after { content: ""; position: absolute; inset: 0; z-index: 2; }

.hero {
    padding: 1.6rem 1.25rem; border-radius: 1.4rem; text-align: center;
    margin-bottom: 1.2rem; box-shadow: 0 6px 18px rgba(120, 80, 60, .10);
    background: linear-gradient(135deg, #fff1dc, #ffe2e7 55%, #e9e8ff);
}
.hero h1 { margin: 0; color: #542b69; font-weight: 900; font-size: 2rem; line-height: 1.3; }
.hero p { margin: .5rem 0 0; color: #584b62; }

.topic-card {
    border-radius: 1.2rem; padding: 1.1rem 1.1rem .4rem; margin-bottom: .25rem; min-height: 13rem;
    border: 1px solid rgba(120, 80, 60, .12); background: #ffffff;
    box-shadow: 0 4px 12px rgba(120, 80, 60, .08);
}
.topic-card .emoji { font-size: 2.4rem; line-height: 1; }
.topic-card h3 { margin: .4rem 0 .2rem; font-size: 1.15rem; color: #3a2e39; }
.topic-card p { margin: 0 0 .5rem; font-size: .9rem; color: #6b5d68; min-height: 2.7em; }
.tag { display:inline-block; font-size:.72rem; font-weight:700; padding:.1rem .6rem;
       border-radius:99px; background:#ffe9d6; color:#b4531f; margin-bottom:.2rem; }
.tag.ai { background:#e6e3ff; color:#4a3fb0; }

div.stButton > button, div.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] > button {
    min-height: 2.9rem; border-radius: .9rem; font-weight: 700;
    transition: transform .08s ease, box-shadow .15s ease;
}
div.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,.12); }
div[data-testid="stMetric"] {
    padding: .8rem 1rem; border: 1px solid rgba(120, 80, 60, .15);
    border-radius: 1rem; background: #ffffff;
}
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 1.1rem; }
.big-center { text-align:center; font-weight:900; line-height:1.2; }
/* PDFを新しいタブで開くボタン（Streamlitの主ボタンに合わせた見た目） */
.pdf-open {
    display: block; width: 100%; min-height: 2.9rem; padding: .6rem 1rem; border: 0; border-radius: .9rem;
    background: #ff7a59; color: #fff; font: 700 1rem 'Zen Maru Gothic', sans-serif; cursor: pointer;
    transition: transform .08s ease, box-shadow .15s ease;
}
.pdf-open:hover { transform: translateY(-1px); box-shadow: 0 4px 10px rgba(0,0,0,.18); }
.pdf-open:active { transform: translateY(0); }
.pdf-note { margin: .25rem 0 .75rem; font-size: .8rem; color: #6b5d68; text-align: center; }
/* PDFビューア（画面いっぱいに重ねて表示） */
.kz-pdf-overlay { position: fixed; inset: 0; z-index: 2147483647; background: rgba(25, 22, 34, .92); display: flex; flex-direction: column; }
.kz-pdf-bar { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 10px 12px; color: #fff; background: #1f2a44; font-family: 'Zen Maru Gothic', sans-serif; }
.kz-pdf-bar button { margin-left: 6px; min-height: 40px; padding: 0 12px; border: 0; border-radius: 10px; font: 700 14px 'Zen Maru Gothic', sans-serif; cursor: pointer; background: #f3e3a3; color: #1f2a44; }
.kz-pdf-bar button.kz-close { background: #ff7a59; color: #fff; }
.kz-pdf-body { flex: 1; overflow: auto; -webkit-overflow-scrolling: touch; padding: 10px 8px 30px; text-align: center; }
.kz-pdf-body canvas { display: block; margin: 0 auto 12px; background: #fff; box-shadow: 0 4px 18px rgba(0,0,0,.4); max-width: 100%; }
.kz-pdf-msg { color: #fff; padding: 40px 10px; font: 700 16px 'Zen Maru Gothic', sans-serif; }
</style>
"""


def setup_page(title, icon, layout="centered", home_link=True):
    """set_page_config + 共通CSS + ページの上の「トップにもどる」。各ページの最初に呼ぶ。サイドバーは使わない（トップ画面の下のメニューで移動する）"""
    st.set_page_config(page_title=title, page_icon=icon, layout=layout, initial_sidebar_state="collapsed")
    st.markdown(_CSS, unsafe_allow_html=True)
    import auth  # 循環importを避けるため関数内で読み込む

    # ログイン画面でも王冠マークなどを消すので、ログインの確認より先に出す（サイドバーに出すとログイン前もサイドバーが出てしまう）
    st.html(_HIDE_CLOUD_BADGES_JS, unsafe_allow_javascript=True)
    auth.gate(is_home=not home_link)
    if home_link and "home" in PAGES:
        with st.container(key="kz-back"):
            st.page_link(PAGES["home"], label="トップにもどる", icon="🏠")
    st.html(_PDF_OPEN_JS, unsafe_allow_javascript=True)     # 「PDFを見る」ボタンを動かす（見えない）


_NO_KEYBOARD_JS = """
<script>
(() => {
  // ドロップダウン（selectbox）を押しても、スマホのキーボードが出ないようにする（文字は打てない）
  const fix = (doc) => doc.querySelectorAll('[data-baseweb="select"] input').forEach((el) => {
    if (el.dataset.kzNoKbd) return;
    el.dataset.kzNoKbd = "1";
    el.setAttribute("inputmode", "none");
    el.setAttribute("readonly", "readonly");
  });
  const docs = [document];
  try { if (window.parent !== window) docs.push(window.parent.document); } catch (e) {}
  for (const doc of docs) {
    fix(doc);
    if (doc.defaultView.__kzNoKbdObserver) continue;
    doc.defaultView.__kzNoKbdObserver = new MutationObserver(() => fix(doc));
    doc.defaultView.__kzNoKbdObserver.observe(doc.body, { childList: true, subtree: true });
  }
})();
</script>
"""


def no_keyboard_selects():
    """このページのドロップダウンを、キーボードが出ないものにする（ページに1回よぶ）"""
    st.html(_NO_KEYBOARD_JS, unsafe_allow_javascript=True)


def pick(label, options, key, format_func=str, index=0):
    """選択式（文字を入力しないので、スマホでキーボードが出ない）。
    「ラベル：いまの選択 ▾」のボタンを押すと、選択肢の一覧（ラジオボタン）が開く。えらんだ値を返す。"""
    options = list(options)
    if not options:
        return None
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[min(max(index or 0, 0), len(options) - 1)]
    current = st.session_state[key]
    with st.popover(f"{label}：{format_func(current)}", use_container_width=True):
        st.radio(label, options, key=key, format_func=format_func, label_visibility="collapsed")
    return st.session_state[key]


def anchor(name):
    """jump_to で飛べる目印"""
    st.markdown(f"<div id='kz-{name}' style='position:relative;top:-70px'></div>", unsafe_allow_html=True)


def jump_to(name, nonce):
    """anchor(name) の場所まで画面をスクロールする（nonce を変えると、もう一度動く）"""
    st.html(f"""<script>
(() => {{
  const id = "kz-{name}"; void "{nonce}";
  const go = (tries) => {{
    const docs = [document];
    try {{ if (window.parent !== window) docs.push(window.parent.document); }} catch (e) {{}}
    for (const doc of docs) {{
      const el = doc.getElementById(id);
      if (el) {{ el.scrollIntoView({{ behavior: "smooth", block: "start" }}); return; }}
    }}
    if (tries > 0) setTimeout(() => go(tries - 1), 150);
  }};
  setTimeout(() => go(20), 100);
}})();
</script>""", unsafe_allow_javascript=True)


def pdf_preview_button(pdf_bytes, label="📄 表彰状を 見る"):
    """PDFを、保存せずに、画面の上のビューアで見せるボタン。保存・印刷は、ビューアの中のボタンから。"""
    import base64

    data = base64.b64encode(pdf_bytes).decode("ascii")
    st.html(
        f'<button type="button" class="pdf-open" data-pdf="{data}">{label}</button>'
        '<div class="pdf-note">画面の上に ひらくよ。保存や印刷は、ひらいた画面の ボタンから できるよ。</div>',
        unsafe_allow_javascript=True,
    )


def build_navigation():
    """サイドバーのメニューとページを登録して返す（教材.py から呼ぶ）。"""
    band = age_band()
    titles = BAND_PAGE_TITLES.get(band, {})
    for key, path, title, icon, url_path in PAGE_DEFS:
        PAGES[key] = st.Page(page_file(path), title=titles.get(key, title), icon=icon, url_path=url_path, default=(key == "home"))
    import auth

    # サイドバーのメニューは出さない（トップ画面の下のメニューと、各ページの「トップにもどる」で移動する）
    position = "hidden"
    names = BAND_SECTIONS.get(band, {})
    adult_only = {"itpass", "fe"} if band == "小" else set()      # ITパスポート・基本情報は大人向け（小学生のメニューには出さない）
    nav = {names.get(section, section): [PAGES[k] for k in keys if k not in adult_only] for section, keys in SECTIONS.items()}
    # 家計簿（大人用）：メニューには出さないページ。URL の最後に /kakeibo を付けて開く（パスワードは kakeibo/app.py）
    nav[names.get("きろく", "きろく")].append(st.Page(page_file("kakeibo/app.py"), title="家計簿", icon="💴", url_path="kakeibo"))
    # 買い物リスト（大人用）：家計簿と同じく、メニューには出さないページ。URL の最後に /kaimono（ログインは家計簿と共通）
    nav[names.get("きろく", "きろく")].append(st.Page(page_file("shopping/app.py"), title="買い物リスト", icon="🛒", url_path="kaimono"))
    return st.navigation(nav, position=position)


def page_file(path):
    """ページのファイル名を、ディスク上の実際の書き方にそろえる。

    Mac では「ゲ」が「ケ＋゛」のように分かれて保存されることがあり、
    そのままの名前だと st.page_link がページを見つけられない。
    """
    folder, name = os.path.split(path)
    target = unicodedata.normalize("NFC", name)
    try:
        for found in os.listdir(os.path.join(os.path.dirname(__file__), folder)):
            if unicodedata.normalize("NFC", found) == target:
                return os.path.join(folder, found)
    except OSError:
        pass
    return path


def age_level_index(count):
    """ログイン中の年齢から、年齢層ラジオ（小1〜2 … 大人）の初期位置を返す。"""
    age = st.session_state.get("auth_age")
    if age is None:
        return 0
    limits = (8, 10, 12, 15, 18)
    return next((i for i, limit in enumerate(limits) if age <= limit), count - 1)


def hero(title, subtitle=""):
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f"<div class='hero'><h1>{title}</h1>{sub}</div>", unsafe_allow_html=True)


def init_state(defaults):
    """未設定のキーだけ初期化する。"""
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def reset_state(prefix, defaults):
    """prefix で始まるキーだけ消して初期値に戻す（他ページの状態は触らない）。"""
    for key in [k for k in st.session_state.keys() if k.startswith(prefix)]:
        del st.session_state[key]
    init_state(defaults)


def get_gemini_client():
    """APIキーは .streamlit/secrets.toml の GEMINI_API_KEY か環境変数から読む。"""
    from google import genai

    key = None
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass
    key = key or os.environ.get("GEMINI_API_KEY")
    if not key:
        st.error(
            "AIのカギ（GEMINI_API_KEY）が見つからないよ。"
            " `.streamlit/secrets.toml` に `GEMINI_API_KEY = \"...\"` を書いてね。"
        )
        st.stop()
    try:          # 返事が来ないまま待ちつづけないように（1回の問い合わせは60秒まで）
        from google.genai import types
        return genai.Client(api_key=key, http_options=types.HttpOptions(timeout=60_000))
    except Exception:
        return genai.Client(api_key=key)


GEMINI_FALLBACK_MODEL = "gemini-3.5-flash-lite"   # 予備：混雑・回数の上限のとき（回数の上限はモデルごとに別）


def ai_error_text(e):
    """Gemini のエラーを、子どもにもわかる文にする"""
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    name, msg = type(e).__name__, str(e)
    if code == 429 or "RESOURCE_EXHAUSTED" in msg:
        return "今日のAIの回数を 使いきったみたい。夕方5時（日本時間）に もどるよ"
    if isinstance(code, int) and code >= 500:
        return "AIが 混み合っているみたい。少し待ってから もう一度ためしてね"
    if "timeout" in name.lower() or "timed out" in msg.lower() or "Timeout" in msg:
        return "AIの返事が おそすぎたよ。もう一度ためしてね"
    return f"AIでエラーが起きちゃった（{name}）。もう一度ためしてね"
