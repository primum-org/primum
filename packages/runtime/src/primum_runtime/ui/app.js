// The runtime's page: one switch per output (and a level for those that take one), the state
// of each input and the panic button. The service is the only
// source of truth: the page shows the states it receives and never guesses one.

import { loadCatalog, pickLanguage } from "./i18n.js";
import { loadIcons } from "./icons.js";

const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 10000;

const page = {
  connection: document.getElementById("connection"),
  panicActive: document.getElementById("panic-active"),
  releasePanic: document.getElementById("release-panic"),
  error: document.getElementById("error"),
  errorMessage: document.getElementById("error-message"),
  errorHint: document.getElementById("error-hint"),
  errorTechnical: document.getElementById("error-technical"),
  errorTechnicalText: document.getElementById("error-technical-text"),
  errorClose: document.getElementById("error-close"),
  outputs: document.getElementById("outputs"),
  outputRow: document.getElementById("output-row"),
  inputsSection: document.getElementById("inputs-section"),
  inputs: document.getElementById("inputs"),
  inputRow: document.getElementById("input-row"),
  panic: document.getElementById("panic"),
};

const [catalog] = await Promise.all([
  loadCatalog(pickLanguage(navigator.languages)),
  loadIcons(document.documentElement),
]);
catalog.apply(document);

let state = null;
let online = false;

// --- Rendering -------------------------------------------------------------------------

function render() {
  page.panicActive.hidden = !state?.panic;
  for (const output of state?.outputs ?? []) {
    const button = rowFor(output.name).querySelector(".switch");
    // Offline the last state may be stale (stopping the service turns outputs off): the switch
    // is "mixed" (neither on nor off), with no word and the thumb in the middle.
    button.setAttribute("aria-pressed", online ? String(output.on) : "mixed");
    const word = output.on ? catalog.t("output.on") : catalog.t("output.off");
    button.querySelector(".switch-state").textContent = online ? word : "";
    button.disabled = !online || state.panic;
    renderLevel(output);
  }
  const inputs = state?.inputs ?? [];
  page.inputsSection.hidden = inputs.length === 0;
  for (const input of inputs) {
    const shown = inputRowFor(input.name).querySelector(".input-state");
    // Offline the last state may be stale: no word, as for a switch.
    const word = input.active ? catalog.t("input.active") : catalog.t("input.inactive");
    shown.textContent = online ? word : "";
    shown.dataset.active = String(online && input.active);
  }
}

// An output that can be set to a level (its driver has the action "set") gets a slider. While
// a finger is on it, the slider is the person's: a state that arrives does not move it.
function renderLevel(output) {
  const level = rowFor(output.name).querySelector(".level");
  level.hidden = !output.actions.includes("set");
  if (level.hidden) return;
  const slider = level.querySelector(".level-slider");
  slider.disabled = !online || state.panic;
  if (slider.dataset.held === "true") return;
  slider.value = String(Math.round(output.level));
  // Offline the last level may be stale: no number, as a switch has no word.
  level.querySelector(".level-value").textContent = online ? levelText(slider.value) : "";
}

const levelText = (level) => catalog.t("output.level", { level });

function inputRowFor(name) {
  const existing = page.inputs.querySelector(`[data-input="${CSS.escape(name)}"]`);
  if (existing) return existing;
  const row = page.inputRow.content.firstElementChild.cloneNode(true);
  row.dataset.input = name;
  row.querySelector(".output-name").textContent = name;
  page.inputs.append(row);
  return row;
}

function rowFor(name) {
  const existing = page.outputs.querySelector(`[data-output="${CSS.escape(name)}"]`);
  if (existing) return existing;
  const row = page.outputRow.content.firstElementChild.cloneNode(true);
  row.dataset.output = name;
  row.querySelector(".output-name").textContent = name;
  const button = row.querySelector(".switch");
  button.setAttribute("aria-label", catalog.t("output.toggle", { name }));
  button.addEventListener("click", () => ask(name, button.getAttribute("aria-pressed") === "true" ? "off" : "on"));
  const slider = row.querySelector(".level-slider");
  slider.setAttribute("aria-label", catalog.t("output.level_of", { name }));
  // Moving the slider only shows the number; the level is asked for once, on letting go.
  slider.addEventListener("input", () => {
    slider.dataset.held = "true";
    row.querySelector(".level-value").textContent = levelText(slider.value);
  });
  slider.addEventListener("change", async () => {
    await ask(name, "set", { level: Number(slider.value) });
    slider.dataset.held = "false";
    render(); // whatever came of it, the slider shows the level the service reports
  });
  page.outputs.append(row);
  return row;
}

function showOffline(offline) {
  page.connection.hidden = !offline;
}

function showError(error) {
  const { message, hint } = catalog.error(error);
  const technical = catalog.technical(error);
  page.errorMessage.textContent = message;
  page.errorHint.textContent = hint;
  page.errorTechnical.hidden = technical.length === 0;
  page.errorTechnicalText.textContent = technical.join("\n");
  page.error.hidden = false;
}

// --- Commands ----------------------------------------------------------------------------

async function command(method, path, body) {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) options.body = JSON.stringify(body);
  let response;
  try {
    response = await fetch(`api/${path}`, options);
  } catch {
    showOffline(true);
    return;
  }
  // An unexpected failure may not be JSON: its HTTP status stands in for the code.
  const payload = await response.json().catch(() => ({ code: `http.${response.status}` }));
  if (!response.ok) {
    showError(payload);
    return;
  }
  page.error.hidden = true;
  state = payload;
  render();
}

// Ask an output for one of the actions of its driver, with the arguments it takes by name.
const ask = (name, action, args = {}) =>
  command("PUT", `outputs/${encodeURIComponent(name)}`, { action, arguments: args });

page.panic.addEventListener("click", () => command("POST", "panic"));
page.releasePanic.addEventListener("click", () => command("DELETE", "panic"));
page.errorClose.addEventListener("click", () => { page.error.hidden = true; });

// --- Live state --------------------------------------------------------------------------

function connect(delay = RECONNECT_MIN_MS) {
  const url = new URL("api/ws", location.href);
  url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(url);
  socket.addEventListener("open", () => {
    online = true;
    delay = RECONNECT_MIN_MS;
    showOffline(false);
  });
  socket.addEventListener("message", (event) => {
    state = JSON.parse(event.data);
    render();
  });
  socket.addEventListener("close", () => {
    online = false;
    showOffline(true);
    render();
    setTimeout(() => connect(Math.min(delay * 2, RECONNECT_MAX_MS)), delay);
  });
}

connect();
