import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import { afterEach, expect, test, vi } from "vitest";

import { createAppRouter } from "@/router";
import { board, state } from "@/testing/board";
import SettingsView from "@/views/SettingsView.vue";

enableAutoUnmount(afterEach);
afterEach(() => vi.unstubAllGlobals());

test("unpairing with no connection says it was not done, not that it is being tried again", async () => {
  board(state(), () => {
    throw new TypeError("Failed to fetch");
  });
  const view = mount(SettingsView, { global: { plugins: [createAppRouter()] } });

  await view.get("button").trigger("click");
  await flushPromises();

  expect(view.text()).toContain("was not sent");
  expect(view.text()).not.toContain("Retrying");
});
