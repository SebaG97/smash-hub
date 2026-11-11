/**
 * Official tournament rulebooks. The PDF in /public/reglamentos is the official
 * document; the web version is a word-for-word transcription of it, split into
 * blocks so it reads well on phones. See docs/architecture/reglamentos.md.
 */
export type RuleBlock =
  /** A paragraph. */
  | { kind: "p"; text: string }
  /** A bulleted list, exactly as the document lists it. */
  | { kind: "list"; items: string[] }
  /** Glossary entries: term and definition. */
  | { kind: "terms"; items: [term: string, definition: string][] }
  /** Footnotes (the asterisked notes under a list), shown smaller. */
  | { kind: "notes"; items: string[] };

export type RuleSection = {
  /** As printed in the document: "2", "3.23.1"… */
  number: string;
  title: string;
  /** Anchor; defaults to regla-<number> with dashes ("regla-3-23-1"). */
  id?: string;
  blocks?: RuleBlock[];
  sections?: RuleSection[];
  /** Listed in the chapter index, as the document's own index does for 3.23–3.25. */
  index?: boolean;
};

export type Rulebook = {
  /** URL of the reader: /reglamentos/<id>. */
  id: string;
  title: string;
  version: string;
  /** Last revision, YYYY-MM-DD. */
  revised: string;
  /** The official PDF, a path under /public. */
  pdf: string;
  /** Name for the downloaded file. */
  filename: string;
  pages: number;
  /** start.gg tournament slugs (as in /previa/<slug>) this rulebook applies to. */
  tournaments: string[];
  chapters: RuleSection[];
};

/** What the tournament preview needs: no rule text, so its page stays light. */
export type RulebookSummary = Omit<Rulebook, "chapters" | "tournaments"> & {
  index: { id: string; number: string; title: string; sub: boolean }[];
};

export function sectionId(s: Pick<RuleSection, "id" | "number">) {
  return s.id ?? `regla-${s.number.replaceAll(".", "-")}`;
}

/** "1 de noviembre de 2026". */
export function revisedText(date: string) {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("es-PY", {
    timeZone: "UTC",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export const p = (text: string): RuleBlock => ({ kind: "p", text });
export const list = (...items: string[]): RuleBlock => ({
  kind: "list",
  items,
});
export const notes = (...items: string[]): RuleBlock => ({
  kind: "notes",
  items,
});
