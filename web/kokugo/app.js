/* AI国語アドベンチャー（画面はぜんぶ JavaScript）。
   漢字の読み書きの答え合わせは、ここでする（kokugo_logic.py の check_reading / check_writing と同じ）。
   Python へ：gen（文章と10問）・essay（作文の採点）・done（記録と表彰状）・ai（AI先生の解説）・learned（学んだ ✓）・lquiz（やってみよう をつくりなおす） */
"use strict";
const { createApp, reactive, computed } = Vue;
const THEMES = ["恐竜", "マインクラフト", "魔法学校", "宇宙飛行士", "ねこ", "サッカー"];
const STAGES = [["小", "小学校"], ["中", "中学校"], ["高", "高校"]];
const GROUP_HEAD = { 読解: "📖 読解のコツ", "文法・表現": "✏️ 文法・表現", "言葉・漢字": "🈶 言葉・漢字", 古典: "📜 古典のミニ講座" };

// ---- 答え合わせ（kokugo_logic.py と同じ） ----
const clean = t => String(t || "").normalize("NFKC").replace(/[\s「」『』（）()【】\[\]、。,.・]/g, "");
const toHira = t => String(t || "").replace(/[ァ-ヶ]/g, c => String.fromCharCode(c.charCodeAt(0) - 0x60));
const hasKanji = t => /[一-鿿々〆ヶ]/.test(t || "");
function checkReading(typed, answers) {
  const t = toHira(clean(typed));
  if (!t) return ["retry", "ひらがなで書いてね。"];
  if (hasKanji(t)) return ["retry", "漢字のままになっているよ。読み方を ひらがなで書いてね。"];
  return (answers || []).some(a => toHira(clean(a)) === t) ? ["ok", ""] : ["ng", ""];
}
function checkWriting(typed, answers, reading) {
  const t = clean(typed);
  if (!t) return ["retry", "漢字で書いてね。"];
  if (!hasKanji(t)) {
    if (reading && toHira(t) === toHira(clean(reading))) return ["retry", "ひらがなのままになっているよ。漢字に変えて書いてね。"];
    return ["retry", "漢字をつかって書いてね。"];
  }
  const goods = (answers || []).map(clean);
  if (goods.includes(t)) return ["ok", ""];
  const skel = s => toHira(s).replace(/[ぁ-ゖ]/g, "");
  for (const g of goods) if (skel(t) === skel(g) && toHira(t) !== toHira(g)) return ["ng", "送りがなが ちがうよ。"];
  return ["ng", ""];
}

createApp({
  setup() {
    const L = Kit.load("jp_v1", {});
    const S = reactive({
      ready: false, args: {}, view: "home", tab: L.tab || "quiz", grade: L.grade || "", course: L.course || "", theme: "",
      busy: false, silly: false, toast: "",
      stage: "", open: {}, item: "", lq: {}, lqAns: {}, lqChecked: {}, lqWait: "", yaku: false,
      play: null, step: 0, ans: null, typed: "", pick: null, retry: "", score: 0, log: [], rows: [], run: "", essayWait: false,
      ai: null, aiWait: false, pdf: "", showYaku: false,
    });
    const keep = () => Kit.save("jp_v1", { tab: S.tab, grade: S.grade, course: S.course });
    const C = computed(() => S.args.cat || { grades: [], gradeNames: {}, byGrade: {}, courses: {}, kindLabels: {}, kindHowto: {}, kindNames: {} });
    const D = computed(() => S.args.learn || { lectures: {}, bySchool: {}, works: {}, workSchool: {}, guides: {}, kindNames: {} });
    const me = computed(() => S.args.me || {});
    const learned = computed(() => new Set(S.args.learned || []));
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.grade || !allowed.value.includes(S.grade)) S.grade = allowed.value.includes(me.value.grade) ? me.value.grade : allowed.value[allowed.value.length - 1];
      fixCourse();
      if (!S.stage) S.stage = "lec";
    }
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2800); }
    const allowed = computed(() => { const gs = C.value.grades, m = me.value.maxGrade, k = gs.indexOf(m); return m && k >= 0 ? gs.slice(0, k + 1) : gs; });
    const gradeRows = computed(() => STAGES.map(([k, name]) => ({ k, name, grades: allowed.value.filter(g => g[0] === k) })).filter(r => r.grades.length));
    const courses = computed(() => C.value.byGrade[S.grade] || []);
    function fixCourse() { if (!courses.value.includes(S.course)) S.course = courses.value[0] || ""; }
    function pickGrade(g) { S.grade = g; fixCourse(); keep(); }
    const school = computed(() => S.grade[0] || "小");

    // ---- 問題にちょうせん ----
    function gen(extra) {
      S.busy = true; S.silly = false; keep();
      Kit.ask({ type: "gen", grade: S.grade, course: S.course, theme: S.theme, ...extra }, r => {
        S.busy = false;
        if (r.silly) { S.silly = true; S.view = "home"; S.tab = "quiz"; Kit.top(); return; }
        if (r.error || !r.quiz) { toast(r.error || "うまく作れなかったよ。もう一度ためしてね"); return; }
        begin({ quiz: r.quiz, theme: r.theme, grade: r.grade, course: r.course, passage: r.passage });
      });
    }
    function begin(play) {
      S.play = play; S.step = 0; S.ans = null; S.typed = ""; S.pick = null; S.retry = ""; S.score = 0; S.log = []; S.rows = [];
      S.run = Kit.uid(); S.ai = null; S.aiWait = false; S.pdf = ""; S.showYaku = false;
      S.view = "play"; Kit.top();
    }
    function again() {
      const quiz = JSON.parse(JSON.stringify(S.play.quiz));
      quiz.questions.forEach(q => { if (q.opts) q.opts = Kit.shuffle(q.opts); });
      begin({ ...S.play, quiz });
    }
    const qs = computed(() => (S.play && S.play.quiz.questions) || []);
    const q = computed(() => qs.value[S.step] || {});
    const chapter = computed(() => q.value.section != null ? (S.play.quiz.chapters || [])[q.value.section] : null);
    const passage = computed(() => S.play && S.play.passage);
    const correctText = x => ["text", "classic"].includes(x.kind) ? x.ans : x.kind === "essay" ? "（AIの採点）" : (x.answers || []).join("／");
    function record(typed, ok, note, points) {
      S.ans = { typed, ok, note: note || "", points: points ?? (ok ? (C.value.point || 10) : 0) }; S.retry = "";
    }
    function decideChoice() { if (S.pick != null) record(S.pick, S.pick === q.value.ans); }
    function decideText() {
      const [res, note] = ["read", "kana"].includes(q.value.kind) ? checkReading(S.typed, q.value.answers) : checkWriting(S.typed, q.value.answers, q.value.reading || "");
      if (res === "retry") { S.retry = "✏️ " + note; return; }
      record(S.typed.trim(), res === "ok", note);
    }
    const essayLen = computed(() => clean(S.typed).length);
    function sendEssay() {
      const [lo, hi] = q.value.limit || [100, 200], n = essayLen.value;
      if (n < Math.floor(lo / 2)) { S.retry = `✏️ もう少し書いてみよう（いま ${n}字。${lo}字くらいから）`; return; }
      if (n > Math.floor(hi * 1.5)) { S.retry = `✏️ 長すぎるよ（いま ${n}字。${hi}字までにまとめよう）`; return; }
      S.essayWait = true; S.retry = "";
      Kit.ask({ type: "essay", grade: S.play.grade, q: { text: q.value.text, limit: q.value.limit, rubric: q.value.rubric }, answer: S.typed.trim() }, r => {
        S.essayWait = false;
        if (r.error) { S.retry = r.error; return; }
        const note = (r.good ? `👍 よいところ：${r.good}\n` : "") + (r.advice ? `💡 アドバイス：${r.advice}` : "");
        record(S.typed.trim(), r.score >= 6, note, r.score);
      });
    }
    function next() {
      const x = q.value, a = S.ans, label = (C.value.kindLabels[x.kind] || "").split(" ").slice(1).join(" ");
      let question = `${label} ${x.text}`;
      if (["text", "classic"].includes(x.kind)) question = `${C.value.kindNames[x.kind]}（${x.view}） ${x.text}\n（${(x.opts || []).join("／")}）`;
      S.rows.push([question, a.typed + (x.kind === "essay" ? `（${a.points}/10点）` : ""), correctText(x), a.ok]);
      S.log.push(a.ok); S.score += a.points;
      if (S.step < qs.value.length - 1) { S.step++; S.ans = null; S.typed = ""; S.pick = null; S.retry = ""; S.showYaku = false; Kit.top(); return; }
      finish();
    }
    function finish() {
      S.view = "end"; Kit.top();
      if (S.score === 100) Kit.party();
      const p = S.play;
      Kit.ask({ type: "done", run: S.run, grade: p.grade, course: p.course, theme: p.theme, passage: p.passage ? p.passage.id : "", score: S.score, rows: S.rows }, r => { S.pdf = r.pdf || ""; });
      const wrong = wrongList.value;
      if (wrong.length) {
        S.aiWait = true;
        Kit.ask({ type: "ai", run: S.run, grade: p.grade, items: wrong.map(i => ({ q: S.rows[i][0], user: S.rows[i][1], correct: S.rows[i][2], hint: qs.value[i].ng || "" })) },
          r => { S.aiWait = false; S.ai = r.notes || null; });
      }
    }
    const wrongList = computed(() => S.log.map((ok, i) => (!ok && qs.value[i] && qs.value[i].kind !== "essay") ? i : -1).filter(i => i >= 0));
    const kindParts = computed(() => {
      const out = {};
      qs.value.forEach((x, i) => { const k = x.kind; out[k] = out[k] || [0, 0]; out[k][1]++; if (S.log[i]) out[k][0]++; });
      return Object.entries(out).map(([k, [c, n]]) => `${C.value.kindNames[k]}：${c} / ${n}`).join("　");
    });
    const optClass = c => S.ans == null ? { on: S.pick === c } : { right: c === q.value.ans, wrong: c === S.ans.typed && c !== q.value.ans };
    let quitAt = 0;
    function quit() {
      if (Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと やめて メニューに もどるよ"); return; }
      S.view = "home"; Kit.top();
    }

    // ---- 学ぶ ----
    const classicOk = computed(() => C.value.grades.indexOf(S.grade) >= 4);       // 古典は小5から
    const learnItems = computed(() => {
      const out = [];
      (D.value.bySchool[school.value] || []).forEach(id => {
        const lec = D.value.lectures[id];
        if (!lec || (!classicOk.value && (lec.group || "古典") === "古典")) return;
        out.push({ uid: "lec_" + id, kind: "lec", id, head: GROUP_HEAD[lec.group || "古典"] || "📜 古典のミニ講座", title: `${lec.emoji} ${lec.title}`, obj: lec });
      });
      if (classicOk.value) (D.value.workSchool[school.value === "高" ? "高" : "中"] || []).forEach(id => {
        const w = D.value.works[id]; if (w) out.push({ uid: "work_" + id, kind: "work", id, head: "📜 古典の作品を読む", title: `📜 ${w.title}`, obj: w });
      });
      out.forEach((it, n) => it.n = n + 1);
      return out;
    });
    const learnHeads = computed(() => {
      const out = [];
      for (const it of learnItems.value) { let h = out[out.length - 1]; if (!h || h.head !== it.head) out.push(h = { head: it.head, items: [] }); h.items.push(it); }
      for (const h of out) h.done = h.items.filter(x => learned.value.has(x.uid)).length;
      return out;
    });
    const learnDone = computed(() => learnItems.value.filter(x => learned.value.has(x.uid)).length);
    const isOpen = h => S.open[h.head] ?? false;
    const toggle = h => { S.open[h.head] = !isOpen(h); };
    const itemAt = computed(() => learnItems.value.findIndex(x => x.uid === S.item));
    const item = computed(() => learnItems.value[itemAt.value] || null);
    function openItem(uid) { S.item = uid; S.yaku = false; S.view = "learn"; Kit.top(); }
    function stepItem(d) { const it = learnItems.value[itemAt.value + d]; if (it) openItem(it.uid); }
    const lquiz = id => S.lq[id] || (S.args.lquiz || {})[id] || [];
    function lqCheck(id) { S.lqChecked[id] = true; }
    function lqResult(id, i, x) {
      const got = (S.lqAns[id] || {})[i] || "";
      return x.type === "choice" ? got === x.ans : checkReading(got, x.answers)[0] === "ok";
    }
    function lqNew(id) {
      S.lqWait = id;
      Kit.ask({ type: "lquiz", lid: id }, r => { S.lqWait = ""; if (r.quiz) { S.lq[id] = r.quiz; S.lqAns[id] = {}; S.lqChecked[id] = false; } });
    }
    function markLearned(it) {
      Kit.ask({ type: "learned", grade: S.grade, uid: it.uid, title: it.obj.title }, () => toast(it.kind === "work" ? "✓ 読んだ！ に しました" : "✓ 学んだ！ に しました"));
    }
    const workCourse = w => { let c = (C.value.workCourse || {})[S.grade]; if (c && w.kind === "kindai") c = school.value === "高" ? "gengo_bunka" : null; return c; };
    const isOrig = w => ["kobun", "waka", "kindai"].includes(w.kind);
    const nl = t => Kit.esc(t).replace(/\n/g, "<br>");

    Streamlit.ready(onArgs);
    return { S, C, D, me, THEMES, learned, allowed, gradeRows, courses, pickGrade, gen, again, qs, q, chapter, passage, correctText,
      decideChoice, decideText, essayLen, sendEssay, next, wrongList, kindParts, optClass, quit, keep,
      classicOk, learnItems, learnHeads, learnDone, isOpen, toggle, itemAt, item, openItem, stepItem, lquiz, lqCheck, lqResult, lqNew, markLearned, workCourse, isOrig, nl, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <template v-if="S.view === 'home'">
    <div class="hero"><div class="hero-t"><div class="logo">あ</div><div><b>AI国語アドベンチャー</b><small>テーマに合わせて、AIが その場で 世界にひとつだけの 国語教材を 作るよ！</small></div></div></div>
    <div class="card">
      <div class="h3">🎓 学年<span v-if="me.maxGrade" class="small muted">{{ C.gradeNames[me.maxGrade] }}まで えらべるよ</span></div>
      <div v-if="allowed.length > 1" class="grades">
        <div v-for="r in gradeRows" :key="r.k" class="grow-row"><span class="gname">{{ r.name }}</span>
          <div class="gbtns"><button v-for="g in r.grades" :key="g" :class="{ on: S.grade === g }" @click="pickGrade(g)">{{ g.slice(1) }}年</button></div></div>
      </div>
      <div v-else class="small"><b>{{ C.gradeNames[S.grade] }}</b> の問題が出るよ</div>
    </div>
    <div class="seg two"><button :class="{ on: S.tab === 'quiz' }" @click="S.tab = 'quiz'; keep()">🏁 問題にちょうせん</button><button :class="{ on: S.tab === 'learn' }" @click="S.tab = 'learn'; keep()">📖 学ぶ</button></div>

    <template v-if="S.tab === 'quiz'">
      <div v-if="S.silly" class="note bad">🚨 この入力は 記録されました。どんなテーマで 遊ぶか、おうちの人と 相談してみよう。</div>
      <div class="card">
        <template v-if="courses.length > 1">
          <div class="h3">📚 科目</div>
          <div class="pick"><button v-for="c in courses" :key="c" class="pk" :class="{ on: S.course === c }" @click="S.course = c; keep()"><span class="radio"></span><span class="grow"><b>{{ C.courses[c].name }}</b><small>{{ C.courses[c].desc }}</small></span></button></div>
        </template>
        <div v-else-if="S.course" class="small muted">📚 {{ C.courses[S.course].name }}：{{ C.courses[S.course].desc }}</div>
        <div class="h3" style="margin-top:12px">✍️ テーマ<span class="small muted">{{ C.themeMax }}文字まで・何でも OK！</span></div>
        <input class="tin" v-model="S.theme" :maxlength="C.themeMax + 5" placeholder="ここに 文字を 入力してね" @keydown.enter.prevent="!$event.isComposing && !S.busy && gen({})">
        <div class="sugg"><button v-for="t in THEMES" :key="t" @click="S.theme = t">{{ t }}</button></div>
      </div>
      <button class="big" :disabled="S.busy" @click="gen({})">{{ S.busy ? '🧙‍♂️ AI先生が 文章と 問題を 作っているよ…（20〜30秒）' : '🚀 このテーマで AIに 問題を 作ってもらう！' }}</button>
    </template>

    <template v-else>
      <div class="lsum"><span>📖 学んだ</span><b>{{ learnDone }}</b><i>/ {{ learnItems.length }}</i><div class="bar"><i :style="{ width: (learnItems.length ? learnDone / learnItems.length * 100 : 0) + '%' }"></i></div></div>
      <div class="acc">
        <template v-for="h in learnHeads" :key="h.head">
          <button class="ahead" :class="{ open: isOpen(h) }" @click="toggle(h)"><b class="grow">{{ h.head }}</b>
            <span class="adone" :class="{ all: h.done === h.items.length }">✓ {{ h.done }}/{{ h.items.length }}</span><span class="achev">{{ isOpen(h) ? '▲' : '▼' }}</span></button>
          <div v-if="isOpen(h)" class="abody">
            <button v-for="it in h.items" :key="it.uid" class="lrow" @click="openItem(it.uid)"><span class="num">{{ it.n }}</span><b class="grow">{{ it.title }}</b><i v-if="learned.has(it.uid)" class="ok">✓</i><span class="chev">›</span></button>
          </div>
        </template>
      </div>
    </template>
  </template>

  <!-- 学ぶ：講座・作品 -->
  <template v-else-if="S.view === 'learn' && item">
    <div class="bar-top"><button class="back" @click="S.view = 'home'; Kit.top()">‹ 目次</button><b>{{ item.head }}</b><span></span></div>
    <template v-if="item.kind === 'lec'">
      <div class="card lesson">
        <div class="lt"><span class="num">{{ item.n }}</span><h2>{{ item.title }}</h2><i v-if="learned.has(item.uid)" class="ok big">✓</i></div>
        <p class="intro">💡 {{ item.obj.intro }}</p>
        <div class="sub">おぼえよう</div>
        <ul class="points"><li v-for="(p, k) in item.obj.points" :key="k">{{ p }}</li></ul>
      </div>
      <div class="card">
        <div class="sub">{{ (item.obj.group || '古典') === '古典' ? '📜 作品の中で 見てみよう' : '👀 例' }}</div>
        <div v-for="(ex, k) in item.obj.examples" :key="k" class="ex"><blockquote>{{ ex[0] }}</blockquote><div class="small muted">👉 {{ ex[1] }}</div></div>
      </div>
      <div class="card">
        <div class="sub">🙋 やってみよう（点数は つかないよ）</div>
        <div v-for="(x, i) in lquiz(item.id)" :key="item.id + i" class="lq">
          <div><b>{{ i + 1 }}.</b> {{ x.q }}</div>
          <div v-if="x.type === 'choice'" class="opts sm">
            <button v-for="(o, k) in x.opts" :key="k" class="opt" :class="S.lqChecked[item.id] ? { right: o === x.ans, wrong: (S.lqAns[item.id] || {})[i] === o && o !== x.ans } : { on: (S.lqAns[item.id] || {})[i] === o }"
              :disabled="S.lqChecked[item.id]" @click="(S.lqAns[item.id] = S.lqAns[item.id] || {})[i] = o"><span class="grow">{{ o }}</span></button>
          </div>
          <input v-else class="tin" style="margin-top:6px" :disabled="S.lqChecked[item.id]" :value="(S.lqAns[item.id] || {})[i] || ''" @input="(S.lqAns[item.id] = S.lqAns[item.id] || {})[i] = $event.target.value" placeholder="ひらがなで">
          <div v-if="S.lqChecked[item.id]" class="fb" :class="lqResult(item.id, i, x) ? 'ok' : 'ng'">{{ lqResult(item.id, i, x) ? '⭕ せいかい！' : '❌ 答えは「' + (x.type === 'choice' ? x.ans : x.show) + '」' }}<small>{{ x.explain }}</small></div>
        </div>
        <div class="row2"><button class="btn" :disabled="S.lqWait === item.id" @click="lqNew(item.id)">{{ S.lqWait === item.id ? 'つくっています…' : '🔄 ちがう問題にする' }}</button><button class="btn pri" :disabled="S.lqChecked[item.id]" @click="lqCheck(item.id)">答えを たしかめる</button></div>
      </div>
    </template>
    <template v-else>
      <div class="card lesson">
        <div class="lt"><span class="num">{{ item.n }}</span><h2>📜 {{ item.obj.title }}</h2><i v-if="learned.has(item.uid)" class="ok big">✓</i></div>
        <div class="small muted">{{ item.obj.author }}／{{ item.obj.era }}／{{ (D.guides[item.id] || {}).kind }}</div>
        <div class="sub">🔎 読みどころ</div>
        <ul class="points"><li v-for="(p, k) in (D.guides[item.id] || {}).points" :key="k">{{ p }}</li></ul>
      </div>
      <div class="card">
        <div class="sub">{{ isOrig(item.obj) ? '原文' : '書き下し文' }}</div>
        <div class="classic" v-html="nl(item.obj.text)"></div>
        <div v-if="item.obj.hakubun" class="small muted" style="margin-top:6px">白文：{{ item.obj.hakubun.replace(/\\n/g, '　') }}</div>
        <button class="link" @click="S.yaku = !S.yaku">{{ S.yaku ? '▲ とじる' : (item.obj.kind !== 'kindai' ? '📖 現代語訳を 見る' : '📖 言葉の意味を 見る') }}</button>
        <div v-if="S.yaku" class="yaku" v-html="nl(item.obj.yaku)"></div>
      </div>
      <button v-if="workCourse(item.obj)" class="big" :disabled="S.busy" @click="gen({ work: item.id })">{{ S.busy ? '🧙‍♂️ AI先生が 問題を 作っているよ…（20〜30秒）' : '🏁 この作品で 問題に挑戦（' + C.courses[workCourse(item.obj)].name + '・10問）' }}</button>
    </template>
    <div class="row2">
      <button v-if="learned.has(item.uid)" class="btn done" disabled>{{ item.kind === 'work' ? '✓ 読んだ！' : '✓ 学んだ！' }}</button>
      <button v-else class="btn ok" @click="markLearned(item)">{{ item.kind === 'work' ? '✅ 読んだ！' : '✅ 学んだ！' }}</button>
      <button class="btn" @click="S.view = 'home'; Kit.top()">⬆ 目次へ</button>
    </div>
    <div class="row2" style="margin-top:8px"><button class="btn" :disabled="itemAt <= 0" @click="stepItem(-1)">‹ 前へ</button><button class="btn" :disabled="itemAt >= learnItems.length - 1" @click="stepItem(1)">次へ ›</button></div>
  </template>

  <!-- 10問 -->
  <template v-else-if="S.view === 'play' && S.play">
    <div class="bar-top"><button class="back" @click="quit">‹ やめる</button><b>{{ S.play.theme }}・{{ C.courses[S.play.course].name }}</b><span class="cnt">{{ S.score }}点</span></div>
    <div class="prog"><i :style="{ width: (S.step / qs.length * 100) + '%' }"></i></div>
    <div class="small muted" style="margin:-6px 4px 8px">第{{ S.step + 1 }}問 / {{ qs.length }}問</div>
    <div v-if="chapter" class="card story"><div class="h3">{{ chapter.title }}</div><div class="stxt">{{ chapter.story }}</div></div>
    <div v-else-if="passage" class="card story"><div class="h3">📜 {{ passage.title }}</div><div class="small muted">{{ passage.author }}／{{ passage.era }}／{{ D.kindNames[passage.kind] }}</div>
      <div class="classic" style="margin-top:8px" v-html="nl(passage.text)"></div><div v-if="passage.hakubun" class="small muted" style="margin-top:6px">白文：{{ passage.hakubun.replace(/\\n/g, '　') }}</div></div>
    <div class="qhead">❓ 第{{ S.step + 1 }}問　{{ C.kindLabels[q.kind] }}<span v-if="['text', 'classic'].includes(q.kind)">（{{ q.view }}）</span></div>
    <div v-if="C.kindHowto[q.kind]" class="small muted" style="margin:0 4px 4px">{{ C.kindHowto[q.kind] }}</div>
    <div class="card qtext">{{ q.text }}</div>
    <div v-if="q.kind === 'essay'" class="small muted" style="margin:-6px 4px 8px">字数：{{ q.limit[0] }}〜{{ q.limit[1] }}字　／　採点の観点：{{ (q.rubric || []).join('・') }}（AIの採点なので、点数は目安だよ）</div>

    <template v-if="S.ans == null">
      <template v-if="['text', 'classic'].includes(q.kind)">
        <div class="opts"><button v-for="(o, k) in q.opts" :key="S.step + '-' + k" class="opt" :class="optClass(o)" @click="S.pick = o"><span class="mk">{{ 'アイウ'[k] }}</span><span class="grow">{{ o }}</span></button></div>
        <button class="big" :disabled="S.pick == null" @click="decideChoice">これで決定！</button>
      </template>
      <template v-else-if="q.kind === 'essay'">
        <textarea class="tarea" v-model="S.typed" placeholder="ここに書こう"></textarea>
        <div class="small muted" style="text-align:right">{{ essayLen }}字</div>
        <div v-if="S.retry" class="note warn">{{ S.retry }}</div>
        <button class="big" :disabled="S.essayWait || !S.typed.trim()" @click="sendEssay">{{ S.essayWait ? '📝 AI先生が 読んでいるよ…' : 'これで提出！' }}</button>
      </template>
      <template v-else>
        <input class="tin big-in" v-model="S.typed" :placeholder="{ read: '読み方（ひらがな）', write: '漢字で書こう', kana: '現代かなづかい（ひらがな）' }[q.kind]" autocomplete="off" @keydown.enter.prevent="!$event.isComposing && S.typed.trim() && decideText()">
        <div v-if="S.retry" class="note warn" style="margin-top:8px">{{ S.retry }}</div>
        <button class="big" :disabled="!S.typed.trim()" @click="decideText">これで決定！</button>
      </template>
    </template>
    <template v-else>
      <div v-if="['text', 'classic'].includes(q.kind)" class="opts"><button v-for="(o, k) in q.opts" :key="S.step + '-' + k" class="opt" :class="optClass(o)" disabled><span class="mk">{{ 'アイウ'[k] }}</span><span class="grow">{{ o }}</span></button></div>
      <div v-else class="small" style="margin:4px">キミの答え：<b>{{ S.ans.typed }}</b></div>
      <div v-if="q.kind === 'essay'" class="fb" :class="S.ans.ok ? 'ok' : 'ng'">📝 {{ S.ans.points }} / 10点（目安）<small class="pre">{{ S.ans.note }}</small><small>{{ q.ok }}</small></div>
      <div v-else-if="S.ans.ok" class="fb ok">⭕ せいかい！<small>{{ q.ok }}</small></div>
      <div v-else class="fb ng">❌ ざんねん… 正しい答えは「{{ correctText(q) }}」だよ。<small v-if="S.ans.note">{{ S.ans.note }}</small><small>{{ q.ng }}</small></div>
      <template v-if="q.section == null && passage">
        <button class="link" @click="S.showYaku = !S.showYaku">{{ S.showYaku ? '▲ とじる' : '📖 現代語訳を 見る' }}</button>
        <div v-if="S.showYaku" class="yaku" v-html="nl(passage.yaku)"></div>
      </template>
      <button class="big" @click="next">{{ S.step >= qs.length - 1 ? '結果発表へ！ 🏆' : '次の問題へ 進む ➡️' }}</button>
    </template>
  </template>

  <!-- 結果 -->
  <template v-else-if="S.view === 'end'">
    <h2 class="center" style="margin-top:6px">🏆 大冒険 おつかれさま！</h2>
    <div class="card score one"><div><small>キミの点数</small><b>{{ S.score }}</b><i>/ 100点</i></div></div>
    <div class="marks">{{ S.log.map(o => o ? '⭕' : '❌').join('') }}</div>
    <div class="small muted center" style="margin:-4px 0 10px">{{ kindParts }}</div>
    <div class="note" :class="S.score >= 60 ? 'good' : 'warn'">
      <template v-if="S.score === 100">🥇【ランク：国語マスター神】すごすぎる！ 全問 大正解！ 漢字も 読解も 完璧に クリアしたね！</template>
      <template v-else-if="S.score >= 60">🥈【ランク：一流の冒険家】素晴らしい！ 気持ちの変化を しっかり 読み解けたね。次は ちがうテーマで 満点を 目指そう！</template>
      <template v-else>🏃【ランク：みならい冒険家】おつかれさま！ 次は キミの 大好きな 別のテーマで リベンジだ！</template>
    </div>
    <button class="btn pdf" :disabled="!S.pdf" @click="Kit.openPdf(S.pdf)">{{ S.pdf ? '📄 表彰状を 見る' : '📄 表彰状を 作っています…' }}</button>
    <template v-if="wrongList.length">
      <div class="h3" style="margin:14px 4px 8px">👀 まちがえた問題を 見なおそう（{{ wrongList.length }}問）</div>
      <div v-for="(i, n) in wrongList" :key="i" class="card">
        <div><b>第{{ i + 1 }}問</b>　{{ qs[i].text }}</div>
        <div class="cmp"><span>キミの答え</span><code>{{ S.rows[i][1] }}</code><span>正しい答え</span><b>{{ S.rows[i][2] }}</b></div>
        <div v-if="S.ai && S.ai[n]" class="aibox"><b>🤖 AI先生の解説</b><div class="pre">{{ S.ai[n] }}</div></div>
        <div v-else-if="S.aiWait" class="aibox wait"><div class="spin sm"></div>AI先生が 解説を 書いているよ…</div>
        <div v-else class="aibox">📝 {{ qs[i].ng }}</div>
      </div>
    </template>
    <div class="row2" style="margin-top:12px"><button class="btn" @click="again">🔁 同じお話を もう一度</button><button class="btn pri" @click="S.view = 'home'; S.theme = ''; Kit.top()">🔄 別のテーマで 遊ぶ</button></div>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
