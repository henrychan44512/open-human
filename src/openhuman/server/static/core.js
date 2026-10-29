/* 共享工具：元素、请求、SSE、打字机。 */

const $ = (sel, root = document) => root.querySelector(sel);

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- 屋子 ----------
   光有两层：上面一层冷（窗外），下面一层暖（屋里有人）。
   鼠标一动，两层走不同的步子 —— 走得多的显得近，走得少的显得远。
   位移只有几像素，眼睛读出的是前后，不是"在动"。 */

const html = document.documentElement;
let aim = 0;

function track(e) {
  if (aim) return;
  aim = requestAnimationFrame(() => {
    aim = 0;
    html.style.setProperty("--px", (e.clientX / innerWidth - 0.5).toFixed(3));
    html.style.setProperty("--py", (e.clientY / innerHeight - 0.5).toFixed(3));
  });
}

if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  addEventListener("mousemove", track, { passive: true });
}

/* 房间跟着天光走。差别只有几个百分点，但不该一样：
   同一个他，早上七点和半夜十二点不是同一种暗。 */
(function setPhase() {
  const h = new Date().getHours();
  const name = h < 5 || h >= 20 ? "night" : h < 8 ? "dawn" : h < 17 ? "day" : "dusk";
  document.body.dataset.phase = name;
})();

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

/* ---------- 打字机 ----------
   模型比人快，直接贴上去就不像人了。
   这里按字符吐，标点后停一下；积压太多就加速追上。 */

const PAUSE = {
  '，': 150, '、': 150, '；': 120, '：': 120,
  '。': 230, '！': 230, '？': 230, '…': 230,
};

const TYPO_RATE = 0.16;
const TYPO_MIN = 42;

class Typer {
  constructor(container, onGrow) {
    this.container = container;
    this.onGrow = onGrow;
    this.txt = el('span', 'txt');
    this.caret = el('span', 'caret');
    container.append(this.txt, this.caret);
    this.buf = '';
    this.done = false;
    this.typoAt = -1;
    this.pos = 0;
    this.timer = null;
    this.promise = new Promise((resolve) => (this.resolve = resolve));
    this._step();
  }

  push(text) {
    this.buf += text;
  }

  finish() {
    this.done = true;
    this._maybePlanTypo();
  }

  _grow() {
    if (this.onGrow) this.onGrow();
  }

  _maybePlanTypo() {
    if (this.typoAt >= 0) return;
    if (this.txt.textContent.length < TYPO_MIN) return;
    if (Math.random() > TYPO_RATE) return;
    this.typoAt = Math.floor(this.txt.textContent.length * (0.3 + Math.random() * 0.4));
  }

  _delay(ch) {
    let d = 26 + Math.random() * 18;
    if (PAUSE[ch]) d += PAUSE[ch];
    else if (ch === '\n') d += 190;
    const lag = this.buf.length;
    if (lag > 40) d *= 0.4;
    else if (lag > 16) d *= 0.68;
    return d;
  }

  _step() {
    if (!this.buf) {
      if (this.done) {
        // 最后一个字说完，光标也停一下再走 —— 人说完话不会立刻闭嘴。
        // 先 resolve：等下一个字的输入框不该陪着一起等。
        this.caret.classList.add("done");
        setTimeout(() => this.caret.remove(), 800);
        this.resolve();
        return;
      }
      // 等他说第一个字。30ms 空转是白烧 CPU，80ms 看不出来。
      this.timer = setTimeout(() => this._step(), 80);
      return;
    }

    const ch = this.buf[0];
    this.buf = this.buf.slice(1);

    // 打错一个字再删掉：重复上一个字，停一下，退格
    if (this.typoAt >= 0 && this.pos === this.typoAt && ch.trim()) {
      this.typoAt = -1;
      this.txt.textContent += ch + ch;
      this.pos += 2;
      this._grow();
      setTimeout(() => {
        this.txt.textContent = this.txt.textContent.slice(0, -1);
        this.pos -= 1;
      }, 240);
      this.timer = setTimeout(() => this._step(), this._delay(ch) + 240);
      return;
    }

    this.txt.textContent += ch;
    this.pos += 1;
    this._grow();
    this.timer = setTimeout(() => this._step(), this._delay(ch));
  }
}

/* ---------- SSE ---------- */

async function streamChat(slug, body, on) {
  const res = await fetch(`/api/chat/${slug}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buf.indexOf('\n\n')) >= 0) {
      const block = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      let name = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) name = line.slice(7).trim();
        else if (line.startsWith('data: ')) data += line.slice(6);
      }
      if (!data) continue;
      try {
        on(name, JSON.parse(data));
      } catch {
        /* 半个包，忽略 */
      }
    }
  }
}
