// Text for the page from the message catalogs (decision 0009). UI keys are always written
// literally, as t("panic.button") or data-i18n="panic.button": the catalog test finds them so.

const LANGUAGES = ["en", "es"];
const DEFAULT_LANGUAGE = "en";
// Params that carry system text: shown apart as a technical detail, never inside a message.
export const TECHNICAL_PARAMS = ["detail", "consumer", "fields"];

/** The first language the browser prefers that has a catalog. */
export function pickLanguage(preferred) {
  for (const tag of preferred) {
    const language = tag.toLowerCase().split("-")[0];
    if (LANGUAGES.includes(language)) return language;
  }
  return DEFAULT_LANGUAGE;
}

export async function loadCatalog(language) {
  const response = await fetch(`generated/i18n/${language}.json`);
  return new Catalog(language, await response.json());
}

export class Catalog {
  constructor(language, { ui, errors }) {
    this.language = language;
    this.ui = ui;
    this.errors = errors;
    this.lists = new Intl.ListFormat(language, { type: "conjunction" });
  }

  /** The UI string for ``key`` with its {placeholders} filled from ``params``. */
  t(key, params = {}) {
    return this.format(this.ui[key] ?? key, params);
  }

  /** Message and hint for an API error ``{code, params}``; unknown codes get a generic text. */
  error({ code, params = {} }) {
    const entry = this.errors[code];
    if (!entry) return { message: this.t("error.unknown", { code }), hint: "" };
    return { message: this.format(entry.message, params), hint: this.format(entry.hint, params) };
  }

  /** Lines "name: value" for the technical params of an error, or none. */
  technical({ params = {} }) {
    return TECHNICAL_PARAMS.filter((name) => name in params).map(
      (name) => `${name}: ${this.value(params[name])}`,
    );
  }

  /** Fill every element marked with data-i18n, and the page's language and title. */
  apply(root) {
    root.documentElement.lang = this.language;
    root.title = this.t("app.title");
    for (const element of root.querySelectorAll("[data-i18n]")) {
      element.textContent = this.t(element.dataset.i18n);
    }
  }

  format(template, params) {
    return template.replace(/\{(\w+)\}/g, (match, name) =>
      name in params ? this.value(params[name]) : match,
    );
  }

  value(param) {
    // Lists (tuples on the server) are formatted for the language: "17 and 27", "17 y 27".
    return Array.isArray(param) ? this.lists.format(param.map(String)) : String(param);
  }
}
