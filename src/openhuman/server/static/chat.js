/* 聊天页：醒来 → 回放 → 流式 + 打字节奏 → 引用 */

const slug = location.pathname.split("/").filter(Boolean).pop();
// 这间屋子的灯要往人身上打，不是打在空处（见 style.css 里的 .vignette）
document.body.classList.add("chat");
const transcript = $("#transcript");
const input = $("#input");
const boot = $("#boot");
const bar = $("#bootbar");
const drawer = $("#drawer");
const jump = $("#jump");
const state = $("#state");

let busy = false;
let him = null; // 这个人格包：名字、记忆数、sleep_line、wake_line
let awake = false;
let raisedHand = false; // 他说着话的时候，你按了 Enter

/* ---------- 醒来 ----------
   冷启动时窗口先出来，模型还在从磁盘往内存里搬。这一段等的是**真的**：
   进度条走多久，他就醒得多慢。以前那个 1.7 秒的动画是演给人看的。 */

let progress = 0;
const grow = setInterval(() => {
  progress += (96 - progress) * 0.045; // 越来越慢，逼近 96 —— 真在加载时也像在加载
  bar.style.width = progress.toFixed(1) + "%";
}, 90);

async function bootSequence() {
  const info = await api(`/api/humans/${slug}`).catch(() => null);
  him = info;
  if (info) document.title = info.name; // 窗口在任务栏里先有名字

  const cold = !(info && info.online);
  const sub = $("#bootsub");
  if (cold) {
    // 开机先说一句人话：屏幕不该是哑的
    sub.replaceChildren(el("i"), document.createTextNode("正在把他叫醒"));
    sub.classList.add("on");
  }

  // 等久了才说第二句，早了像在催他
  const slow = setTimeout(() => {
    if (cold) sub.replaceChildren(el("i"), document.createTextNode("还在读，得再等一下"));
  }, 9000);

  const warm = await api(`/api/warm/${slug}`, { method: "POST" }).catch(() => ({ ok: false }));
  clearTimeout(slow);

  await sleep(cold ? 500 : 150); // 热启动也别一闪而过

  clearInterval(grow);
  bar.style.width = "100%";
  await sleep(260);
  boot.classList.add("gone");
  setTimeout(() => boot.remove(), 1000);

  return !!warm.ok || !!(info && info.online);
}

/* ---------- 说 ---------- */

/* 一行话。他和你的区别只在 mark 和字体（见 CSS）。 */
function addLine(role, text) {
  const line = el("div", `line ${role}`);
  line.append(el("span", "mark", role === "me" ? "›" : ">"));
  const body = el("span", "body", text);
  line.append(body);
  transcript.append(line);
  return { line, body };
}

/* 他开口说一句。beat 是开口前的那口气：光标先闪一会儿，他才抬起头 ——
   一上来就冒字，像一块屏幕，不像一个人刚看见你。 */
async function startLine(text, beat = 0) {
  const { body } = addLine("him");
  const typer = new Typer(body, scroll);
  if (beat) await sleep(beat);
  typer.push(text);
  typer.finish();
  scroll();
  return typer.promise;
}

/* 旁白：连不上、没醒 —— 这些话不该由他的嘴说出来 */
function notice(text) {
  transcript.append(el("div", "notice", "· " + text));
  scroll();
}

/* ---------- 回放 ----------
   服务端一直记着这段对话，界面刷新不该把它藏起来。
   回放不走打字机：那是"正在发生"，这是"已经发生"。 */

function replay(messages, cards) {
  const last = messages[messages.length - 1] || {};
  const quiet = minutesSince(last.ts);

  // 走了半个钟头以上才说「上次」。刚刷新一下页面就说「上次」，像在装。
  const when = relativeDay(last.ts);
  const head = el("div", "mem show dim");
  if (quiet < 20) head.textContent = "  刚才说到这儿";
  else head.textContent = when ? `  上次说到这儿 · ${when}` : "  上次说到这儿";
  transcript.append(head);

  for (const m of messages) {
    const mine = m.role === "user";
    addLine(mine ? "me" : "him", m.text);
    if (!mine && m.citations && m.citations.length) showMemories(m.citations, cards);
  }
  scroll(true);
  return quiet;
}

/* ---------- 发送 ---------- */

async function send(text) {
  if (busy || !text.trim()) return;
  busy = true;
  raisedHand = false;
  input.value = "";

  addLine("me", text);
  scroll(true);

  const { line: hers, body } = addLine("him");
  const typer = new Typer(body, scroll);
  hers.classList.add("typing");
  let citations = [];
  let cards = {};
  let failed = "";

  document.body.classList.add("waiting");

  try {
    await streamChat(slug, { text, ...toolPayload() }, (event, data) => {
      if (event === "meta") {
        citations = data.citations || [];
        cards = data.cards || {};
      } else if (event === "delta") {
        document.body.classList.remove("waiting");
        typer.push(data.text);
      } else if (event === "tool") {
        showTool(data);
      } else if (event === "error") {
        failed = data.message || "出了点问题";
      }
    });
  } catch {
    failed = "连接断了";
  }

  document.body.classList.remove("waiting");
  // 流半路断了也要收尾：不收的话光标一直闪，输入框永远锁着
  typer.finish();
  await typer.promise;
  hers.classList.remove("typing");

  const said = body.textContent.trim();

  if (failed) {
    // 他一个字都没说出来：这一行就别留着了，让旁白说话
    if (!said) hers.remove();
    notice(failed === "连接断了" ? "他那边没声音了" : failed);
  } else if (!said) {
    // 没报错，也没出声。留一个孤零零的「>」比沉默更像坏了
    hers.remove();
    notice("他没出声");
  } else if (citations.length) {
    showMemories(citations, cards);
  }

  busy = false;
  input.focus();
  wake();

  // 他说的时候你抬了手：现在轮到你说
  if (raisedHand && input.value.trim()) send(input.value);
}

/* ---------- 引用 ---------- */

function prettyDate(iso) {
  if (!iso || iso.length < 10) return "";
  return `${iso.slice(0, 4)}.${iso.slice(5, 7)}.${iso.slice(8, 10)}`;
}

/* 他分得清「刚才」和「上次」：一个数分钟，一个数日历。 */
function minutesSince(iso) {
  const then = Date.parse(iso || "");
  return Number.isNaN(then) ? Infinity : (Date.now() - then) / 60000;
}

/* "上次说到这儿 · 昨天"。装个日子，人才真的是隔了一夜回来的。 */
function relativeDay(iso) {
  if (!iso || iso.length < 10) return "";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((midnight(new Date()) - midnight(then)) / 86400000);
  if (days <= 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  return `${then.getMonth() + 1} 月 ${then.getDate()} 日`;
}

function showMemories(ids, cards) {
  const box = el("div", "mem show");
  for (const id of ids) {
    const meta = (cards && cards[id]) || {};
    const btn = el("button", "memref");
    btn.append(el("span", "memdate", prettyDate(meta.date) || id));
    if (meta.title) btn.append(el("span", "memtitle", meta.title));
    btn.addEventListener("click", () => openCard(id));
    box.append(btn);
  }
  transcript.append(box);
  scroll();

  // 四秒后淡下去，但仍然可点
  setTimeout(() => box.classList.add("dim"), 4200);
}

function renderBody(text) {
  const frag = document.createDocumentFragment();
  let buf = [];

  const flush = () => {
    const joined = buf.join("\n").trim();
    buf = [];
    if (joined) frag.append(el("p", "para", joined));
  };

  for (const line of String(text || "").split("\n")) {
    if (line.startsWith("## ")) {
      flush();
      frag.append(el("div", "sec", line.slice(3).trim()));
    } else {
      buf.push(line);
    }
  }
  flush();
  return frag;
}

async function openCard(id) {
  try {
    const card = await api(`/api/humans/${slug}/cards/${id}`);
    $("#d-date").textContent = card.date;
    $("#d-title").textContent = card.title;
    const tags = [...(card.people || []), ...(card.places || []), ...(card.tags || [])];
    $("#d-tags").textContent = tags.length ? tags.join(" · ") : "";
    $("#d-text").replaceChildren(renderBody(card.body));
    clearTimeout(drawerTimer);
    drawer.classList.remove("off");
    drawer.classList.add("open");
    // 屋子退到后面去：卡片是前景，他在背景里
    document.body.classList.add("open-card");
  } catch {
    /* 卡片不存在就算了 */
  }
}

let drawerTimer = null;

function closeCard() {
  drawer.classList.remove("open");
  document.body.classList.remove("open-card");
  clearTimeout(drawerTimer);
  drawerTimer = setTimeout(() => drawer.classList.add("off"), 460);
}

$("#drawer-close").addEventListener("click", closeCard);
// 点空白处也收起来 —— 看过的东西，不用郑重其事地关
$("#scrim").addEventListener("click", closeCard);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeCard();
});

/* ---------- 布局 ---------- */

/* 贴着底走，但别抢人：你往上翻着看旧话，新字就不该把你拽回底部。
   离开底部时右下角浮出一个小小的 ↓，点一下才回来。 */
let stick = true;

transcript.addEventListener(
  "scroll",
  () => {
    stick =
      transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 48;
    jump.classList.toggle("on", !stick);
  },
  { passive: true }
);

let scrollQueued = false;

/* 每吐一个字都量一次 scrollHeight，就是一秒几十次强制布局。
   一帧只做一次，看着一样，跑起来轻。 */
function scroll(force) {
  if (force) stick = true;
  if (!stick || scrollQueued) return;
  scrollQueued = true;
  requestAnimationFrame(() => {
    scrollQueued = false;
    if (!stick) return;
    transcript.scrollTop = transcript.scrollHeight;
    jump.classList.remove("on");
  });
}

jump.addEventListener("click", () => scroll(true));

input.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || e.isComposing) return;
  e.preventDefault();
  if (busy) {
    raisedHand = true; // 他在说，先举手；等他说完就轮到你
    return;
  }
  send(input.value);
});

/* ---------- 工具 ----------
   开关在设置页（localStorage 的 oh.tools）。对话页不再摆那个按钮：
   跟「你说吧…」坐在同一行里的工具菜单，是这间屋子里最像机器的东西。 */

function toolPayload() {
  const mode = localStorage.getItem("oh.tools") || "off";
  if (mode === "off") return { tools: false, allow_mutating: false };
  return { tools: true, allow_mutating: mode === "write" };
}

function describeTool(ev) {
  const args = ev.args || {};
  const verb = {
    read_file: `看了 ${args.path || "一个文件"}`,
    list_dir: `翻了翻 ${args.path || "目录"}`,
    write_file: `写了 ${args.path || "一个文件"}`,
    append_file: `在 ${args.path || "一个文件"} 末尾记了一句`,
    edit_file: `改了 ${args.path || "一个文件"}`,
    run_command: `跑了一条命令`,
  }[ev.name] || ev.name;
  return ev.ok ? verb : `${verb}（没成）`;
}

function showTool(ev) {
  const line = el("div", "toolline");
  line.append(el("b", "", "· "), document.createTextNode(describeTool(ev)));
  transcript.append(line);
  scroll();
}

/* 从头开始是件重事：他会忘掉刚才聊的。
   所以分两步 —— 第一下只是问，第二下才真的忘。不用系统弹窗：
   那东西一冒出来，这间屋子就变成普通网页了。 */

let armedUntil = 0;

$("#fresh").addEventListener("click", async () => {
  if (busy) return;
  const btn = $("#fresh");

  if (Date.now() > armedUntil) {
    armedUntil = Date.now() + 4000;
    btn.textContent = "[确定？]";
    btn.classList.add("armed");
    setTimeout(() => {
      if (Date.now() >= armedUntil) {
        btn.textContent = "[新]";
        btn.classList.remove("armed");
      }
    }, 4200);
    return;
  }

  armedUntil = 0;
  btn.textContent = "[新]";
  btn.classList.remove("armed");
  await api(`/api/session/${slug}/new`, { method: "POST" }).catch(() => {});
  location.reload();
});

/* ---------- 屋子暗下去 ----------
   几十秒没人说话，屏幕暗一点，呼吸慢一点；你一动，他就醒。
   右上角那行字换成他的话 —— 这不是屏保，是"他在那儿等着"。 */

let idleTimer = null;
let speakTimer = null;
let spokeFirst = false; // 他先开口，一次就够
const IDLE_MS = 48000;
const SPEAK_MS = 180000;

function paintState() {
  let text = "";
  if (him) {
    const idle = document.body.classList.contains("idle");
    if (idle && him.sleep_line) text = him.sleep_line;
    else text = awake ? `${him.indexed} 段记忆` : "离线";
  }
  // 鼠标一动就会走到这儿，别每次都重写同一个文本节点
  if (state.textContent !== text) state.textContent = text;
}

function wake() {
  document.body.classList.remove("idle");
  paintState();
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    if (busy) return;
    document.body.classList.add("idle");
    paintState();
  }, IDLE_MS);
  clearTimeout(speakTimer);
  if (!spokeFirst) speakTimer = setTimeout(speakFirst, SPEAK_MS);
}

/* 你不说话的时候，他不是一块石头。
   静默三分钟，他出个声 —— 只一次，也不落进会话：那是他在等你，
   不是又一轮对话。切到别的窗口去了就别演，没人看。 */
function speakFirst() {
  if (spokeFirst || busy || !awake || document.hidden) return;
  if (!him || !him.idle_line) return;
  spokeFirst = true;
  startLine(him.idle_line);
}

for (const evt of ["mousemove", "keydown", "click", "focusin", "wheel"]) {
  document.addEventListener(evt, wake, { passive: true });
}
// 切走了就不用变暗 —— 屋子是给坐在屏幕前的人看的，给后台标签页演没用。
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) wake();
});

/* ---------- 开始 ---------- */

(async () => {
  awake = await bootSequence();

  if (!him) {
    await startLine("（这个人格包加载不了。）");
    input.disabled = false;
    return;
  }

  $("#who").textContent = him.name;

  if (!awake) {
    notice("他没醒 · 模型没起来，看看 data/llama.log");
    await startLine("……我这边还没醒。");
    input.disabled = false;
    wake();
    return;
  }

  const past = await api(`/api/session/${slug}`).catch(() => null);
  const messages = (past && past.messages) || [];

  if (messages.length) {
    const quiet = replay(messages, (past && past.cards) || {});
    // 走开过一阵子回来，他先开口。四十五分钟是「你出去过一趟」的尺度：
    // 短了像每回刷新都要打招呼，长了又像根本没发现你不在。
    if (quiet >= 45 && him.wake_line) await startLine(him.wake_line, 500);
  } else {
    await startLine(him.first_line, 900);
  }

  input.disabled = false;
  input.focus();
  wake();
})();
