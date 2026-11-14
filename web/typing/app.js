/* AIタイピングマスター（画面はぜんぶ JavaScript）。ゲームの本体は typing.js（TypingGame）・code.js（CodeGame・Sandbox）。
   Python へ：gen（AIで10問つくる）・typing_done / code_done（おわった：点数・記録・表彰状）。どれも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed, nextTick } = Vue;
const MODES = [["みながらモード", "👀", "ローマ字が みえるよ"], ["あんもくモード", "🙈", "ひらがなだけで ちょうせん！"]];
const THEMES = ["どうぶつ", "マインクラフト", "おかし", "うちゅう", "サッカー", "きょうりゅう"];

createApp({
  setup() {
    const L = Kit.load("ty_v1", {});
    const S = reactive({
      ready: false, args: {}, view: "menu",           // menu・play・end・code・codeEnd・sandbox
      mode: L.mode || "みながらモード", level: L.level || "", theme: "",
      play: {}, issues: [], busy: false, result: null, raw: null, toast: "", run: "", unlockedNow: false,
    });
    const keep = () => Kit.save("ty_v1", { mode: S.mode, level: S.level });
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.level || !(a.levels || []).includes(S.level)) S.level = a.level;
    }
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2600); }
    const ura = computed(() => S.args.unlocked || S.args.adminUra || S.unlockedNow);

    // ゲームの本体を、この画面の #game の中に出す
    // ゲームが window につけた キー・フォーカスの見張りと 時計は、やめるときに ぜんぶ外す（前のゲームが 動きつづけないように）
    let cleanup = [];
    function dispose() { cleanup.forEach(f => { try { f(); } catch (e) {} }); cleanup = []; }
    function mount(make) {
      dispose();
      nextTick(() => {
        const box = document.getElementById("game"); box.innerHTML = "";
        const addL = window.addEventListener, setI = window.setInterval, ls = [], ts = [];
        window.addEventListener = function (t, f, o) { ls.push([t, f, o]); return addL.call(window, t, f, o); };
        window.setInterval = function (f, ms, ...x) { const id = setI.call(window, f, ms, ...x); ts.push(id); return id; };
        try { make(box); } finally { window.addEventListener = addL; window.setInterval = setI; }
        cleanup = [() => ls.forEach(([t, f, o]) => window.removeEventListener(t, f, o)), () => ts.forEach(id => clearInterval(id))];
      });
    }
    function start() {
      const theme = S.theme.trim();
      if (!theme) { toast("⚠️ 言葉を 入力してね！"); return; }
      S.busy = true; keep();
      Kit.ask({ type: "gen", theme }, r => {
        S.busy = false;
        if (r.error || !r.issues) { toast(r.error || "うまく作れなかったよ。もう一度ためしてね"); return; }
        S.issues = r.issues; S.play = { theme: r.theme, mode: S.mode, level: S.level };
        playTyping();
      });
    }
    function playTyping() {
      S.run = Kit.uid(); S.result = null; S.view = "play"; Kit.top();
      mount(box => new TypingGame(box, { issues: S.issues, mode: S.play.mode, round: S.run }, v => {
        S.raw = v; S.view = "end"; Kit.top(); dispose();
        Kit.ask({ type: "typing_done", run: S.run, result: v, issues: S.issues, ...S.play }, r => {
          if (r.error) { toast(r.error); return; }
          S.result = r; if (r.unlocked) S.unlockedNow = true;
          Kit.party();
        });
      }));
    }
    function playCode() {
      S.run = Kit.uid(); S.result = null; S.view = "code"; Kit.top();
      mount(box => new CodeGame(box, { round: S.run }, v => {
        S.raw = v; S.view = "codeEnd"; Kit.top(); dispose();
        Kit.ask({ type: "code_done", run: S.run, result: v, level: S.level }, r => { if (!r.error) { S.result = r; Kit.party(); } });
      }));
    }
    function playSandbox() { S.view = "sandbox"; Kit.top(); mount(box => new Sandbox(box, {})); }
    let quitAt = 0;
    function quit(force) {
      if (!force && Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと やめて メニューに もどるよ"); return; }
      dispose();
      const box = document.getElementById("game"); if (box) box.innerHTML = "";
      S.view = "menu"; Kit.top();
    }
    const fmtTime = s => { const m = Math.floor(s / 60), r = Math.round((s % 60) * 10) / 10; return m ? `${m}分 ${r}秒` : `${r}秒`; };
    const weak = computed(() => ((S.raw && S.raw.weakKeys) || []).map(([k, n]) => `「${String(k).toUpperCase()}」（${n}回）`).join("、"));
    Streamlit.ready(onArgs);
    return { S, MODES, THEMES, ura, start, playTyping, playCode, playSandbox, quit, fmtTime, weak, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <template v-if="S.view === 'menu'">
    <div class="hero"><div class="hero-t"><div class="logo">⌨</div><div><b>AIタイピングマスター</b><small>すきな テーマを 入れると、AIが キミ専用の もんだいを 10問 つくるよ！</small></div></div></div>
    <div class="card">
      <div class="h3">① モード</div>
      <div class="pick two"><button v-for="m in MODES" :key="m[0]" class="pk" :class="{ on: S.mode === m[0] }" @click="S.mode = m[0]"><span class="ic">{{ m[1] }}</span><span class="grow"><b>{{ m[0] }}</b><small>{{ m[2] }}</small></span></button></div>
    </div>
    <div class="card">
      <div class="h3">② 年れい<span class="small muted">点数の「スピード」の目標に つかうよ</span></div>
      <div class="pick two"><button v-for="lv in S.args.levels" :key="lv" class="pk" :class="{ on: S.level === lv }" @click="S.level = lv"><span class="radio"></span><b class="lv">{{ lv }}</b></button></div>
    </div>
    <div class="card">
      <div class="h3">③ テーマ<span class="small muted">すきな 言葉（キーワード）</span></div>
      <input class="tin" v-model="S.theme" maxlength="40" placeholder="ここに 文字を 入力してね" @keydown.enter.prevent="!$event.isComposing && start()">
      <div class="sugg"><button v-for="t in THEMES" :key="t" @click="S.theme = t">{{ t }}</button></div>
    </div>
    <button class="big" :disabled="S.busy" @click="start">{{ S.busy ? '🧙‍♂️ AI先生が 10問を 作っているよ…' : '🚀 AIに もんだいを 作ってもらって スタート！' }}</button>
    <div class="small muted" style="margin:10px 4px 0">コツ：「si / shi」「ti / chi」「tu / tsu」など、どの打ち方でも 正解に なるよ！ 1文字ずつ その場で 判定するよ。</div>
    <div v-if="ura" class="card ura">
      <div class="h3">{{ S.args.adminUra && !S.args.unlocked ? '🛡️ 裏メニュー（管理者の直接入口）' : '🔓 ひらいた 裏メニュー' }}</div>
      <div class="row2"><button class="btn pri" @click="playCode">🤖 プログラミング・ミッション</button><button class="btn" @click="playSandbox">🎨 じゆうに プログラミング</button></div>
    </div>
    <div v-else class="small muted center" style="margin-top:12px">💡 5分（300秒）以内に クリアすると、ひみつの「裏メニュー」が 出てくるよ！</div>
  </template>

  <div v-show="['play', 'code', 'sandbox'].includes(S.view)">
    <div class="bar-top"><button class="back" @click="quit(S.view === 'sandbox')">‹ {{ S.view === 'sandbox' ? 'メニュー' : 'やめる' }}</button>
      <b>{{ S.view === 'play' ? 'テーマ：' + S.play.theme : S.view === 'code' ? '💻 プログラミング・ミッション' : '🎨 じゆうに プログラミング' }}</b><span></span></div>
    <div v-if="S.view === 'sandbox'" class="small muted" style="margin:-4px 4px 8px">左に コードを 書いて「▶ じっこう」。ほしを ぜんぶ あつめたり、色で 絵を かいたり してみよう！</div>
    <div id="game"></div>
  </div>

  <template v-if="S.view === 'end'">
    <div v-if="!S.result" class="card center wait"><div class="spin"></div>けっかを 計算中…</div>
    <template v-else>
      <h2 class="center" style="margin-top:6px">🏆 タイピング大冒険クリア！</h2>
      <div class="note good center">{{ S.result.rankText }}</div>
      <div class="card score one"><div><small>点数</small><b>{{ S.result.score }}</b><i>/ 100点</i></div></div>
      <div class="small muted center" style="margin:-4px 0 10px">✅ 正確さ {{ S.result.accuracyPt }} / 60点 ＋ ⚡ スピード {{ S.result.speedPt }} / 40点（{{ S.play.level }}）</div>
      <div class="stats">
        <div><small>🎯 ノーミス正解</small><b>{{ S.raw.perfect }} / {{ S.raw.total }}問</b></div>
        <div><small>⏱️ ごうけいタイム</small><b>{{ fmtTime(S.raw.time) }}</b></div>
        <div><small>⚡ はやさ</small><b>{{ S.raw.kpm }} 打/分</b></div>
        <div><small>✅ 正確さ</small><b>{{ S.raw.accuracy }} %</b></div>
        <div><small>❌ ミスタイプ</small><b>{{ S.raw.misses }} 回</b></div>
        <div><small>🔥 さいだいコンボ</small><b>{{ S.raw.maxCombo }}</b></div>
      </div>
      <div v-if="S.raw.misses === 0" class="note good">✨ ノーミス達成！ パーフェクト！</div>
      <div v-else-if="weak" class="note warn">🔍 まちがえやすかったキー：{{ weak }}　つぎは ここを 意識してみよう！</div>
      <button class="btn pdf" @click="Kit.openPdf(S.result.pdf)">📄 表彰状を 見る</button>
      <div v-if="S.result.unlocked" class="gate">
        <b>✨ 5分以内で クリア達成！ ひみつのゲートが 開いたよ！ ✨</b>
        <p>本物の Python のコードを 打つと ロボットが 動く「プログラミング・ミッション（全6ステージ）」に 挑戦しよう！</p>
        <button class="big" @click="playCode">🔥 プログラミング・ミッションを 始める！</button>
      </div>
      <div v-else class="note warn">💡 5分（300秒）以内で クリアすると、特別な「裏メニュー」が 出現するよ！ 次は もっと早く 打てるように 挑戦してみよう！</div>
      <div class="row2" style="margin-top:10px"><button class="btn pri" @click="playTyping">🔁 同じ もんだいで もう一度</button><button class="btn" @click="quit(true)">🔄 別の テーマで 遊ぶ</button></div>
    </template>
  </template>

  <template v-if="S.view === 'codeEnd'">
    <div v-if="!S.result" class="card center wait"><div class="spin"></div>けっかを 計算中…</div>
    <template v-else>
      <h2 class="center" style="margin-top:6px">👑 プログラミング・マスター達成！</h2>
      <div class="card score one"><div><small>点数</small><b>{{ S.result.score }}</b><i>/ 100点</i></div></div>
      <div class="stats three">
        <div><small>🌟 ノーミス ステージ</small><b>{{ S.raw.perfect }} / {{ S.raw.stages }}</b></div>
        <div><small>❌ バグ（ミス）</small><b>{{ S.raw.misses }} 回</b></div>
        <div><small>⏱️ クリアタイム</small><b>{{ fmtTime(S.raw.time) }}</b></div>
      </div>
      <div class="note good">🤖 全ステージ クリア おめでとう！ move・for・変数・if は、本物の プログラマーも 毎日つかっている 命令だよ。つぎは「じゆうモード」で、自分だけの プログラムを 書いてみよう！</div>
      <button class="btn pdf" @click="Kit.openPdf(S.result.pdf)">📄 表彰状を 見る</button>
      <div class="row2"><button class="btn pri" @click="playSandbox">🎨 じゆうに プログラミングする</button><button class="btn" @click="quit(true)">🔄 もう一度 最初から 遊ぶ</button></div>
    </template>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
