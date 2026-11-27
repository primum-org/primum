import en from "@i18n/en.json";
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { COMMAND_TIMEOUT_MS } from "@/api/client";
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

test("a device sent here by an order the board did not take is told so", async () => {
  session.refused = "forgotten";
  const router = createAppRouter();
  await router.push("/pair");

  const view = mount(PairView, { global: { plugins: [router] } });

  expect(view.get('[role="alert"]').text()).toContain("no longer knows this device");
  session.refused = null;
});

test("pairing with a board that does not answer says it is out of reach, not that an order was left undone", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("fetch", (_url: URL, init: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    }));
  const router = createAppRouter();
  session.pairing = { required: true, device: null };
  const pushed = router.push("/pair");
  await vi.advanceTimersByTimeAsync(0);
  await pushed;
  const view = mount(PairView, { global: { plugins: [router] } });
  await view.get("#pairing-code").setValue("123456");

  await view.get("form").trigger("submit");
  await vi.advanceTimersByTimeAsync(COMMAND_TIMEOUT_MS);
  await flushPromises();

  expect(view.text()).toContain("No connection with the board");
  expect(view.text()).not.toContain("did not answer");
  vi.useRealTimers();
});

test("a device sent here with no order given is told why, and not that an order was lost", async () => {
  session.refused = "unpaired";
  const router = createAppRouter();
  await router.push("/pair");

  const view = mount(PairView, { global: { plugins: [router] } });

  expect(view.get('[role="status"]').text()).toBe("The board no longer knows this device. Pair it again to go on.");
  expect(view.find('[role="alert"]').exists()).toBe(false);
  session.refused = null;
});
