const state = {
  projects: [],
  currentProject: null,
  currentTaskId: null,
  pollingTimer: null,
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
  loadProjects();
});

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
    .filter((project) => !query || project.name.toLowerCase().includes(query) || project.title.toLowerCase().includes(query))
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
    { config_path: $("configPathInput").value.trim() || "config.local.json" }
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
    config_path: $("configPathInput").value.trim() || "config.local.json",
    bgm_path: $("bgmPathInput").value.trim(),
  });
  watchTask(response.task.id);
}

async function startAutoProject() {
  const response = await apiPost("/api/projects/auto", {
    theme: $("themeInput").value.trim(),
    config_path: $("configPathInput").value.trim() || "config.local.json",
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
