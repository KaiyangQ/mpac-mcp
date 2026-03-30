const scenarios = window.MPAC_SCENARIOS || [];

const galleryEl = document.getElementById("scenario-gallery");
const scenarioViewEl = document.getElementById("scenario-view");
const backButtonEl = document.getElementById("back-button");

const viewIdEl = document.getElementById("view-id");
const viewTitleEl = document.getElementById("view-title");
const viewTaglineEl = document.getElementById("view-tagline");
const sharedTitleEl = document.getElementById("shared-title");
const sharedLabelEl = document.getElementById("shared-label");
const sharedBeforeEl = document.getElementById("shared-before");
const sharedAfterEl = document.getElementById("shared-after");
const actorsEl = document.getElementById("actors");
const stepTitleEl = document.getElementById("step-title");
const stepSummaryEl = document.getElementById("step-summary");
const leftTitleEl = document.getElementById("left-title");
const leftBodyEl = document.getElementById("left-body");
const rightTitleEl = document.getElementById("right-title");
const rightBodyEl = document.getElementById("right-body");
const stepStatusEl = document.getElementById("step-status");
const stepProtocolEl = document.getElementById("step-protocol");
const stepCountEl = document.getElementById("step-count");
const prevStepEl = document.getElementById("prev-step");
const nextStepEl = document.getElementById("next-step");
const outcomeTitleEl = document.getElementById("outcome-title");
const outcomeListEl = document.getElementById("outcome-list");
const assessmentEl = document.getElementById("assessment");
const notesEl = document.getElementById("notes");
const traceParticipantsEl = document.getElementById("trace-participants");
const traceIntentsEl = document.getElementById("trace-intents");
const traceOperationsEl = document.getElementById("trace-operations");
const traceConflictsEl = document.getElementById("trace-conflicts");

let activeScenarioIndex = 0;
let activeStepIndex = 0;

function renderGallery() {
  galleryEl.innerHTML = "";
  scenarios.forEach((scenario, index) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "gallery-card";
    card.innerHTML = `
      <p class="eyebrow">${scenario.id}</p>
      <h3>${scenario.title}</h3>
      <p class="card-copy">${scenario.presentation.tagline}</p>
      <div class="card-foot">
        <span>${scenario.presentation.steps.length} steps</span>
        <span>Watch demo</span>
      </div>
    `;
    card.addEventListener("click", () => openScenario(index));
    galleryEl.appendChild(card);
  });
}

function openScenario(index) {
  activeScenarioIndex = index;
  activeStepIndex = 0;
  scenarioViewEl.classList.remove("hidden");
  window.scrollTo({ top: scenarioViewEl.offsetTop - 12, behavior: "smooth" });
  renderScenario();
}

function renderScenario() {
  const scenario = scenarios[activeScenarioIndex];
  const presentation = scenario.presentation;
  const shared = presentation.shared_object;

  viewIdEl.textContent = scenario.id;
  viewTitleEl.textContent = scenario.title;
  viewTaglineEl.textContent = presentation.tagline;
  sharedTitleEl.textContent = shared.title;
  sharedLabelEl.textContent = shared.label;
  sharedBeforeEl.textContent = shared.before;
  sharedAfterEl.textContent = shared.after;

  actorsEl.innerHTML = "";
  presentation.actors.forEach((actor) => {
    const item = document.createElement("div");
    item.className = `actor actor-${actor.color}`;
    item.innerHTML = `<strong>${actor.name}</strong><span>${actor.role}</span>`;
    actorsEl.appendChild(item);
  });

  outcomeTitleEl.textContent = presentation.outcome.title;
  outcomeListEl.innerHTML = "";
  presentation.outcome.bullets.forEach((bullet) => {
    const item = document.createElement("li");
    item.textContent = bullet;
    outcomeListEl.appendChild(item);
  });

  assessmentEl.textContent = scenario.assessment;
  notesEl.innerHTML = "";
  scenario.notes.forEach((note) => {
    const item = document.createElement("li");
    item.textContent = note;
    notesEl.appendChild(item);
  });

  const snapshot = scenario.snapshot;
  traceParticipantsEl.textContent = JSON.stringify(snapshot.participants, null, 2);
  traceIntentsEl.textContent = JSON.stringify(snapshot.intents, null, 2);
  traceOperationsEl.textContent = JSON.stringify(snapshot.operations, null, 2);
  traceConflictsEl.textContent = JSON.stringify({ conflicts: snapshot.conflicts, resolutions: snapshot.resolutions }, null, 2);

  renderStep();
}

function renderStep() {
  const scenario = scenarios[activeScenarioIndex];
  const step = scenario.presentation.steps[activeStepIndex];

  stepTitleEl.textContent = step.title;
  stepSummaryEl.textContent = step.summary;
  leftTitleEl.textContent = step.left_title;
  leftBodyEl.textContent = step.left_body;
  rightTitleEl.textContent = step.right_title;
  rightBodyEl.textContent = step.right_body;
  stepCountEl.textContent = `${activeStepIndex + 1} / ${scenario.presentation.steps.length}`;

  stepStatusEl.innerHTML = "";
  step.status.forEach((status) => {
    const chip = document.createElement("span");
    chip.className = "status-chip";
    chip.textContent = status;
    stepStatusEl.appendChild(chip);
  });

  stepProtocolEl.innerHTML = "";
  step.protocol.forEach((item) => {
    const tag = document.createElement("span");
    tag.className = "protocol-tag";
    tag.textContent = item;
    stepProtocolEl.appendChild(tag);
  });

  prevStepEl.disabled = activeStepIndex === 0;
  nextStepEl.disabled = activeStepIndex === scenario.presentation.steps.length - 1;
}

prevStepEl.addEventListener("click", () => {
  if (activeStepIndex > 0) {
    activeStepIndex -= 1;
    renderStep();
  }
});

nextStepEl.addEventListener("click", () => {
  const total = scenarios[activeScenarioIndex].presentation.steps.length;
  if (activeStepIndex < total - 1) {
    activeStepIndex += 1;
    renderStep();
  }
});

backButtonEl.addEventListener("click", () => {
  scenarioViewEl.classList.add("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

renderGallery();
