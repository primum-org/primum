// The text logic, with the real catalogs.

import en from "@i18n/en.json";
import es from "@i18n/es.json";
import { expect, test } from "vitest";

import { Catalog, pickLanguage } from "@/i18n";

const english = new Catalog("en", en);
const spanish = new Catalog("es", es);

test("pickLanguage takes the first preferred language that has a catalog", () => {
  expect(pickLanguage(["fr-FR", "es-ES", "en"])).toBe("es");
  expect(pickLanguage(["EN-gb"])).toBe("en");
});

test("pickLanguage falls back to English", () => {
  expect(pickLanguage(["fr", "de"])).toBe("en");
  expect(pickLanguage([])).toBe("en");
});

test("t fills placeholders and keeps unknown ones visible", () => {
  expect(spanish.t("error.unknown", { code: "http.500" })).toBe("Error inesperado (http.500).");
  expect(spanish.t("error.unknown")).toBe("Error inesperado ({code}).");
});

test("a key the catalog lacks shows as the key, never as nothing", () => {
  expect(english.t("no.such.key")).toBe("no.such.key");
});

test("error formats lists for the language", () => {
  const error = { code: "hal.safe_state_incomplete", params: { pins: [17, 27] } };

  expect(english.error(error).message).toBe("Pins 17 and 27 could not be put in their safe state.");
  expect(spanish.error(error).message).toBe("No se pudieron poner en estado seguro los pines 17 y 27.");
});

test("error gives a generic message for a code the catalog does not know", () => {
  expect(english.error({ code: "http.500" })).toEqual({
    message: "Unexpected error (http.500).",
    hint: "",
  });
});

test("technical params are listed apart, never inside the message", () => {
  const error = { code: "hal.pin_unavailable", params: { pin: 2, chip: "/dev/gpiochip0", detail: "busy" } };

  expect(english.error(error).message).toBe("Pin 2 is being used by something else on this board.");
  expect(english.technical(error)).toEqual(["detail: busy"]);
  expect(english.technical({ code: "panic.active" })).toEqual([]);
});
