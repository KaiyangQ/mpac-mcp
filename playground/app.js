const state = {
  sessionId: null,
  suggestion: null,
};

const healthPillEl = document.getElementById("health-pill");
const apiKeyEl = document.getElementById("api-key");
const modelEl = document.getElementById("model");
const taskEl = document.getElementById("task");
const targetsEl = document.getElementById("targets");
const agentOneNameEl = document.getElementById("agent-one-name");
const agentOneStyleEl = document.getElementById("agent-one-style");
const agentTwoNameEl = document.getElementById("agent-two-name");
const agentTwoStyleEl = document.getElementById("agent-two-style");
const runButtonEl = document.getElementById("run-button");
const statusTextEl = document.getElementById("status-text");
const sessionIdEl = document.getElementById("session-id");
const participantCountEl = document.getElementById("participant-count");
const intentCountEl = document.getElementById("intent-count");
const operationCountEl = document.getElementById("operation-count");
const conflictCountEl = document.getElementById("conflict-count");
const plansEl = document.getElementById("plans");
const resolutionPanelEl = document.getElementById("resolution-panel");
const resolutionRationaleEl = document.getElementById("resolution-rationale");
const applySuggestionEl = document.getElementById("apply-suggestion");
const refreshSessionEl = document.getElementById("refresh-session");
const messageLogEl = document.getElementById("message-log");
const conflictsEl = document.getElementById("conflicts");
const intentsEl = document.getElementById("intents");
const operationsEl = document.getElementById("operations");

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const apiKey = apiKeyEl.value.trim();
  const model = modelEl.value.trim();
  if (apiKey) {
    headers["X-Anthropic-Api-Key"] = apiKey;
  }
  if (model) {
    headers["X-Anthropic-Model"] = model;
  }

  const response = await fetch(path, { ...options, headers });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed");
  }
  return payload;
}

function renderPlans(plans = []) {
  plansEl.innerHTML = "";
  plans.forEach((plan) => {
    const card = document.createElement("article");
    card.className = "plan-card";
    card.innerHTML = `
      <p class="mini-label">${plan.intent_id}</p>
      <h3>${plan.objective}</h3>
      <p class="body-copy">${plan.summary}</p>
      <div class="plan-meta">
        <span>Target: ${plan.target}</span>
        <span>Operation: ${plan.op_kind}</span>
      </div>
    `;
    plansEl.appendChild(card);
  });
}

function renderSnapshot(payload) {
  const snapshot = payload.snapshot;
  const messageLog = snapshot.message_log || [];
  state.sessionId = payload.session_id;
  state.suggestion = payload.resolution_suggestion || null;

  sessionIdEl.textContent = state.sessionId || "No session yet";
  participantCountEl.textContent = Object.keys(snapshot.participants || {}).length;
  intentCountEl.textContent = Object.keys(snapshot.intents || {}).length;
  operationCountEl.textContent = Object.keys(snapshot.operations || {}).length;
  conflictCountEl.textContent = Object.keys(snapshot.conflicts || {}).length;

  messageLogEl.textContent = JSON.stringify(messageLog, null, 2);
  conflictsEl.textContent = JSON.stringify(
    { conflicts: snapshot.conflicts || {}, resolutions: snapshot.resolutions || {} },
    null,
    2
  );
  intentsEl.textContent = JSON.stringify(snapshot.intents || {}, null, 2);
  operationsEl.textContent = JSON.stringify(
    { operations: snapshot.operations || {}, shared_state: snapshot.shared_state || {} },
    null,
    2
  );

  if (state.suggestion) {
    resolutionPanelEl.classList.remove("hidden");
    resolutionRationaleEl.textContent = state.suggestion.rationale;
  } else {
    resolutionPanelEl.classList.add("hidden");
    resolutionRationaleEl.textContent = "";
  }
}

async function loadHealth() {
  try {
    const payload = await fetch("/api/health").then((res) => res.json());
    healthPillEl.textContent = payload.anthropic_configured
      ? "Server has a default Anthropic key"
      : "Paste a key above to run live agents";
    if (!modelEl.value && payload.default_model) {
      modelEl.value = payload.default_model;
    }
  } catch (error) {
    healthPillEl.textContent = "Server check failed";
  }
}

async function runRound() {
  statusTextEl.textContent = "Running live round...";
  runButtonEl.disabled = true;
  try {
    const payload = await request("/api/session", {
      method: "POST",
      body: JSON.stringify({
        task: taskEl.value.trim(),
        shared_targets: targetsEl.value
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        agents: [
          {
            id: "agent:builder",
            name: agentOneNameEl.value.trim() || "Builder Agent",
            style: agentOneStyleEl.value.trim(),
          },
          {
            id: "agent:reviewer",
            name: agentTwoNameEl.value.trim() || "Reviewer Agent",
            style: agentTwoStyleEl.value.trim(),
          },
        ],
      }),
    });
    renderPlans(payload.plans || []);
    renderSnapshot(payload);
    statusTextEl.textContent = "Round complete";
  } catch (error) {
    statusTextEl.textContent = error.message;
  } finally {
    runButtonEl.disabled = false;
  }
}

async function applySuggestion() {
  if (!state.sessionId || !state.suggestion) {
    return;
  }
  applySuggestionEl.disabled = true;
  statusTextEl.textContent = "Applying resolution...";
  try {
    const payload = await request(`/api/session/${state.sessionId}/resolve`, {
      method: "POST",
      body: JSON.stringify(state.suggestion),
    });
    renderSnapshot(payload);
    statusTextEl.textContent = "Resolution applied";
  } catch (error) {
    statusTextEl.textContent = error.message;
  } finally {
    applySuggestionEl.disabled = false;
  }
}

async function refreshSnapshot() {
  if (!state.sessionId) {
    return;
  }
  statusTextEl.textContent = "Refreshing snapshot...";
  try {
    const payload = await request(`/api/session/${state.sessionId}`);
    renderSnapshot(payload);
    statusTextEl.textContent = "Snapshot refreshed";
  } catch (error) {
    statusTextEl.textContent = error.message;
  }
}

runButtonEl.addEventListener("click", runRound);
applySuggestionEl.addEventListener("click", applySuggestion);
refreshSessionEl.addEventListener("click", refreshSnapshot);

loadHealth();
