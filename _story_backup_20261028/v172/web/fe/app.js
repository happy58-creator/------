/* 基本情報技術者試験 学習（教材の中のページ。ITパスポートの画面をもとに、科目A・科目Bに合わせたもの）。画面はぜんぶここ（Vue）。
   データ：data.js（window.ITP：解説・問題・用語）。
   記録：この端末（localStorage）と、Python 経由で Googleスプレッドシート（「基本情報」シート）の両方。
   Python → 画面：stats（スプレッドシートの記録から作った問題ごとの成績）、sessions（模試の履歴）、ai（AIの答え）、user
   画面 → Python：{ type: "log", ... }（1回分の結果）／{ type: "ask", ... }（AIに質問） */
const { createApp, reactive, computed, watch, nextTick } = Vue;
const D = window.ITP || { lessons: [], questions: [], terms: [] };

// ---- 分野 ----
const FIELDS = {
  T: { name: "テクノロジ系", short: "テクノロジ", color: "#3466d6" },
  M: { name: "マネジメント系", short: "マネジメント", color: "#23966a" },
  S: { name: "ストラテジ系", short: "ストラテジ", color: "#e07a2f" },
  B: { name: "科目B", short: "科目B", color: "#7b3fa1" },
};
const CATS = [
  ["T01", "基礎理論"], ["T02", "アルゴリズムとプログラミング"], ["T03", "コンピュータ構成要素"], ["T04", "システム構成要素"], ["T05", "ソフトウェア"], ["T06", "ハードウェア"],
  ["T07", "ユーザーインタフェース"], ["T08", "情報メディア"], ["T09", "データベース"], ["T10", "ネットワーク"], ["T11", "セキュリティ"],
  ["M12", "システム開発技術"], ["M13", "ソフトウェア開発管理技術"], ["M14", "プロジェクトマネジメント"], ["M15", "サービスマネジメント"], ["M16", "システム監査"],
  ["S17", "システム戦略"], ["S18", "システム企画"], ["S19", "経営戦略マネジメント"], ["S20", "技術戦略マネジメント"], ["S21", "ビジネスインダストリ"], ["S22", "企業活動"], ["S23", "法務"],
  ["B1", "アルゴリズムとプログラミング（科目B）"], ["B2", "情報セキュリティ（科目B）"],
].map(([id, name]) => ({ id, name, f: id[0] }));
const CAT = Object.fromEntries(CATS.map(c => [c.id, c]));
const KANA = ["ア", "イ", "ウ", "エ", "オ", "カ", "キ", "ク", "ケ", "コ", "サ", "シ"];
const Q = D.questions.filter(q => CAT[q.cat] && Array.isArray(q.choices) && q.choices.length >= 2 && q.choices.length <= KANA.length);
const QID = Object.fromEntries(Q.map(q => [q.id, q]));
const LESSON = Object.fromEntries((D.lessons || []).map(l => [l.cat, l]));
const TERMS = (D.terms || []).filter(t => t.term && t.def);

// 模試の形（n のキー：1文字なら分野、2文字以上なら中分類）
const EXAMS = {
  A: { name: "科目A 模試", n: { T: 41, M: 7, S: 12 }, min: 90 },
  B: { name: "科目B 模試", n: { B1: 16, B2: 4 }, min: 100 },
  miniA: { name: "科目A ミニ模試", n: { T: 14, M: 2, S: 4 }, min: 30 },
  miniB: { name: "科目B ミニ模試", n: { B1: 4, B2: 1 }, min: 25 },
};
const PASS_TOTAL = 600;             // 科目A・科目B それぞれ 600点以上（分野ごとの基準点はない）
const GROUP = { T: ["テクノロジ", "#3466d6"], M: ["マネジメント", "#23966a"], S: ["ストラテジ", "#e07a2f"], B: ["科目B", "#7b3fa1"], B1: ["アルゴリズム", "#7b3fa1"], B2: ["セキュリティ", "#c2416e"] };
const inGroup = (q, g) => g.length === 1 ? q.cat[0] === g : q.cat === g;

// ---- 保存（この端末） ----
const LS_KEY = "fe_v1";
function loadLocal() { try { return JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch (e) { return {}; } }
const local = Object.assign({ stats: {}, flags: {}, known: {}, sessions: [], exam: null, examDate: "", unsent: [] }, loadLocal());
function persist() { try { localStorage.setItem(LS_KEY, JSON.stringify(local)); } catch (e) { } }

// ---- 小道具 ----
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const shuffle = a => { a = [...a]; for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
const pct = (c, n) => n ? Math.round(c / n * 100) : 0;
const pad2 = n => String(n).padStart(2, "0");
const fmtTime = s => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return h ? `${h}:${pad2(m)}:${pad2(x)}` : `${m}:${pad2(x)}`; };
const today = () => { const d = new Date(); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`; };
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const app = createApp({
  setup() {
    const S = reactive({
      view: "home", user: "", ai: {}, aiWait: "", server: {}, serverSessions: [],
      // 学ぶ
      lessonCat: "", learnField: "S",
      // 演習・模試の進行
      run: null,            // { mode, title, ids, i, answers:{id:choice}, flags:{}, checked:{}, start, limit, done, result }
      setup: { scope: "cat", f: "S", cat: "S01", n: 10, order: "smart" },
      // 用語カード
      cards: null,          // { list:[...], i, flip }
      cardScope: "all",
      reviewFilter: "all",
      examDate: local.examDate || "",
      tick: 0, toast: "", confirm: null,
    });
    const L = reactive(local);
    // この画面は、教材のページの中の背の高い枠（iframe）。画面の真ん中に出すと見えないところに出てしまうので、
    // いま見えている場所（外側のページのスクロール位置）を調べて、そこに出す
    function visibleTop() {
      try { const r = window.frameElement.getBoundingClientRect(); return Math.max(0, -r.top); } catch (e) { return 0; }
    }
    function visibleHeight() { try { return window.parent.innerHeight || window.innerHeight; } catch (e) { return window.innerHeight; } }
    const place = (name, ratio) => document.documentElement.style.setProperty(name, Math.round(visibleTop() + visibleHeight() * ratio) + "px");
    let toastTimer = 0;
    const toast = m => { place("--tt", 0.04); S.toast = m; clearTimeout(toastTimer); toastTimer = setTimeout(() => S.toast = "", 2400); };
    const send = v => Streamlit.setValue({ ...v, nonce: uid() });
    const top = () => { window.scrollTo(0, 0); try { window.frameElement && window.frameElement.scrollIntoView({ block: "start" }); } catch (e) { } };

    // ---- 成績（この端末＋スプレッドシート） ----
    // 1問ごと：{ n: 解いた回数, c: 正解の回数, last: 1/0（いちばん新しい結果）, t: 日時 }
    const stat = id => {
      const a = L.stats[id], b = S.server[id];
      if (a && b) return (b.n > a.n ? b : a);
      return a || b || null;
    };
    function record(id, ok) {
      const s = L.stats[id] = { ...(stat(id) || { n: 0, c: 0 }) };
      s.n++; if (ok) s.c++; s.last = ok ? 1 : 0; s.t = Date.now();
    }
    const catStat = computed(() => {
      void S.tick;
      const out = {};
      for (const c of CATS) out[c.id] = { n: 0, c: 0, seen: 0, total: 0, wrong: 0 };
      for (const q of Q) {
        const o = out[q.cat]; o.total++;
        const s = stat(q.id); if (!s) continue;
        o.seen++; o.n += s.n; o.c += s.c; if (s.last === 0) o.wrong++;
      }
      return out;
    });
    const fieldStat = computed(() => {
      const out = Object.fromEntries(Object.keys(FIELDS).map(k => [k, { n: 0, c: 0, seen: 0, total: 0 }]));
      for (const c of CATS) { const a = catStat.value[c.id], o = out[c.f]; o.n += a.n; o.c += a.c; o.seen += a.seen; o.total += a.total; }
      return out;
    });
    const allStat = computed(() => Object.values(fieldStat.value).reduce((a, b) => ({ n: a.n + b.n, c: a.c + b.c, seen: a.seen + b.seen, total: a.total + b.total }), { n: 0, c: 0, seen: 0, total: 0 }));
    const weakIds = computed(() => { void S.tick; return Q.filter(q => { const s = stat(q.id); return s && (s.last === 0 || (s.n >= 2 && s.c / s.n < 0.6)); }).map(q => q.id); });
    const flagIds = computed(() => Object.keys(L.flags).filter(id => QID[id]));
    const sessions = computed(() => {
      const seen = new Set(), out = [];
      for (const s of [...L.sessions, ...S.serverSessions]) { if (!s.key || seen.has(s.key)) continue; seen.add(s.key); out.push(s); }
      return out.sort((a, b) => String(b.date).localeCompare(String(a.date)));
    });
    const examSessions = computed(() => sessions.value.filter(s => EXAMS[s.mode]));
    const weakCats = computed(() => CATS.map(c => ({ ...c, s: catStat.value[c.id] })).filter(c => c.s.n >= 3).sort((a, b) => a.s.c / a.s.n - b.s.c / b.s.n).slice(0, 5));
    const daysLeft = computed(() => {
      if (!S.examDate) return null;
      const d = Math.ceil((new Date(S.examDate + "T00:00:00") - new Date(today() + "T00:00:00")) / 86400000);
      return d;
    });
    watch(() => S.examDate, v => { L.examDate = v; persist(); });
    watch(() => S.confirm, v => { if (v) place("--mt", 0.25); });

    // ---- 問題を選ぶ ----
    // smart：まだ解いていない → まちがえた → 正答率が低い の順に多めに（同じくらいならランダム）
    function pickIds(pool, n, order) {
      if (order === "random") return shuffle(pool).slice(0, n);
      const score = id => { const s = stat(id); if (!s) return 0 + Math.random(); if (s.last === 0) return 1 + Math.random(); return 2 + s.c / s.n + Math.random(); };
      if (order === "seq") return pool.slice(0, n);
      return [...pool].sort((a, b) => score(a) - score(b)).slice(0, n);
    }
    function examIds(kind) {
      const ids = [];
      for (const f of Object.keys(EXAMS[kind].n)) {
        const pool = Q.filter(q => inGroup(q, f)).map(q => q.id);
        // 中分類が偏らないように、中分類ごとに順番に1問ずつ取る（各中分類の中は smart の順）
        const byCat = {};
        for (const id of pickIds(pool, pool.length, "smart")) (byCat[QID[id].cat] = byCat[QID[id].cat] || []).push(id);
        const lists = Object.values(byCat).map(shuffle);
        const want = EXAMS[kind].n[f], got = [];
        const weight = l => l.length;
        while (got.length < want && lists.some(l => l.length)) {
          // 問題数の多い中分類ほど多めに出す（本番の出題比率に近づける）
          const avail = lists.filter(l => l.length), total = avail.reduce((a, l) => a + weight(l), 0);
          let r = Math.random() * total, pickL = avail[0];
          for (const l of avail) { r -= weight(l); if (r <= 0) { pickL = l; break; } }
          got.push(pickL.shift());
        }
        ids.push(...shuffle(got));
      }
      return ids;
    }

    // ---- 演習（1問ずつ答え合わせ） ----
    function startDrill(ids, title, mode) {
      if (!ids.length) { toast("出せる問題がありません"); return; }
      S.run = { mode: mode || "drill", title, ids, i: 0, answers: {}, checked: {}, flags: {}, start: Date.now(), limit: 0, done: false, result: null, key: uid() };
      S.view = "run"; top();
    }
    function startFromSetup() {
      const st = S.setup;
      let pool = st.scope === "cat" ? Q.filter(q => q.cat === st.cat) : st.scope === "field" ? Q.filter(q => q.cat[0] === st.f) : st.scope === "weak" ? weakIds.value.map(id => QID[id])
        : st.scope === "flag" ? flagIds.value.map(id => QID[id]) : st.scope === "new" ? Q.filter(q => !stat(q.id)) : Q;
      const ids = pickIds(pool.map(q => q.id), st.n === "all" ? pool.length : +st.n, st.order);
      const title = st.scope === "cat" ? CAT[st.cat].name : st.scope === "field" ? FIELDS[st.f].name : { weak: "苦手な問題", flag: "見直し（★）", new: "まだ解いていない問題", all: "全分野" }[st.scope];
      startDrill(ids, title, "drill");
    }
    function drillCat(cat, n) { startDrill(pickIds(Q.filter(q => q.cat === cat).map(q => q.id), n || 10, "smart"), CAT[cat].name, "drill"); }

    // ---- 模試（最後にまとめて採点） ----
    function startExam(kind) {
      if (L.exam && L.exam.kind) {
        S.confirm = { msg: "とちゅうの模試があります。続けますか？", ok: "続ける", cancel: "新しく始める", fn: () => resumeExam(), no: () => { L.exam = null; persist(); startExam(kind); } };
        return;
      }
      const ids = examIds(kind);
      S.run = { mode: kind, title: EXAMS[kind].name, ids, i: 0, answers: {}, checked: {}, flags: {}, start: Date.now(), limit: EXAMS[kind].min * 60, done: false, result: null, key: uid(), kind };
      saveExam(); S.view = "run"; top();
    }
    function saveExam() { const r = S.run; if (!r || !r.limit || r.done) return; L.exam = { kind: r.kind, ids: r.ids, i: r.i, answers: r.answers, flags: r.flags, start: r.start, limit: r.limit, key: r.key, title: r.title }; persist(); }
    function resumeExam() {
      const e = L.exam; if (!e) return;
      S.run = { mode: e.kind, title: e.title, ids: e.ids, i: e.i || 0, answers: e.answers || {}, checked: {}, flags: e.flags || {}, start: e.start, limit: e.limit, done: false, result: null, key: e.key, kind: e.kind };
      S.view = "run"; top();
      if (remain.value <= 0) finishRun(true);
    }
    const isExam = computed(() => S.run && !!S.run.limit);
    const remain = computed(() => { void S.tick; const r = S.run; return r && r.limit ? r.limit - (Date.now() - r.start) / 1000 : 0; });
    setInterval(() => {
      S.tick++;
      if (S.run && S.run.limit && !S.run.done && remain.value <= 0) { toast("時間です。採点します"); finishRun(true); }
    }, 1000);

    const cur = computed(() => S.run ? QID[S.run.ids[S.run.i]] : null);
    function choose(k) {
      const r = S.run, q = cur.value; if (!r || !q || r.done) return;
      if (!isExam.value && r.checked[q.id]) return;
      r.answers[q.id] = k;
      if (!isExam.value) {                    // 演習：すぐ答え合わせ
        r.checked[q.id] = true; record(q.id, k === q.answer); persist(); S.tick++;
        nextTick(() => { const el = document.querySelector(".fb"); if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" }); });
      } else saveExam();
    }
    function go(i) { const r = S.run; if (!r) return; r.i = Math.max(0, Math.min(r.ids.length - 1, i)); if (isExam.value) saveExam(); S.navOpen = false; top(); }
    function next() { const r = S.run; if (r.i < r.ids.length - 1) go(r.i + 1); else finishAsk(); }
    function toggleFlag(id) { if (L.flags[id]) delete L.flags[id]; else L.flags[id] = 1; persist(); }
    function toggleMark(id) { const r = S.run; r.flags[id] = !r.flags[id]; saveExam(); }
    function finishAsk() {
      const r = S.run; if (!r) return;
      if (isExam.value) {
        const blank = r.ids.filter(id => r.answers[id] == null).length, marked = r.ids.filter(id => r.flags[id]).length;
        S.confirm = { msg: `採点しますか？${blank ? `<br><b>未回答 ${blank}問</b>` : ""}${marked ? `<br>見直しマーク ${marked}問` : ""}`, ok: "採点する", fn: () => finishRun(false) };
      } else finishRun(false);
    }
    function finishRun(timeUp) {
      const r = S.run; if (!r || r.done) return;
      const ids = isExam.value ? r.ids : r.ids.filter(id => r.answers[id] != null);
      // 模試は出題のまとまりごと、演習は分野ごとに集計
      const groups = isExam.value ? Object.keys(EXAMS[r.kind].n) : Object.keys(FIELDS);
      const per = Object.fromEntries(groups.map(g => [g, [0, 0]])), rows = [];
      for (const id of ids) {
        const q = QID[id], ok = r.answers[id] === q.answer, f = groups.find(g => inGroup(q, g)) || groups[0];
        per[f][1]++; if (ok) per[f][0]++;
        rows.push([id, ok ? 1 : 0]);
        if (isExam.value) record(id, ok);
      }
      const c = rows.filter(x => x[1]).length, n = rows.length;
      const fieldScore = Object.fromEntries(Object.entries(per).map(([f, [cc, nn]]) => [f, nn ? Math.round(cc / nn * 1000) : null]));
      const total = n ? Math.round(c / n * 1000) : 0;
      const pass = isExam.value ? total >= PASS_TOTAL : null;
      const secs = Math.round((Date.now() - r.start) / 1000);
      r.result = { c, n, total, fieldScore, per, pass, secs, timeUp, groups };
      r.done = true; S.reviewFilter = isExam.value ? "wrong" : "all";
      if (isExam.value) { L.exam = null; }
      const sess = { key: r.key, date: new Date().toISOString().slice(0, 16).replace("T", " "), mode: r.mode, title: r.title, c, n, total, pass, f: per, secs };
      L.sessions = [sess, ...L.sessions].slice(0, 60);
      persist(); S.tick++;
      if (n) send({ type: "log", key: r.key, mode: r.mode, title: r.title, c, n, total, pass, per, secs, rows });
      S.view = "result"; top();
    }
    function quitRun() {
      const r = S.run;
      if (r && !r.done && Object.keys(r.answers).length && !isExam.value) { finishRun(false); return; }
      if (r && isExam.value && !r.done) { saveExam(); toast("模試はとちゅうで保存しました。ホームの「続ける」から再開できます"); }
      S.run = null; S.view = "home"; top();
    }
    const reviewIds = computed(() => {
      const r = S.run; if (!r) return [];
      const ids = r.ids.filter(id => r.answers[id] != null || isExam.value);
      if (S.reviewFilter === "wrong") return ids.filter(id => r.answers[id] !== QID[id].answer);
      if (S.reviewFilter === "mark") return ids.filter(id => r.flags[id]);
      return ids;
    });
    function retryWrong() {
      const r = S.run; const ids = r.ids.filter(id => r.answers[id] != null && r.answers[id] !== QID[id].answer || (isExam.value && r.answers[id] == null));
      startDrill(shuffle(ids), "まちがえた問題をもう一度", "drill");
    }
    function openReview(id) {         // 結果画面から1問を開いて解説を見る
      const r = S.run; r.i = r.ids.indexOf(id); S.view = "review"; top();
    }

    // ---- AIに質問 ----
    function askAI(q, extra) {
      const r = S.run, mine = r ? r.answers[q.id] : null;
      const nonce = uid(); S.aiWait = q.id;
      Streamlit.setValue({ type: "ask", nonce, id: q.id, q: strip(q.q), choices: q.choices.map(strip), answer: q.answer, mine, exp: strip(q.exp), extra: extra || "" });
      S.aiQ = { id: q.id, nonce };
    }
    const strip = h => String(h || "").replace(/<br\s*\/?>/g, "\n").replace(/<\/(tr|p|li|pre|div)>/g, "\n").replace(/<\/t[dh]>/g, " | ").replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
    const aiFor = id => S.ai && S.ai.id === id ? S.ai : null;
    const aiHtml = t => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");

    // ---- 用語カード ----
    function startCards(scope) {
      S.cardScope = scope;
      let list = scope === "all" ? TERMS : scope === "unknown" ? TERMS.filter(t => !L.known[t.term]) : TERMS.filter(t => (t.cat || "")[0] === scope || t.cat === scope);
      if (!list.length) { toast("カードがありません"); return; }
      S.cards = { list: shuffle(list), i: 0, flip: false, know: 0, again: 0 };
      S.view = "cards"; top();
    }
    function cardMark(know) {
      const c = S.cards, t = c.list[c.i];
      if (know) { L.known[t.term] = 1; c.know++; } else { delete L.known[t.term]; c.again++; }
      persist();
      if (c.i < c.list.length - 1) { c.i++; c.flip = false; } else { toast(`おわり！ 覚えた ${c.know}・もう一度 ${c.again}`); S.view = "cardsHome"; }
    }
    const knownCount = computed(() => { void S.tick; return Object.keys(L.known).length; });

    // ---- Streamlit から ----
    Streamlit.ready(args => {
      S.user = args.user || "";
      if (args.stats) S.server = args.stats;
      if (args.sessions) S.serverSessions = args.sessions;
      if (args.ai && args.ai.nonce && (!S.aiQ || args.ai.nonce === S.aiQ.nonce)) { S.ai = args.ai; S.aiWait = ""; }
      S.tick++;
    });

    function goView(v) { S.view = v; S.lessonCat = ""; top(); }
    const fieldOf = cat => FIELDS[cat[0]];
    const lessonOf = cat => LESSON[cat];
    const termsOf = cat => TERMS.filter(t => t.cat === cat);
    const qCount = cat => Q.filter(q => q.cat === cat).length;
    function openLesson(cat) { S.lessonCat = cat; S.view = "lesson"; top(); }
    const lessonIdx = computed(() => CATS.findIndex(c => c.id === S.lessonCat));

    return { S, L, FIELDS, CATS, CAT, KANA, Q, QID, EXAMS, PASS_TOTAL, GROUP, TERMS, pct, fmtTime, stat, catStat, fieldStat, allStat, weakIds, flagIds, sessions, examSessions, weakCats, daysLeft,
      startDrill, startFromSetup, drillCat, startExam, resumeExam, isExam, remain, cur, choose, go, next, toggleFlag, toggleMark, finishAsk, finishRun, quitRun, reviewIds, retryWrong, openReview,
      askAI, aiFor, aiHtml, startCards, cardMark, knownCount, goView, fieldOf, lessonOf, termsOf, qCount, openLesson, lessonIdx };
  },
  template: `
<div class="wrap">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <!-- ===== ホーム ===== -->
  <template v-if="S.view === 'home'">
    <div class="hero">
      <div class="hero-t"><span class="logo">FE</span><div><b>基本情報技術者</b><small>科目A・科目B 対応・オリジナル問題 {{ Q.length }}問</small></div></div>
      <div class="dday" v-if="daysLeft !== null"><small>試験まで</small><b>{{ daysLeft >= 0 ? daysLeft : '—' }}</b><small>日</small></div>
    </div>
    <div v-if="L.exam" class="card resume" @click="resumeExam">
      <div><b>とちゅうの{{ L.exam.title }}</b><small>{{ Object.keys(L.exam.answers || {}).length }} / {{ L.exam.ids.length }}問 回答ずみ・のこり {{ fmtTime(L.exam.limit - (Date.now() - L.exam.start) / 1000) }}</small></div><span class="go">続ける ›</span>
    </div>
    <div class="card prog">
      <div class="prog-top"><div><small>正答率</small><b>{{ allStat.n ? pct(allStat.c, allStat.n) + '%' : '—' }}</b></div><div><small>解いた問題</small><b>{{ allStat.seen }}<i>/{{ allStat.total }}</i></b></div><div><small>苦手</small><b>{{ weakIds.length }}<i>問</i></b></div></div>
      <div v-for="(f, k) in FIELDS" :key="k" class="fbar">
        <span class="fname" :style="{ color: f.color }">{{ f.short }}</span>
        <div class="bar"><i :style="{ width: (fieldStat[k].total ? fieldStat[k].seen / fieldStat[k].total * 100 : 0) + '%', background: f.color }"></i></div>
        <span class="fval">{{ fieldStat[k].n ? pct(fieldStat[k].c, fieldStat[k].n) + '%' : '—' }}</span>
      </div>
      <small class="muted">バー＝解いた割合　右＝正答率</small>
    </div>
    <div class="menu">
      <button class="mi big ex" @click="startExam('A')"><span class="ic">🎯</span><b>科目A 模試</b><small>60問・90分・合否判定（600点）</small></button>
      <button class="mi big exb" @click="startExam('B')"><span class="ic">🧩</span><b>科目B 模試</b><small>20問・100分（アルゴリズム16問・セキュリティ4問）</small></button>
      <button class="mi" @click="startExam('miniA')"><span class="ic">⏱️</span><b>科目A ミニ</b><small>20問・30分</small></button>
      <button class="mi" @click="startExam('miniB')"><span class="ic">⏱️</span><b>科目B ミニ</b><small>5問・25分</small></button>
      <button class="mi" @click="goView('learn')"><span class="ic">📖</span><b>学ぶ</b><small>分野ごとの解説</small></button>
      <button class="mi" @click="goView('setup')"><span class="ic">✏️</span><b>問題演習</b><small>1問ずつ解説つき</small></button>
      <button class="mi" @click="S.setup.scope = 'weak'; S.setup.n = 20; startFromSetup()" :disabled="!weakIds.length"><span class="ic">🔁</span><b>苦手を解く</b><small>{{ weakIds.length }}問</small></button>
      <button class="mi" @click="goView('cardsHome')"><span class="ic">🃏</span><b>用語カード</b><small>{{ knownCount }} / {{ TERMS.length }}語 覚えた</small></button>
      <button class="mi" @click="S.setup.scope = 'flag'; S.setup.n = 'all'; startFromSetup()" :disabled="!flagIds.length"><span class="ic">⭐</span><b>見直し</b><small>★をつけた {{ flagIds.length }}問</small></button>
      <button class="mi" @click="goView('stats')"><span class="ic">📊</span><b>成績</b><small>模試の記録・苦手分野</small></button>
    </div>
    <div class="card" v-if="weakCats.length">
      <div class="h3">苦手な分野</div>
      <button v-for="c in weakCats" :key="c.id" class="row" @click="drillCat(c.id)"><span class="tag" :style="{ background: FIELDS[c.f].color }">{{ c.id }}</span><span class="grow">{{ c.name }}</span><b>{{ pct(c.s.c, c.s.n) }}%</b><span class="go">解く ›</span></button>
    </div>
    <div class="card small">
      <div class="h3">試験日</div>
      <input type="date" v-model="S.examDate" class="date"> <span class="muted">（入れると、ホームに「試験まで◯日」が出ます）</span>
    </div>
    <div class="card small muted">
      <b>科目A</b>：四肢択一 60問／90分（テクノロジ系 約41問・マネジメント系 約7問・ストラテジ系 約12問）。<br>
      <b>科目B</b>：多肢選択 20問／100分（アルゴリズムとプログラミング 16問〔擬似言語〕・情報セキュリティ 4問）。<br>
      <b>合格基準</b>：科目A・科目Bともに 600点以上（1000点満点）。<br>
      本番はIRT（問題の難しさで重みが変わる）で採点されます。このアプリの点数は「正答率×1000」の目安です。
    </div>
  </template>

  <!-- ===== 学ぶ ===== -->
  <template v-else-if="S.view === 'learn'">
    <div class="bar-top"><button class="back" @click="goView('home')">‹ ホーム</button><b>学ぶ</b><span></span></div>
    <div class="seg"><button v-for="(f, k) in FIELDS" :key="k" :class="{ on: S.learnField === k }" :style="S.learnField === k ? { background: f.color } : {}" @click="S.learnField = k">{{ f.short }}</button></div>
    <div class="list">
      <button v-for="c in CATS.filter(c => c.f === S.learnField)" :key="c.id" class="lrow" @click="openLesson(c.id)">
        <span class="tag" :style="{ background: FIELDS[c.f].color }">{{ c.id }}</span>
        <span class="grow"><b>{{ c.name }}</b><small>{{ qCount(c.id) }}問・用語 {{ termsOf(c.id).length }}語{{ catStat[c.id].n ? '・正答率 ' + pct(catStat[c.id].c, catStat[c.id].n) + '%' : '' }}</small></span>
        <span class="ring" :style="{ '--p': (catStat[c.id].total ? catStat[c.id].seen / catStat[c.id].total * 100 : 0) + '%', '--c': FIELDS[c.f].color }"></span>
      </button>
    </div>
  </template>

  <template v-else-if="S.view === 'lesson'">
    <div class="bar-top"><button class="back" @click="S.view = 'learn'; S.lessonCat = ''">‹ 一覧</button><b>{{ CAT[S.lessonCat].name }}</b><span></span></div>
    <template v-if="lessonOf(S.lessonCat)">
      <div class="card lesson-head" :style="{ borderTopColor: fieldOf(S.lessonCat).color }">
        <small :style="{ color: fieldOf(S.lessonCat).color }">{{ fieldOf(S.lessonCat).name }}・{{ S.lessonCat }}</small>
        <h2>{{ CAT[S.lessonCat].name }}</h2><p>{{ lessonOf(S.lessonCat).summary }}</p>
      </div>
      <div v-for="(s, i) in lessonOf(S.lessonCat).sections" :key="i" class="card sec"><h3>{{ s.h }}</h3><div class="rich" v-html="s.body"></div></div>
      <div class="card tips" v-if="(lessonOf(S.lessonCat).tips || []).length"><h3>試験のツボ</h3><ul><li v-for="(t, i) in lessonOf(S.lessonCat).tips" :key="i" v-html="t"></li></ul></div>
      <div class="card" v-if="termsOf(S.lessonCat).length"><h3>重要用語</h3>
        <div v-for="t in termsOf(S.lessonCat)" :key="t.term" class="term"><b>{{ t.term }}</b><small v-if="t.yomi">{{ t.yomi }}</small><p>{{ t.def }}</p></div></div>
    </template>
    <div v-else class="card muted">この分野の解説はまだありません</div>
    <div class="btns sticky"><button class="btn" @click="lessonIdx > 0 && openLesson(CATS[lessonIdx - 1].id)" :disabled="lessonIdx <= 0">‹ 前</button><button class="btn pri" @click="drillCat(S.lessonCat)">この分野を10問解く</button><button class="btn" @click="lessonIdx < CATS.length - 1 && openLesson(CATS[lessonIdx + 1].id)" :disabled="lessonIdx >= CATS.length - 1">次 ›</button></div>
  </template>

  <!-- ===== 演習の設定 ===== -->
  <template v-else-if="S.view === 'setup'">
    <div class="bar-top"><button class="back" @click="goView('home')">‹ ホーム</button><b>問題演習</b><span></span></div>
    <div class="card">
      <div class="h3">範囲</div>
      <div class="chips">
        <button v-for="o in [['cat','分野をえらぶ'],['field','大分類'],['all','全分野'],['new','まだ解いていない'],['weak','苦手'],['flag','★見直し']]" :key="o[0]" class="chip" :class="{ on: S.setup.scope === o[0] }" @click="S.setup.scope = o[0]">{{ o[1] }}</button>
      </div>
      <div v-if="S.setup.scope === 'field'" class="chips" style="margin-top:10px"><button v-for="(f, k) in FIELDS" :key="k" class="chip" :class="{ on: S.setup.f === k }" @click="S.setup.f = k">{{ f.name }}</button></div>
      <div v-if="S.setup.scope === 'cat'" class="catgrid">
        <template v-for="(f, k) in FIELDS" :key="k"><div class="cg-h" :style="{ color: f.color }">{{ f.name }}</div>
          <button v-for="c in CATS.filter(c => c.f === k)" :key="c.id" class="cg" :class="{ on: S.setup.cat === c.id }" :style="S.setup.cat === c.id ? { background: f.color, borderColor: f.color } : {}" @click="S.setup.cat = c.id">{{ c.name }}<small>{{ catStat[c.id].n ? pct(catStat[c.id].c, catStat[c.id].n) + '%' : qCount(c.id) + '問' }}</small></button>
        </template>
      </div>
    </div>
    <div class="card">
      <div class="h3">問題数</div>
      <div class="chips"><button v-for="n in [5, 10, 20, 30, 'all']" :key="n" class="chip" :class="{ on: S.setup.n === n }" @click="S.setup.n = n">{{ n === 'all' ? 'ぜんぶ' : n + '問' }}</button></div>
      <div class="h3" style="margin-top:14px">出す順番</div>
      <div class="chips"><button v-for="o in [['smart','おすすめ（未回答・まちがい優先）'],['random','ランダム']]" :key="o[0]" class="chip" :class="{ on: S.setup.order === o[0] }" @click="S.setup.order = o[0]">{{ o[1] }}</button></div>
    </div>
    <button class="btn pri wide" @click="startFromSetup">はじめる</button>
  </template>

  <!-- ===== 問題（演習・模試） ===== -->
  <template v-else-if="(S.view === 'run' || S.view === 'review') && S.run && cur">
    <div class="bar-top run-top">
      <button class="back" @click="S.view === 'review' ? (S.view = 'result') : quitRun()">{{ S.view === 'review' ? '‹ 結果' : (isExam ? '中断' : '‹ やめる') }}</button>
      <b>{{ S.run.i + 1 }}<i>/{{ S.run.ids.length }}</i></b>
      <span v-if="isExam && S.view === 'run'" class="timer" :class="{ low: remain < 600 }">⏱ {{ fmtTime(remain) }}</span>
      <button v-else class="star" :class="{ on: L.flags[cur.id] }" @click="toggleFlag(cur.id)">{{ L.flags[cur.id] ? '★' : '☆' }}</button>
    </div>
    <div class="pbar"><i :style="{ width: ((S.run.i + 1) / S.run.ids.length * 100) + '%' }"></i></div>
    <div class="card qcard">
      <div class="qmeta"><span class="tag" :style="{ background: fieldOf(cur.cat).color }">{{ fieldOf(cur.cat).short }}</span><span>{{ CAT[cur.cat].name }}</span><span class="muted">{{ cur.topic }}</span>
        <span class="lv">{{ '●'.repeat(cur.level || 2) }}{{ '○'.repeat(3 - (cur.level || 2)) }}</span></div>
      <div class="qtext rich" v-html="cur.q"></div>
    </div>
    <div class="choices">
      <button v-for="(c, k) in cur.choices" :key="k" class="ch"
        :class="{ sel: S.run.answers[cur.id] === k, ok: (S.run.checked[cur.id] || S.view === 'review') && k === cur.answer, ng: (S.run.checked[cur.id] || S.view === 'review') && S.run.answers[cur.id] === k && k !== cur.answer }"
        @click="S.view === 'run' && choose(k)"><span class="kana">{{ KANA[k] }}</span><span class="rich" v-html="c"></span></button>
    </div>

    <!-- 解説（演習は答えたあと・結果から開いたとき） -->
    <div v-if="S.run.checked[cur.id] || S.view === 'review'" class="card fb" :class="S.run.answers[cur.id] === cur.answer ? 'good' : 'bad'">
      <div class="fb-h">{{ S.run.answers[cur.id] == null ? '未回答' : S.run.answers[cur.id] === cur.answer ? '正解！' : '不正解' }}<span>正解は <b>{{ KANA[cur.answer] }}</b></span></div>
      <div class="rich exp" v-html="cur.exp"></div>
      <div class="why"><div v-for="(w, k) in cur.why || []" :key="k" class="w" :class="{ right: k === cur.answer }"><span class="kana">{{ KANA[k] }}</span><span class="rich" v-html="w"></span></div></div>
      <div class="tlist" v-if="(cur.terms || []).length"><span v-for="t in cur.terms" :key="t" class="tchip">{{ t }}</span></div>
      <div class="ai">
        <button v-if="!aiFor(cur.id)" class="btn ghost" :disabled="S.aiWait === cur.id" @click="askAI(cur)">{{ S.aiWait === cur.id ? 'AIが考えています…' : '🤖 AIにもっとくわしく聞く' }}</button>
        <div v-else class="aians"><div class="ai-h">🤖 AIの解説</div><div v-html="aiHtml(aiFor(cur.id).text)"></div>
          <button class="btn ghost small" :disabled="S.aiWait === cur.id" @click="askAI(cur, '別の例えや覚え方でもう一度')">{{ S.aiWait === cur.id ? '考えています…' : '別の説明を聞く' }}</button></div>
      </div>
      <div class="btns"><button class="btn" @click="go(S.run.i - 1)" :disabled="S.run.i === 0">‹ 前</button>
        <button v-if="S.view === 'run'" class="btn pri" @click="next">{{ S.run.i < S.run.ids.length - 1 ? '次の問題 ›' : '結果を見る' }}</button>
        <button v-else class="btn pri" @click="S.run.i < S.run.ids.length - 1 ? go(S.run.i + 1) : (S.view = 'result')">{{ S.run.i < S.run.ids.length - 1 ? '次 ›' : '結果へ' }}</button></div>
    </div>

    <!-- 模試の操作 -->
    <template v-if="isExam && S.view === 'run'">
      <div class="btns"><button class="btn" @click="go(S.run.i - 1)" :disabled="S.run.i === 0">‹ 前</button>
        <button class="btn mark" :class="{ on: S.run.flags[cur.id] }" @click="toggleMark(cur.id)">{{ S.run.flags[cur.id] ? '🚩 見直しマーク' : '🏳 見直す' }}</button>
        <button class="btn pri" @click="S.run.i < S.run.ids.length - 1 ? go(S.run.i + 1) : finishAsk()">{{ S.run.i < S.run.ids.length - 1 ? '次 ›' : '採点へ' }}</button></div>
      <div class="card navgrid">
        <div class="h3">問題一覧<small class="muted">（押すとその問題へ）</small></div>
        <div class="grid"><button v-for="(id, i) in S.run.ids" :key="id" class="nb" :class="{ cur: i === S.run.i, done: S.run.answers[id] != null, mk: S.run.flags[id] }" @click="go(i)">{{ i + 1 }}</button></div>
        <button class="btn pri wide" style="margin-top:12px" @click="finishAsk">採点する</button>
      </div>
    </template>
    <div v-if="!isExam && S.view === 'run' && !S.run.checked[cur.id]" class="muted small center">選ぶと、すぐに答えと解説が出ます</div>
  </template>

  <!-- ===== 結果 ===== -->
  <template v-else-if="S.view === 'result' && S.run && S.run.result">
    <div class="bar-top"><button class="back" @click="S.run = null; goView('home')">‹ ホーム</button><b>結果</b><span></span></div>
    <div class="card score" :class="S.run.result.pass === true ? 'pass' : S.run.result.pass === false ? 'fail' : ''">
      <small>{{ S.run.title }}{{ S.run.result.timeUp ? '（時間切れ）' : '' }}</small>
      <template v-if="S.run.result.pass !== null"><div class="verdict">{{ S.run.result.pass ? '合格ライン' : 'あと少し' }}</div>
        <div class="total"><b>{{ S.run.result.total }}</b><i>/1000</i></div></template>
      <div v-else class="total"><b>{{ S.run.result.c }}</b><i>/{{ S.run.result.n }}問 正解</i></div>
      <div class="sub">{{ S.run.result.c }} / {{ S.run.result.n }}問 正解・{{ fmtTime(S.run.result.secs) }}</div>
    </div>
    <div class="card" v-if="S.run.result.pass !== null">
      <div v-for="k in S.run.result.groups" :key="k" class="fscore">
        <span :style="{ color: GROUP[k][1] }">{{ GROUP[k][0] }}</span>
        <div class="bar"><i :style="{ width: (S.run.result.fieldScore[k] || 0) / 10 + '%', background: GROUP[k][1] }"></i><em style="left:60%"></em></div>
        <b>{{ S.run.result.fieldScore[k] ?? '—' }}</b><small>{{ S.run.result.per[k][0] }}/{{ S.run.result.per[k][1] }}</small>
      </div>
      <small class="muted">合格の目安：600点以上（線の位置）。分野ごとの基準点はありません</small>
    </div>
    <div class="btns"><button class="btn" @click="retryWrong">まちがいをもう一度</button><button class="btn pri" @click="S.run = null; goView('home')">ホームへ</button></div>
    <div class="card">
      <div class="h3">ふり返り</div>
      <div class="chips"><button v-for="o in [['wrong','まちがい'],['all','ぜんぶ'],['mark','見直しマーク']]" :key="o[0]" class="chip" :class="{ on: S.reviewFilter === o[0] }" @click="S.reviewFilter = o[0]">{{ o[1] }}</button></div>
      <div v-if="!reviewIds.length" class="muted small" style="padding:10px 2px">ありません</div>
      <button v-for="id in reviewIds" :key="id" class="rv" @click="openReview(id)">
        <span class="mk" :class="S.run.answers[id] === QID[id].answer ? 'o' : 'x'">{{ S.run.answers[id] === QID[id].answer ? '○' : S.run.answers[id] == null ? '−' : '×' }}</span>
        <span class="grow"><small>{{ S.run.ids.indexOf(id) + 1 }}. {{ CAT[QID[id].cat].name }}・{{ QID[id].topic }}</small><span class="qs" v-html="QID[id].q"></span></span><span class="go">›</span>
      </button>
    </div>
  </template>

  <!-- ===== 用語カード ===== -->
  <template v-else-if="S.view === 'cardsHome'">
    <div class="bar-top"><button class="back" @click="goView('home')">‹ ホーム</button><b>用語カード</b><span></span></div>
    <div class="card"><div class="h3">どのカードで練習する？</div>
      <button class="row" @click="startCards('unknown')"><span class="grow"><b>まだ覚えていない用語</b></span><b>{{ TERMS.length - knownCount }}語</b><span class="go">›</span></button>
      <button class="row" @click="startCards('all')"><span class="grow"><b>ぜんぶ</b></span><b>{{ TERMS.length }}語</b><span class="go">›</span></button>
      <button v-for="(f, k) in FIELDS" :key="k" class="row" @click="startCards(k)"><span class="tag" :style="{ background: f.color }">{{ k }}</span><span class="grow">{{ f.name }}</span><b>{{ TERMS.filter(t => (t.cat || '')[0] === k).length }}語</b><span class="go">›</span></button>
    </div>
    <div class="muted small center">カードを押すと意味が出ます。「覚えた」「もう一度」で進みます</div>
  </template>
  <template v-else-if="S.view === 'cards' && S.cards">
    <div class="bar-top"><button class="back" @click="S.view = 'cardsHome'">‹ もどる</button><b>{{ S.cards.i + 1 }}<i>/{{ S.cards.list.length }}</i></b><span></span></div>
    <div class="flash" :class="{ flip: S.cards.flip }" @click="S.cards.flip = !S.cards.flip">
      <div class="face front"><small>{{ (CAT[S.cards.list[S.cards.i].cat] || {}).name }}</small><b>{{ S.cards.list[S.cards.i].term }}</b><i v-if="S.cards.list[S.cards.i].yomi">{{ S.cards.list[S.cards.i].yomi }}</i><span class="hint">タップで意味</span></div>
      <div class="face back"><b>{{ S.cards.list[S.cards.i].term }}</b><p>{{ S.cards.list[S.cards.i].def }}</p></div>
    </div>
    <div class="btns"><button class="btn" @click="cardMark(false)">もう一度</button><button class="btn pri" @click="cardMark(true)">覚えた</button></div>
  </template>

  <!-- ===== 成績 ===== -->
  <template v-else-if="S.view === 'stats'">
    <div class="bar-top"><button class="back" @click="goView('home')">‹ ホーム</button><b>成績</b><span></span></div>
    <div class="card"><div class="h3">模試の記録</div>
      <div v-if="!examSessions.length" class="muted small">まだありません</div>
      <div v-for="s in examSessions.slice(0, 20)" :key="s.key" class="srow">
        <span class="grow"><b>{{ s.title || (EXAMS[s.mode] || {}).name }}</b><small>{{ s.date }}</small></span>
        <span class="pill" :class="s.pass ? 'p' : 'f'">{{ s.pass ? '合格ライン' : '不合格ライン' }}</span><b class="big">{{ s.total }}</b>
      </div>
    </div>
    <div class="card"><div class="h3">分野ごとの正答率</div>
      <template v-for="(f, k) in FIELDS" :key="k"><div class="cg-h" :style="{ color: f.color }">{{ f.name }}</div>
        <button v-for="c in CATS.filter(c => c.f === k)" :key="c.id" class="srow cat" @click="drillCat(c.id)">
          <span class="grow">{{ c.name }}<small>{{ catStat[c.id].seen }}/{{ catStat[c.id].total }}問 解いた</small></span>
          <div class="bar mini"><i :style="{ width: (catStat[c.id].n ? catStat[c.id].c / catStat[c.id].n * 100 : 0) + '%', background: f.color }"></i></div>
          <b>{{ catStat[c.id].n ? pct(catStat[c.id].c, catStat[c.id].n) + '%' : '—' }}</b></button>
      </template>
    </div>
  </template>

  <div v-if="S.confirm" class="modal" @click.self="S.confirm = null"><div class="sheet">
    <div class="msg" v-html="S.confirm.msg"></div>
    <div class="btns"><button class="btn" @click="S.confirm.no ? (S.confirm.no(), S.confirm = null) : (S.confirm = null)">{{ S.confirm.cancel || 'やめる' }}</button><button class="btn pri" @click="S.confirm.fn(); S.confirm = null">{{ S.confirm.ok }}</button></div>
  </div></div>
</div>`,
});
app.mount("#app");
