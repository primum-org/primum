// The screens. Addresses are after a # so that the app works wherever the service puts it
// (/app/ now, / later) without the service knowing its screens.

import { createRouter, createWebHashHistory, type Router } from "vue-router";

import { mustPair, refreshPairing, session } from "@/session";
import HomeView from "@/views/HomeView.vue";
import PairView from "@/views/PairView.vue";

export function createAppRouter(): Router {
  const router = createRouter({
    history: createWebHashHistory(),
    routes: [
      { path: "/", name: "home", component: HomeView },
      { path: "/pair", name: "pair", component: PairView },
    ],
  });
  // Nothing is shown to a device the board does not know: the pairing screen comes first.
  router.beforeEach(async (to) => {
    if (session.pairing === null) await refreshPairing();
    if (mustPair()) return to.name === "pair" ? true : { name: "pair" };
    return to.name === "pair" ? { name: "home" } : true;
  });
  return router;
}
