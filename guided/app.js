const state = {
  scenarios: [],
  selectedScenarioId: null,
  sessionId: null,
  session: null,
};

const healthPillEl = document.getElementById("health-pill");
const scenarioListEl = document.getElementById("scenario-list");
const startButtonEl = document.getElementById("start-button");
const nextButtonEl = document.getElementById("next-button");
const sessionTitleEl = document.getElementById("session-title");
const sessionSummaryEl = document.getElementById("session-summary");
const coachStepEl = document.getElementById("coach-step");
const coachNarratorEl = document.getElementById("coach-narrator");
const coachTipEl = document.getElementById("coach-tip");
const participantCountEl = document.getElementById("participant-count");
const intentCountEl = document.getElementById("intent-count");
const operationCountEl = document.getElementById("operation-count");
const conflictCountEl = document.getElementById("conflict-count");
const operatorInstructionEl = document.getElementById("operator-instruction");
const protocolFocusEl = document.getElementById("protocol-focus");
const messageDeltaEl = document.getElementById("message-delta");
const commentaryEl = document.getElementById("commentary");
const snapshotEl = document.getElementById("snapshot");
const historyEl = document.getElementById("history");

async function jsonRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function renderScenarios() {
  scenarioListEl.innerHTML = "";
  state.scenarios.forEach((scenario) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `scenario-card ${state.selectedScenarioId === scenario.scenario_id ? "active" : ""}`;
    card.innerHTML = `
      <p class="mini-label">${scenario.scenario_id}</p>
      <h3>${scenario.title}</h3>
      <p class="body-copy">${scenario.summary}</p>
      <div class="card-foot">
        <span>${scenario.step_count} steps</span>
        <span>${scenario.actor_names.join(" / ")}</span>
      </div>
    `;
    card.addEventListener("click", () => {
      state.selectedScenarioId = scenario.scenario_id;
      renderScenarios();
      startButtonEl.disabled = false;
      sessionTitleEl.textContent = scenario.title;
      sessionSummaryEl.textContent = scenario.summary;
    });
    scenarioListEl.appendChild(card);
  });
}

function renderSession(session) {
  state.session = session;
  state.sessionId = session.session_id;
  sessionTitleEl.textContent = session.scenario.title;
  sessionSummaryEl.textContent = session.presentation.tagline;

  const snapshot = session.snapshot;
  participantCountEl.textContent = Object.keys(snapshot.participants || {}).length;
  intentCountEl.textContent = Object.keys(snapshot.intents || {}).length;
  operationCountEl.textContent = Object.keys(snapshot.operations || {}).length;
  conflictCountEl.textContent = Object.keys(snapshot.conflicts || {}).length;

  const current = session.history[session.history.length - 1];
  if (current) {
    coachStepEl.textContent = current.title;
    coachNarratorEl.textContent = current.commentary.narrator;
    coachTipEl.textContent = current.commentary.operator_tip;
    operatorInstructionEl.textContent = current.operator_instruction;
    messageDeltaEl.textContent = JSON.stringify(current.message_delta, null, 2);
    commentaryEl.textContent = JSON.stringify(current.commentary, null, 2);
  } else {
    coachStepEl.textContent = "Ready to begin";
    coachNarratorEl.textContent = "Press Start scenario, then advance one step at a time.";
    coachTipEl.textContent = "";
    operatorInstructionEl.textContent = "Your first protocol action will appear here.";
    messageDeltaEl.textContent = "";
    commentaryEl.textContent = "";
  }

  protocolFocusEl.innerHTML = "";
  (current?.protocol_focus || []).forEach((item) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = item;
    protocolFocusEl.appendChild(tag);
  });

  snapshotEl.textContent = JSON.stringify(snapshot, null, 2);
  historyEl.textContent = JSON.stringify(
    session.history.map((item) => ({
      step_index: item.step_index,
      title: item.title,
      protocol_focus: item.protocol_focus,
    })),
    null,
    2
  );

  nextButtonEl.disabled = session.completed;
}

async function loadScenarios() {
  const health = await jsonRequest("/api/health");
  healthPillEl.textContent = health.anthropic_configured
    ? "Claude commentary is enabled"
    : "Guided steps work without Claude, but commentary will be fallback text";
  const payload = await jsonRequest("/api/guided/scenarios");
  state.scenarios = payload.items || [];
  renderScenarios();
}

async function startScenario() {
  if (!state.selectedScenarioId) {
    return;
  }
  const session = await jsonRequest("/api/guided/session", {
    method: "POST",
    body: JSON.stringify({ scenario_id: state.selectedScenarioId }),
  });
  renderSession(session);
  nextButtonEl.disabled = false;
}

async function nextStep() {
  if (!state.sessionId) {
    return;
  }
  const session = await jsonRequest(`/api/guided/session/${state.sessionId}/next`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  renderSession(session);
}

startButtonEl.addEventListener("click", startScenario);
nextButtonEl.addEventListener("click", nextStep);

loadScenarios().catch((error) => {
  healthPillEl.textContent = error.message;
});
