/* AI英語チャレンジ（画面はぜんぶ JavaScript）。
   Python へ：gen（AIで10問つくる）・log（10問おわった：記録と表彰状）。どちらも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed } = Vue;
const TOTAL = 10;
const TOPICS = ["どうぶつ", "たべもの", "スポーツ", "がっこう", "りょこう", "しごと"];

createApp({
  setup() {
    const L = Kit.load("en_v1", {});
    const S = reactive({
      ready: false, args: {}, view: "menu",
      level: L.level || "", course: L.course || "単語", assist: L.assist ?? true, topic: "",
      qs: [], i: 0, pick: null, decided: null, hint: false, log: [], rows: [], run: "",
      busy: false, sec: 0, err: "", pdf: "", toast: "",
    });
    const keep = () => Kit.save("en_v1", { level: S.level, course: S.course, assist: S.assist });
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.level || !(a.levels || []).includes(S.level)) S.level = a.level;
    }
    const courses = computed(() => S.args.courses || []);
    const courseOf = id => courses.value.find(c => c.id === id) || {};
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2600); }

    // AIに10問たのむ：待っている秒数を見せる。90秒たっても返事がなければ、ボタンをもどして知らせる（あとから返事が来たら、そのまま始める）
    let waitT = 0;
    function start() {
      S.busy = true; S.err = ""; S.sec = 0; keep();
      clearInterval(waitT);
      waitT = setInterval(() => {
        S.sec++;
        if (S.sec >= 90) { clearInterval(waitT); S.busy = false; S.err = "AIの返事が 来ないみたい…。通信を たしかめて、もう一度 押してみてね"; }
      }, 1000);
      Kit.ask({ type: "gen", course: S.course, level: S.level, topic: S.topic.trim() }, r => {
        clearInterval(waitT); S.busy = false;
        if (r.error || !r.questions) { if (S.view === "menu") S.err = r.error || "うまく作れなかったよ。もう一度ためしてね"; return; }
        if (S.view !== "menu") return;
        S.err = ""; begin(r.questions, S.topic.trim());
      });
    }
    function begin(qs, topic) {
      S.qs = qs.map(q => ({ ...q, choices: Kit.shuffle(q.choices) }));
      S.playTopic = topic; S.playCourse = S.course; S.playLevel = S.level; S.playAssist = S.assist;
      S.i = 0; S.pick = null; S.decided = null; S.hint = false; S.log = []; S.rows = []; S.pdf = ""; S.run = Kit.uid();
      S.view = "play"; Kit.top();
    }
    const q = computed(() => S.qs[S.i] || {});
    const score = computed(() => S.log.filter(Boolean).length);
    function decide() {
      if (S.pick == null) return;
      S.decided = S.pick;
      const ok = S.pick === q.value.answer;
      S.log.push(ok);
      S.rows.push([q.value.prompt + (q.value.translation ? `\n（${q.value.translation}）` : ""), S.pick, q.value.answer, ok]);
    }
    function next() {
      if (S.i < TOTAL - 1 && S.i < S.qs.length - 1) { S.i++; S.pick = null; S.decided = null; S.hint = false; Kit.top(); return; }
      S.view = "end"; Kit.top();
      if (score.value === S.qs.length) Kit.party();
      Kit.ask({ type: "log", run: S.run, course: S.playCourse, level: S.playLevel, topic: S.playTopic, rows: S.rows }, r => { S.pdf = r.pdf || ""; });
    }
    function again() { begin(S.qs, S.playTopic); }
    const wrong = computed(() => S.qs.filter((x, k) => S.log[k] === false));
    let quitAt = 0;
    function quit() {
      if (S.i > 0 && Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと やめます"); return; }
      S.view = "menu"; Kit.top();
    }
    const optClass = c => S.decided == null ? { on: S.pick === c } : { right: c === q.value.answer, wrong: c === S.decided && c !== q.value.answer };
    Streamlit.ready(onArgs);
    return { S, TOTAL, TOPICS, courses, courseOf, start, q, score, decide, next, again, wrong, quit, optClass, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <template v-if="S.view === 'menu'">
    <div class="hero"><div class="hero-t"><div class="logo">Aa</div><div><b>AI英語チャレンジ</b><small>年れいに合わせて、AIが英語の問題を 10問 つくるよ！</small></div></div></div>
    <div class="card">
      <div class="h3">① 年れい<span v-if="S.args.age != null" class="small muted">{{ S.args.age }}さいに合わせて えらんでおいたよ</span></div>
      <div class="pick two">
        <button v-for="lv in S.args.levels" :key="lv" class="pk" :class="{ on: S.level === lv }" @click="S.level = lv"><span class="radio"></span><b class="lv">{{ lv }}</b></button>
      </div>
    </div>
    <div class="card">
      <div class="h3">② コース</div>
      <div class="pick">
        <button v-for="c in courses" :key="c.id" class="pk" :class="{ on: S.course === c.id }" @click="S.course = c.id"><span class="ic">{{ c.icon }}</span><span class="grow"><b>{{ c.id }}コース</b><small>{{ c.desc }}</small></span></button>
      </div>
    </div>
    <div class="card">
      <div class="h3">③ おたすけ・テーマ<span class="small muted">どちらも おこのみで</span></div>
      <button class="toggle" :class="{ on: S.assist }" @click="S.assist = !S.assist"><span class="sw"></span><span class="grow"><b>おたすけモード</b><small class="muted" style="display:block;font-size:12px">読み方・日本語訳・絵文字を 見ながら 答える</small></span></button>
      <input class="tin" style="margin-top:12px" v-model="S.topic" maxlength="40" placeholder="テーマ（空らんなら おまかせ）">
      <div class="sugg"><button v-for="t in TOPICS" :key="t" @click="S.topic = t">{{ t }}</button></div>
    </div>
    <div v-if="S.err" class="errbox">⚠️ {{ S.err }}</div>
    <button class="big" :disabled="S.busy" @click="start">{{ S.busy ? '🧙‍♂️ AI先生が 10問を 作っているよ…（' + S.sec + '秒）' : (S.err ? '🔁 もう一度 つくってもらう' : '🚀 AIに10問 つくってもらう！') }}</button>
    <div v-if="S.busy" class="small muted center" style="margin-top:6px">ふつうは 10〜30秒ほどで できあがるよ</div>
  </template>

  <template v-else-if="S.view === 'play'">
    <div class="bar-top"><button class="back" @click="quit">‹ やめる</button><b>{{ S.playCourse }}コース・{{ S.i + 1 }} / {{ S.qs.length }}問目</b><span class="cnt">⭕{{ score }}</span></div>
    <div class="prog"><i :style="{ width: (S.i / S.qs.length * 100) + '%' }"></i></div>
    <div class="card center qbox">
      <div v-if="S.playAssist && q.emoji" class="emoji">{{ q.emoji }}</div>
      <div class="prompt">{{ q.prompt }}</div>
      <div v-if="S.playAssist && S.playCourse === '単語' && q.reading" class="reading">（{{ q.reading }}）</div>
    </div>
    <div class="h3" style="margin:4px 4px 0">{{ courseOf(S.playCourse).ask }}</div>
    <div class="opts">
      <button v-for="(c, k) in q.choices" :key="S.i + '-' + k" class="opt" :class="optClass(c)" :disabled="S.decided != null" @click="S.pick = c"><span class="mk">{{ 'ABCDE'[k] }}</span><span class="grow">{{ c }}</span></button>
    </div>
    <template v-if="S.decided == null">
      <div v-if="S.hint" class="note warn" style="margin-top:10px">💡 {{ q.hint || 'よく見て 考えてみよう！' }}</div>
      <div class="row2"><button class="btn" :disabled="S.hint" @click="S.hint = true">💡 ヒント</button><button class="btn pri" :disabled="S.pick == null" @click="decide">これで決定！</button></div>
    </template>
    <template v-else>
      <div class="fb" :class="S.decided === q.answer ? 'ok' : 'ng'">{{ S.decided === q.answer ? '⭕ せいかい！ ' + q.answer : '❌ ざんねん… 正しい答えは「' + q.answer + '」だよ' }}
        <small v-if="q.translation">📖 日本語訳：{{ q.translation }}</small><small v-if="q.explanation">{{ q.explanation }}</small></div>
      <button class="big" @click="next">{{ S.i >= S.qs.length - 1 ? '結果発表へ！ 🏆' : '次の問題へ ➡️' }}</button>
    </template>
  </template>

  <template v-else>
    <h2 class="center" style="margin-top:6px">🏆 おつかれさま！</h2>
    <div class="card score">
      <div><small>点数</small><b>{{ score * 10 }}</b><i>/ 100点</i></div>
      <div><small>正解</small><b>{{ score }}</b><i>/ {{ S.qs.length }}問</i></div>
      <div><small>コース</small><b style="font-size:20px">{{ S.playCourse }}</b></div>
    </div>
    <div class="marks">{{ S.log.map(o => o ? '⭕' : '❌').join('') }}</div>
    <div class="note" :class="score >= 7 ? 'good' : 'warn'">{{ score === S.qs.length ? '🥇 パーフェクト！ 英語マスターだ！' : score >= 7 ? '🥈 すばらしい！ あと少しで満点だよ。' : '🌱 よくがんばったね！ まちがえた問題を見なおして、もう一回やってみよう。' }}</div>
    <button class="btn pdf" :disabled="!S.pdf" @click="Kit.openPdf(S.pdf)">{{ S.pdf ? '📄 表彰状を 見る' : '📄 表彰状を 作っています…' }}</button>
    <template v-if="wrong.length">
      <div class="h3" style="margin:14px 4px 8px">👀 まちがえた問題（{{ wrong.length }}問）</div>
      <div v-for="(w, k) in wrong" :key="k" class="card">
        <b>{{ w.emoji ? w.emoji + ' ' : '' }}{{ w.prompt }}</b>　→　<b style="color:var(--ok)">{{ w.answer }}</b>
        <div v-if="w.translation" class="small muted">日本語訳：{{ w.translation }}</div>
        <div v-if="w.explanation" class="small muted">{{ w.explanation }}</div>
      </div>
    </template>
    <div class="row2" style="margin-top:12px"><button class="btn" @click="again">🔁 同じ問題を もう一度</button><button class="btn pri" @click="S.view = 'menu'; Kit.top()">🔄 べつの問題を つくる</button></div>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
