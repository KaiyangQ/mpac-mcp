const scenarios = window.MPAC_SCENARIOS || [];

const listEl = document.getElementById("scenario-list");
const scenarioIdEl = document.getElementById("scenario-id");
const titleEl = document.getElementById("scenario-title");
const summaryEl = document.getElementById("scenario-summary");
const assessmentEl = document.getElementById("scenario-assessment");
const notesEl = document.getElementById("scenario-notes");
const timelineEl = document.getElementById("timeline");
const messageCountEl = document.getElementById("message-count");
const participantCountEl = document.getElementById("participant-count");
const intentCountEl = document.getElementById("intent-count");
const operationCountEl = document.getElementById("operation-count");
const conflictCountEl = document.getElementById("conflict-count");
const participantsJsonEl = document.getElementById("participants-json");
const intentsJsonEl = document.getElementById("intents-json");
const operationsJsonEl = document.getElementById("operations-json");
const conflictsJsonEl = document.getElementById("conflicts-json");

function renderScenarioList() {
  scenarios.forEach((scenario, index) => {
    const button = document.createElement("button");
    button.className = "scenario-button";
    button.textContent = `${index + 1}. ${scenario.title}`;
    button.addEventListener("click", () => renderScenario(index));
    listEl.appendChild(button);
  });
}

function timelineCard(message, index) {
  const card = document.createElement("article");
  card.className = "timeline-card";
  card.innerHTML = `
    <div class="timeline-meta">
      <span class="timeline-index">#${index + 1}</span>
      <span class="timeline-type">${message.message_type}</span>
      <span class="timeline-sender">${message.sender.principal_id}</span>
    </div>
    <div class="timeline-body">
      <p><strong>Payload</strong></p>
      <pre>${escapeHtml(JSON.stringify(message.payload, null, 2))}</pre>
    </div>
  `;
  return card;
}

function renderScenario(index) {
  const scenario = scenarios[index];
  if (!scenario) {
    return;
  }

  [...listEl.children].forEach((node, nodeIndex) => {
    node.classList.toggle("active", nodeIndex === index);
  });

  scenarioIdEl.textContent = scenario.id;
  titleEl.textContent = scenario.title;
  summaryEl.textContent = scenario.summary;
  assessmentEl.textContent = scenario.assessment;

  notesEl.innerHTML = "";
  scenario.notes.forEach((note) => {
    const item = document.createElement("li");
    item.textContent = note;
    notesEl.appendChild(item);
  });

  const snapshot = scenario.snapshot;
  const messages = snapshot.message_log;
  timelineEl.innerHTML = "";
  messages.forEach((message, messageIndex) => timelineEl.appendChild(timelineCard(message, messageIndex)));

  messageCountEl.textContent = `${messages.length} messages`;
  participantCountEl.textContent = `${Object.keys(snapshot.participants).length} tracked`;
  intentCountEl.textContent = `${Object.keys(snapshot.intents).length} tracked`;
  operationCountEl.textContent = `${Object.keys(snapshot.operations).length} tracked`;
  conflictCountEl.textContent = `${Object.keys(snapshot.conflicts).length} conflicts / ${Object.keys(snapshot.resolutions).length} resolutions`;

  participantsJsonEl.textContent = JSON.stringify(snapshot.participants, null, 2);
  intentsJsonEl.textContent = JSON.stringify(snapshot.intents, null, 2);
  operationsJsonEl.textContent = JSON.stringify(snapshot.operations, null, 2);
  conflictsJsonEl.textContent = JSON.stringify(
    {
      conflicts: snapshot.conflicts,
      resolutions: snapshot.resolutions,
    },
    null,
    2
  );
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

renderScenarioList();
renderScenario(0);
