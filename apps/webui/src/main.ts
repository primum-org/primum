import "@design/tokens/tokens.css";
import "@/styles/app.css";

import { createApp, watch } from "vue";

import App from "@/App.vue";
import { loadCatalog, pickLanguage, t } from "@/i18n";
import { createAppRouter } from "@/router";
import { listen, mustPair, refreshPairing } from "@/session";

await loadCatalog(pickLanguage(navigator.languages));
document.title = t("app.title");

const router = createAppRouter();
// The board may forget this device at any time: the pairing screen takes over when it does.
watch(mustPair, (must) => {
  if (must) void router.replace({ name: "pair" });
});

await refreshPairing();
if (!mustPair()) listen();

createApp(App).use(router).mount("#app");
