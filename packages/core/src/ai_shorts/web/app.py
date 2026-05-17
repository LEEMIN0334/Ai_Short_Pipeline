# ruff: noqa: E501

from typing import Annotated

from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ai_shorts.agents.runtime.registry import AGENT_DEFINITIONS, AgentDefinition
from ai_shorts.agents.runtime.store import (
    AgentTask,
    AgentTaskCreate,
    enqueue_task,
    list_tasks,
)
from ai_shorts.dashboard.store import (
    ClipUpdate,
    CostLogRow,
    ProjectCreate,
    ProjectSummary,
    ProjectUpdate,
    create_project,
    get_project,
    list_projects,
    list_recent_costs,
    update_clip,
    update_project,
)


class HealthResponse(BaseModel):
    ok: bool


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummary]


class CostsResponse(BaseModel):
    costs: list[CostLogRow]


class AgentCatalogResponse(BaseModel):
    agents: list[AgentDefinition]


class AgentTasksResponse(BaseModel):
    tasks: list[AgentTask]


def create_app() -> FastAPI:
    app = FastAPI(title="AI Shorts Studio", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return _html()

    @app.get("/api/health")
    async def health() -> HealthResponse:
        return HealthResponse(ok=True)

    @app.get("/api/projects")
    async def projects() -> ProjectListResponse:
        return ProjectListResponse(projects=await list_projects())

    @app.post("/api/projects")
    async def create_project_endpoint(project: ProjectCreate) -> ProjectSummary:
        return await create_project(project)

    @app.get("/api/projects/{project_id}")
    async def project_detail(
        project_id: Annotated[str, Path(min_length=1)],
    ) -> ProjectSummary:
        project = await get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    @app.patch("/api/projects/{project_id}")
    async def update_project_endpoint(
        project_id: Annotated[str, Path(min_length=1)],
        update: ProjectUpdate,
    ) -> ProjectSummary:
        project = await update_project(project_id, update)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    @app.patch("/api/clips/{clip_id}")
    async def update_clip_endpoint(
        clip_id: Annotated[str, Path(min_length=1)],
        update: ClipUpdate,
    ) -> object:
        clip = await update_clip(clip_id, update)
        if clip is None:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip

    @app.get("/api/costs")
    async def costs() -> CostsResponse:
        return CostsResponse(costs=list(await list_recent_costs()))

    @app.get("/api/agents")
    async def agents() -> AgentCatalogResponse:
        return AgentCatalogResponse(agents=list(AGENT_DEFINITIONS))

    @app.get("/api/agent-tasks")
    async def agent_tasks() -> AgentTasksResponse:
        return AgentTasksResponse(tasks=await list_tasks(limit=12))

    @app.post("/api/agent-tasks")
    async def create_agent_task(task: AgentTaskCreate) -> AgentTask:
        return await enqueue_task(task)

    return app


app = create_app()


def _html() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Shorts Studio</title>
  <style>
    :root {
      --bg: #08090d;
      --chrome: #0d0f14;
      --panel: #10131a;
      --panel-2: #141821;
      --panel-3: #191d27;
      --ink: #f4f7fb;
      --muted: #8d97a7;
      --line: #252a36;
      --line-soft: #1a1f2a;
      --accent: #8b8cff;
      --accent-2: #41d7a7;
      --warn: #f0b15a;
      --danger: #ff6b6b;
      --ok: #54d990;
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      min-height: 100vh;
      margin: 0;
      background:
        radial-gradient(circle at 20% -10%, rgba(139, 140, 255, 0.18), transparent 32%),
        radial-gradient(circle at 85% 0%, rgba(65, 215, 167, 0.12), transparent 28%),
        var(--bg);
      color: var(--ink);
    }
    button, input, textarea, select { font: inherit; }
    .shell {
      display: grid;
      grid-template-columns: 230px minmax(360px, 0.9fr) minmax(460px, 1.4fr);
      min-height: 100vh;
    }
    .sidebar {
      border-right: 1px solid var(--line-soft);
      background: rgba(10, 12, 18, 0.86);
      padding: 14px 12px;
      position: sticky;
      top: 0;
      height: 100vh;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      height: 38px;
      padding: 0 8px 12px;
      border-bottom: 1px solid var(--line-soft);
      margin-bottom: 12px;
      font-weight: 700;
    }
    .mark {
      width: 18px;
      height: 18px;
      border-radius: 5px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 0 24px rgba(139, 140, 255, 0.4);
    }
    .nav-section { margin: 16px 0 6px; padding: 0 8px; color: var(--muted); font-size: 11px; }
    .nav-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 34px;
      padding: 0 8px;
      border-radius: 6px;
      color: #c8d0dc;
      font-size: 13px;
    }
    .nav-item.active { background: #171b25; color: var(--ink); }
    .dot { width: 7px; height: 7px; border-radius: 999px; background: var(--accent-2); }
    .worklist {
      border-right: 1px solid var(--line-soft);
      background: rgba(12, 14, 20, 0.72);
      min-width: 0;
    }
    .topbar {
      height: 58px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      border-bottom: 1px solid var(--line-soft);
    }
    .topbar h1 { margin: 0; font-size: 15px; font-weight: 720; }
    .server-status {
      color: var(--muted);
      font-size: 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 5px 9px;
      background: #0c0f15;
    }
    .compose { padding: 14px 14px 10px; border-bottom: 1px solid var(--line-soft); }
    .compose summary {
      cursor: pointer;
      color: var(--ink);
      font-weight: 700;
      font-size: 13px;
      list-style: none;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .compose summary::after { content: "+"; color: var(--muted); }
    .compose[open] summary::after { content: "-"; }
    label {
      display: block;
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      margin: 12px 0 6px;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      color: var(--ink);
      background: #0c0f15;
      outline: none;
    }
    input:focus, textarea:focus, select:focus {
      border-color: rgba(139, 140, 255, 0.75);
      box-shadow: 0 0 0 3px rgba(139, 140, 255, 0.12);
    }
    textarea { min-height: 86px; resize: vertical; }
    button {
      border: 1px solid rgba(139, 140, 255, 0.38);
      border-radius: 6px;
      background: linear-gradient(180deg, #7273f3, #595be0);
      color: #fff;
      padding: 9px 12px;
      font-weight: 700;
      cursor: pointer;
      min-height: 36px;
    }
    button.secondary {
      background: #151a24;
      border-color: var(--line);
      color: var(--ink);
    }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-top: 12px; }
    .status { color: var(--muted); font-size: 13px; }
    .project-list { display: grid; }
    .project-item {
      border-bottom: 1px solid var(--line-soft);
      padding: 12px 14px;
      background: transparent;
      cursor: pointer;
    }
    .project-item:hover { background: #111620; }
    .project-item.active { background: linear-gradient(90deg, rgba(139, 140, 255, 0.14), transparent); }
    .project-title { display: flex; justify-content: space-between; gap: 12px; align-items: start; }
    .project-title strong { font-size: 13px; }
    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 700;
      background: #1a1f2b;
      color: #a9b2c1;
      white-space: nowrap;
    }
    .badge.ok { color: var(--ok); background: rgba(84, 217, 144, 0.12); }
    .badge.warn { color: var(--warn); background: rgba(240, 177, 90, 0.12); }
    .badge.danger { color: var(--danger); background: rgba(255, 107, 107, 0.12); }
    .muted { color: var(--muted); }
    .detail {
      min-width: 0;
      background: rgba(10, 12, 18, 0.42);
    }
    .detail-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line-soft);
      background: rgba(13, 15, 20, 0.86);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    .detail-head h2 { padding: 0; margin: 0; font-size: 18px; }
    .detail-body { padding: 16px 18px 28px; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .clip-grid { display: grid; gap: 10px; }
    .clip-card {
      display: grid;
      grid-template-columns: 72px 1fr;
      gap: 12px;
      border: 1px solid var(--line-soft);
      border-radius: 8px;
      padding: 12px;
      background: rgba(16, 19, 26, 0.74);
    }
    .clip-index {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 48px;
      border-radius: 7px;
      color: var(--accent-2);
      background: rgba(65, 215, 167, 0.08);
      border: 1px solid rgba(65, 215, 167, 0.18);
      font-weight: 800;
      font-size: 13px;
    }
    .clip-card h3 { margin: 0 0 8px; font-size: 14px; }
    .clip-card textarea { min-height: 120px; font-size: 13px; }
    pre {
      background: #05070a; color: #d8e0ec; border-radius: 8px; padding: 12px;
      overflow: auto; white-space: pre-wrap; font-size: 12px; line-height: 1.45;
      border: 1px solid var(--line-soft);
    }
    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin: 18px 0 10px;
      color: #d8deea;
      font-size: 13px;
      font-weight: 760;
    }
    @media (max-width: 1040px) {
      .shell { grid-template-columns: 74px minmax(300px, 0.95fr) minmax(420px, 1.2fr); }
      .nav-label, .brand span, .nav-section, .nav-count { display: none; }
      .sidebar { padding: 14px 10px; }
      .nav-item { justify-content: center; }
    }
    @media (max-width: 820px) {
      .shell { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line-soft); }
      .worklist { border-right: 0; }
      .detail-head { position: static; }
      .split, .clip-card { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <aside class="sidebar">
      <div class="brand"><div class="mark"></div><span>AI Shorts</span></div>
      <div class="nav-section">Workspace</div>
      <div class="nav-item active"><span class="nav-label">Projects</span><span class="dot"></span></div>
      <div class="nav-item"><span class="nav-label">Grok clips</span><span class="nav-count">loop</span></div>
      <div class="nav-item"><span class="nav-label">PM agent</span><span class="nav-count">runtime</span></div>
      <div class="nav-section">Server</div>
      <div class="nav-item"><span class="nav-label">Postgres</span><span class="nav-count">local</span></div>
      <div class="nav-item"><span class="nav-label">Redis</span><span class="nav-count">local</span></div>
    </aside>
    <section class="worklist">
      <div class="topbar">
        <h1>Shorts projects</h1>
        <span id="serverStatus" class="server-status">Checking</span>
      </div>
      <details class="compose">
        <summary>New job</summary>
        <label for="title">Title</label>
        <input id="title" placeholder="Hot topic angle">
        <label for="topic">Topic</label>
        <textarea id="topic" placeholder="What this short should explain or dramatize"></textarea>
        <div class="split">
          <div>
            <label for="duration">Duration seconds</label>
            <input id="duration" type="number" value="45" min="10" max="180">
          </div>
          <div>
            <label for="clipCount">Grok clips</label>
            <input id="clipCount" type="number" value="4" min="1" max="12">
          </div>
        </div>
        <label for="manualScript">Manual Gemini script</label>
        <textarea id="manualScript" placeholder="Paste the semi-manual Gemini script here"></textarea>
        <label for="notes">Notes</label>
        <textarea id="notes" placeholder="Voice, references, constraints"></textarea>
        <div class="actions">
          <button id="createBtn">Create job</button>
          <button id="refreshBtn" class="secondary">Refresh</button>
        </div>
      </details>
      <div id="projectList" class="project-list"></div>
    </section>
    <section class="detail">
      <div class="detail-head">
        <div>
          <h2 id="detailTitle">Select a project</h2>
          <div id="detailMeta" class="status"></div>
        </div>
        <select id="statusSelect">
          <option value="idea">idea</option>
          <option value="scripting">scripting</option>
          <option value="clips">clips</option>
          <option value="assembly">assembly</option>
          <option value="review">review</option>
          <option value="complete">complete</option>
          <option value="paused">paused</option>
        </select>
      </div>
      <div class="detail-body">
        <div class="split">
          <div>
            <label for="detailScript">Manual script</label>
            <textarea id="detailScript"></textarea>
          </div>
          <div>
            <label for="detailNotes">Production notes</label>
            <textarea id="detailNotes"></textarea>
          </div>
        </div>
        <div class="actions">
          <button id="saveProjectBtn">Save project</button>
          <span id="saveStatus" class="status"></span>
        </div>
        <div class="section-title"><span>Grok loop clips</span><span class="badge">10-15s</span></div>
        <div id="clipGrid" class="clip-grid"></div>
        <div class="section-title"><span>Recent PM cost log</span><span class="badge">local</span></div>
        <pre id="costLog">[]</pre>
        <div class="section-title"><span>Agent command center</span><span class="badge">worker</span></div>
        <div class="split">
          <div>
            <label for="agentSelect">Agent</label>
            <select id="agentSelect"></select>
          </div>
          <div>
            <label for="agentCommand">Command</label>
            <input id="agentCommand" value="mvp">
          </div>
        </div>
        <label for="agentPrompt">Prompt</label>
        <textarea id="agentPrompt" placeholder="Ask the always-on agents what to work on"></textarea>
        <div class="actions">
          <button id="queueAgentBtn">Queue agent task</button>
          <button id="refreshTasksBtn" class="secondary">Refresh tasks</button>
        </div>
        <pre id="agentTasks">[]</pre>
      </div>
    </section>
  </main>
  <script>
    const state = { projects: [], selected: null };
    const byId = (id) => document.getElementById(id);
    const api = async (path, options = {}) => {
      const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options
      });
      if (!res.ok) throw new Error(await res.text());
      return await res.json();
    };
    const fmtDate = (value) => new Date(value).toLocaleString();
    const badgeClass = (status) => ["complete", "approved", "generated"].includes(status) ? "ok" : (["failed", "rejected"].includes(status) ? "danger" : "warn");
    async function loadProjects() {
      byId("serverStatus").textContent = "Online";
      const data = await api("/api/projects");
      state.projects = data.projects;
      renderProjectList();
      if (!state.selected && state.projects.length) await selectProject(state.projects[0].project_id);
      await loadCosts();
      await loadAgents();
      await loadAgentTasks();
    }
    function renderProjectList() {
      byId("projectList").innerHTML = state.projects.map((p) => `
        <div class="project-item ${state.selected && state.selected.project_id === p.project_id ? "active" : ""}" data-project="${p.project_id}">
          <div class="project-title">
            <strong>${escapeHtml(p.title)}</strong>
            <span class="badge">${p.status}</span>
          </div>
          <div class="status">${p.project_id} - ${p.clip_count} clips - ${fmtDate(p.updated_at)}</div>
        </div>
      `).join("");
      document.querySelectorAll("[data-project]").forEach((el) => {
        el.addEventListener("click", () => selectProject(el.getAttribute("data-project")));
      });
    }
    async function selectProject(projectId) {
      state.selected = await api(`/api/projects/${projectId}`);
      renderProjectList();
      renderDetail();
    }
    function renderDetail() {
      const p = state.selected;
      if (!p) return;
      byId("detailTitle").textContent = p.title;
      byId("detailMeta").textContent = `${p.project_id} - ${p.target_duration_seconds}s - created ${fmtDate(p.created_at)}`;
      byId("statusSelect").value = p.status;
      byId("detailScript").value = p.manual_script || "";
      byId("detailNotes").value = p.notes || "";
      byId("clipGrid").innerHTML = p.clips.map((clip) => `
        <article class="clip-card">
          <div class="clip-index">#${String(clip.clip_index).padStart(2, "0")}</div>
          <div>
            <h3>
              ${escapeHtml(clip.title)}
              <span class="badge ${badgeClass(clip.status)}">${clip.status}</span>
            </h3>
            <label>Grok prompt</label>
            <textarea data-clip-field="${clip.clip_id}:prompt">${escapeHtml(clip.prompt)}</textarea>
            <label>Video URI</label>
            <input data-clip-field="${clip.clip_id}:video_uri" value="${escapeHtml(clip.video_uri)}" placeholder=".local_storage/clips/...mp4">
            <label>Loop notes</label>
            <textarea data-clip-field="${clip.clip_id}:loop_match_notes">${escapeHtml(clip.loop_match_notes)}</textarea>
            <div class="actions">
              <select data-clip-field="${clip.clip_id}:status">
                ${["todo", "prompt_ready", "generated", "approved", "rejected"].map((s) => `<option value="${s}" ${s === clip.status ? "selected" : ""}>${s}</option>`).join("")}
              </select>
              <button data-save-clip="${clip.clip_id}">Save</button>
            </div>
          </div>
        </article>
      `).join("");
      document.querySelectorAll("[data-save-clip]").forEach((el) => {
        el.addEventListener("click", () => saveClip(el.getAttribute("data-save-clip")));
      });
    }
    async function saveProject() {
      const p = state.selected;
      if (!p) return;
      await api(`/api/projects/${p.project_id}`, {
        method: "PATCH",
        body: JSON.stringify({
          status: byId("statusSelect").value,
          manual_script: byId("detailScript").value,
          notes: byId("detailNotes").value
        })
      });
      byId("saveStatus").textContent = "Saved";
      await selectProject(p.project_id);
    }
    async function saveClip(clipId) {
      const get = (field) => document.querySelector(`[data-clip-field="${clipId}:${field}"]`).value;
      await api(`/api/clips/${clipId}`, {
        method: "PATCH",
        body: JSON.stringify({
          prompt: get("prompt"),
          video_uri: get("video_uri"),
          loop_match_notes: get("loop_match_notes"),
          status: get("status")
        })
      });
      await selectProject(state.selected.project_id);
    }
    async function createJob() {
      const project = await api("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          title: byId("title").value,
          topic: byId("topic").value,
          target_duration_seconds: Number(byId("duration").value),
          manual_script: byId("manualScript").value,
          notes: byId("notes").value,
          clip_count: Number(byId("clipCount").value)
        })
      });
      byId("title").value = "";
      byId("topic").value = "";
      byId("manualScript").value = "";
      byId("notes").value = "";
      await loadProjects();
      await selectProject(project.project_id);
    }
    async function loadCosts() {
      const data = await api("/api/costs");
      byId("costLog").textContent = JSON.stringify(data.costs, null, 2);
    }
    async function loadAgents() {
      const data = await api("/api/agents");
      byId("agentSelect").innerHTML = data.agents.map((agent) => `
        <option value="${agent.agent_id}">${escapeHtml(agent.display_name)}</option>
      `).join("");
    }
    async function loadAgentTasks() {
      const data = await api("/api/agent-tasks");
      byId("agentTasks").textContent = JSON.stringify(data.tasks, null, 2);
    }
    async function queueAgentTask() {
      await api("/api/agent-tasks", {
        method: "POST",
        body: JSON.stringify({
          requested_by: "dashboard",
          agent_id: byId("agentSelect").value,
          command: byId("agentCommand").value,
          prompt: byId("agentPrompt").value || "untitled short"
        })
      });
      byId("agentPrompt").value = "";
      await loadAgentTasks();
    }
    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
      })[c]);
    }
    byId("createBtn").addEventListener("click", createJob);
    byId("refreshBtn").addEventListener("click", loadProjects);
    byId("saveProjectBtn").addEventListener("click", saveProject);
    byId("queueAgentBtn").addEventListener("click", queueAgentTask);
    byId("refreshTasksBtn").addEventListener("click", loadAgentTasks);
    loadProjects().catch((err) => {
      byId("serverStatus").textContent = "Error";
      console.error(err);
    });
  </script>
</body>
</html>
"""
