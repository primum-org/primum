// The screens. Addresses are after a # so that the service serves the app without knowing
// its screens: whatever is typed after the #, the same file answers.

import { createRouter, createWebHashHistory, type Router } from "vue-router";

import { mustPair, refreshPairing, session } from "@/session";
import ActivityView from "@/views/ActivityView.vue";
import ControlView from "@/views/ControlView.vue";
import PairView from "@/views/PairView.vue";
import SettingsView from "@/views/SettingsView.vue";

export function createAppRouter(): Router {
  const router = createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: "/", name: "control", component: ControlView },
      { path: "/activity", name: "activity", component: ActivityView },
      { path: "/settings", name: "settings", component: SettingsView },
      { path: "/pair", name: "pair", component: PairView },
    ],
  });
  // Nothing is shown to a device the board does not know: the pairing screen comes first.
  router.beforeEach(async (to) => {
    // A board that cannot say is not a reason to stop here: every screen says why above
    // its content, and that it is being asked again.
    if (session.pairing === null && session.problem === null) await refreshPairing();
    if (mustPair()) return to.name === "pair" ? true : { name: "pair" };
    return to.name === "pair" ? { name: "control" } : true;
  });
  return router;
}
