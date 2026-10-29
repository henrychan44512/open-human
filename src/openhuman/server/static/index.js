/* 首页：人格列表 */

(async () => {
  const list = $("#list");
  const status = $("#status");

  try {
    const data = await api("/api/humans");
    status.textContent = data.online ? `模型在线 · ${data.model}` : "模型离线";

    if (!data.humans.length) {
      const box = el("div", "empty");
      box.innerHTML = "humans/ 下还没有人格包。<br><br>放一个文件夹进去，刷新即可。<br><br><code>humans/demo/</code>";
      list.append(box);
      return;
    }

    for (const human of data.humans) {
      // 还在的人是一点亮，归档的人是一个空圈 —— 这两种状态不该长得一样。
      const archived = human.presence !== "living";
      const card = el("a", "human" + (human.online ? "" : " off") + (archived ? " archived" : ""));
      card.href = `/chat/${human.slug}`;

      const name = el("div", "name");
      name.append(el("span", "dot", archived ? "○" : "●"), document.createTextNode(human.name));

      card.append(name);
      card.append(el("div", "line", human.line || "…"));
      card.append(
        el(
          "div",
          "meta",
          `${archived ? "已归档 · " : ""}${human.memories} 张记忆卡 · 最后记录 ${human.last_record || "—"}`
        )
      );
      list.append(card);
    }
  } catch (err) {
    status.textContent = "连不上服务";
    list.append(el("div", "empty", String(err.message || err)));
  }
})();
