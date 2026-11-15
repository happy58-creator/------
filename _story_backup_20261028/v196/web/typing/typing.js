/* ローマ字タイピング。1キーごとに判定して、まちがえたキーも記録する。 */
class TypingGame {
  constructor(root, args, onDone) {
    this.onDone = onDone;
    this.round = args.round;
    this.hideRomaji = args.mode === "あんもくモード";
    this.questions = (args.issues || []).map((q) => {
      const units = Kana.buildUnits(q.japanese) || Kana.unitsFromRomaji(q.romaji);
      return { text: String(q.japanese || ""), units };
    }).filter((q) => q.units.length);
    this.q = 0;
    this.keys = 0;
    this.misses = 0;
    this.combo = 0;
    this.maxCombo = 0;
    this.perfect = 0;
    this.missedQuestions = 0;
    this.details = []; // 問題ごとの {text, miss}（PDF・履歴用）
    this.qMissCount = 0;
    this.weak = {};
    this.elapsed = 0;
    this.runningSince = 0;
    this.state = "ready"; // ready → count → play → pause → done

    root.innerHTML = `
      <div class="game">
        <div class="hud">
          <span class="pill">📝 <b data-r="qno">1</b> / ${this.questions.length}</span>
          <span class="pill">⏱ <b data-r="time">0:00</b></span>
          <span class="pill">⚡ <b data-r="speed">0</b> 打/分</span>
          <span class="pill">❌ ミス <b data-r="miss">0</b></span>
          <span class="pill combo" data-r="comboBox">🔥 <b data-r="combo">0</b> コンボ</span>
          <button class="icon" data-r="sound"></button>
        </div>
        <div class="progress"><div data-r="bar"></div></div>
        <div class="card" data-r="card">
          <div class="jp" data-r="jp"></div>
          <div class="roma" data-r="roma"></div>
          <div class="nextq" data-r="nextq"></div>
          <div class="praise" data-r="praise"></div>
        </div>
        <div data-r="kb"></div>
        <div class="ime" data-r="ime" hidden>⚠️ 日本語入力が オンに なっているよ！「英数」キー（または 半角/全角キー）を おしてね</div>
        <div class="overlay" data-r="overlay"></div>
      </div>`;
    this.$ = (name) => root.querySelector(`[data-r="${name}"]`);
    this.kb = new UI.Keyboard(this.$("kb"));
    this.$("sound").onclick = (e) => { e.currentTarget.textContent = UI.toggleSound() ? "🔊" : "🔇"; };
    this.$("sound").textContent = UI.sound.on ? "🔊" : "🔇";
    this.$("overlay").onclick = () => this.overlayClick();
    window.addEventListener("keydown", (e) => this.onKey(e));
    UI.watchFocus(() => this.pause(), () => {});
    this.timer = setInterval(() => this.tick(), 200);
    this.loadQuestion();
    this.showOverlay(`
      <div class="big">⌨️</div>
      <h2>じゅんび OK？</h2>
      <p>${this.hideRomaji ? "あんもくモード：ローマ字は かくれているよ。" : "みながらモード：ローマ字を 見ながら 打とう。"}<br>
      「shi / si」「chi / ti」など、どの打ち方でも OK！</p>
      <p class="tip">日本語入力は オフ（英数）にしてね</p>
      <button class="primary">ここを クリックして スタート！</button>
      <p class="tip">（クリックしたあとは スペースキーでも はじめられるよ）</p>`);
  }

  // ---------------- 画面 ----------------
  showOverlay(html) {
    const o = this.$("overlay");
    o.innerHTML = `<div class="dialog">${html}</div>`;
    o.hidden = false;
  }

  hideOverlay() {
    this.$("overlay").hidden = true;
  }

  overlayClick() {
    window.focus();
    if (this.state === "ready") this.countdown();
    else if (this.state === "pause") this.resume();
  }

  countdown() {
    this.state = "count";
    let n = 3;
    const step = () => {
      if (n === 0) {
        UI.sfx.go();
        this.hideOverlay();
        this.state = "play";
        this.runningSince = performance.now();
        this.draw();
        return;
      }
      UI.sfx.count();
      this.showOverlay(`<div class="count">${n}</div>`);
      n--;
      setTimeout(step, 650);
    };
    step();
  }

  pause() {
    if (this.state !== "play") return;
    this.elapsed += performance.now() - this.runningSince;
    this.state = "pause";
    this.showOverlay(`<div class="big">⏸</div><h2>ひとやすみ中</h2>
      <p>ゲームの画面から はなれたので 止めたよ。</p><button class="primary">クリックして つづける</button>`);
  }

  resume() {
    this.state = "play";
    this.runningSince = performance.now();
    this.hideOverlay();
  }

  seconds() {
    const running = this.state === "play" || this.state === "between";
    return (this.elapsed + (running ? performance.now() - this.runningSince : 0)) / 1000;
  }

  tick() {
    const sec = this.seconds();
    this.$("time").textContent = UI.fmtTime(sec);
    this.$("speed").textContent = sec > 1 ? Math.round(this.keys / (sec / 60)) : 0;
  }

  loadQuestion() {
    const q = this.questions[this.q];
    this.matcher = new Kana.Matcher(q.units);
    this.qMissed = false;
    this.qMissCount = 0;
    this.$("qno").textContent = this.q + 1;
    this.$("bar").style.width = (this.q / this.questions.length) * 100 + "%";
    const nx = this.questions[this.q + 1];
    this.$("nextq").textContent = nx ? `つぎ：${nx.text}` : "さいごの もんだい！";
    this.$("praise").textContent = "";
    this.draw();
  }

  draw() {
    const q = this.questions[this.q], m = this.matcher;
    const done = m.kanaProgress();
    const chars = [...q.text];
    this.$("jp").innerHTML = done < 0
      ? UI.esc(q.text)
      : `<span class="ok">${UI.esc(chars.slice(0, done).join(""))}</span>${UI.esc(chars.slice(done).join(""))}`;
    const [typed, rest] = m.guide();
    const restHtml = this.hideRomaji
      ? '<span class="cursor">＿</span>'
      : (rest ? `<span class="cur">${UI.esc(rest[0])}</span><span class="todo">${UI.esc(rest.slice(1))}</span>` : "");
    this.$("roma").innerHTML = `<span class="ok">${UI.esc(typed)}</span>${restHtml}`;
    this.$("miss").textContent = this.misses;
    this.$("combo").textContent = this.combo;
    this.$("comboBox").classList.toggle("hot", this.combo >= 20);
    // あんもくモードでは、まちがえたときだけ キーを教える
    const help = !this.hideRomaji || this.justMissed;
    this.kb.show(this.state === "play" && rest && help ? rest[0] : null);
  }

  // ---------------- キー入力 ----------------
  onKey(e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "Process" || e.isComposing) {
      this.$("ime").hidden = false;
      return;
    }
    if (e.key === " " || e.key === "Enter") e.preventDefault();
    if (this.state === "ready" && e.key === " ") return this.countdown();
    if (this.state === "pause" && e.key === " ") return this.resume();
    if (this.state !== "play" || e.key.length !== 1) return;
    if (/[^\x20-\x7e]/.test(e.key)) {
      this.$("ime").hidden = false;
      return;
    }
    this.$("ime").hidden = true;
    e.preventDefault();
    const k = /[A-Z]/.test(e.key) ? e.key.toLowerCase() : e.key;
    const expected = this.matcher.guide()[1][0];
    if (this.matcher.input(k)) {
      this.keys++;
      this.justMissed = false;
      this.combo++;
      this.maxCombo = Math.max(this.maxCombo, this.combo);
      UI.sfx.key();
      this.kb.flash(k, true);
      if (this.matcher.done) return this.clearQuestion();
    } else {
      this.misses++;
      this.justMissed = true;
      this.combo = 0;
      this.qMissed = true;
      this.qMissCount++;
      if (expected) this.weak[expected] = (this.weak[expected] || 0) + 1;
      UI.sfx.miss();
      this.kb.flash(k, false);
      const card = this.$("card");
      card.classList.remove("shake");
      void card.offsetWidth;
      card.classList.add("shake");
    }
    this.draw();
  }

  clearQuestion() {
    if (this.qMissed) this.missedQuestions++;
    else this.perfect++;
    this.details.push({ text: this.questions[this.q].text, miss: this.qMissCount });
    UI.sfx.clear();
    this.draw();
    const words = this.qMissed ? ["クリア！", "いいね！", "その調子！"] : ["パーフェクト！✨", "ノーミス！🌟", "すごい！💯"];
    this.$("praise").textContent = words[Math.floor(Math.random() * words.length)];
    this.$("card").classList.add("cleared");
    this.state = "between";
    setTimeout(() => {
      this.$("card").classList.remove("cleared");
      if (this.q + 1 >= this.questions.length) return this.finish();
      this.q++;
      this.state = "play";
      this.loadQuestion();
    }, 450);
  }

  finish() {
    this.elapsed += performance.now() - this.runningSince;
    this.state = "done";
    clearInterval(this.timer);
    this.tick();
    this.$("bar").style.width = "100%";
    this.kb.show(null);
    UI.sfx.finish();
    const time = Math.round(this.elapsed / 100) / 10;
    const kpm = time > 0 ? Math.round(this.keys / (time / 60)) : 0;
    const accuracy = this.keys + this.misses ? Math.round((this.keys * 1000) / (this.keys + this.misses)) / 10 : 100;
    const rank = kpm >= 180 && accuracy >= 95 ? "S" : kpm >= 120 && accuracy >= 90 ? "A" : kpm >= 80 ? "B" : kpm >= 40 ? "C" : "D";
    const weakKeys = Object.entries(this.weak).sort((a, b) => b[1] - a[1]).slice(0, 5);
    this.showOverlay(`<div class="big">🏁</div><h2>FINISH！</h2><p>けっかを 計算中…</p>`);
    setTimeout(() => this.onDone({
      type: "typing_done", round: this.round, time, keys: this.keys, misses: this.misses, kpm, accuracy, rank,
      perfect: this.perfect, missedQuestions: this.missedQuestions, maxCombo: this.maxCombo, weakKeys,
      total: this.questions.length, details: this.details,
    }), 1300);
  }
}
