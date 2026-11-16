/* せいせきの履歴（画面はぜんぶ JavaScript）。
   Python へ：load（えらんだシートの記録）・pdf（その回の結果をPDFに）。どちらも nonce つき（kit.js） */
"use strict";
const { createApp, reactive, computed } = Vue;
const ICON = { 計算: "calc", 国語: "book", 英語: "lang", スピーキング: "mic", タイピング: "keyboard", プログラミング: "code", 漢字: "pen", 連打: "zap", チェス: "crown", ストーリー: "swords",
  ITパスポート: "monitor", 基本情報: "terminal", 学習: "checkc", ログイン: "lock", 入力チェック: "alarm" };
const SCORE_COLS = ["点数", "回数", "ノーミス正解"];
const PAGE = 30;

createApp({
  components: { ic: Ic },
  methods: { I(n, c) { return Icon.svg(n, c); }, iO: e => Icon.of(e), iL: s => Icon.lead(s), iX: s => Icon.strip(s) },
  setup() {
    const L = Kit.load("hist_v1", {});
    const S = reactive({ ready: false, args: {}, sheet: L.sheet || "", who: "みんな", data: {}, busy: "", pdfBusy: -1, toast: "", more: PAGE, open: -1, voice: {}, vbusy: "", playing: "" });
    function onArgs(a) {
      const first = !S.ready;
      S.args = a; S.ready = true; Kit.takeReply(a);
      if (!(a.sheets || []).includes(S.sheet)) S.sheet = (a.sheets || [])[0] || "";
      if (first && S.sheet) load(S.sheet);
    }
    let toastT = 0;
    function toast(m) { Kit.placeToast(); S.toast = m; clearTimeout(toastT); toastT = setTimeout(() => S.toast = "", 2600); }
    function load(sheet, fresh) {
      S.sheet = sheet; S.more = PAGE; S.open = -1; S.who = "みんな"; Kit.save("hist_v1", { sheet });
      if (S.data[sheet] && !fresh) return;
      S.busy = sheet;
      Kit.ask({ type: "load", sheet, fresh: !!fresh }, r => {
        if (S.busy === sheet) S.busy = "";
        if (r.error) { toast(r.error); return; }
        S.data[r.sheet] = { cols: r.cols, rows: r.rows, locks: r.locks, lockMax: r.lockMax, keep: r.keep };
      });
    }
    const cur = computed(() => S.data[S.sheet] || null);
    const names = computed(() => [...new Set(((cur.value || {}).rows || []).map(r => String(r["名前"])))].sort());
    const rows = computed(() => {
      const all = (cur.value || {}).rows || [];
      return S.args.admin && S.who !== "みんな" ? all.filter(r => String(r["名前"]) === S.who) : all;
    });
    const newest = computed(() => [...rows.value].reverse());
    const scoreCol = computed(() => SCORE_COLS.find(c => ((cur.value || {}).cols || []).includes(c)) || "");
    const scores = computed(() => rows.value.map(r => parseFloat(r[scoreCol.value])).filter(v => isFinite(v)));
    const best = computed(() => scores.value.length ? Math.max(...scores.value) : null);
    const avg = computed(() => scores.value.length ? Math.round(scores.value.reduce((a, b) => a + b, 0) / scores.value.length * 10) / 10 : null);
    // 点数の線グラフ（新しい30回）
    const chart = computed(() => {
      const v = scores.value.slice(-30);
      if (v.length < 2) return null;
      const W = 320, H = 110, max = Math.max(...v, 1), min = Math.min(...v, 0), span = max - min || 1;
      const pts = v.map((y, i) => [8 + i * (W - 16) / (v.length - 1), H - 10 - (y - min) / span * (H - 24)]);
      return { W, H, line: pts.map(p => p.map(n => n.toFixed(1)).join(",")).join(" "), pts, max, min, last: v[v.length - 1] };
    });
    // 1行の見出し：日時・（名前）・点数、それ以外の列は小さく
    const sideCols = computed(() => ((cur.value || {}).cols || []).filter(c => !["日時", "名前", scoreCol.value].includes(c)));
    function openPdf(r) {
      S.pdfBusy = r._i;
      Kit.ask({ type: "pdf", sheet: S.sheet, i: r._i }, x => { S.pdfBusy = -1; if (x.error) toast(x.error); else Kit.openPdf(x.pdf); });
    }
    function csv() {
      const cols = (cur.value || {}).cols || [];
      const q = s => `"${String(s ?? "").replace(/"/g, '""')}"`;
      const text = "﻿" + [cols.map(q).join(","), ...rows.value.map(r => cols.map(c => q(r[c])).join(","))].join("\r\n");
      const blob = new Blob([text], { type: "text/csv" }), url = URL.createObjectURL(blob);
      try {      // トップの画面で保存する（スマホでも保存しやすい）
        const doc = window.parent.document, a = doc.createElement("a");
        a.href = url; a.download = `履歴_${S.sheet}.csv`; doc.body.appendChild(a); a.click(); a.remove();
      } catch (e) { const a = document.createElement("a"); a.href = url; a.download = `履歴_${S.sheet}.csv`; document.body.appendChild(a); a.click(); a.remove(); }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    }
    const when = d => String(d || "").slice(0, 16);
    Streamlit.ready(onArgs);
    // ---- 録音（AI英語スピーキング「話す」）：聞く・鍵をかける
    function openVoice(r) {
      if (S.voice[r._rec]) { S.voice[r._rec].show = !S.voice[r._rec].show; return; }
      S.vbusy = r._rec;
      Kit.ask({ type: "voice", sheet: S.sheet, key: r._rec }, x => {
        S.vbusy = "";
        if (x.error) { toast(x.error); return; }
        S.voice[x.key] = { ...x, show: true };
      });
    }
    let audio = null;
    function play(key, k) {
      const v = S.voice[key], b64 = v && v.clips[k]; if (!b64) return;
      try { audio && audio.pause(); } catch (e) {}
      audio = new Audio(`data:${v.mime};base64,${b64}`); S.playing = key + k;
      audio.onended = audio.onerror = () => { if (S.playing === key + k) S.playing = ""; };
      audio.play().catch(() => { S.playing = ""; toast("このブラウザでは 再生できないみたい"); });
    }
    function lock(r) {
      const on = !r._lock;
      S.vbusy = "L" + r._rec;
      Kit.ask({ type: "lock", sheet: S.sheet, key: r._rec, on }, x => {
        S.vbusy = "";
        if (x.error) { toast(x.error); return; }
        toast(x.msg);
        if (x.ok) { r._lock = x.lock; const d = S.data[S.sheet]; if (d && d.locks != null) d.locks = x.locks; }
      });
    }
    return { S, ICON, openVoice, play, lock, load, cur, names, rows, newest, scoreCol, best, avg, chart, sideCols, openPdf, csv, when };
  },
  template: `
<div class="wrap" v-if="S.ready">
  <div v-if="S.toast" class="toast"><ic v-if="iL(S.toast)[0]" :n="iL(S.toast)[0]"></ic>{{ iX(iL(S.toast)[1]) }}</div>
  <div class="hero"><div class="hero-t"><div class="logo"><ic n="clip"></ic></div><div><b>せいせきの履歴</b><small>これまでの記録を 見よう！</small></div></div></div>
  <div class="tabs"><button v-for="s in S.args.sheets" :key="s" :class="{ on: S.sheet === s }" @click="load(s)"><span><ic :n="ICON[s] || 'file'"></ic></span>{{ s }}</button></div>

  <div v-if="S.busy === S.sheet && !cur" class="card center wait"><div class="spin"></div>読みこみ中…</div>
  <template v-else-if="cur">
    <div v-if="S.args.admin && names.length" class="card who">
      <div class="h3"><ic n="user"></ic>だれの記録？</div>
      <div class="chips"><button class="chip" :class="{ on: S.who === 'みんな' }" @click="S.who = 'みんな'; S.more = 30">みんな</button>
        <button v-for="n in names" :key="n" class="chip" :class="{ on: S.who === n }" @click="S.who = n; S.more = 30">{{ n }}</button></div>
    </div>
    <div v-else-if="!S.args.admin" class="small muted" style="margin:0 4px 8px">{{ S.args.me }} さんの記録だけ 表示しています。</div>

    <div v-if="!rows.length" class="card center muted">まだ記録がないよ。あそぶと、ここに 残るよ！</div>
    <template v-else>
      <div class="stats3">
        <div><small>あそんだ回数</small><b>{{ rows.length }}</b><i>回</i></div>
        <div v-if="scoreCol"><small>ベスト（{{ scoreCol }}）</small><b>{{ best ?? '—' }}</b></div>
        <div v-if="scoreCol"><small>平均</small><b>{{ avg ?? '—' }}</b></div>
      </div>
      <div v-if="chart" class="card chart">
        <div class="small muted">{{ scoreCol }}の うつりかわり（新しい{{ Math.min(30, rows.length) }}回）</div>
        <svg :viewBox="'0 0 ' + chart.W + ' ' + chart.H" preserveAspectRatio="none">
          <polyline :points="chart.line" fill="none" stroke="var(--pri)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
          <circle v-for="(p, k) in chart.pts" :key="k" :cx="p[0]" :cy="p[1]" r="3" fill="#fff" stroke="var(--pri)" stroke-width="2" />
        </svg>
        <div class="axis"><span>{{ chart.min }}</span><span>さいご {{ chart.last }}</span><span>{{ chart.max }}</span></div>
      </div>

      <div class="h3" style="margin:12px 4px 6px"><ic n="folder"></ic>記録（新しい順）<button class="link" style="margin-left:auto;padding:0" @click="load(S.sheet, true)">↻ 読みなおす</button></div>
      <div class="list">
        <div v-for="r in newest.slice(0, S.more)" :key="r._i" class="rec" :class="{ open: S.open === r._i }">
          <button class="rhead" @click="S.open = S.open === r._i ? -1 : r._i">
            <span class="grow"><b>{{ when(r['日時']) }}<ic v-if="r._lock" n="lock" class="lk"></ic><ic v-else-if="r._rec" n="headphones" class="hp"></ic></b><small v-if="S.args.admin">{{ r['名前'] }}</small><small class="side">{{ sideCols.slice(0, 2).map(c => r[c]).filter(Boolean).join('・') }}</small></span>
            <em v-if="scoreCol && r[scoreCol] !== ''" class="sc">{{ r[scoreCol] }}<i v-if="scoreCol === '点数'">点</i></em><span class="achev">{{ S.open === r._i ? '▲' : '▼' }}</span>
          </button>
          <div v-if="S.open === r._i" class="rbody">
            <div v-for="c in sideCols" :key="c" class="kv"><span>{{ c }}</span><b>{{ r[c] === '' ? '—' : r[c] }}</b></div>
            <div v-if="r._rec" class="voice">
              <div class="vrow">
                <button class="btn" :disabled="S.vbusy === r._rec" @click="openVoice(r)"><ic n="headphones"></ic>{{ S.vbusy === r._rec ? '読みこみ中…' : (S.voice[r._rec] && S.voice[r._rec].show ? '録音を とじる' : '録音を 聞く') }}</button>
                <button class="btn lockb" :class="{ on: r._lock }" :disabled="S.vbusy === 'L' + r._rec" @click="lock(r)"><ic n="lock"></ic>{{ r._lock ? '鍵をはずす' : '鍵をかける' }}</button>
              </div>
              <div class="small muted">鍵をかけた録音は 消えません{{ cur.locks != null ? '（' + cur.locks + ' / ' + cur.lockMax + '）' : '（1人' + cur.lockMax + '回まで）' }}。鍵のない録音は 新しい{{ cur.keep }}回だけ残ります</div>
              <div v-if="S.voice[r._rec] && S.voice[r._rec].show" class="vlist">
                <div v-for="(t, k) in S.voice[r._rec].texts" :key="k" v-show="t" class="vitem">
                  <button class="vplay" :class="{ live: S.playing === r._rec + k }" :disabled="!S.voice[r._rec].clips[k]" @click="play(r._rec, k)"><ic :n="S.voice[r._rec].clips[k] ? 'play' : 'x'"></ic></button>
                  <span class="grow">{{ t }}<small v-if="!S.voice[r._rec].clips[k]" class="muted">（録音なし）</small></span>
                </div>
              </div>
            </div>
            <div v-else-if="r._gone" class="small muted" style="margin:6px 0">録音は もう残っていません（新しい{{ cur.keep }}回と、鍵をかけた回だけ残ります）</div>
            <button v-if="r._pdf" class="btn pdf" :disabled="S.pdfBusy === r._i" @click="openPdf(r)"><ic v-if="iL(S.pdfBusy === r._i ? 'PDFを 作っています…' : '📄 そのときの結果を PDFで 見る')[0]" :n="iL(S.pdfBusy === r._i ? 'PDFを 作っています…' : '📄 そのときの結果を PDFで 見る')[0]"></ic>{{ iX(iL(S.pdfBusy === r._i ? 'PDFを 作っています…' : '📄 そのときの結果を PDFで 見る')[1]) }}</button>
          </div>
        </div>
      </div>
      <button v-if="newest.length > S.more" class="btn" @click="S.more += 30">もっと見る（あと {{ newest.length - S.more }}件）</button>
      <button class="btn" style="margin-top:10px" @click="csv"><ic n="save"></ic>CSVで ダウンロード</button>
      <div class="small muted center" style="margin-top:10px">保存先：{{ S.args.storage }}</div>
    </template>
  </template>
</div>
<div v-else class="loading">読みこみ中…</div>`,
}).mount("#app");
