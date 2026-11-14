/* 算数・数学マスター（画面はぜんぶ JavaScript）。
   問題作りと答え合わせは Python（math_units.py・math_check.py）。ここは画面と動きだけ。
   Python へ送るもの（nonce つき）：
     start（10問ほしい）・check（答え合わせ）・ai（AI先生の解説）・learned（学んだ ✓）・example（数字を変えた例題）
   Python から来るもの：args（単元の一覧・学ぶの教材・学んだ ✓・ベスト）と reply（送ったものへの返事） */
"use strict";
const { createApp, reactive, computed, nextTick } = Vue;
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MIX = "__mix__";
const TOTAL = 10;

// $...$（文の中）と $$...$$（1行）を KaTeX で。ほかの文字はそのまま（改行は <br>）
function tex(src) {
  const s = String(src ?? "");
  let out = "", i = 0;
  while (i < s.length) {
    const dd = s.startsWith("$$", i), d = !dd && s[i] === "$";
    if (dd || d) {
      const mark = dd ? "$$" : "$", end = s.indexOf(mark, i + mark.length);
      if (end > i) {
        const body = s.slice(i + mark.length, end);
        try { out += katex.renderToString(body, { displayMode: dd, throwOnError: false, strict: false }); }
        catch (e) { out += esc(body); }
        i = end + mark.length;
        continue;
      }
    }
    const next = s.slice(i).search(/\$/);
    const chunk = next < 0 ? s.slice(i) : s.slice(i, i + (next || 1));
    out += esc(chunk).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/\n/g, "<br>");
    i += chunk.length;
  }
  return out;
}

// 答えの入力を助けるボタン（スマホのキーボードで打ちにくい記号）
const KEYS = ["√", "π", "²", "/", "±", "(", ")", "≧", "≦", ",", "x", "="];

createApp({
  setup() {
    const L = (() => { try { return JSON.parse(sessionStorage.getItem("calc_v1") || "{}"); } catch (e) { return {}; } })();
    const S = reactive({
      ready: false, args: {},
      tab: L.tab || "practice",           // practice（練習問題）・learn（学ぶ）
      view: "home",                       // home・lesson・play・result
      grade: L.grade || "", course: L.course || "", unit: L.unit || MIX,
      lesson: "", open: {},                // 学ぶ：開いている単元
      set: null, answers: [], blankAsk: 0, // 問題（Python から）と、入れた答え
      result: null, ai: null, aiWait: false,
      focus: -1, howto: false, all: false, toast: "",
      examples: {}, exWait: "", busy: "",
    });
    const keep = () => { try { sessionStorage.setItem("calc_v1", JSON.stringify({ tab: S.tab, grade: S.grade, course: S.course, unit: S.unit })); } catch (e) {} };

    // ---- Python とのやりとり ----
    const waits = {};                      // nonce → 返事が来たらすること
    function ask(v, then) { const nonce = uid(); waits[nonce] = then; Streamlit.setValue({ ...v, nonce }); }
    let lastReply = "";
    function onArgs(a) {
      S.args = a; S.ready = true;
      const r = a.reply;
      if (r && r.nonce && r.nonce !== lastReply) { lastReply = r.nonce; const f = waits[r.nonce]; delete waits[r.nonce]; if (f) f(r); }
      if (!S.grade || !C.value.grades.includes(S.grade)) S.grade = me.value.grade || "小3";
      fixCourse();
    }
    const C = computed(() => S.args.cat || { grades: [], gradeNames: {}, courses: {}, unitNames: {}, byGrade: {} });
    const me = computed(() => S.args.me || { grade: "小3", canPick: true, band: "小" });
    const learned = computed(() => new Set(S.args.learned || []));
    const bestOf = (g, c, u) => (S.args.best || {})[`${g}|${c}|${u}`];

    // ---- 練習問題のえらび方 ----
    const courses = computed(() => (C.value.byGrade[S.grade] || {}).courses || []);
    function fixCourse() { if (!courses.value.includes(S.course)) S.course = courses.value[0] || ""; }
    const units = computed(() => ((C.value.byGrade[S.grade] || {}).units || {})[S.course] || []);
    const nowUnits = computed(() => ((C.value.byGrade[S.grade] || {}).now || {})[S.course] || []);
    const unitName = u => u === MIX ? "いろいろ（まとめ）" : (C.value.unitNames[u] || u);
    const doneCount = computed(() => units.value.filter(u => learned.value.has(u)).length);
    function pickGrade(g) { S.grade = g; fixCourse(); S.unit = MIX; keep(); }
    function pickCourse(c) { S.course = c; S.unit = MIX; keep(); }
    function pickUnit(u) { S.unit = u; keep(); }

    // ---- 10問 ----
    function start(g, c, u) {
      if (g) { S.grade = g; S.course = c; S.unit = u; keep(); }
      S.busy = "start";
      ask({ type: "start", grade: S.grade, course: S.course, unit: S.unit }, r => {
        S.busy = "";
        if (r.error || !r.questions) { toast(r.error || "うまくいかなかったよ"); return; }
        S.set = { id: r.id, grade: S.grade, course: S.course, unit: S.unit, questions: r.questions };
        S.answers = r.questions.map(() => ""); S.blankAsk = 0; S.result = null; S.ai = null; S.focus = -1;
        S.view = "play"; top();
      });
    }
    const filled = computed(() => S.answers.filter(a => String(a).trim()).length);
    function submit(force) {
      const blanks = S.answers.length - filled.value;
      if (blanks && !force) { S.blankAsk = blanks; nextTick(() => { const el = document.querySelector(".blank"); if (el) el.scrollIntoView({ block: "center", behavior: "smooth" }); }); return; }
      S.blankAsk = 0; S.busy = "check"; S.result = null; S.ai = null;
      S.view = "result"; top();
      const set = S.set;
      ask({ type: "check", id: set.id, answers: S.answers.map(a => String(a)) }, r => {
        S.busy = "";
        if (r.error || !r.rows) { toast(r.error || "うまくいかなかったよ"); S.view = "play"; return; }
        S.result = r;
        if (r.score === 100) party();
        if (r.wrong && r.wrong.length) {          // まちがえた問題があれば、AI先生の解説をたのむ（答えは先に見せる）
          S.aiWait = true;
          ask({ type: "ai", id: set.id }, x => { S.aiWait = false; S.ai = x.notes || null; });
        }
      });
    }
    // 答えの入力：Enter で次の問題へ（変換の確定の Enter はそのまま）
    function onKey(e, i) {
      if (e.key !== "Enter" || e.isComposing || e.keyCode === 229) return;
      e.preventDefault();
      const next = document.querySelector(`[data-ans="${i + 1}"]`);
      if (next) { next.focus(); next.scrollIntoView({ block: "center", behavior: "smooth" }); } else e.target.blur();
    }
    function insert(i, k) {
      const el = document.querySelector(`[data-ans="${i}"]`); if (!el) return;
      const a = el.selectionStart ?? el.value.length, b = el.selectionEnd ?? a;
      const add = k === "√" ? "√" : k;
      S.answers[i] = el.value.slice(0, a) + add + el.value.slice(b);
      nextTick(() => { el.focus(); const p = a + add.length; try { el.setSelectionRange(p, p); } catch (e) {} });
    }
    let blurT = 0;
    const onFocus = i => { clearTimeout(blurT); S.focus = i; };
    const onBlur = () => { blurT = setTimeout(() => S.focus = -1, 150); };

    // ---- 学ぶ ----
    const order = computed(() => S.args.order || []);            // [見出し, 学年, 科目, 単元]
    const lessons = computed(() => S.args.lessons || {});
    const heads = computed(() => {
      const out = [];
      order.value.forEach((it, n) => {
        let h = out[out.length - 1];
        if (!h || h.head !== it[0]) out.push(h = { head: it[0], items: [] });
        h.items.push({ n: n + 1, head: it[0], grade: it[1], course: it[2], uid: it[3] });
      });
      return out;
    });
    const learnDone = computed(() => order.value.filter(it => learned.value.has(it[3])).length);
    const myHead = computed(() => { const g = { 高3: "高2" }[me.value.grade] || me.value.grade; const it = order.value.find(x => x[1] === g); return it ? it[0] : ""; });
    function openLesson(u) { S.lesson = u; S.view = "lesson"; top(); }
    const lessonAt = computed(() => order.value.findIndex(it => it[3] === S.lesson));
    const lessonItem = computed(() => order.value[lessonAt.value] || null);
    function stepLesson(d) { const it = order.value[lessonAt.value + d]; if (it) openLesson(it[3]); }
    const example = u => S.examples[u] || (S.args.examples || {})[u] || null;
    function moreExample(u) {
      S.exWait = u;
      ask({ type: "example", uid: u }, r => { S.exWait = ""; if (r.ex) S.examples[u] = { ...r.ex, open: true }; });
    }
    function markLearned(it) {
      ask({ type: "learned", uid: it[3], grade: it[1] }, () => toast("✓ 学んだ！ に しました"));
    }
    const showEx = reactive({});

    // ---- 小物 ----
    let toastT = 0;
    function toast(m) { place(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2200); }
    function place() { try { const r = window.frameElement.getBoundingClientRect(); document.documentElement.style.setProperty("--tt", Math.max(0, -r.top) + 10 + "px"); } catch (e) {} }
    function top() { nextTick(() => { window.scrollTo(0, 0); try { window.frameElement && window.frameElement.scrollIntoView({ block: "start" }); } catch (e) {} }); }
    function home(tab) {
      if (tab) { S.tab = tab; keep(); }
      S.view = "home"; top();
      if (S.tab === "learn") toMine();
    }
    function setTab(t) { S.tab = t; keep(); if (t === "learn") toMine(); }
    // 学ぶの目次は、いまの学年のところを見せる
    function toMine() { nextTick(() => { const el = document.querySelector(".headrow.mine"); if (el) el.scrollIntoView({ block: "start" }); }); }
    // 10問のとちゅうで「やめる」：答えを入れていたら、もう一度押したときにやめる
    let quitAt = 0;
    function quit() {
      if (filled.value && Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("入れた答えは消えるよ。もう一度押すと やめます"); return; }
      home();
    }
    function party() {
      const box = document.createElement("div"); box.className = "party";
      try { const r = window.frameElement.getBoundingClientRect(); box.style.top = Math.max(0, -r.top) + "px"; box.style.height = (window.parent.innerHeight || 700) + "px"; } catch (e) {}
      for (let k = 0; k < 40; k++) { const i = document.createElement("i"); i.style.left = Math.random() * 100 + "%"; i.style.animationDelay = Math.random() * .6 + "s"; i.style.background = ["#f2b33d", "#e0577f", "#3a5bd9", "#2db56a", "#9b5de5"][k % 5]; box.appendChild(i); }
      document.body.appendChild(box); setTimeout(() => box.remove(), 2600);
    }
    function openPdf(b64) {             // 表彰状：トップの画面のビューアで開く（common.py の「PDFを見る」と同じしくみ）
      try {
        const doc = window.parent.document, b = doc.createElement("button");
        b.dataset.pdf = b64; b.style.display = "none"; doc.body.appendChild(b); b.click(); b.remove();
      } catch (e) {
        const bin = atob(b64), bytes = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        window.open(URL.createObjectURL(new Blob([bytes], { type: "application/pdf" })), "_blank");
      }
    }
    const hero = computed(() => ({ 小: ["算数マスター", "学年と たんげんを えらんで、10問の チャレンジに ちょうせんしよう！"],
      中: ["数学マスター", "学年と単元を選んで、10問のチャレンジに挑戦しよう！"], 高: ["数学マスター", "科目と単元を選んで、10問の演習に取り組もう。"] }[me.value.band] || ["算数マスター", ""]));

    Streamlit.ready(onArgs);
    return { S, C, me, MIX, TOTAL, KEYS, tex, learned, bestOf, courses, units, nowUnits, unitName, doneCount, pickGrade, pickCourse, pickUnit,
      start, filled, submit, onKey, insert, onFocus, onBlur, heads, lessons, learnDone, myHead, openLesson, lessonAt, lessonItem, stepLesson,
      example, moreExample, markLearned, showEx, home, setTab, quit, openPdf, hero, order };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <!-- ホーム -->
  <template v-if="S.view === 'home'">
    <div class="hero"><div class="hero-t"><div class="logo">∑</div><div><b>{{ hero[0] }}</b><small>{{ hero[1] }}</small></div></div></div>
    <div class="seg two"><button :class="{ on: S.tab === 'practice' }" @click="setTab('practice')">🏁 練習問題</button><button :class="{ on: S.tab === 'learn' }" @click="setTab('learn')">📖 学ぶ</button></div>

    <template v-if="S.tab === 'practice'">
      <div class="card">
        <div class="h3">🎓 学年</div>
        <div v-if="me.canPick" class="chips">
          <button v-for="g in C.grades" :key="g" class="chip" :class="{ on: S.grade === g }" @click="pickGrade(g)">{{ C.gradeNames[g] }}</button>
        </div>
        <div v-else class="small"><b>{{ C.gradeNames[S.grade] }}</b> の問題が出るよ（{{ me.age }}さい）</div>
        <template v-if="courses.length > 1">
          <div class="h3" style="margin-top:12px">📚 科目</div>
          <div class="chips"><button v-for="c in courses" :key="c" class="chip" :class="{ on: S.course === c }" @click="pickCourse(c)">{{ C.courses[c].name }}</button></div>
          <div class="small muted" style="margin-top:4px">{{ (C.courses[S.course] || {}).desc }}</div>
        </template>
        <div v-else-if="S.course" class="small muted" style="margin-top:6px">📚 {{ C.courses[S.course].name }}：{{ C.courses[S.course].desc }}</div>
      </div>
      <div class="h3" style="margin:14px 4px 6px">✏️ 単元<span class="small muted">学んだ単元 {{ doneCount }} / {{ units.length }}（✓）</span></div>
      <div class="list">
        <button v-for="u in [MIX, ...units]" :key="u" class="urow" :class="{ on: S.unit === u }" @click="pickUnit(u)">
          <span class="radio"></span>
          <span class="grow"><b>{{ unitName(u) }}</b><small v-if="u !== MIX && !nowUnits.includes(u)">前の学年のふくしゅう</small><small v-if="u === MIX">この学年の単元を まぜて出すよ</small></span>
          <i v-if="learned.has(u)" class="ok">✓</i>
          <em v-if="bestOf(S.grade, S.course, u) != null" class="best">🏆{{ bestOf(S.grade, S.course, u) }}</em>
        </button>
      </div>
      <button class="big" :disabled="!!S.busy" @click="start()">{{ S.busy === 'start' ? 'つくっています…' : '🏁 ' + TOTAL + '問に挑戦！' }}</button>
    </template>

    <template v-else>
      <div class="card small">📖 学んだ単元：<b>{{ learnDone }} / {{ order.length }}</b>　単元を押すと、説明と例題が見られるよ</div>
      <template v-for="h in heads" :key="h.head">
        <div class="h3 headrow" :class="{ mine: h.head === myHead }">🎓 {{ h.head }}<span v-if="h.head === myHead" class="small">いまの学年</span></div>
        <div class="list">
          <button v-for="it in h.items" :key="it.uid" class="lrow" @click="openLesson(it.uid)">
            <span class="num">{{ it.n }}</span><b class="grow">{{ unitName(it.uid) }}</b><i v-if="learned.has(it.uid)" class="ok">✓</i><span class="chev">›</span>
          </button>
        </div>
      </template>
    </template>
  </template>

  <!-- 学ぶ（1つの単元） -->
  <template v-else-if="S.view === 'lesson' && lessonItem">
    <div class="bar-top"><button class="back" @click="home('learn')">‹ 目次</button><b>{{ lessonItem[0] }}</b><span></span></div>
    <div class="card lesson">
      <div class="lt"><span class="num">{{ lessonAt + 1 }}</span><h2>{{ unitName(S.lesson) }}</h2><i v-if="learned.has(S.lesson)" class="ok big">✓</i></div>
      <p class="intro" v-html="'💡 ' + tex(lessons[S.lesson].intro)"></p>
      <div class="sub">おぼえよう</div>
      <ul class="points"><li v-for="(p, k) in lessons[S.lesson].points" :key="k" v-html="tex(p)"></li></ul>
      <div v-if="lessons[S.lesson].caution" class="caution" v-html="'⚠️ ' + tex(lessons[S.lesson].caution)"></div>
    </div>
    <div class="card">
      <div class="sub">✏️ 例題</div>
      <div class="q" v-html="tex(lessons[S.lesson].example.q)"></div>
      <ol class="steps"><li v-for="(st, k) in lessons[S.lesson].example.steps" :key="k" v-html="tex(st)"></li></ol>
      <div class="ans">👉 答え：<b v-html="tex(lessons[S.lesson].example.answer)"></b></div>
    </div>
    <div class="card" v-if="example(S.lesson)">
      <div class="sub">🔁 数字を変えた例題</div>
      <div class="q" v-html="tex(example(S.lesson).q)"></div>
      <button v-if="!showEx[S.lesson]" class="btn" @click="showEx[S.lesson] = true">答えを見る</button>
      <template v-else>
        <div class="ans">👉 答え：<b>{{ example(S.lesson).show }}</b></div>
        <div class="small muted" style="margin-top:4px" v-html="'📝 ' + tex(example(S.lesson).explain)"></div>
      </template>
      <button class="link" :disabled="S.exWait === S.lesson" @click="showEx[S.lesson] = false; moreExample(S.lesson)">{{ S.exWait === S.lesson ? 'つくっています…' : 'ほかの数字で ›' }}</button>
    </div>
    <div class="row2">
      <button v-if="learned.has(S.lesson)" class="btn done" disabled>✓ 学んだ！</button>
      <button v-else class="btn ok" @click="markLearned(lessonItem)">✅ 学んだ！</button>
      <button class="btn pri" :disabled="!!S.busy" @click="start(lessonItem[1], lessonItem[2], lessonItem[3])">🏁 この単元を練習</button>
    </div>
    <div class="row2" style="margin-top:8px">
      <button class="btn" :disabled="lessonAt <= 0" @click="stepLesson(-1)">‹ 前の単元</button>
      <button class="btn" :disabled="lessonAt >= order.length - 1" @click="stepLesson(1)">次の単元 ›</button>
    </div>
  </template>

  <!-- 10問 -->
  <template v-else-if="S.view === 'play' && S.set">
    <div class="bar-top"><button class="back" @click="quit()">‹ やめる</button><b>{{ C.gradeNames[S.set.grade] }}・{{ unitName(S.set.unit) }}</b><span class="cnt">{{ filled }}/{{ S.set.questions.length }}</span></div>
    <div class="small muted" style="margin:-4px 4px 8px">わからない問題は 空らんのままでも OK。ぜんぶできたら 一番下の「答えあわせ」を押してね。</div>
    <button class="howto-b" @click="S.howto = !S.howto">✍️ 答えの書き方 {{ S.howto ? '▲' : '▼' }}</button>
    <div v-if="S.howto" class="card small howto">
      <div><b>分数</b> 3/4　<b>帯分数</b> 2と1/3　<b>小数</b> 0.25</div>
      <div><b>ルート</b> √3、2√3、√(x+1)（ルートの中は いちばん小さく、分母は有理化）</div>
      <div><b>円周率</b> π　<b>累乗</b> x^2 または x²　<b>かけ算</b> 2x、3(x+1)</div>
      <div><b>答えが2つ</b> x=2, -3 や x=±√3　<b>連立方程式</b> x=1, y=2　<b>座標</b> (2, -3)</div>
      <div><b>不等式</b> x&gt;3、x≧-1/2（&gt;= でもOK）　<b>複素数</b> 3+2i</div>
      <div class="muted">全角で打っても、単位（cm・度・通り など）をつけても OK。下の記号ボタンも使えるよ</div>
    </div>
    <div v-for="(q, i) in S.set.questions" :key="S.set.id + i" class="card qcard" :class="{ filled: String(S.answers[i]).trim() }">
      <div class="qh"><b>問 {{ i + 1 }}</b><small>{{ unitName(q.unit) }}</small></div>
      <div class="q" v-html="tex(q.q)"></div>
      <div v-if="q.hint" class="small muted" v-html="tex(q.hint)"></div>
      <input class="ans-in" :data-ans="i" v-model="S.answers[i]" placeholder="答えを入力" autocomplete="off" autocapitalize="off" spellcheck="false"
        @keydown="onKey($event, i)" @focus="onFocus(i)" @blur="onBlur">
      <div v-if="S.focus === i" class="keys" @mousedown.prevent @touchstart.prevent.stop>
        <button v-for="k in KEYS" :key="k" @mousedown.prevent @touchend.prevent="insert(i, k)" @click="insert(i, k)">{{ k }}</button>
      </div>
    </div>
    <div v-if="S.blankAsk" class="card blank">
      <b>まだ {{ S.blankAsk }}問 空らんだよ。このまま答えあわせしてもいい？</b>
      <div class="row2" style="margin-top:10px"><button class="btn" @click="S.blankAsk = 0">もどって答える</button><button class="btn pri" @click="submit(true)">このまま答えあわせ</button></div>
    </div>
    <button v-else class="big red" @click="submit(false)">🚨 答えあわせをする！</button>
  </template>

  <!-- 結果 -->
  <template v-else-if="S.view === 'result'">
    <div v-if="!S.result" class="card center wait"><div class="spin"></div>答えあわせ中…</div>
    <template v-else>
      <h2 class="center" style="margin-top:6px">🏆 チャレンジ おつかれさま！</h2>
      <div class="card score">
        <div><small>今回の点数</small><b>{{ S.result.score }}</b><i>/ 100点</i></div>
        <div><small>正解</small><b>{{ S.result.correct }}</b><i>/ {{ S.result.n }}問</i></div>
        <div><small>ベスト</small><b>{{ S.result.best }}</b><i>点</i></div>
      </div>
      <div v-if="S.result.newBest" class="note good">🎉 ベストスコア更新！</div>
      <div v-if="S.result.blank" class="small muted center">未入力の問題が {{ S.result.blank }}問 あったよ。</div>
      <div class="note" :class="S.result.score >= 80 ? 'good' : 'warn'">💬 {{ S.result.comment }}</div>
      <button v-if="S.result.pdf" class="btn pdf" @click="openPdf(S.result.pdf)">📄 表彰状を 見る</button>

      <template v-if="S.result.wrong.length">
        <div class="h3" style="margin:16px 4px 8px">👀 まちがえた問題を 見なおそう（{{ S.result.wrong.length }}問）</div>
        <div v-for="(i, n) in S.result.wrong" :key="i" class="card">
          <div class="qh"><b>問 {{ i + 1 }}</b><small>{{ unitName(S.set.questions[i].unit) }}</small></div>
          <div class="q" v-html="tex(S.set.questions[i].q)"></div>
          <div class="cmp"><span>あなたの答え</span><code>{{ S.result.rows[i].user || '（未入力）' }}</code><span>正しい答え</span><b>{{ S.result.rows[i].show }}</b></div>
          <div v-if="S.result.rows[i].note && S.result.rows[i].note !== '（未入力）'" class="small hintline">💡 {{ S.result.rows[i].note }}</div>
          <div v-if="S.ai && S.ai[n]" class="aibox"><b>🤖 AI先生の解説</b><div v-html="tex(S.ai[n])"></div><div class="small muted" v-html="'📝 解き方のポイント：' + tex(S.result.rows[i].explain)"></div></div>
          <div v-else-if="S.aiWait" class="aibox wait"><div class="spin sm"></div>AI先生が 解説を 書いているよ…</div>
          <div v-else class="aibox" v-html="'📝 解き方：' + tex(S.result.rows[i].explain)"></div>
        </div>
      </template>
      <button class="link" style="margin:6px 4px" @click="S.all = !S.all">📊 全部の結果を{{ S.all ? 'とじる' : '見る' }}</button>
      <div v-if="S.all" class="list">
        <div v-for="(r, i) in S.result.rows" :key="i" class="rrow"><span class="mk" :class="r.ok ? 'o' : 'x'">{{ r.ok ? '⭕' : '❌' }}</span>
          <div class="grow"><div class="q sm" v-html="tex(S.set.questions[i].q)"></div><small>あなた：{{ r.user || '（未入力）' }}　正解：{{ r.show }}</small></div></div>
      </div>
      <div class="row2" style="margin-top:14px">
        <button class="btn pri" :disabled="!!S.busy" @click="start(S.set.grade, S.set.course, S.set.unit)">🔁 同じ単元で もう一度</button>
        <button class="btn" @click="home('practice')">🔄 単元を えらびなおす</button>
      </div>
    </template>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
