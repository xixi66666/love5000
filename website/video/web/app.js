const DEFAULT_CONFIG_PATH = "config/config.local.json";

const state = {
  projects: [],
  currentProject: null,
  currentTaskId: null,
  pollingTimer: null,
  config: null,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  $("refreshButton").addEventListener("click", loadProjects);
  $("projectSearch").addEventListener("input", renderProjectList);
  $("autoButton").addEventListener("click", startAutoProject);
  $("resumeButton").addEventListener("click", resumeProject);
  $("subtitlesButton").addEventListener("click", generateSubtitles);
  $("renderButton").addEventListener("click", renderProject);
  $("saveStoryboardButton").addEventListener("click", saveStoryboard);
  $("saveConfigButton").addEventListener("click", saveConfig);
  $("configPathInput").value = DEFAULT_CONFIG_PATH;
  loadConfig();
  loadProjects();
});

async function loadConfig() {
  const data = await apiGet("/api/config");
  state.config = data.config || {};
  $("configPathInput").value = data.config_path || DEFAULT_CONFIG_PATH;
  fillConfigForm(state.config);
  setConfigState("已读取", "success");
}

function fillConfigForm(config) {
  const openai = config.openai || {};
  const tts = config.tts || {};
  const tencent = config.tencent_tts || {};
  const modelscope = config.modelscope_video || {};
  const assets = config.assets || {};

  $("openaiBaseUrlInput").value = openai.base_url || "";
  $("openaiApiKeyInput").value = "";
  $("textModelInput").value = openai.text_model || "";
  $("imageModelInput").value = openai.image_model || "";
  $("ttsModelInput").value = openai.tts_model || "";
  $("ttsVoiceInput").value = openai.tts_voice || "";
  $("ttsProviderInput").value = tts.provider || "openai";
  $("tencentSecretIdInput").value = "";
  $("tencentSecretKeyInput").value = "";
  $("tencentRegionInput").value = tencent.region || "ap-guangzhou";
  $("tencentVoiceTypeInput").value = tencent.voice_type || 101001;
  $("modelscopeApiKeyInput").value = "";
  $("modelscopeModelInput").value = modelscope.model || "wanx2.1-i2v-plus";
  $("defaultBgmInput").value = assets.default_bgm || "assets/default_bgm.mp3";
}

function collectConfigForm() {
  const original = state.config || {};
  const modelscope = original.modelscope_video || {};
  const tencent = original.tencent_tts || {};
  return {
    openai: {
      base_url: $("openaiBaseUrlInput").value.trim(),
      api_key: $("openaiApiKeyInput").value.trim(),
      text_model: $("textModelInput").value.trim(),
      image_model: $("imageModelInput").value.trim(),
      tts_model: $("ttsModelInput").value.trim(),
      tts_voice: $("ttsVoiceInput").value.trim(),
    },
    tts: {
      provider: $("ttsProviderInput").value,
    },
    tencent_tts: {
      secret_id: $("tencentSecretIdInput").value.trim(),
      secret_key: $("tencentSecretKeyInput").value.trim(),
      region: $("tencentRegionInput").value.trim() || "ap-guangzhou",
      voice_type: numberOrDefault($("tencentVoiceTypeInput").value, tencent.voice_type || 101001),
      primary_language: numberOrDefault(tencent.primary_language, 1),
      codec: tencent.codec || "mp3",
      sample_rate: numberOrDefault(tencent.sample_rate, 16000),
      speed: numberOrDefault(tencent.speed, 0),
      volume: numberOrDefault(tencent.volume, 5),
    },
    modelscope_video: {
      api_key: $("modelscopeApiKeyInput").value.trim(),
      base_url: modelscope.base_url || "https://dashscope.aliyuncs.com/api/v1",
      model: $("modelscopeModelInput").value.trim() || "wanx2.1-i2v-plus",
      duration: numberOrDefault(modelscope.duration, 5),
      resolution: modelscope.resolution || "720P",
      poll_interval_seconds: numberOrDefault(modelscope.poll_interval_seconds, 5),
      timeout_seconds: numberOrDefault(modelscope.timeout_seconds, 600),
    },
    assets: {
      default_bgm: $("defaultBgmInput").value.trim() || "assets/default_bgm.mp3",
    },
  };
}

async function saveConfig() {
  setBusy(true);
  try {
    const saved = await apiPost("/api/config", { config: collectConfigForm() });
    state.config = saved.config || {};
    $("configPathInput").value = saved.config_path || DEFAULT_CONFIG_PATH;
    fillConfigForm(state.config);
    setConfigState("已保存", "success");
    setLog("配置已保存到 " + $("configPathInput").value);
  } finally {
    setBusy(false);
  }
}

function setConfigState(text, type = "") {
  const badge = $("configState");
  badge.textContent = text;
  badge.className = `status-badge ${type}`;
}

async function loadProjects() {
  const data = await apiGet("/api/projects");
  state.projects = data.projects || [];
  $("projectCount").textContent = String(state.projects.length);
  renderProjectList();
}

function renderProjectList() {
  const query = $("projectSearch").value.trim().toLowerCase();
  const list = $("projectList");
  list.innerHTML = "";
  state.projects
    .filter((project) => !query || (project.name || "").toLowerCase().includes(query) || (project.title || "").toLowerCase().includes(query))
    .forEach((project) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `project-item ${state.currentProject && state.currentProject.name === project.name ? "active" : ""}`;
      button.innerHTML = `
        <strong>${escapeHtml(project.title || project.name)}</strong>
        <span>${escapeHtml(project.name)} · ${project.shot_count} 个镜头</span>
      `;
      button.addEventListener("click", () => loadProject(project.name));
      list.appendChild(button);
    });
}

async function loadProject(projectName) {
  const detail = await apiGet(`/api/projects/${encodeURIComponent(projectName)}`);
  state.currentProject = detail;
  $("emptyState").classList.add("hidden");
  $("projectEditor").classList.remove("hidden");
  $("projectTitle").textContent = detail.storyboard.title || detail.name;
  $("projectPath").textContent = detail.project_dir;
  $("titleInput").value = detail.storyboard.title || "";
  $("narrationInput").value = detail.narration || "";
  $("shotCount").textContent = `${detail.storyboard.shots.length} 个镜头`;
  renderShots(detail.storyboard.shots);
  renderPreview(detail);
  renderAssets(detail.assets);
  $("warningLog").textContent = detail.warnings || "暂无警告";
  renderProjectList();
}

function renderShots(shots) {
  const list = $("shotList");
  list.innerHTML = "";
  shots.forEach((shot, index) => {
    const card = document.createElement("article");
    card.className = "shot-card";
    card.dataset.shotId = shot.id;
    card.innerHTML = `
      <div class="keyframe">
        ${
          shot.keyframe_exists
            ? `<img src="${shot.keyframe_url}?t=${Date.now()}" alt="${escapeHtml(shot.id)} 关键帧" />`
            : `<div class="keyframe-placeholder">${escapeHtml(shot.id)}<br />暂无关键帧</div>`
        }
      </div>
      <div class="shot-fields">
        <div class="shot-meta">
          <h3>${index + 1}. ${escapeHtml(shot.id)}</h3>
          <span class="status-badge">${Number(shot.duration).toFixed(1)}s</span>
        </div>
        <div class="field-row">
          <label class="field">
            <span>时长</span>
            <input data-field="duration" type="number" min="0.1" step="0.1" value="${escapeAttr(shot.duration)}" />
          </label>
          <label class="field">
            <span>字幕</span>
            <input data-field="subtitle" type="text" value="${escapeAttr(shot.subtitle || "")}" />
          </label>
        </div>
        <label class="field">
          <span>描述</span>
          <textarea data-field="description" rows="2">${escapeHtml(shot.description || "")}</textarea>
        </label>
        <label class="field">
          <span>图片提示词</span>
          <textarea data-field="image_prompt" rows="4">${escapeHtml(shot.image_prompt || "")}</textarea>
        </label>
        <div class="shot-actions">
          <button class="button secondary" type="button" data-action="save-shot">保存镜头</button>
          <button class="button primary" type="button" data-action="regen">重生关键帧</button>
        </div>
      </div>
    `;
    card.querySelector('[data-action="save-shot"]').addEventListener("click", () => saveStoryboard());
    card.querySelector('[data-action="regen"]').addEventListener("click", () => regenerateKeyframe(shot.id));
    list.appendChild(card);
  });
}

function collectStoryboard() {
  const original = state.currentProject.storyboard;
  const shots = Array.from(document.querySelectorAll(".shot-card")).map((card) => {
    const shotId = card.dataset.shotId;
    const originalShot = original.shots.find((shot) => shot.id === shotId) || {};
    return {
      id: shotId,
      duration: Number(card.querySelector('[data-field="duration"]').value),
      subtitle: card.querySelector('[data-field="subtitle"]').value.trim(),
      description: card.querySelector('[data-field="description"]').value.trim(),
      image_prompt: card.querySelector('[data-field="image_prompt"]').value.trim(),
      video: originalShot.video || `assets/videos/${shotId}.mp4`,
    };
  });
  return {
    title: $("titleInput").value.trim(),
    aspect_ratio: original.aspect_ratio || "9:16",
    duration_seconds: shots.reduce((total, shot) => total + Number(shot.duration || 0), 0),
    style: original.style || "",
    shots,
  };
}

async function saveStoryboard() {
  ensureProject();
  setBusy(true);
  try {
    const saved = await apiPost(`/api/projects/${encodeURIComponent(state.currentProject.name)}/storyboard`, {
      storyboard: collectStoryboard(),
      narration: $("narrationInput").value.trim(),
    });
    state.currentProject = saved;
    await loadProject(saved.name);
    setLog("分镜已保存");
  } finally {
    setBusy(false);
  }
}

async function regenerateKeyframe(shotId) {
  ensureProject();
  await saveStoryboard();
  const response = await apiPost(
    `/api/projects/${encodeURIComponent(state.currentProject.name)}/shots/${encodeURIComponent(shotId)}/regenerate-keyframe`,
    { config_path: getConfigPath() }
  );
  watchTask(response.task.id);
}

async function generateSubtitles() {
  ensureProject();
  const result = await apiPost(`/api/projects/${encodeURIComponent(state.currentProject.name)}/subtitles`, {});
  setLog(`字幕已生成：${result.subtitles}`);
  await loadProject(state.currentProject.name);
}

async function renderProject() {
  ensureProject();
  await saveStoryboard();
  const response = await apiPost(`/api/projects/${encodeURIComponent(state.currentProject.name)}/render`, {});
  watchTask(response.task.id);
}

async function resumeProject() {
  ensureProject();
  const response = await apiPost(`/api/projects/${encodeURIComponent(state.currentProject.name)}/resume`, {
    config_path: getConfigPath(),
    bgm_path: $("bgmPathInput").value.trim(),
  });
  watchTask(response.task.id);
}

async function startAutoProject() {
  const response = await apiPost("/api/projects/auto", {
    theme: $("themeInput").value.trim(),
    config_path: getConfigPath(),
    bgm_path: $("bgmPathInput").value.trim(),
  });
  watchTask(response.task.id);
}

function watchTask(taskId) {
  state.currentTaskId = taskId;
  if (state.pollingTimer) {
    clearInterval(state.pollingTimer);
  }
  pollTask();
  state.pollingTimer = setInterval(pollTask, 1200);
}

async function pollTask() {
  if (!state.currentTaskId) return;
  const task = await apiGet(`/api/tasks/${encodeURIComponent(state.currentTaskId)}`);
  const badge = $("taskBadge");
  badge.textContent = task.status;
  badge.className = `status-badge ${task.status === "success" ? "success" : task.status === "failed" ? "error" : ""}`;
  $("taskLog").textContent = [...(task.logs || []), task.error ? `错误：${task.error}` : ""].filter(Boolean).join("\n") || "暂无日志";
  if (task.status === "success" || task.status === "failed") {
    clearInterval(state.pollingTimer);
    state.pollingTimer = null;
    setBusy(false);
    await loadProjects();
    const projectName = (task.result && task.result.project_name) || task.project_name || (state.currentProject && state.currentProject.name);
    if (projectName) {
      await loadProject(projectName);
    }
  } else {
    setBusy(true);
  }
}

function renderPreview(detail) {
  const video = $("videoPreview");
  const placeholder = $("videoPlaceholder");
  if (detail.assets.final_video) {
    video.src = `/api/assets/${encodeURIComponent(detail.name)}/video/final?t=${Date.now()}`;
    placeholder.classList.add("hidden");
    $("videoState").textContent = "可预览";
    $("videoState").className = "status-badge success";
  } else {
    video.removeAttribute("src");
    placeholder.classList.remove("hidden");
    $("videoState").textContent = "暂无视频";
    $("videoState").className = "status-badge";
  }
}

function renderAssets(assets) {
  $("assetStatus").innerHTML = Object.entries({
    final_video: "成片",
    subtitles: "字幕",
    voice: "旁白",
    bgm: "BGM",
  })
    .map(([key, label]) => `<span class="status-badge ${assets[key] ? "success" : ""}">${label}: ${assets[key] ? "有" : "缺"}</span>`)
    .join("");
}

function setBusy(isBusy) {
  document.querySelectorAll("button").forEach((button) => {
    if (button.id !== "refreshButton") {
      button.disabled = isBusy;
    }
  });
}

function setLog(message) {
  $("taskLog").textContent = message;
}

function ensureProject() {
  if (!state.currentProject) {
    throw new Error("请先选择项目");
  }
}

function getConfigPath() {
  return $("configPathInput").value.trim() || DEFAULT_CONFIG_PATH;
}

function numberOrDefault(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

async function apiGet(path) {
  const response = await fetch(path);
  return parseResponse(response);
}

async function apiPost(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse(response);
}

async function parseResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    $("taskLog").textContent = data.error || "请求失败";
    throw new Error(data.error || "请求失败");
  }
  return data;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/'/g, "&#39;");
}
