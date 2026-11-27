import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import { afterEach, expect, test, vi } from "vitest";

import { COMMAND_TIMEOUT_MS } from "@/api/client";
import type { PackagesBody } from "@/api/types";
import PackagesPanel from "@/components/PackagesPanel.vue";
import { mustPair, session } from "@/session";
import { board, json, output, state } from "@/testing/board";

const SHOP = { hash: "sha256:aaaaaaaaaaaaaaaaaaaa", project: "Shop window" };
const SHOP2 = { hash: "sha256:bbbbbbbbbbbbbbbbbbbb", project: "Shop window" };
const LIGHTS = { hash: "sha256:cccccccccccccccccccc", project: "Evening lights" };
const kept = (over: Partial<PackagesBody> = {}): PackagesBody => ({
  running: SHOP,
  active: SHOP,
  previous: LIGHTS,
  staged: SHOP2,
  problem: null,
  fixed: false,
  ...over,
});

// A board whose answers to the package's requests the test gives, in order.
function boardWith(...answers: Response[]) {
  return board(state(), () => answers.shift() ?? json(kept()));
}

// A panel left mounted would go on asking for the packages in the tests after it.
enableAutoUnmount(afterEach);

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("the active, staged and previous packages by their project, and a hash to tell versions apart", async () => {
  const asked = boardWith(json(kept()));
  const view = mount(PackagesPanel);
  await flushPromises();

  expect(asked[0]).toMatchObject({ method: "GET", path: "/api/package" });
  const rows = view.findAll("li");
  expect(rows.map((row) => row.findAll(".row-name p").map((line) => line.text()))).toEqual([
    ["Active", "Shop window", "aaaaaaaaaaaa"],
    ["Ready to activate", "Shop window", "bbbbbbbbbbbb"],
    ["Previous", "Evening lights", "cccccccccccc"],
  ]);
});

test("activating asks first, saying what stops, and only then asks the board", async () => {
  const asked = boardWith(json(kept()), json(kept({ active: SHOP2, running: SHOP2, previous: SHOP, staged: null })));
  const view = mount(PackagesPanel);
  await flushPromises();

  await view.get(".package-staged .row-controls button").trigger("click");
  expect(asked).toHaveLength(1);
  expect(view.get(".confirm").text()).toContain("every output will go to its safe state");

  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();

  expect(asked[1]).toEqual({ method: "POST", path: "/api/package/activate", body: { hash: SHOP2.hash } });
  expect(view.text()).toContain("Shop window is running.");
  expect(view.find(".package-staged").text()).toContain("None");
});

test("going back asks first too, and can be called off", async () => {
  const asked = boardWith(json(kept()), json(kept({ active: LIGHTS, previous: SHOP })));
  const view = mount(PackagesPanel);
  await flushPromises();

  await view.get(".package-previous .row-controls button").trigger("click");
  await view.findAll(".confirm button")[1]?.trigger("click"); // cancel
  expect(view.find(".confirm").exists()).toBe(false);
  expect(asked).toHaveLength(1);

  await view.get(".package-previous .row-controls button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();
  expect(asked[1]).toEqual({ method: "POST", path: "/api/package/rollback", body: undefined });
});

test("what the board refuses is said, and what was active stays", async () => {
  const failed = { code: "package.activation_failed", params: { hash: SHOP2.hash, problem: "x" } };
  boardWith(json(kept()), json(failed, 500));
  const view = mount(PackagesPanel);
  await flushPromises();

  await view.get(".package-staged .row-controls button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();

  expect(view.text()).toContain("could not be started, and the board went back");
  expect(view.find(".package-active").text()).toContain("aaaaaaaaaaaa");
});

test("an activation that takes longer than an order is waited for", async () => {
  vi.useFakeTimers();
  boardWith(json(kept()));
  const view = mount(PackagesPanel);
  await flushPromises();
  vi.stubGlobal("fetch", (_url: URL, init: RequestInit) =>
    new Promise<Response>((resolve, reject) => {
      const slow = setTimeout(() => resolve(json(kept({ active: SHOP2, staged: null }))), COMMAND_TIMEOUT_MS * 2);
      init.signal?.addEventListener("abort", () => {
        clearTimeout(slow);
        reject(new DOMException("aborted", "AbortError"));
      });
    }),
  );

  await view.get(".package-staged .row-controls button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  expect(view.get(".confirm .button-primary").text()).toBe("Activating…");
  await vi.advanceTimersByTimeAsync(COMMAND_TIMEOUT_MS * 2);
  await flushPromises();

  expect(view.text()).toContain("Shop window is running.");
  expect(session.refused).toBeNull();
});

test("nothing is activated in panic, nor offline", async () => {
  boardWith(json(kept()));
  session.state = state({ panic: true });
  const view = mount(PackagesPanel);
  await flushPromises();

  expect(view.get(".package-staged .row-controls button").attributes("disabled")).toBeDefined();
  expect(view.text()).toContain("once panic is released");

  session.state = state();
  session.online = false;
  await view.vm.$nextTick();
  expect(view.get(".package-previous .row-controls button").attributes("disabled")).toBeDefined();
});

test("a board started with fixed options says that nothing can be changed here", async () => {
  boardWith(json(kept({ fixed: true, active: null, previous: null, staged: null })));
  const view = mount(PackagesPanel);
  await flushPromises();

  expect(view.text()).toContain("cannot be changed from here");
  expect(view.find("button").exists()).toBe(false);
});

test("while shown, the packages are asked for again when the state says something new, not on a beat", async () => {
  vi.useFakeTimers();
  const asked = boardWith(json(kept()), json(kept({ active: LIGHTS })));
  const { listen, stop, PACKAGES_MIN_INTERVAL_MS } = await import("@/session");
  class FakeSocket extends EventTarget {
    static last: FakeSocket | null = null;
    constructor() {
      super();
      FakeSocket.last = this;
    }
    close(): void {}
  }
  vi.stubGlobal("WebSocket", FakeSocket);
  listen();
  const say = (said: object) =>
    FakeSocket.last?.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(said) }));
  say(state());
  await flushPromises();
  const view = mount(PackagesPanel);
  await flushPromises();
  const before = asked.length;

  say(state()); // a beat
  await flushPromises();
  expect(asked).toHaveLength(before);

  say(state({ sequences: [{ id: "s", name: "Show", running: false }] })); // another device activated something
  await vi.advanceTimersByTimeAsync(PACKAGES_MIN_INTERVAL_MS);
  expect(asked).toHaveLength(before + 1);

  view.unmount();
  say(state({ sequences: [] }));
  await vi.advanceTimersByTimeAsync(PACKAGES_MIN_INTERVAL_MS);
  expect(asked).toHaveLength(before + 1); // not shown any more
  stop();
});

test("a device the board forgot is sent to pair again, not left with a code it has nowhere to give", async () => {
  const unpaired = { code: "pairing.required", params: {} };
  boardWith(json(kept()), json(unpaired, 401), json({ required: true, device: null }));
  const view = mount(PackagesPanel);
  await flushPromises();

  await view.get(".package-previous .row-controls button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();

  expect(session.refused).toBe("forgotten");
  expect(mustPair()).toBe(true); // the pairing screen takes over (main.ts)
  expect(view.find("[role=alert]").exists()).toBe(false);
});

test("what was said to run is no longer said once something else is active", async () => {
  boardWith(json(kept()), json(kept({ active: SHOP2, running: SHOP2, previous: SHOP, staged: null })));
  const view = mount(PackagesPanel);
  await flushPromises();
  await view.get(".package-staged .row-controls button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();
  expect(view.find(".notice-success").exists()).toBe(true);

  session.packages = kept({ active: SHOP, running: SHOP, previous: SHOP2, staged: null }); // gone back from elsewhere
  await view.vm.$nextTick();

  expect(view.find(".notice-success").exists()).toBe(false);
});

test("the packages are asked for once every few seconds at most while things keep changing", async () => {
  vi.useFakeTimers();
  const asked = boardWith();
  const { listen, stop, PACKAGES_MIN_INTERVAL_MS } = await import("@/session");
  class FakeSocket extends EventTarget {
    static last: FakeSocket | null = null;
    constructor() {
      super();
      FakeSocket.last = this;
    }
    close(): void {}
  }
  vi.stubGlobal("WebSocket", FakeSocket);
  listen();
  const say = (level: number) =>
    FakeSocket.last?.dispatchEvent(
      new MessageEvent("message", { data: JSON.stringify(state({ outputs: [output({ level })] })) }),
    );
  say(0);
  mount(PackagesPanel);
  await vi.advanceTimersByTimeAsync(0);
  const before = asked.length;

  // A sequence running: the state changes ten times a second for a second.
  for (let step = 1; step <= 10; step++) {
    say(step);
    await vi.advanceTimersByTimeAsync(100);
  }
  expect(asked.length - before).toBeLessThanOrEqual(1);

  await vi.advanceTimersByTimeAsync(PACKAGES_MIN_INTERVAL_MS);
  expect(asked.length - before).toBe(1); // the last change is not missed
  stop();
});

test("packages that could not be asked for are asked again when the connection is back", async () => {
  board(state(), () => {
    throw new TypeError("Failed to fetch");
  });
  const view = mount(PackagesPanel);
  await flushPromises();
  expect(view.text()).toContain("Asking the board for its packages");

  vi.stubGlobal("fetch", async () => json(kept()));
  session.online = false;
  await flushPromises();
  session.online = true;
  await flushPromises();

  expect(view.text()).toContain("Evening lights");
});

test("a confirmation whose package another device changed meanwhile goes, and leaves the other buttons free", async () => {
  boardWith(json(kept()));
  const view = mount(PackagesPanel);
  await flushPromises();
  await view.get(".package-staged .row-controls button").trigger("click");

  session.packages = kept({ active: SHOP2, running: SHOP2, previous: SHOP, staged: null }); // activated from elsewhere
  await flushPromises();

  expect(view.find(".confirm").exists()).toBe(false);
  expect(view.get(".package-previous .row-controls button").attributes("disabled")).toBeUndefined();
});

test("after a change, the focus goes to the section, not nowhere", async () => {
  boardWith(json(kept()), json(kept({ active: SHOP2, running: SHOP2, previous: SHOP, staged: null })));
  const view = mount(PackagesPanel, { attachTo: document.body });
  await flushPromises();
  await view.get(".package-staged .row-controls button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();

  expect(document.activeElement).toBe(view.get("h2").element);
});
