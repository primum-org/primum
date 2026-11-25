// Texts from the message catalogs in i18n/ (decision 0009): UI strings by key, errors by
// code. Keys are always written literally, as t("pairing.heading"): the catalog test finds
// them so.

import { shallowRef } from "vue";

export const LANGUAGES = ["en", "es"] as const;
export type Language = (typeof LANGUAGES)[number];
const DEFAULT_LANGUAGE: Language = "en";
// Params that carry system text: shown apart as a technical detail, never inside a message.
export const TECHNICAL_PARAMS = ["detail", "consumer", "fields"];

export type Param = string | number | boolean | readonly (string | number | boolean)[];
export type Params = Readonly<Record<string, Param>>;
export interface ErrorLike {
  readonly code: string;
  readonly params?: Params;
}
interface Messages {
  readonly webui: Readonly<Record<string, string>>;
  readonly errors: Readonly<Record<string, { readonly message: string; readonly hint: string }>>;
}

const LOADERS: Record<Language, () => Promise<{ default: Messages }>> = {
  en: () => import("@i18n/en.json"),
  es: () => import("@i18n/es.json"),
};

/** The first language the browser prefers that has a catalog. */
export function pickLanguage(preferred: readonly string[]): Language {
  for (const tag of preferred) {
    const language = tag.toLowerCase().split("-")[0];
    const known = LANGUAGES.find((each) => each === language);
    if (known) return known;
  }
  return DEFAULT_LANGUAGE;
}

export class Catalog {
  private readonly lists: Intl.ListFormat;

  constructor(
    readonly language: Language,
    private readonly messages: Messages,
  ) {
    this.lists = new Intl.ListFormat(language, { type: "conjunction" });
  }

  /** The UI string for `key` with its {placeholders} filled from `params`. */
  t(key: string, params: Params = {}): string {
    return this.format(this.messages.webui[key] ?? key, params);
  }

  /** Message and hint for an error; a code the catalog does not know gets a generic text. */
  error({ code, params = {} }: ErrorLike): { message: string; hint: string } {
    const entry = this.messages.errors[code];
    if (!entry) return { message: this.t("error.unknown", { code }), hint: "" };
    return { message: this.format(entry.message, params), hint: this.format(entry.hint, params) };
  }

  /** Lines "name: value" for the technical params of an error, or none. */
  technical({ params = {} }: ErrorLike): string[] {
    return TECHNICAL_PARAMS.filter((name) => name in params).map(
      (name) => `${name}: ${this.value(params[name] ?? "")}`,
    );
  }

  private format(template: string, params: Params): string {
    return template.replace(/\{(\w+)\}/g, (match, name: string) => {
      const param = params[name];
      return param === undefined ? match : this.value(param);
    });
  }

  private value(param: Param): string {
    // Lists (tuples on the board) are formatted for the language: "17 and 27", "17 y 27".
    return typeof param === "object" ? this.lists.format(param.map(String)) : String(param);
  }
}

// The catalog in use. Loaded before the app is mounted, so a component always has one.
const current = shallowRef<Catalog | null>(null);

export async function loadCatalog(language: Language): Promise<Catalog> {
  const catalog = new Catalog(language, (await LOADERS[language]()).default);
  useCatalog(catalog);
  return catalog;
}

export function useCatalog(catalog: Catalog): void {
  current.value = catalog;
  document.documentElement.lang = catalog.language;
}

export function catalog(): Catalog {
  if (current.value === null) throw new Error("no catalog loaded: loadCatalog comes first");
  return current.value;
}

export const t = (key: string, params?: Params): string => catalog().t(key, params);
