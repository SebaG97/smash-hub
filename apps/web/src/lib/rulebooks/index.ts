import { centerStage2026 } from "./center-stage-2026";
import { sectionId, type Rulebook, type RulebookSummary } from "./types";

export {
  revisedText,
  sectionId,
  type RuleBlock,
  type RuleSection,
  type Rulebook,
  type RulebookSummary,
} from "./types";

/**
 * Every published rulebook. Imported only on the server: the previa gets a
 * summary as a prop, and only /reglamentos/<id> renders the text.
 * To add one, see docs/architecture/reglamentos.md.
 */
export const RULEBOOKS: Rulebook[] = [centerStage2026];

export function rulebook(id: string): Rulebook | null {
  return RULEBOOKS.find((r) => r.id === id) ?? null;
}

/** The chapters, plus the sections the document's own index lists. */
export function rulebookIndex(r: Rulebook): RulebookSummary["index"] {
  return r.chapters.flatMap((c) => [
    { id: sectionId(c), number: c.number, title: c.title, sub: false },
    ...(c.sections ?? [])
      .filter((s) => s.index)
      .map((s) => ({
        id: sectionId(s),
        number: s.number,
        title: s.title,
        sub: true,
      })),
  ]);
}

/** The rulebook of a tournament (its start.gg slug), without the rule text. */
export function rulebookForTournament(slug: string): RulebookSummary | null {
  const r = RULEBOOKS.find((b) => b.tournaments.includes(slug));
  if (!r) return null;
  return {
    id: r.id,
    title: r.title,
    version: r.version,
    revised: r.revised,
    pdf: r.pdf,
    filename: r.filename,
    pages: r.pages,
    index: rulebookIndex(r),
  };
}
