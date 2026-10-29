/* 设置页：读写 config.toml 的几行；工具开关存在浏览器里，和对话页共用一把钥匙 */

(async () => {
  const status = $("#status");
  const saved = $("#saved");
  const note = $("#note");
  const tools = $("#tools");
  const ver = $("#ver");

  const fields = {
    backend: $("#backend"),
    base_url: $("#base_url"),
    temperature: $("#temperature"),
    top_p: $("#top_p"),
    max_reply_tokens: $("#max_reply_tokens"),
  };

  function flash() {
    saved.classList.add("on");
    setTimeout(() => saved.classList.remove("on"), 1600);
  }

  async function paintStatus() {
    const data = await api("/api/settings");
    const model = data.backend === "deepseek" ? data.deepseek.model : data.llama.model;
    status.textContent = data.online ? `模型在线 · ${model}` : "模型离线";
    return data;
  }

  try {
    const data = await paintStatus();
    ver.textContent = `v${data.version} · beta`;
    fields.backend.value = data.backend;
    fields.base_url.value = data.llama.base_url;
    fields.temperature.value = data.llama.temperature;
    fields.top_p.value = data.llama.top_p;
    fields.max_reply_tokens.value = data.max_reply_tokens;
    note.textContent = data.has_deepseek_key
      ? "已检测到 DEEPSEEK_API_KEY"
      : "DeepSeek 需要在环境变量里设 DEEPSEEK_API_KEY";
  } catch (err) {
    status.textContent = "读不到设置";
    note.textContent = String(err.message || err);
    return;
  }

  const mode = localStorage.getItem("oh.tools");
  tools.value = ["off", "read", "write"].includes(mode) ? mode : "off";
  tools.addEventListener("change", () => {
    localStorage.setItem("oh.tools", tools.value);
    flash();
  });

  let timer = null;

  async function save() {
    const body = {
      backend: fields.backend.value,
      base_url: fields.base_url.value.trim(),
      temperature: Number(fields.temperature.value),
      top_p: Number(fields.top_p.value),
      max_reply_tokens: Number(fields.max_reply_tokens.value),
    };
    try {
      await api("/api/settings", { method: "POST", body: JSON.stringify(body) });
      flash();
      await paintStatus(); // 切了后端，右上角那句「模型在线」也得跟着变
    } catch (err) {
      note.textContent = "保存失败: " + (err.message || err);
    }
  }

  for (const node of Object.values(fields)) {
    node.addEventListener("change", save);
    node.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(save, 700);
    });
  }
})();
