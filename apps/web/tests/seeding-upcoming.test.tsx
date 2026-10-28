import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { SeedingList } from "../src/components/seeding-board";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const calendar = {
  items: [
    {
      name: "SAN'S 10",
      url: "https://www.start.gg/tournament/san-s-10-2026",
      starts_at: "2026-11-21T22:00:00+00:00",
      city: "Asunción",
      event: {
        name: "Ultimate Singles",
        slug: "tournament/san-s-10-2026/event/ultimate-singles",
        url: "https://www.start.gg/tournament/san-s-10-2026/event/ultimate-singles",
        entrants: 24,
      },
    },
    {
      name: "Center Stage 2026",
      url: "https://www.start.gg/tournament/center-stage-2026-1",
      starts_at: "2026-11-14T19:00:00+00:00",
      city: "Asunción",
      event: {
        name: "Ultimate Singles",
        slug: "tournament/center-stage-2026-1/event/ultimate-singles",
        url: "https://www.start.gg/tournament/center-stage-2026-1/event/ultimate-singles",
        entrants: 76,
      },
    },
  ],
};
const projects = [
  {
    slug: "cs",
    name: "CENTER STAGE 2026 · Ultimate Singles",
    kind: "seeding",
    country_code: null,
    startgg_event_slug: "tournament/center-stage-2026-1/event/ultimate-singles",
    event_date: "2026-11-14T03:00:00+00:00",
    window_start: "2025-11-14T03:00:00+00:00",
    published: false,
  },
];

it("fills the new seeding from an upcoming start.gg tournament", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.includes("insights/calendar") ? calendar : projects,
    })),
  );
  render(<SeedingList />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Usar este torneo" }),
  );
  expect(screen.getByLabelText("Nombre")).toHaveValue(
    "SAN'S 10 · Ultimate Singles",
  );
  expect(screen.getByLabelText("Link del evento en start.gg")).toHaveValue(
    "https://www.start.gg/tournament/san-s-10-2026/event/ultimate-singles",
  );
  expect(screen.getByLabelText("Fecha del evento")).toHaveValue("2026-11-21");
  expect(screen.getByLabelText("Datos desde")).toHaveValue("2025-11-21");
  // A tournament that already has a seeding links to it instead.
  expect(
    screen.getByRole("link", { name: "Abrir su seeding" }),
  ).toHaveAttribute("href", "/seeding/cs");
  expect(screen.getAllByRole("link", { name: "Ver en start.gg" })).toHaveLength(
    2,
  );
});

it("shows readers no upcoming tournaments", async () => {
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => [] }));
  vi.stubGlobal("fetch", fetchMock);
  render(<SeedingList />);
  expect(
    await screen.findByText("Todavía no hay seedings publicados."),
  ).toBeInTheDocument();
  expect(screen.queryByText("Próximos torneos")).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
