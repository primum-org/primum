import { enableAutoUnmount, flushPromises, mount } from "@vue/test-utils";
import { afterEach, expect, test, vi } from "vitest";

import DevicesPanel from "@/components/DevicesPanel.vue";
import { session } from "@/session";
import { board, json, state } from "@/testing/board";

const THIS = { id: "1", name: "Joan's phone", current: true };
const TABLET = { id: "2", name: "Tablet", current: false };
const NAMELESS = { id: "3", name: "", current: false };

enableAutoUnmount(afterEach);
afterEach(() => vi.unstubAllGlobals());

function boardWith(...answers: Response[]) {
  return board(state(), () => answers.shift() ?? json([THIS]));
}

test("the paired devices, this one marked and not offered to forget here", async () => {
  const asked = boardWith(json([THIS, TABLET, NAMELESS]));
  const view = mount(DevicesPanel);
  await flushPromises();

  expect(asked[0]).toMatchObject({ method: "GET", path: "/api/pairing/devices" });
  const rows = view.findAll("li");
  expect(rows.map((row) => row.find(".row-name").text())).toEqual(["Joan's phone", "Tablet", "No name"]);
  expect(rows[0]?.text()).toContain("This device");
  expect(rows[0]?.find("button").exists()).toBe(false);
  expect(rows[1]?.find("button").exists()).toBe(true);
});

test("forgetting another device asks first, saying what it means, then asks the board by its id", async () => {
  const asked = boardWith(json([THIS, TABLET]), json([THIS]));
  const view = mount(DevicesPanel);
  await flushPromises();

  await view.findAll("li")[1]?.get("button").trigger("click");
  expect(asked).toHaveLength(1);
  expect(view.get(".confirm").text()).toContain("Tablet will no longer reach the board until it pairs again");

  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();

  expect(asked[1]).toEqual({ method: "DELETE", path: "/api/pairing/devices/2", body: undefined });
  expect(view.findAll("li")).toHaveLength(1);
});

test("forgetting can be called off", async () => {
  const asked = boardWith(json([THIS, TABLET]));
  const view = mount(DevicesPanel);
  await flushPromises();

  await view.findAll("li")[1]?.get("button").trigger("click");
  await view.findAll(".confirm button")[1]?.trigger("click");

  expect(view.find(".confirm").exists()).toBe(false);
  expect(asked).toHaveLength(1);
});

test("a device another one forgot meanwhile is said as the board says it", async () => {
  boardWith(json([THIS, TABLET]), json({ code: "pairing.device_unknown", params: { id: "2" } }, 404));
  const view = mount(DevicesPanel);
  await flushPromises();

  await view.findAll("li")[1]?.get("button").trigger("click");
  await view.get(".confirm .button-primary").trigger("click");
  await flushPromises();

  expect(view.find("[role=alert]").exists()).toBe(true);
});

test("out of reach says nothing here, and the list is asked for again when the board is back", async () => {
  const asked = board(state(), () => {
    throw new TypeError("Failed to fetch");
  });
  const view = mount(DevicesPanel);
  await flushPromises();
  expect(view.find("[role=status]").exists()).toBe(false); // the strip above every screen says it

  session.online = false;
  await flushPromises();
  vi.stubGlobal("fetch", async (url: URL) => {
    asked.push({ method: "GET", path: url.pathname, body: undefined });
    return json([THIS]);
  });
  session.online = true;
  await flushPromises();

  expect(view.findAll("li")).toHaveLength(1);
});
