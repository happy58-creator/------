/* AI英語スピーキング（画面はぜんぶ JavaScript）。
   聞く：英語を読み上げて、意味や答えを選ぶ ／ 話す：英語を見て声に出す → その場でブラウザが判定 → 最後に録音をまとめてAIが採点
   Python へ：gen（AIで10問つくる）・done（記録と表彰状。話すモードは AI採点も）。どちらも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed } = Vue;
const TOPICS = ["どうぶつ", "たべもの", "スポーツ", "がっこう", "りょこう", "しごと"];
const COURSE_IC = { 単語: "word", 文: "lines", しつもん: "question" };
const MODE_IC = { 聞く: "headphones", 話す: "talk" };

createApp({
  components: { ic: Ic },
  setup() {
    const L = Kit.load("sp_v1", {});
    const S = reactive({
      ready: false, args: {}, view: "menu",
      level: L.level || "", mode: L.mode || "聞く", courses: L.courses || {}, slow: !!L.slow, assist: L.assist ?? true, show: L.show === "en" ? "en" : "enja", topic: "",
      busy: false, sec: 0, err: "", toast: "",
      qs: [], i: 0, pick: null, decided: null, hint: false, log: [], rows: [], run: "",
      rec: "idle", live: "", takes: [], built: [], playing: "", heard: 0, play: null,
      sending: false, result: null, pdf: "",
    });
    const keep = () => Kit.save("sp_v1", { level: S.level, mode: S.mode, courses: S.courses, slow: S.slow, assist: S.assist, show: S.show });
    function onArgs(a) {
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!S.level || !(a.levels || []).includes(S.level)) S.level = a.level;
      if (!(a.modes || []).some(m => m.id === S.mode)) S.mode = "聞く";
    }
    const modeOf = id => (S.args.modes || []).find(m => m.id === id) || { courses: [] };
    const courseList = computed(() => modeOf(S.mode).courses);
    const courseNow = computed(() => { const ids = courseList.value.map(c => c.id); return ids.includes(S.courses[S.mode]) ? S.courses[S.mode] : (ids[0] || ""); });
    const infoOf = (m, c) => modeOf(m).courses.find(x => x.id === c) || {};
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2800); }

    // ---- AIに10問たのむ（待っている秒数を見せる。90秒で ボタンをもどす）
    let waitT = 0;
    function tick(limit, onLimit) { clearInterval(waitT); S.sec = 0; waitT = setInterval(() => { S.sec++; if (limit && S.sec >= limit) { clearInterval(waitT); onLimit(); } }, 1000); }
    function start() {
      S.busy = true; S.err = ""; keep();
      tick(90, () => { S.busy = false; S.err = "AIの返事が 来ないみたい…。通信を たしかめて、もう一度 押してみてね"; });
      const want = { mode: S.mode, course: courseNow.value, level: S.level, topic: S.topic.trim() };
      Kit.ask({ type: "gen", ...want }, r => {
        clearInterval(waitT); S.busy = false;
        if (S.view !== "menu") return;
        if (r.error || !r.questions) { S.err = r.error || "うまく作れなかったよ。もう一度ためしてね"; return; }
        S.err = ""; begin(r.questions, want);
      });
    }
    function begin(qs, want) {
      // 文コース：文の単語パーツ＋ひっかけを まぜて ならべる
      S.qs = qs.map(q => q.parts ? { ...q, tiles: Kit.shuffle([...q.parts.map((p, k) => ({ id: "p" + k, ...p })), ...(q.decoys || []).map((d, k) => ({ id: "d" + k, ...d }))]) } : q);
      S.play = { slow: S.slow, assist: S.assist, show: S.show, ...want };
      S.built = [];
      S.i = 0; S.pick = null; S.decided = null; S.hint = false; S.log = []; S.rows = []; S.takes = []; S.rec = "idle"; S.live = "";
      S.result = null; S.pdf = ""; S.sending = false; S.run = Kit.uid(); S.heard = 0;
      S.view = "play"; Kit.top();
    }
    const q = computed(() => S.qs[S.i] || {});
    const isListen = computed(() => S.play && S.play.mode === "聞く");

    // ---- 読み上げ
    function say(text, slow) {
      S.playing = text;
      if (!Voice.say(text, slow, () => { if (S.playing === text) S.playing = ""; })) { S.playing = ""; toast("このブラウザは 読み上げが使えないみたい"); }
    }
    function listen(slow) { S.heard++; say(q.value.en, slow ?? S.play.slow); }

    // ---- 聞く：えらんで決定
    const score = computed(() => S.log.filter(Boolean).length);
    // 文コース：パーツをタップで ならべる・もどす
    const isBuild = computed(() => !!(q.value.parts && q.value.tiles));
    const tileOf = id => (q.value.tiles || []).find(t => t.id === id) || {};
    function put(t) { if (S.decided == null && !S.built.includes(t.id)) { S.built.push(t.id); S.pick = S.built.length >= q.value.parts.length ? builtText() : null; } }
    function pull(k) { if (S.decided == null) { S.built.splice(k, 1); S.pick = null; } }
    const builtText = () => S.built.map(id => tileOf(id).w).join(" ");
    const sameText = (a, b) => String(a).toLowerCase().replace(/[^a-z0-9' ]/g, "").replace(/\s+/g, " ").trim() === String(b).toLowerCase().replace(/[^a-z0-9' ]/g, "").replace(/\s+/g, " ").trim();
    const slotOk = k => { const t = tileOf(S.built[k]), p = (q.value.parts || [])[k]; return !!p && String(t.w).toLowerCase() === String(p.w).toLowerCase(); };
    function decide() {
      if (S.pick == null) return;
      S.decided = S.pick;
      const ok = isBuild.value ? sameText(S.pick, q.value.answer) : S.pick === q.value.answer;
      S.log.push(ok);
      S.rows.push([q.value.en + (q.value.ja ? `\n（${q.value.ja}）` : ""), S.pick, q.value.answer, ok]);
    }
    const optClass = c => S.decided == null ? { on: S.pick === c } : { right: c === q.value.answer, wrong: c === S.decided && c !== q.value.answer };
    const isRight = computed(() => S.decided != null && (isBuild.value ? sameText(S.decided, q.value.answer) : S.decided === q.value.answer));

    // ---- 話す：録音と判定
    const take = computed(() => S.takes[S.i] || null);
    async function mic() {
      if (S.rec === "rec") { Rec.stop(); S.rec = "wait"; return; }
      Voice.stop(); S.playing = "";
      S.rec = "rec"; S.live = "";
      try {
        await Rec.start(S.play.course === "単語" ? 5 : 12, {
          text: t => { S.live = t; },
          end: res => {
            if (!res.wav) { S.rec = take.value ? "done" : "idle"; toast("声が 聞こえなかったよ。もう少し大きな声で 言ってみてね"); return; }
            const canJudge = Rec.hasSR && (!res.srErr || res.srErr === "no-speech" || res.alts.length > 0);   // 聞きとりが動かなかったときは、さいごのAI採点だけ
            const m = canJudge ? Match.check(q.value.en, res.alts) : null;
            const old = S.takes[S.i]; if (old && old.url) URL.revokeObjectURL(old.url);
            S.takes[S.i] = { said: m ? m.said : res.said, pct: m ? m.pct : null, words: m ? m.words : null, wav: res.wav, url: res.url, sec: res.sec };
            S.rec = "done";
            if (m && m.pct === 100) Kit.party();
          },
        });
      } catch (e) { S.rec = take.value ? "done" : "idle"; toast(e.message || "マイクが使えないよ"); }
    }
    let mine = null;
    function playMine(url) { try { mine && mine.pause(); mine = new Audio(url); mine.play(); } catch (e) {} }
    const pctClass = p => p == null ? "" : p >= 80 ? "good" : p >= 50 ? "mid" : "low";

    // ---- つぎへ・おわり
    function next() {
      if (Rec.on) Rec.stop();
      if (S.i < S.qs.length - 1) {
        S.i++; S.pick = null; S.decided = null; S.hint = false; S.built = []; S.rec = S.takes[S.i] ? "done" : "idle"; S.live = ""; Kit.top();
        if (isListen.value) listen();          // タップのすぐあとなら、iPhone でも自動で読み上げられる
        return;
      }
      finish();
    }
    function finish() {
      Voice.stop(); Rec.release();
      S.view = "end"; S.sending = true; Kit.top();
      if (isListen.value && score.value === S.qs.length) Kit.party();
      const base = { type: "done", run: S.run, mode: S.play.mode, course: S.play.course, level: S.play.level, topic: S.play.topic };
      const extra = isListen.value ? { rows: S.rows }
        : { items: S.qs.map((x, k) => { const t = S.takes[k] || {}; return { en: x.en, said: t.said || "", audio: t.wav || "", local: t.pct || 0 }; }) };
      tick(0);
      Kit.ask({ ...base, ...extra }, r => {
        clearInterval(waitT); S.sending = false;
        if (r.error) { S.result = { error: r.error }; return; }
        S.result = r; S.pdf = r.pdf || "";
        if (!isListen.value && r.score >= 90) Kit.party();
      });
    }
    function again() { begin(S.qs, S.play); }
    let quitAt = 0;
    function quit() {
      if ((S.i > 0 || S.takes.length) && Date.now() - quitAt > 2500) { quitAt = Date.now(); toast("もう一度押すと やめます"); return; }
      Voice.stop(); Rec.release(); S.view = "menu"; Kit.top();
    }
    function toMenu() { S.view = "menu"; Kit.top(); }
    const wrong = computed(() => S.qs.filter((x, k) => S.log[k] === false));
    const scoreOf = k => S.result && S.result.scores ? S.result.scores[k] : null;
    const label = p => p ? `${p.mode === "聞く" ? "聞く" : "話す"}・${p.course}` : "";

    Streamlit.ready(onArgs);
    return { S, TOPICS, COURSE_IC, MODE_IC, Voice, Rec, keep, modeOf, courseList, courseNow, infoOf, start, q, isListen, say, listen, score, decide, optClass, isBuild, tileOf, put, pull, slotOk, isRight,
      take, mic, playMine, pctClass, next, again, quit, toMenu, wrong, scoreOf, label, Kit };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast">{{ S.toast }}</div>

  <!-- ===== えらぶ画面 ===== -->
  <template v-if="S.view === 'menu'">
    <div class="hero"><div class="hero-t"><div class="logo"><ic n="mic" :s="26"></ic></div><div><b>AI英語スピーキング</b><small>英語を 聞いて答える・見て話す。声を出して 練習しよう！</small></div></div></div>

    <div class="seg two modes">
      <button v-for="m in S.args.modes" :key="m.id" :class="{ on: S.mode === m.id }" @click="S.mode = m.id; keep()"><ic :n="MODE_IC[m.id]" :s="22"></ic><span><b>{{ m.desc }}</b></span></button>
    </div>

    <div class="card">
      <div class="h3"><ic n="user" :s="17"></ic>年れい<span v-if="S.args.age != null" class="small muted">{{ S.args.age }}さいに合わせて えらんでおいたよ</span></div>
      <div class="pick two">
        <button v-for="lv in S.args.levels" :key="lv" class="pk" :class="{ on: S.level === lv }" @click="S.level = lv"><span class="radio"></span><b class="lv">{{ lv }}</b></button>
      </div>
    </div>
    <div class="card">
      <div class="h3"><ic n="target" :s="17"></ic>コース</div>
      <div class="pick">
        <button v-for="c in courseList" :key="c.id" class="pk" :class="{ on: courseNow === c.id }" @click="S.courses[S.mode] = c.id; keep()">
          <span class="cic"><ic :n="COURSE_IC[c.id]" :s="20"></ic></span><span class="grow"><b>{{ c.id }}コース</b><small>{{ c.desc }}</small></span></button>
      </div>
    </div>
    <div class="card">
      <div class="h3"><ic n="sliders" :s="17"></ic>せってい・テーマ<span class="small muted">おこのみで</span></div>
      <template v-if="S.mode === '聞く'">
        <div class="small muted" style="margin-bottom:4px">答えの 表示</div>
        <div class="seg two"><button :class="{ on: S.show === 'en' }" @click="S.show = 'en'; keep()">英語だけ</button><button :class="{ on: S.show === 'enja' }" @click="S.show = 'enja'; keep()">英語 ＋ 日本語</button></div>
      </template>
      <button v-if="S.mode === '聞く'" class="toggle" :class="{ on: S.slow }" @click="S.slow = !S.slow; keep()"><span class="sw"></span><span class="grow"><b>はじめから ゆっくり読む</b><small class="muted tsub">あとから「ゆっくり」ボタンでも 聞けるよ</small></span></button>
      <button v-else class="toggle" :class="{ on: S.assist }" @click="S.assist = !S.assist; keep()"><span class="sw"></span><span class="grow"><b>おたすけモード</b><small class="muted tsub">カタカナの読み方と 日本語の意味を 見ながら話す</small></span></button>
      <div class="tinrow"><ic n="tag" :s="18"></ic><input class="tin" v-model="S.topic" maxlength="40" placeholder="テーマ（空らんなら おまかせ）"></div>
      <div class="sugg"><button v-for="t in TOPICS" :key="t" @click="S.topic = t">{{ t }}</button></div>
    </div>

    <div v-if="S.mode === '話す' && !Rec.canRec" class="errbox"><ic n="warn" :s="17"></ic> このブラウザは マイクが使えないみたい。Safari か Chrome で ひらいてね</div>
    <div v-else-if="S.mode === '話す' && !Rec.hasSR" class="note warn">このブラウザは その場の判定が できないので、さいごの AI先生の採点だけになるよ</div>
    <div v-if="!Voice.ok" class="note warn">このブラウザは 英語の読み上げが できないみたい</div>
    <div v-if="S.err" class="errbox"><ic n="warn" :s="17"></ic> {{ S.err }}</div>
    <button class="big" :disabled="S.busy" @click="start">
      <template v-if="S.busy"><span class="spin sm wh"></span>AI先生が 10問を 作っているよ…（{{ S.sec }}秒）</template>
      <template v-else><ic :n="S.err ? 'refresh' : 'spark'" :s="20"></ic>{{ S.err ? 'もう一度 つくってもらう' : 'AIに10問 つくってもらう' }}</template>
    </button>
    <div v-if="S.busy" class="small muted center" style="margin-top:6px">ふつうは 10〜30秒ほどで できあがるよ</div>
    <div class="small muted center" style="margin-top:8px">音が出ないときは、iPhone の消音スイッチと 音量を たしかめてね</div>
  </template>

  <!-- ===== 問題 ===== -->
  <template v-else-if="S.view === 'play'">
    <div class="bar-top"><button class="back" @click="quit"><ic n="back" :s="16"></ic>やめる</button><b>{{ label(S.play) }}・{{ S.i + 1 }} / {{ S.qs.length }}</b>
      <span class="cnt" v-if="isListen"><ic n="check" :s="15"></ic>{{ score }}</span><span v-else class="cnt">{{ S.takes.filter(Boolean).length }}回</span></div>
    <div class="prog"><i :style="{ width: (S.i / S.qs.length * 100) + '%' }"></i></div>

    <!-- 聞く -->
    <template v-if="isListen">
      <div class="card center qbox">
        <button class="bigplay" :class="{ live: S.playing === q.en }" @click="listen()"><ic n="speaker" :s="44"></ic></button>
        <div class="small muted" style="margin-top:8px">{{ S.heard ? 'もう一度 聞くときは タップ' : 'タップして 英語を 聞こう' }}</div>
        <div class="row2 mini"><button class="btn" @click="listen(true)"><ic n="slow" :s="16"></ic>ゆっくり</button><button class="btn" @click="listen(false)"><ic n="again" :s="16"></ic>ふつう</button></div>
        <div v-if="S.decided != null" class="reveal"><div class="en">{{ q.en }}</div><div class="small muted">{{ q.reading }}</div><div class="ja">{{ q.ja }}</div></div>
      </div>
      <div class="h3" style="margin:4px 4px 0">{{ infoOf(S.play.mode, S.play.course).ask }}</div>
      <template v-if="isBuild">
        <div class="build" :class="{ done: S.decided != null }">
          <span v-if="!S.built.length" class="small muted bph">下の パーツを タップして ならべよう</span>
          <button v-for="(id, k) in S.built" :key="id" class="tile on" :class="S.decided != null ? (slotOk(k) ? 'right' : 'wrong') : ''" @click="pull(k)"><b>{{ tileOf(id).w }}</b><small v-if="S.play.show === 'enja' && tileOf(id).ja">{{ tileOf(id).ja }}</small></button>
        </div>
        <div class="bank">
          <button v-for="t in q.tiles" :key="t.id" class="tile" :class="{ used: S.built.includes(t.id) }" :disabled="S.built.includes(t.id) || S.decided != null" @click="put(t)"><b>{{ t.w }}</b><small v-if="S.play.show === 'enja' && t.ja">{{ t.ja }}</small></button>
        </div>
        <button v-if="S.built.length && S.decided == null" class="link" @click="S.built = []; S.pick = null"><ic n="again" :s="14"></ic> 全部もどす</button>
      </template>
      <div v-else class="opts">
        <button v-for="(o, k) in q.options" :key="S.i + '-' + k" class="opt" :class="optClass(o.en)" :disabled="S.decided != null" @click="S.pick = o.en"><span class="mk">{{ 'ABCDE'[k] }}</span>
          <span class="grow"><b class="oen">{{ o.en }}</b><small v-if="(S.play.show === 'enja' || S.decided != null) && o.ja" class="oja">{{ o.ja }}</small></span></button>
      </div>
      <template v-if="S.decided == null">
        <div v-if="S.hint" class="note warn" style="margin-top:10px"><ic n="bulb" :s="16"></ic> {{ q.hint || 'よく聞いて 考えてみよう！' }}</div>
        <div class="row2"><button class="btn" :disabled="S.hint" @click="S.hint = true"><ic n="bulb" :s="16"></ic>ヒント</button><button class="btn pri" :disabled="S.pick == null" @click="decide"><ic n="check" :s="16"></ic>これで決定</button></div>
      </template>
      <template v-else>
        <div class="fb" :class="isRight ? 'ok' : 'ng'"><ic :n="isRight ? 'check' : 'x'" :s="18"></ic>{{ isRight ? 'せいかい！' : '正しい答えは「' + q.answer + '」' }}
          <small v-if="q.explanation">{{ q.explanation }}</small></div>
        <button class="big" @click="next">{{ S.i >= S.qs.length - 1 ? '結果を見る' : '次の問題へ' }}<ic n="next" :s="20"></ic></button>
      </template>
    </template>

    <!-- 話す -->
    <template v-else>
      <div class="card center qbox">
        <div class="h3 c">{{ infoOf(S.play.mode, S.play.course).ask }}</div>
        <div class="prompt" :class="{ long: q.en.length > 28 }">
          <template v-if="take && take.words"><span v-for="(w, k) in take.words" :key="k" :class="w.ok ? 'wok' : 'wng'">{{ w.w }} </span></template>
          <template v-else>{{ q.en }}</template>
        </div>
        <div v-if="S.play.assist" class="assist"><div v-if="q.reading" class="reading">{{ q.reading }}</div><div v-if="q.ja" class="ja">{{ q.ja }}</div></div>
        <div class="row2 mini"><button class="btn" :class="{ live: S.playing === q.en }" @click="say(q.en, false)"><ic n="speaker" :s="16"></ic>お手本</button><button class="btn" @click="say(q.en, true)"><ic n="slow" :s="16"></ic>ゆっくり</button></div>
      </div>

      <div class="micbox">
        <button class="micbtn" :class="S.rec" :disabled="S.rec === 'wait'" @click="mic"><ic :n="S.rec === 'rec' ? 'stop' : 'mic'" :s="40"></ic></button>
        <div class="micmsg">
          <template v-if="S.rec === 'rec'"><b class="recdot">聞いています…</b><span class="small muted">{{ S.live || '話しおわったら もう一度タップ' }}</span></template>
          <template v-else-if="S.rec === 'wait'"><span class="spin sm"></span> まとめています…</template>
          <template v-else-if="take"><b>もう一度 話すなら タップ</b><span class="small muted">さいごに 話した声で 採点するよ</span></template>
          <template v-else><b>タップして 話してね</b><span class="small muted">お手本を 聞いてから まねすると いいよ</span></template>
        </div>
      </div>

      <div v-if="take && S.rec !== 'rec'" class="card takecard">
        <div class="tk-top">
          <div v-if="take.pct != null" class="pct" :class="pctClass(take.pct)"><b>{{ take.pct }}</b><i>%</i></div>
          <div class="grow"><div class="small muted">聞きとれた ことば</div><div class="said">{{ take.said || '（うまく 聞きとれなかったよ）' }}</div></div>
        </div>
        <div v-if="take.pct == null" class="small muted">このブラウザでは その場の判定が できないので、さいごに AI先生が 採点するよ</div>
        <div class="row2 mini"><button class="btn" @click="playMine(take.url)"><ic n="me" :s="16"></ic>自分の声</button><button class="btn" @click="say(q.en, false)"><ic n="speaker" :s="16"></ic>お手本</button></div>
      </div>
      <div v-if="S.hint" class="note warn" style="margin-top:4px"><ic n="bulb" :s="16"></ic> {{ q.tip || q.hint }}</div>
      <div class="row2">
        <button class="btn" :disabled="S.hint" @click="S.hint = true"><ic n="bulb" :s="16"></ic>発音のコツ</button>
        <button class="btn pri" :disabled="S.rec === 'rec' || S.rec === 'wait'" @click="next">{{ S.i >= S.qs.length - 1 ? 'おわって 採点' : (take ? '次へ' : 'とばす') }}<ic n="next" :s="16"></ic></button>
      </div>
    </template>
  </template>

  <!-- ===== けっか ===== -->
  <template v-else>
    <h2 class="center endh"><ic n="award" :s="26"></ic>おつかれさま！</h2>

    <template v-if="isListen">
      <div class="card score">
        <div><small>点数</small><b>{{ Math.round(score * 100 / S.qs.length) }}</b><i>点</i></div>
        <div><small>正解</small><b>{{ score }}</b><i>/ {{ S.qs.length }}問</i></div>
        <div><small>コース</small><b style="font-size:16px">{{ S.play.course }}</b></div>
      </div>
      <div class="marks"><ic v-for="(o, k) in S.log" :key="k" :n="o ? 'check' : 'x'" :s="20" :class="o ? 'mok' : 'mng'"></ic></div>
    </template>
    <template v-else>
      <div v-if="S.sending" class="card center wait"><span class="spin"></span>AI先生が 発音を チェックしているよ…（{{ S.sec }}秒）</div>
      <template v-else-if="S.result && !S.result.error">
        <div class="card score">
          <div><small>点数（へいきん）</small><b>{{ S.result.score }}</b><i>点</i></div>
          <div><small>話した問題</small><b>{{ S.takes.filter(Boolean).length }}</b><i>/ {{ S.qs.length }}</i></div>
          <div><small>コース</small><b style="font-size:16px">{{ S.play.course }}</b></div>
        </div>
        <div v-if="S.result.aiError" class="errbox"><ic n="warn" :s="17"></ic> {{ S.result.aiError }}（ブラウザの判定で 記録したよ）</div>
        <div v-if="S.result.advice" class="aibox"><b><ic n="spark" :s="16"></ic>AI先生から</b>{{ S.result.advice }}</div>
      </template>
    </template>

    <div v-if="S.result && S.result.error" class="errbox"><ic n="warn" :s="17"></ic> {{ S.result.error }}</div>
    <button v-if="!S.sending" class="btn pdf" :disabled="!S.pdf" @click="Kit.openPdf(S.pdf)"><ic n="file" :s="16"></ic>{{ S.pdf ? '表彰状を 見る' : '表彰状は 作れなかったよ' }}</button>

    <!-- 1問ずつ -->
    <template v-if="isListen && wrong.length">
      <div class="h3" style="margin:14px 4px 8px">まちがえた問題（{{ wrong.length }}問）</div>
      <div v-for="(w, k) in wrong" :key="k" class="card rv">
        <button class="sbtn" @click="say(w.en, false)"><ic n="speaker" :s="18"></ic></button>
        <div class="grow"><b>{{ w.en }}</b><div class="small muted">{{ w.ja }}</div><div class="small">答え：<b class="okc">{{ w.answer }}</b></div></div>
      </div>
    </template>
    <template v-if="!isListen && !S.sending">
      <div class="h3" style="margin:14px 4px 8px">1問ずつの 点数</div>
      <div v-for="(x, k) in S.qs" :key="k" class="card rv">
        <div class="sc" :class="pctClass(scoreOf(k) ? scoreOf(k).score : (S.takes[k] || {}).pct)">{{ scoreOf(k) ? scoreOf(k).score : ((S.takes[k] || {}).pct ?? '—') }}</div>
        <div class="grow">
          <b>{{ x.en }}</b>
          <div class="small muted">聞こえた：{{ (scoreOf(k) && scoreOf(k).heard) || (S.takes[k] || {}).said || '（なし）' }}</div>
          <div v-if="scoreOf(k) && scoreOf(k).comment" class="small cmt">{{ scoreOf(k).comment }}</div>
          <div class="rvbtns"><button class="chip" @click="say(x.en, false)"><ic n="speaker" :s="14"></ic>お手本</button><button v-if="S.takes[k] && S.takes[k].url" class="chip" @click="playMine(S.takes[k].url)"><ic n="me" :s="14"></ic>自分の声</button></div>
        </div>
      </div>
    </template>
    <div class="row2" style="margin-top:12px"><button class="btn" @click="again"><ic n="again" :s="16"></ic>同じ問題を もう一度</button><button class="btn pri" @click="toMenu"><ic n="refresh" :s="16"></ic>べつの問題</button></div>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
