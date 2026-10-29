import { expect, it } from "vitest";
import { rankingMonths } from "../src/components/seeding-board";
import { highlights, type Monthly } from "../src/lib/og-monthly";

it("lists a ranking's months in Asunción time", () => {
  expect(rankingMonths("2025-11-14T03:00:00Z", "2026-02-10T12:00:00Z")).toEqual(
    ["2025-11", "2025-12", "2026-01", "2026-02"],
  );
  // 1 March 01:00 UTC is still 28 February in Asunción.
  expect(rankingMonths("2026-02-01T12:00:00Z", "2026-03-01T01:00:00Z")).toEqual(
    ["2026-02"],
  );
});

it("sums up the month under the table", () => {
  const base = { compared: true, left: 2 } as Monthly;
  const row = (tag: string, change: number | null, isNew = false) => ({
    place: 1,
    change,
    new: isNew,
    tag,
    wins: 1,
    losses: 0,
  });
  expect(
    highlights(base, [
      row("vBash", 7),
      row("Topo", 5),
      row("STONET", null, true),
    ]),
  ).toBe("Mayor subida: vBash (+7) · Entra: STONET · Salen 2 jugadores");
  expect(highlights({ ...base, compared: false }, [])).toBe(
    "Primer mes del ranking",
  );
});
