import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import ReglamentoPage from "../src/app/reglamentos/[id]/page";
import { TournamentPreviewPage } from "../src/components/tournament-preview";
import {
  RULEBOOKS,
  rulebook,
  rulebookForTournament,
  sectionId,
  type RuleSection,
} from "../src/lib/rulebooks";

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const rules = rulebookForTournament("center-stage-2026-1")!;

function allSections(sections: RuleSection[]): RuleSection[] {
  return sections.flatMap((s) => [s, ...allSections(s.sections ?? [])]);
}

it("links Center Stage 2026 to its rulebook and nothing else to one", () => {
  expect(rules).toMatchObject({
    id: "center-stage-2026",
    title: "Reglamento Oficial de Center Stage 2026",
    version: "1.0",
    revised: "2026-11-01",
    pdf: "/reglamentos/center-stage-2026-v1.0.pdf",
    pages: 15,
  });
  // The summary the previa gets carries no rule text.
  expect(rules).not.toHaveProperty("chapters");
  expect(rules.index.map((s) => `${s.number} ${s.title}`)).toEqual([
    "1 Glosario",
    "2 Reglas del Evento",
    "3 Reglas del Torneo",
    "3.23 Reglas de Escenarios y Procedimientos",
    "3.24 Reglas Adicionales",
    "3.25 Reglas Finales",
    "4 Indemnización",
  ]);
  expect(rulebookForTournament("otro-torneo")).toBeNull();
  expect(rulebook("no-existe")).toBeNull();
});

it("ships every official PDF and gives every section a unique anchor", () => {
  for (const book of RULEBOOKS) {
    const pdf = readFileSync(join(__dirname, "../public", book.pdf));
    expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");
    const ids = allSections(book.chapters).map(sectionId);
    expect(new Set(ids).size).toBe(ids.length);
  }
});

function serve(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => body })),
  );
}

const tournament = {
  name: "Center Stage 2026",
  slug: "center-stage-2026-1",
  url: "https://www.start.gg/tournament/center-stage-2026-1",
  starts_at: "2026-11-14T19:00:00+00:00",
  city: "Asunción",
  venue: null,
  attendees: 76,
};

function preview(extra = {}) {
  return {
    tournament,
    event: { name: "Ultimate Singles", entrants: 1 },
    seeding: { source: "none", label: "Sin seeding" },
    entrants: [{ id: "p1", tag: "Wesker", seed: null, ranked: true }],
    favorites: [],
    on_fire: [],
    crossings: [],
    rivalries: [],
    newcomers: { count: 0, tags: [] },
    ...extra,
  };
}

it("adds a Reglamento tab with the document, its version and the PDF", async () => {
  serve(preview());
  render(<TournamentPreviewPage slug="center-stage-2026-1" rules={rules} />);
  const tab = await screen.findByRole("tab", { name: "Reglamento" });
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "Resumen",
    "Inscritos",
    "Reglamento",
  ]);
  fireEvent.click(tab);
  expect(window.location.hash).toBe("#reglamento");
  const panel = screen.getByRole("tabpanel");
  expect(
    within(panel).getByRole("heading", {
      name: "Reglamento Oficial de Center Stage 2026",
    }),
  ).toBeInTheDocument();
  expect(panel).toHaveTextContent(
    "Versión 1.0 · Revisado por última vez el 1 de noviembre de 2026",
  );
  expect(
    within(panel).getByRole("link", { name: "Leer el reglamento" }),
  ).toHaveAttribute("href", "/reglamentos/center-stage-2026");
  const open = within(panel).getByRole("link", {
    name: /Abrir el PDF oficial/,
  });
  expect(open).toHaveAttribute(
    "href",
    "/reglamentos/center-stage-2026-v1.0.pdf",
  );
  expect(open).toHaveAttribute("target", "_blank");
  expect(
    within(panel).getByRole("link", { name: /Descargar PDF/ }),
  ).toHaveAttribute("download", "Center Stage Reglamento v1.0.pdf");
  const chapters = within(
    within(panel).getByRole("navigation", { name: "Capítulos del reglamento" }),
  ).getAllByRole("link");
  expect(chapters).toHaveLength(7);
  expect(chapters[3]).toHaveAttribute(
    "href",
    "/reglamentos/center-stage-2026#escenarios",
  );
});

it("opens on the rulebook from a shared #reglamento link", async () => {
  window.history.replaceState(
    null,
    "",
    "/previa/center-stage-2026-1#reglamento",
  );
  serve(preview());
  render(<TournamentPreviewPage slug="center-stage-2026-1" rules={rules} />);
  expect(
    await screen.findByRole("tab", { name: "Reglamento", selected: true }),
  ).toBeInTheDocument();
});

it("has no Reglamento tab when the tournament has no rulebook", async () => {
  window.history.replaceState(null, "", "/previa/otro#reglamento");
  serve(preview());
  render(<TournamentPreviewPage slug="otro" />);
  // Falls back to the summary instead of an empty tab.
  expect(
    await screen.findByRole("tab", { name: "Resumen", selected: true }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "Reglamento" })).toBeNull();
  expect(screen.queryByText(/Reglamento Oficial/)).toBeNull();
});

it("shows the rulebook even before there are entrants", async () => {
  serve(preview({ entrants: [] }));
  render(<TournamentPreviewPage slug="center-stage-2026-1" rules={rules} />);
  expect(
    await screen.findByText("Todavía no hay inscritos."),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Leer el reglamento" }),
  ).toBeInTheDocument();
});

it("reads the whole rulebook in the hub, with an index of anchors", async () => {
  // A server page with no session: anyone can open it.
  render(
    await ReglamentoPage({
      params: Promise.resolve({ id: "center-stage-2026" }),
    }),
  );
  expect(
    screen.getByRole("heading", {
      level: 1,
      name: "Reglamento Oficial de Center Stage 2026",
    }),
  ).toBeInTheDocument();
  for (const name of [
    "1. Glosario",
    "2. Reglas del Evento",
    "3. Reglas del Torneo",
    "4. Indemnización",
  ])
    expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
  expect(
    screen.getByRole("heading", {
      level: 4,
      name: "3.23.1 Lista de escenarios",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { level: 5, name: "3.24.3.1 MLG" }),
  ).toBeInTheDocument();
  // Every index entry points at a section on the page.
  const index = within(
    screen.getByRole("navigation", { name: "Índice del reglamento" }),
  ).getAllByRole("link");
  expect(index).toHaveLength(7);
  for (const link of index) {
    const id = link.getAttribute("href")!.slice(1);
    expect(document.getElementById(id)).not.toBeNull();
  }
  // Word for word, typos included.
  expect(
    screen.getByText(
      /declarar los movimientos especiales del mismo del mismo a la vez\./,
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("Stocks: 3")).toBeInTheDocument();
  expect(
    screen.getByText("Ring a Ding (Debido al copy-right)"),
  ).toBeInTheDocument();
  // The PDF stays at hand.
  expect(
    within(
      screen.getByRole("navigation", { name: "Accesos del reglamento" }),
    ).getByRole("link", { name: "PDF oficial" }),
  ).toHaveAttribute("href", "/reglamentos/center-stage-2026-v1.0.pdf");
  expect(
    screen.getByRole("link", { name: "← Previa del torneo" }),
  ).toHaveAttribute("href", "/previa/center-stage-2026-1#reglamento");
});

it("answers 404 for a rulebook that does not exist", async () => {
  await expect(
    ReglamentoPage({ params: Promise.resolve({ id: "no-existe" }) }),
  ).rejects.toThrow();
});
