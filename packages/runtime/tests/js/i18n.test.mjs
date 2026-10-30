// The page's text logic (ui/i18n.js), with the real catalogs. Run with `just test-js`.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import { Catalog, pickLanguage } from "../../src/primum_runtime/ui/i18n.js";

const catalog = (language) =>
  new Catalog(
    language,
    JSON.parse(readFileSync(new URL(`../../../../i18n/${language}.json`, import.meta.url))),
  );

test("pickLanguage takes the first preferred language that has a catalog", () => {
  assert.equal(pickLanguage(["fr-FR", "es-ES", "en"]), "es");
  assert.equal(pickLanguage(["EN-gb"]), "en");
});

test("pickLanguage falls back to English", () => {
  assert.equal(pickLanguage(["fr", "de"]), "en");
  assert.equal(pickLanguage([]), "en");
});

test("t fills placeholders and keeps unknown ones visible", () => {
  const es = catalog("es");

  assert.equal(es.t("output.toggle", { name: "led" }), "Encender o apagar led");
  assert.equal(es.t("output.toggle"), "Encender o apagar {name}");
});

test("error formats lists of pins for the language", () => {
  const error = { code: "hal.safe_state_incomplete", params: { pins: [17, 27] } };

  assert.equal(catalog("en").error(error).message, "Pins 17 and 27 could not be put in their safe state.");
  assert.equal(catalog("es").error(error).message, "No se pudieron poner en estado seguro los pines 17 y 27.");
});

test("error gives a generic message for a code the catalog does not know", () => {
  const { message, hint } = catalog("en").error({ code: "http.500" });

  assert.equal(message, "Unexpected error (http.500).");
  assert.equal(hint, "");
});

test("technical params are listed apart, never inside the message", () => {
  const en = catalog("en");
  const error = { code: "hal.pin_unavailable", params: { pin: 2, chip: "/dev/gpiochip0", detail: "busy" } };

  assert.equal(en.error(error).message, "Pin 2 is being used by something else on this board.");
  assert.deepEqual(en.technical(error), ["detail: busy"]);
  assert.deepEqual(en.technical({ code: "panic.active" }), []);
});
