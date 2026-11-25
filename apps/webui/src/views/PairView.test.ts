import en from "@i18n/en.json";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { Catalog, useCatalog } from "@/i18n";
import { createAppRouter } from "@/router";
import { session, stop } from "@/session";
import PairView from "@/views/PairView.vue";

class SilentSocket extends EventTarget {
  close(): void {}
}

beforeEach(() => {
  useCatalog(new Catalog("en", en));
  session.pairing = { required: true, device: null };
  vi.stubGlobal("WebSocket", SilentSocket);
});

afterEach(() => {
  stop();
  vi.unstubAllGlobals();
});

async function typed(code: string) {
  const router = createAppRouter();
  await router.push("/pair");
  const view = mount(PairView, { global: { plugins: [router] } });
  await view.get("#pairing-code").setValue(code);
  await view.get("#pairing-name").setValue("Joan's phone");
  await view.get("form").trigger("submit");
  await flushPromises();
  return { view, router };
}

test("the code and the name a person gives are sent, and a paired device goes to control", async () => {
  const device = { id: "1", name: "Joan's phone", current: true };
  const fetched = vi.fn(async () => new Response(JSON.stringify({ token: "t", device })));
  vi.stubGlobal("fetch", fetched);

  const { router } = await typed(" 123456 ");

  const [, init] = fetched.mock.calls[0] as unknown as [URL, RequestInit];
  expect(init.body).toBe('{"code":"123456","name":"Joan\'s phone"}');
  expect(session.pairing?.device).toEqual(device);
  expect(router.currentRoute.value.name).toBe("control");
});

test("a wrong code is said in words, with what to do, and the screen stays", async () => {
  const refused = { code: "pairing.code_wrong", params: { left: 4 } };
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify(refused), { status: 403 }));

  const { view, router } = await typed("000000");

  expect(view.get('[role="alert"]').text()).toContain("That is not the pairing code of this board. Tries left: 4.");
  expect(router.currentRoute.value.name).toBe("pair");
});

test("a board that does not answer is said as that, not as an error", async () => {
  vi.stubGlobal("fetch", async () => {
    throw new TypeError("Failed to fetch");
  });

  const { view } = await typed("123456");

  expect(view.find('[role="alert"]').exists()).toBe(false);
  expect(view.get('[role="status"]').text()).toBe("No connection with the board. Retrying…");
});
