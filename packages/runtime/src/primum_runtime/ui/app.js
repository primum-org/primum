// The runtime's page: one switch per output (and a level for those that take one), the state
// of each input and the panic button. The service is the only
// source of truth: the page shows the states it receives and never guesses one.

import { loadCatalog, pickLanguage } from "./i18n.js";
import { loadIcons } from "./icons.js";

const RECONNECT_MIN_MS = 1000;
const RECONNECT_MAX_MS = 10000;
// A test from the page: the output goes on, and off on its own after this long.
const TEST_MS = 10000;
const COUNTDOWN_STEP_MS = 250;
const MIN_TEST_MS = 1000;

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
let stateAt = 0; // when it arrived, by the page's clock: what a countdown counts from
let online = false;

function take(newState) {
  state = newState;
  stateAt = performance.now();
  render();
}

// --- Rendering -------------------------------------------------------------------------

function render() {
  page.panicActive.hidden = !state?.panic;
  const outputs = state?.outputs ?? [];
  dropRowsNotIn(page.outputs, "output", outputs);
  for (const output of outputs) {
    const button = rowFor(output).querySelector(".switch");
    // Offline the last state may be stale (stopping the service turns outputs off): the switch
    // is "mixed" (neither on nor off), with no word and the thumb in the middle.
    button.setAttribute("aria-pressed", online ? String(output.on) : "mixed");
    const word = output.on ? catalog.t("output.on") : catalog.t("output.off");
    button.querySelector(".switch-state").textContent = online ? word : "";
    button.disabled = !online || state.panic;
    renderTest(output);
    renderLevel(output);
  }
  const inputs = state?.inputs ?? [];
  page.inputsSection.hidden = inputs.length === 0;
  dropRowsNotIn(page.inputs, "input", inputs);
  for (const input of inputs) {
    const shown = inputRowFor(input).querySelector(".input-state");
    // Offline the last state may be stale: no word, as for a switch.
    const word = input.active ? catalog.t("input.active") : catalog.t("input.inactive");
    shown.textContent = online ? word : "";
    shown.dataset.active = String(online && input.active);
  }
}

// A test under way shows how long is left. The service says it once, with the state; the
// page counts down from there on its own clock, and never past zero.
function renderTest(output) {
  const row = rowFor(output);
  // A test is for an output that is off: one left on on purpose would be turned off by it.
  const testing = online && output.remainingMs !== null;
  row.querySelector(".test").disabled = !online || state.panic || (output.on && !testing);
  // Counted from when the state arrived, not from now: rendering the same state again must
  // not start the countdown again.
  row.dataset.testUntil = testing ? String(stateAt + output.remainingMs) : "";
  // A test of something that is off has nothing to count down to.
  row.dataset.countdown = String(testing && output.on);
  row.dataset.restFailed = String(online && output.restFailed);
  countDown(row);
}

function countDown(row) {
  const shown = row.querySelector(".testing");
  const failed = row.dataset.restFailed === "true";
  shown.hidden = row.dataset.countdown !== "true" && !failed;
  if (shown.hidden) return;
  // A countdown is a timer: a screen reader does not announce each second of it. That an
  // output could not be confirmed off is a status, said once when it appears.
  shown.setAttribute("role", failed ? "status" : "timer");
  if (failed) {
    shown.textContent = catalog.t("output.test_stuck");
    return;
  }
  shown.textContent = catalog.t("output.testing", { seconds: Math.ceil(testLeftMs(row) / 1000) });
}

// How long the test of a row has left, by the page's clock; 0 with no test under way.
const testLeftMs = (row) =>
  row.dataset.testUntil ? Math.max(0, Number(row.dataset.testUntil) - performance.now()) : 0;

setInterval(() => page.outputs.querySelectorAll("[data-output]").forEach(countDown), COUNTDOWN_STEP_MS);

// An output that can be set to a level (its driver has the action "set") gets a slider. While
// a finger is on it, the slider is the person's: a state that arrives does not move it.
function renderLevel(output) {
  const level = rowFor(output).querySelector(".level");
  level.hidden = !output.actions.includes("set");
  if (level.hidden) return;
  const slider = level.querySelector(".level-slider");
  const refused = !online || state.panic;
  // A slider taken from the person's hand (panic, or the connection lost) lets go without
  // asking for anything: before it is disabled, since disabling it blurs it, and a blur is
  // a way of letting go.
  if (refused) slider.dataset.held = "false";
  slider.disabled = refused;
  if (slider.dataset.held === "true") return;
  slider.dataset.asked = ""; // answered: the service's level is what counts from here on
  slider.value = String(Math.round(output.level));
  // Offline the last level may be stale: no number, as a switch has no word.
  level.querySelector(".level-value").textContent = online ? levelText(slider.value) : "";
}

const levelText = (level) => catalog.t("output.level", { level });

// The level of an output as the slider shows it: whole, as the service last reported it.
const shownLevel = (id) =>
  Math.round(state?.outputs.find((output) => output.id === id)?.level ?? 0);

// A row is of an element by its id, which never changes; its name is only what is shown.
// The service may come back with other elements (another package): rows of what is gone go.
function dropRowsNotIn(list, kind, elements) {
  const ids = new Set(elements.map((element) => element.id));
  for (const row of list.querySelectorAll(`[data-${kind}]`)) {
    if (!ids.has(row.dataset[kind])) row.remove();
  }
}

function inputRowFor({ id, name }) {
  const existing = page.inputs.querySelector(`[data-input="${CSS.escape(id)}"]`);
  const row = existing ?? page.inputRow.content.firstElementChild.cloneNode(true);
  // The name is set every time: the same element may come back with another (a new package).
  row.querySelector(".output-name").textContent = name;
  if (existing) return existing;
  row.dataset.input = id;
  page.inputs.append(row);
  return row;
}

// What a row says of its element's name, set every time it is rendered: an element keeps its
// id and may change its name (a new package, the page still open).
function nameRow(row, name) {
  if (row.dataset.name === name) return;
  row.dataset.name = name;
  row.querySelector(".output-name").textContent = name;
  row.querySelector(".switch").setAttribute("aria-label", catalog.t("output.toggle", { name }));
  const seconds = TEST_MS / 1000;
  row.querySelector(".test").setAttribute("aria-label", catalog.t("output.test_of", { name, seconds }));
  row.querySelector(".level-slider").setAttribute("aria-label", catalog.t("output.level_of", { name }));
}

function rowFor({ id, name }) {
  const existing = page.outputs.querySelector(`[data-output="${CSS.escape(id)}"]`);
  if (existing) {
    nameRow(existing, name);
    return existing;
  }
  const row = page.outputRow.content.firstElementChild.cloneNode(true);
  row.dataset.output = id;
  nameRow(row, name);
  const button = row.querySelector(".switch");
  button.addEventListener("click", () => ask(id, button.getAttribute("aria-pressed") === "true" ? "off" : "on"));
  const test = row.querySelector(".test");
  test.textContent = catalog.t("output.test");
  test.addEventListener("click", () => ask(id, "on", {}, TEST_MS));
  const slider = row.querySelector(".level-slider");
  // Moving the slider only shows the number; the level is asked for once, on letting go: of
  // the pointer, of the key, or of the slider altogether. Never on "change": a browser sends
  // one per step of a held key, and none when the slider comes back to where it was.
  const hold = () => { slider.dataset.held = "true"; };
  const letGo = async () => {
    if (slider.dataset.held !== "true" || slider.disabled) return;
    slider.dataset.held = "false";
    const wanted = Number(slider.value);
    if (wanted !== shownLevel(id)) {
      slider.dataset.asked = String(wanted);
      // During a test, the new level is part of the test: it keeps the time it had left
      // (a second at least, the shortest a test lasts), instead of staying on for good.
      // Whether a test is under way is the service's word, shown as a countdown or not.
      const testing = row.dataset.testUntil !== "";
      const left = testing ? Math.max(MIN_TEST_MS, Math.round(testLeftMs(row))) : null;
      await ask(id, "set", { level: wanted }, left);
    }
    render(); // whatever came of it, the slider shows the level the service reports
  };
  slider.addEventListener("pointerdown", hold);
  slider.addEventListener("keydown", hold);
  for (const end of ["pointerup", "pointercancel", "keyup", "blur"]) slider.addEventListener(end, letGo);
  slider.addEventListener("input", () => {
    row.querySelector(".level-value").textContent = levelText(slider.value);
  });
  // Changed with nothing held (assistive technology sets a value at once): ask for it,
  // unless letting go has just asked for that very level (a browser sends "change" then too).
  slider.addEventListener("change", () => {
    if (slider.dataset.held === "true" || slider.dataset.asked === slider.value) return;
    // Disabled in the middle of a drag, a browser sends "change" as well: nobody asked.
    if (slider.disabled) return;
    ask(id, "set", { level: Number(slider.value) });
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
  take(payload);
}

// Ask an output for one of the actions of its driver, with the arguments it takes by name.
// With a duration it is a test: the output goes to rest on its own when it has passed.
const ask = (id, action, args = {}, durationMs = null) =>
  command("PUT", `outputs/${encodeURIComponent(id)}`, { action, arguments: args, durationMs });

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
    take(JSON.parse(event.data));
  });
  socket.addEventListener("close", () => {
    online = false;
    showOffline(true);
    render();
    setTimeout(() => connect(Math.min(delay * 2, RECONNECT_MAX_MS)), delay);
  });
}

connect();
