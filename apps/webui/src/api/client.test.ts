import { afterEach, expect, test, vi } from "vitest";

import { api, ApiError, OfflineError } from "@/api/client";

const answer = (status: number, body: unknown): Response =>
  new Response(typeof body === "string" ? body : JSON.stringify(body), { status });

afterEach(() => vi.unstubAllGlobals());

test("a request goes to the API that is served next to the page", async () => {
  const fetched = vi.fn(async () => answer(200, { required: true, device: null }));
  vi.stubGlobal("fetch", fetched);
  document.head.innerHTML = '<base href="http://board.local:8080/">';

  expect(await api.pairing()).toEqual({ required: true, device: null });

  const [url, init] = fetched.mock.calls[0] as unknown as [URL, RequestInit];
  expect(String(url)).toBe("http://board.local:8080/api/pairing");
  expect(init.method).toBe("GET");
});

test("a body is sent as JSON", async () => {
  const fetched = vi.fn(async () => answer(200, { token: "t", device: { id: "1", name: "phone", current: true } }));
  vi.stubGlobal("fetch", fetched);

  await api.pair("123456", "phone");

  const [, init] = fetched.mock.calls[0] as unknown as [URL, RequestInit];
  expect(init.body).toBe('{"code":"123456","name":"phone"}');
  expect(init.headers).toEqual({ "Content-Type": "application/json" });
});

test("what the board refuses is raised with its code and params", async () => {
  vi.stubGlobal("fetch", async () => answer(403, { code: "pairing.code_wrong", params: { left: 4 } }));

  const refused = await api.pair("000000", "").catch((error: unknown) => error);

  expect(refused).toBeInstanceOf(ApiError);
  expect(refused).toMatchObject({ status: 403, code: "pairing.code_wrong", params: { left: 4 }, unpaired: false });
});

test("a device that is not paired is told apart", async () => {
  vi.stubGlobal("fetch", async () => answer(401, { code: "pairing.required", params: {} }));

  expect(await api.unpair().catch((error: unknown) => error)).toMatchObject({ unpaired: true });
});

test("a failure that is not JSON gets its HTTP status as its code", async () => {
  vi.stubGlobal("fetch", async () => answer(502, "<html>Bad Gateway</html>"));

  expect(await api.pairing().catch((error: unknown) => error)).toMatchObject({ code: "http.502", params: {} });
});

test("no answer at all is not an error of the board", async () => {
  vi.stubGlobal("fetch", async () => {
    throw new TypeError("Failed to fetch");
  });

  expect(await api.pairing().catch((error: unknown) => error)).toBeInstanceOf(OfflineError);
});
