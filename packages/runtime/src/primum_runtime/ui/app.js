// The runtime's page: one switch per output and the panic button. The service is the only
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
    button.setAttribute("aria-pressed", String(output.on));
    // Offline the last state may be stale (stopping the service turns outputs off): no word,
    // and the thumb waits in the middle (data-stale).
    const word = output.on ? catalog.t("output.on") : catalog.t("output.off");
    button.querySelector(".switch-state").textContent = online ? word : "";
    button.toggleAttribute("data-stale", !online);
    button.disabled = !online || state.panic;
  }
}

function rowFor(name) {
  const existing = page.outputs.querySelector(`[data-output="${CSS.escape(name)}"]`);
  if (existing) return existing;
  const row = page.outputRow.content.firstElementChild.cloneNode(true);
  row.dataset.output = name;
  row.querySelector(".output-name").textContent = name;
  const button = row.querySelector(".switch");
  button.setAttribute("aria-label", catalog.t("output.toggle", { name }));
  button.addEventListener("click", () => setOutput(name, button.getAttribute("aria-pressed") !== "true"));
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

const setOutput = (name, on) => command("PUT", `outputs/${encodeURIComponent(name)}`, { on });

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
