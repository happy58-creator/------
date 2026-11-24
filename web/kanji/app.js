/* 漢字のかきとり（画面はぜんぶ JavaScript）。書き取りの本体は kanji.js（KanjiGame）。
   Python へ：start（10字えらぶ）・done（書きおわった：点数・記録・表彰状）。どちらも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed, nextTick } = Vue;

createApp({
  components: { ic: Ic },
  methods: { I(n, c) { return Icon.svg(n, c); }, iO: e => Icon.of(e), iL: s => Icon.lead(s), iX: s => Icon.strip(s) },
  setup() {
    const L = Kit.load("kj_v1", {});
    const S = reactive({
      cmt: null,
      ready: false, args: {}, view: "menu",
      grade: L.grade || 1, mode: L.mode || "trace", level: L.level || "", th: !!L.th,
      play: {}, busy: false, result: null, toast: "", run: "",
    });
    const keep = () => Kit.save("kj_v1", { grade: S.grade, mode: S.mode, level: S.level, th: S.th });
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.level || !(a.levels || []).some(l => l.id === S.level)) S.level = a.level;
    }
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2600); }
    const modeOf = id => (S.args.modes || []).find(m => m.id === id) || {};
    const tolOf = id => ((S.args.levels || []).find(l => l.id === id) || {}).tol || 20;

    let game = null;
    function start(again, kind) {
      if (!again) S.play = { grade: S.grade, mode: S.mode, level: S.level, th: S.th, kind: kind || "new" };
      S.busy = true; S.err = ""; keep();
      Kit.ask({ type: "start", grade: S.play.grade, kind: S.play.kind, level: S.play.level }, r => {
        S.busy = false;
        if (r.error || !r.kanjis) { S.err = r.error || "うまくいかなかったよ"; toast(S.err); return; }
        S.run = Kit.uid(); S.result = null; S.cmt = null; S.view = "play"; Kit.top();
        nextTick(() => {        // 書き取りの本体（kanji.js）を、この画面の中に出す
          const box = document.getElementById("game"); box.innerHTML = "";
          game = new KanjiGame(box, { kanjis: r.kanjis, mode: S.play.mode, tol: tolOf(S.play.level), tomehane: S.play.th, round: S.run }, done);
        });
      });
    }
    function done(v) {
      S.view = "end"; S.result = null; Kit.top();
      const results = v.results.map(({ img, cmp, facts, ...x }) => x);       // 記録には 画像を入れない
      Kit.ask({ type: "done", run: S.run, grade: S.play.grade, mode: S.play.mode, level: S.play.level, th: S.play.th, results }, r => {
        if (r.error) { toast(r.error); return; }
        S.result = { ...r, time: v.time, items: v.results };
        if (r.score >= 90) Kit.party();
        askComment(v.results);
      });
    }
    // AI先生のひとこと：書いた字の画像を まとめて1回で送る（とめ・はね・はらい・バランス）
    function askComment(items) {
      const list = items.map((it, i) => ({ ...it, i })).filter(it => it.img);
      if (!list.length) return;
      S.cmt = { busy: true, sec: 0, items: {}, overall: "", error: "" };
      const run = S.run, t = setInterval(() => { if (S.cmt && S.cmt.busy) S.cmt.sec++; else clearInterval(t); }, 1000);
      Kit.ask({ type: "comment", run, level: S.play.level, mode: S.play.mode, th: S.play.th,
        items: list.map(it => ({ i: it.i, ch: it.ch, img: it.cmp || it.img, cmp: !!it.cmp, points: it.points, misses: it.misses, endMiss: it.endMiss || 0, facts: it.facts || [] })) }, r => {
        clearInterval(t);
        if (S.run !== run) return;
        S.cmt = { busy: false, sec: 0, items: r.items || {}, overall: r.overall || "", error: r.error || "" };
      });
    }
    let quitAt = 0;
    function quit() {
      if (Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと やめて メニューに もどるよ"); return; }
      game = null; S.view = "menu"; Kit.top();
    }
    const fmtTime = s => { const m = Math.floor(s / 60), r = Math.round((s % 60) * 10) / 10; return m ? `${m}分 ${r}秒` : `${r}秒`; };
    const mark = it => it.points >= 9 ? "award" : it.points >= (S.args.okPoints || 8) ? "star" : !it.skipped ? "thumb" : "minus";   // けっかの しるし（アイコン）
    const readingOf = ch => ((S.result && S.result.rows) || []).find(r => r.ch === ch)?.reading || "";
    Streamlit.ready(onArgs);
    return { S, modeOf, start, quit, fmtTime, mark, readingOf, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast"><ic v-if="iL(S.toast)[0]" :n="iL(S.toast)[0]"></ic>{{ iX(iL(S.toast)[1]) }}</div>

  <template v-if="S.view === 'menu'">
    <div class="hero"><div class="hero-t"><div class="logo kanji">字</div><div><b>漢字のかきとり</b><small>指やペンで 書いてみよう！ 書き順と 形を チェックするよ。</small></div></div></div>
    <div class="card">
      <div class="h3">① 学年</div>
      <div class="gbtns"><button v-for="g in [1, 2, 3, 4, 5, 6]" :key="g" :class="{ on: S.grade === g }" @click="S.grade = g">{{ g }}年生</button></div>
      <div class="small muted" style="margin-top:8px">{{ S.grade }}年生で ならう漢字は {{ (S.args.counts || {})[S.grade] || 0 }}字。その中から {{ S.args.n }}字 出すよ。</div>
    </div>
    <div class="card">
      <div class="h3">② 書きかた</div>
      <div class="pick"><button v-for="m in S.args.modes" :key="m.id" class="pk" :class="{ on: S.mode === m.id }" @click="S.mode = m.id"><span class="grow"><b><ic v-if="iL(m.name)[0]" :n="iL(m.name)[0]"></ic>{{ iX(iL(m.name)[1]) }}</b><small>{{ m.desc }}</small></span></button></div>
    </div>
    <div class="card">
      <div class="h3">③ 年れい<span class="small muted">判定の ゆるさに つかうよ（低いほど ゆるい）</span></div>
      <div class="pick two"><button v-for="l in S.args.levels" :key="l.id" class="pk" :class="{ on: S.level === l.id }" @click="S.level = l.id"><span class="radio"></span><b class="lv">{{ l.id }}</b></button></div>
    </div>
    <div class="card">
      <div class="h3">④ とめ・はね・はらい<span class="small muted">オンにすると、線の さいごの形も 判定するよ</span></div>
      <div class="pick two">
        <button class="pk" :class="{ on: !S.th }" @click="S.th = false"><span class="radio"></span><b class="lv">オフ（いままでどおり）</b></button>
        <button class="pk" :class="{ on: S.th }" @click="S.th = true"><span class="radio"></span><b class="lv"><ic n="brush"></ic>オン（とめ・はねも 見る）</b></button>
      </div>
      <div class="small" style="margin-top:8px;line-height:1.6;color:#b45309"><ic n="pen"></ic><b>タッチペンが おすすめ</b>：指より 線の さいごの 動きが 正しく つたわるので、とめ・はね・はらい が 判定されやすく、字も きれいに なるよ。</div>
    </div>
    <div v-if="S.args.weak" class="card weakc">
      <div class="h3"><ic n="target"></ic>苦手の 練習<span class="small muted">前に うまく 書けなかった字が {{ S.args.weak }}字 あるよ（学年は 関係なく 出るよ）</span></div>
      <div class="row2">
        <button class="btn" :disabled="S.busy" @click="start(false, 'weak')"><ic n="again"></ic>苦手だけ もう一回</button>
        <button class="btn" :disabled="S.busy" @click="start(false, 'weakai')"><ic n="spark"></ic>苦手な字を 使った文で（AI）</button>
      </div>
      <div class="small muted" style="margin-top:6px">「文で」は、AIが 苦手な字を 使った 文を 作るよ（AIを 1回 使う）。③で「読みから書く」を えらぶと、文だけを 見て 書く 練習に なるよ</div>
    </div>
    <div v-if="S.err" class="small" style="color:#b91c1c;margin:6px 4px">{{ S.err }}</div>
    <button class="big" :disabled="S.busy" @click="start(false)"><ic v-if="iL(S.busy ? 'じゅんび中…' : '🚀 スタート！')[0]" :n="iL(S.busy ? 'じゅんび中…' : '🚀 スタート！')[0]"></ic>{{ iX(iL(S.busy ? 'じゅんび中…' : '🚀 スタート！')[1]) }}</button>
    <div class="small muted" style="margin:12px 4px 0;line-height:1.6">書き順データ：KanjiVG（CC BY-SA 3.0, kanjivg.tagaini.net）　学年・読み：KANJIDIC2（kanjiapi.dev 経由）。書き順・画数・形を 大まかに チェックするよ。④を オンにすると、線の さいごが「とめ・はね・はらい」に なっているかも 見るよ（タッチペン おすすめ。はっきりしない画は 判定しないよ）。</div>
  </template>

  <div v-show="S.view === 'play'">
    <div class="bar-top"><button class="back" @click="quit">‹ やめる</button><b>{{ S.play.kind && S.play.kind !== 'new' ? '苦手' : S.play.grade + '年生' }}・<template v-if="S.play.th">とめはね・</template><ic v-if="iL(modeOf(S.play.mode).name)[0]" :n="iL(modeOf(S.play.mode).name)[0]"></ic>{{ iX(iL(modeOf(S.play.mode).name)[1]) }}</b><span></span></div>
    <div id="game"></div>
  </div>

  <template v-if="S.view === 'end'">
    <div v-if="!S.result" class="card center wait"><div class="spin"></div>けっかを 計算中…</div>
    <template v-else>
      <h2 class="center" style="margin-top:6px"><ic n="trophy"></ic>おつかれさま！</h2>
      <div class="card score">
        <div><small>点数</small><b>{{ S.result.score }}</b><i>/ 100点</i></div>
        <div><small>よくできた</small><b>{{ S.result.good }}</b><i>/ {{ S.result.items.length }}字</i></div>
        <div><small>タイム</small><b style="font-size:20px">{{ fmtTime(S.result.time) }}</b></div>
      </div>
      <div class="small muted center" style="margin-bottom:8px">{{ S.result.info }}</div>
      <button class="btn pdf" @click="Kit.openPdf(S.result.pdf)"><ic n="file"></ic>表彰状を 見る</button>
      <div class="h3" style="margin:12px 4px 6px"><ic n="clip"></ic>1字ずつの けっか</div>
      <div class="kgrid">
        <div v-for="(it, k) in S.result.items" :key="k" class="kcell" :class="{ good: it.points >= (S.args.okPoints || 8), skip: it.skipped }">
          <span class="km" :class="mark(it)"><ic :n="mark(it)"></ic></span><b class="kc">{{ it.ch }}</b><span class="kr">{{ readingOf(it.ch) }}</span>
          <span class="kp">{{ it.points }}点</span><small>{{ it.skipped ? 'わからなかった' : 'ミス' + it.misses + '・ヒント' + it.hints }}<template v-if="S.play.th && !it.skipped"><br>とめはね{{ it.endMiss || 0 }}</template></small>
        </div>
      </div>
      <template v-if="S.cmt">
        <div class="h3" style="margin:14px 4px 6px"><ic n="spark"></ic>AI先生の ひとこと</div>
        <div v-if="S.cmt.busy" class="card center wait"><div class="spin"></div>書いた字を 見ているよ…（{{ S.cmt.sec }}秒）</div>
        <div v-else-if="S.cmt.error" class="small muted" style="margin:0 4px">{{ S.cmt.error }}</div>
        <template v-else>
          <div v-if="S.cmt.overall" class="card aibox">{{ S.cmt.overall }}</div>
          <div class="cmts">
            <template v-for="(it, k) in S.result.items" :key="k">
              <div v-if="it.img && S.cmt.items[k + ':' + it.ch]" class="cmt">
                <img :src="it.img" alt=""><div><b class="kc">{{ it.ch }}</b><p>{{ S.cmt.items[k + ':' + it.ch] }}</p></div>
              </div>
            </template>
          </div>
        </template>
      </template>
      <div class="row2" style="margin-top:12px"><button class="btn pri" :disabled="S.busy" @click="start(true)"><ic n="again"></ic>{{ S.play.kind === 'new' ? 'おなじ学年で もう一度' : '苦手で もう一度' }}</button><button class="btn" @click="S.view = 'menu'; Kit.top()"><ic n="refresh"></ic>学年や書きかたを かえる</button></div>
    </template>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
