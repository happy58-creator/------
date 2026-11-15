/* 漢字のかきとり（画面はぜんぶ JavaScript）。書き取りの本体は kanji.js（KanjiGame）。
   Python へ：start（10字えらぶ）・done（書きおわった：点数・記録・表彰状）。どちらも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed, nextTick } = Vue;

createApp({
  setup() {
    const L = Kit.load("kj_v1", {});
    const S = reactive({
      ready: false, args: {}, view: "menu",
      grade: L.grade || 1, mode: L.mode || "trace", level: L.level || "",
      play: {}, busy: false, result: null, toast: "", run: "",
    });
    const keep = () => Kit.save("kj_v1", { grade: S.grade, mode: S.mode, level: S.level });
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.level || !(a.levels || []).some(l => l.id === S.level)) S.level = a.level;
    }
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2600); }
    const modeOf = id => (S.args.modes || []).find(m => m.id === id) || {};
    const tolOf = id => ((S.args.levels || []).find(l => l.id === id) || {}).tol || 20;

    let game = null;
    function start(again) {
      if (!again) S.play = { grade: S.grade, mode: S.mode, level: S.level };
      S.busy = true; keep();
      Kit.ask({ type: "start", grade: S.play.grade }, r => {
        S.busy = false;
        if (r.error || !r.kanjis) { toast(r.error || "うまくいかなかったよ"); return; }
        S.run = Kit.uid(); S.result = null; S.view = "play"; Kit.top();
        nextTick(() => {        // 書き取りの本体（kanji.js）を、この画面の中に出す
          const box = document.getElementById("game"); box.innerHTML = "";
          game = new KanjiGame(box, { kanjis: r.kanjis, mode: S.play.mode, tol: tolOf(S.play.level), round: S.run }, done);
        });
      });
    }
    function done(v) {
      S.view = "end"; S.result = null; Kit.top();
      Kit.ask({ type: "done", run: S.run, grade: S.play.grade, mode: S.play.mode, level: S.play.level, results: v.results }, r => {
        if (r.error) { toast(r.error); return; }
        S.result = { ...r, time: v.time, items: v.results };
        if (r.score >= 90) Kit.party();
      });
    }
    let quitAt = 0;
    function quit() {
      if (Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと やめて メニューに もどるよ"); return; }
      game = null; S.view = "menu"; Kit.top();
    }
    const fmtTime = s => { const m = Math.floor(s / 60), r = Math.round((s % 60) * 10) / 10; return m ? `${m}分 ${r}秒` : `${r}秒`; };
    const mark = it => it.points >= 9 ? "🌟" : it.points >= (S.args.okPoints || 8) ? "⭐" : !it.skipped ? "👍" : "🙈";
    const readingOf = ch => ((S.result && S.result.rows) || []).find(r => r.ch === ch)?.reading || "";
    Streamlit.ready(onArgs);
    return { S, modeOf, start, quit, fmtTime, mark, readingOf, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <template v-if="S.view === 'menu'">
    <div class="hero"><div class="hero-t"><div class="logo kanji">字</div><div><b>漢字のかきとり</b><small>指やペンで 書いてみよう！ 書き順と 形を チェックするよ。</small></div></div></div>
    <div class="card">
      <div class="h3">① 学年</div>
      <div class="gbtns"><button v-for="g in [1, 2, 3, 4, 5, 6]" :key="g" :class="{ on: S.grade === g }" @click="S.grade = g">{{ g }}年生</button></div>
      <div class="small muted" style="margin-top:8px">{{ S.grade }}年生で ならう漢字は {{ (S.args.counts || {})[S.grade] || 0 }}字。その中から {{ S.args.n }}字 出すよ。</div>
    </div>
    <div class="card">
      <div class="h3">② 書きかた</div>
      <div class="pick"><button v-for="m in S.args.modes" :key="m.id" class="pk" :class="{ on: S.mode === m.id }" @click="S.mode = m.id"><span class="grow"><b>{{ m.name }}</b><small>{{ m.desc }}</small></span></button></div>
    </div>
    <div class="card">
      <div class="h3">③ 年れい<span class="small muted">判定の ゆるさに つかうよ（低いほど ゆるい）</span></div>
      <div class="pick two"><button v-for="l in S.args.levels" :key="l.id" class="pk" :class="{ on: S.level === l.id }" @click="S.level = l.id"><span class="radio"></span><b class="lv">{{ l.id }}</b></button></div>
    </div>
    <button class="big" :disabled="S.busy" @click="start(false)">{{ S.busy ? 'じゅんび中…' : '🚀 スタート！' }}</button>
    <div class="small muted" style="margin:12px 4px 0;line-height:1.6">書き順データ：KanjiVG（CC BY-SA 3.0, kanjivg.tagaini.net）　学年・読み：KANJIDIC2（kanjiapi.dev 経由）。「とめ・はね・はらい」の細かい判定は しないよ（書き順・画数・形を 大まかに チェック）。</div>
  </template>

  <div v-show="S.view === 'play'">
    <div class="bar-top"><button class="back" @click="quit">‹ やめる</button><b>{{ S.play.grade }}年生・{{ modeOf(S.play.mode).name }}</b><span></span></div>
    <div id="game"></div>
  </div>

  <template v-if="S.view === 'end'">
    <div v-if="!S.result" class="card center wait"><div class="spin"></div>けっかを 計算中…</div>
    <template v-else>
      <h2 class="center" style="margin-top:6px">🏆 おつかれさま！</h2>
      <div class="card score">
        <div><small>点数</small><b>{{ S.result.score }}</b><i>/ 100点</i></div>
        <div><small>よくできた</small><b>{{ S.result.good }}</b><i>/ {{ S.result.items.length }}字</i></div>
        <div><small>タイム</small><b style="font-size:20px">{{ fmtTime(S.result.time) }}</b></div>
      </div>
      <div class="small muted center" style="margin-bottom:8px">{{ S.result.info }}</div>
      <button class="btn pdf" @click="Kit.openPdf(S.result.pdf)">📄 表彰状を 見る</button>
      <div class="h3" style="margin:12px 4px 6px">📋 1字ずつの けっか</div>
      <div class="kgrid">
        <div v-for="(it, k) in S.result.items" :key="k" class="kcell" :class="{ good: it.points >= (S.args.okPoints || 8), skip: it.skipped }">
          <span class="km">{{ mark(it) }}</span><b class="kc">{{ it.ch }}</b><span class="kr">{{ readingOf(it.ch) }}</span>
          <span class="kp">{{ it.points }}点</span><small>{{ it.skipped ? 'わからなかった' : 'ミス' + it.misses + '・ヒント' + it.hints }}</small>
        </div>
      </div>
      <div class="row2" style="margin-top:12px"><button class="btn pri" :disabled="S.busy" @click="start(true)">🔁 おなじ学年で もう一度</button><button class="btn" @click="S.view = 'menu'; Kit.top()">🔄 学年や書きかたを かえる</button></div>
    </template>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
