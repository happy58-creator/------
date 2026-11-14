/* AIプログラミング教室（画面はぜんぶ JavaScript）。
   Python へ：gen（AIでレッスンをつくる）・log（クイズがおわった：記録と表彰状）。どちらも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed, nextTick } = Vue;
const PHASES = [["words", "① たんご"], ["grammar", "② ぶんぽう"], ["write", "③ かこう"], ["quiz", "④ クイズ"]];

// スマホのキーボードは " や ' を “ ” ‘ ’ にしたり、全角で入ったりするので、半角の記号にそろえる（前の Python と同じ）
const QUOTES = { "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"', "＂": '"', "〝": '"', "〟": '"', "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'", "＇": "'", "｀": "`" };
const normalize = t => [...String(t || "")].map(c => QUOTES[c] ?? (c >= "！" && c <= "～" ? String.fromCharCode(c.charCodeAt(0) - 0xFEE0) : c === "　" ? "" : c)).join("");
const squash = t => normalize(t).replace(/\s+/g, "");     // 空白はぜんぶ気にしない

createApp({
  setup() {
    const L = Kit.load("pg_v1", {});
    const S = reactive({
      ready: false, args: {}, view: "menu",
      lang: L.lang || "Python", level: L.level || "", topic: "",
      lesson: null, play: {}, phase: "words", w: 0, typed: "", wDone: false, wMiss: false,
      qi: 0, pick: null, decided: null, log: [], rows: [], run: "", busy: false, pdf: "", toast: "",
    });
    const keep = () => Kit.save("pg_v1", { lang: S.lang, level: S.level });
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.level || !(a.levels || []).includes(S.level)) S.level = a.level;
      if (!(a.langs || []).some(l => l.id === S.lang)) S.lang = (a.langs || [{}])[0].id;
    }
    const langOf = computed(() => (S.args.langs || []).find(l => l.id === S.lang) || { topics: [] });
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2600); }
    function pickLang(id) { S.lang = id; S.topic = ""; }

    function start() {
      S.busy = true; keep();
      Kit.ask({ type: "gen", lang: S.lang, level: S.level, topic: S.topic }, r => {
        S.busy = false;
        if (r.error || !r.lesson) { toast(r.error || "うまく作れなかったよ。もう一度ためしてね"); return; }
        S.lesson = r.lesson; S.play = { lang: S.lang, level: S.level, topic: r.topic };
        begin();
      });
    }
    function begin() {
      S.lesson.quiz = S.lesson.quiz.map(q => ({ ...q, choices: Kit.shuffle(q.choices) }));
      S.phase = "words"; S.w = 0; S.typed = ""; S.wDone = false; S.wMiss = false;
      S.qi = 0; S.pick = null; S.decided = null; S.log = []; S.rows = []; S.pdf = ""; S.run = Kit.uid();
      S.view = "learn"; Kit.top();
    }
    function go(ph) { S.phase = ph; Kit.top(); }

    // ③ かいてみよう：見本の1行と同じに打てたか（空白・全角半角は気にしない）。打つたびに色をつける
    const steps = computed(() => (S.lesson && S.lesson.steps) || []);
    const step = computed(() => steps.value[S.w] || null);
    const soFar = computed(() => steps.value.slice(0, S.w).map(s => s.code).join("\n"));
    const marks = computed(() => {
      if (!step.value) return [];
      const g = [...squash(step.value.code)], t = [...squash(S.typed)];
      const out = g.map((ch, i) => ({ ch, c: i < t.length ? (t[i] === ch ? "ok" : "ng") : "rest" }));
      if (t.length > g.length) out.push({ ch: t.slice(g.length).join(""), c: "over" });
      return out;
    });
    function check() {
      if (!step.value || S.wDone) return;
      if (squash(S.typed) === squash(step.value.code)) { S.wDone = true; S.wMiss = false; }
      else S.wMiss = true;
    }
    function nextStep() {
      S.w++; S.typed = ""; S.wDone = false; S.wMiss = false;
      nextTick(() => { const el = document.querySelector(".codein"); if (el) el.focus(); });
    }
    const onKey = e => { if (e.key === "Enter" && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); S.wDone ? (S.w < steps.value.length ? nextStep() : null) : check(); } };

    // ④ クイズ
    const quiz = computed(() => (S.lesson && S.lesson.quiz) || []);
    const q = computed(() => quiz.value[S.qi] || {});
    const score = computed(() => S.log.filter(Boolean).length);
    function decide() {
      if (S.pick == null) return;
      S.decided = S.pick;
      const ok = S.pick === q.value.answer;
      S.log.push(ok);
      S.rows.push([`${q.value.question}\n（${q.value.choices.join("／")}）`, S.pick, q.value.answer, ok]);
    }
    function nextQ() {
      if (S.qi < quiz.value.length - 1) { S.qi++; S.pick = null; S.decided = null; Kit.top(); return; }
      S.view = "end"; Kit.top();
      if (score.value === quiz.value.length) Kit.party();
      Kit.ask({ type: "log", run: S.run, ...S.play, rows: S.rows }, r => { S.pdf = r.pdf || ""; });
    }
    const optClass = c => S.decided == null ? { on: S.pick === c } : { right: c === q.value.answer, wrong: c === S.decided && c !== q.value.answer };
    let quitAt = 0;
    function quit() {
      if (Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと、レッスンを やめます"); return; }
      S.view = "menu"; Kit.top();
    }
    Streamlit.ready(onArgs);
    return { S, PHASES, langOf, pickLang, start, go, steps, step, soFar, marks, check, nextStep, onKey, quiz, q, score, decide, nextQ, optClass, quit, begin, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <template v-if="S.view === 'menu'">
    <div class="hero"><div class="hero-t"><div class="logo">&lt;/&gt;</div><div><b>AIプログラミング教室</b><small>言語と年れいを えらぶと、AI先生が ぴったりの レッスンを つくるよ！</small></div></div></div>
    <div class="card">
      <div class="h3">① 言語</div>
      <div class="chips"><button v-for="l in S.args.langs" :key="l.id" class="chip" :class="{ on: S.lang === l.id }" @click="pickLang(l.id)">{{ l.id }}</button></div>
      <div class="small muted" style="margin-top:8px">💡 {{ langOf.desc }}</div>
    </div>
    <div class="card">
      <div class="h3">② 年れい<span v-if="S.args.age != null" class="small muted">{{ S.args.age }}さいに合わせて えらんでおいたよ</span></div>
      <div class="pick two"><button v-for="lv in S.args.levels" :key="lv" class="pk" :class="{ on: S.level === lv }" @click="S.level = lv"><span class="radio"></span><b class="lv">{{ lv }}</b></button></div>
    </div>
    <div class="card">
      <div class="h3">③ 学ぶテーマ</div>
      <div class="chips">
        <button class="chip" :class="{ on: !S.topic }" @click="S.topic = ''">おまかせ（はじめの一歩）</button>
        <button v-for="t in langOf.topics" :key="t" class="chip" :class="{ on: S.topic === t }" @click="S.topic = t">{{ t }}</button>
      </div>
    </div>
    <button class="big" :disabled="S.busy" @click="start">{{ S.busy ? '🧙‍♂️ AI先生が レッスンを 作っているよ…（15秒くらい）' : '🚀 AI先生に レッスンを 作ってもらう！' }}</button>
  </template>

  <template v-else-if="S.view === 'learn' && S.lesson">
    <div class="bar-top"><button class="back" @click="quit">‹ やめる</button><b>{{ S.play.lang }}・{{ S.play.topic }}</b><span></span></div>
    <div class="phases"><button v-for="([k, name], n) in PHASES" :key="k" :class="{ on: S.phase === k, past: PHASES.findIndex(p => p[0] === S.phase) > n }" @click="go(k)">{{ name }}</button></div>

    <template v-if="S.phase === 'words'">
      <div class="note info">{{ S.lesson.overview }}</div>
      <div v-for="(w, k) in S.lesson.words" :key="k" class="card"><code class="term">{{ w.term }}</code>
        <div style="margin-top:6px"><b>意味：</b>{{ w.meaning }}</div><div class="small"><b>何に使う？</b> {{ w.usage }}</div></div>
      <button class="big" @click="go('grammar')">つぎへ：文法を見る ➡️</button>
    </template>

    <template v-else-if="S.phase === 'grammar'">
      <div v-for="(g, k) in S.lesson.grammar" :key="k" class="card">
        <div class="h3">{{ g.title }}</div>
        <div class="sub">書き方の型</div><pre class="code">{{ g.pattern }}</pre>
        <div style="margin:6px 0">{{ g.explain }}</div>
        <template v-if="g.example"><div class="sub">れい</div><pre class="code">{{ g.example }}</pre></template>
      </div>
      <div class="row2"><button class="btn" @click="go('words')">⬅️ 単語にもどる</button><button class="btn pri" @click="go('write')">つぎへ：書いてみよう ➡️</button></div>
    </template>

    <template v-else-if="S.phase === 'write'">
      <div class="small muted" style="margin:0 4px 8px">1行ずつ、見本のとおりに打ってね。スペースの数や全角・半角は 気にしなくていいよ。</div>
      <template v-if="soFar"><div class="sub">ここまでのプログラム</div><pre class="code done">{{ soFar }}</pre></template>
      <template v-if="step">
        <div class="prog"><i :style="{ width: (S.w / steps.length * 100) + '%' }"></i></div>
        <div class="small muted" style="margin:-6px 4px 8px">{{ S.w + 1 }} / {{ steps.length }} ステップ</div>
        <div class="note info">🗣️ {{ step.explain }}</div>
        <div class="sub">👇 この1行を打とう</div><pre class="code">{{ step.code }}</pre>
        <input class="tin codein" v-model="S.typed" :disabled="S.wDone" placeholder="ここに打って Enter（または 決定）" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" @keydown="onKey">
        <div v-if="S.typed" class="live"><span v-for="(m, k) in marks" :key="k" :class="m.c">{{ m.ch }}</span></div>
        <div v-if="S.wDone" class="fb ok">🎉 せいかい！</div>
        <div v-else-if="S.wMiss" class="fb ng">❌ おしい！ 赤い文字を なおして もう一回 ためしてね。</div>
        <button v-if="!S.wDone" class="big" :disabled="!S.typed.trim()" @click="check">決定！</button>
        <button v-else class="big" @click="nextStep">{{ S.w === steps.length - 1 ? '完成！ 実行結果を見る ➡️' : 'つぎのステップへ ➡️' }}</button>
      </template>
      <template v-else>
        <div class="fb ok">🎉 プログラムが 完成したよ！</div>
        <div class="sub" style="margin-top:10px">💻 実行すると こうなるよ</div><pre class="code out">{{ S.lesson.output }}</pre>
        <button class="big" @click="go('quiz')">つぎへ：クイズに挑戦 ➡️</button>
      </template>
    </template>

    <template v-else>
      <div class="prog"><i :style="{ width: (S.qi / quiz.length * 100) + '%' }"></i></div>
      <div class="h3">❓ {{ S.qi + 1 }} / {{ quiz.length }}<span class="small muted">⭕{{ score }}</span></div>
      <div class="card qtext">{{ q.question }}</div>
      <div class="opts"><button v-for="(c, k) in q.choices" :key="S.qi + '-' + k" class="opt" :class="optClass(c)" :disabled="S.decided != null" @click="S.pick = c"><span class="mk">{{ 'ABCD'[k] }}</span><span class="grow mono">{{ c }}</span></button></div>
      <button v-if="S.decided == null" class="big" :disabled="S.pick == null" @click="decide">これで決定！</button>
      <template v-else>
        <div class="fb" :class="S.decided === q.answer ? 'ok' : 'ng'">{{ S.decided === q.answer ? '⭕ せいかい！' : '❌ ざんねん… 正しい答えは「' + q.answer + '」だよ' }}<small v-if="q.explanation">{{ q.explanation }}</small></div>
        <button class="big" @click="nextQ">{{ S.qi >= quiz.length - 1 ? '結果発表へ！ 🏆' : '次の問題へ ➡️' }}</button>
      </template>
    </template>
  </template>

  <template v-else-if="S.view === 'end'">
    <h2 class="center" style="margin-top:6px">🏆 レッスンクリア！</h2>
    <div class="card score">
      <div><small>点数</small><b>{{ score * 20 }}</b><i>/ 100点</i></div>
      <div><small>正解</small><b>{{ score }}</b><i>/ {{ quiz.length }}問</i></div>
      <div><small>言語</small><b style="font-size:17px">{{ S.play.lang }}</b></div>
    </div>
    <div class="marks">{{ S.log.map(o => o ? '⭕' : '❌').join('') }}</div>
    <div class="note" :class="score >= 3 ? 'good' : 'warn'">{{ score === quiz.length ? '🥇 パーフェクト！ もう立派なプログラマーだ！' : score >= 3 ? '🥈 いいね！ 単語と文法をもう一度見ると、さらに身につくよ。' : '🌱 よくがんばったね！ レッスンをもう一度やってみよう。' }}</div>
    <button class="btn pdf" :disabled="!S.pdf" @click="Kit.openPdf(S.pdf)">{{ S.pdf ? '📄 表彰状を 見る' : '📄 表彰状を 作っています…' }}</button>
    <div class="row2" style="margin-top:12px"><button class="btn" @click="begin">🔁 同じレッスンを もう一度</button><button class="btn pri" @click="S.view = 'menu'; Kit.top()">🔄 べつのレッスンを 作る</button></div>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
