import "@design/tokens/tokens.css";
import "@/styles/app.css";

import { createApp, watch } from "vue";

import App from "@/App.vue";
import { loadCatalog, pickLanguage, t } from "@/i18n";
import { createAppRouter } from "@/router";
import { connect, mustPair } from "@/session";

await loadCatalog(pickLanguage(navigator.languages));
document.title = t("app.title");

const router = createAppRouter();
// The board may forget this device at any time: the pairing screen takes over when it does.
watch(mustPair, (must) => {
  if (must) void router.replace({ name: "pair" });
});

// Not waited for: a board that does not answer, or answers with an error, is asked again
// behind a screen that says so, never behind a blank page.
void connect();

createApp(App).use(router).mount("#app");
