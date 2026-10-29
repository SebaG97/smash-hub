import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TournamentSummaryBlock } from "../src/components/insights";
import { MainEventFlag } from "../src/components/mains";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

afterEach(() => {
  cleanup();
  clearAdmin();
  vi.unstubAllGlobals();
});

const events = [
  { id: "pro", name: "SUPER SMASH BURGAME", main: true, entrants: 42 },
  { id: "ama", name: "Burgame Amateur", main: false, entrants: 15 },
];

function summary(event: "pro" | "ama") {
  return {
    event_id: event,
    event: event === "pro" ? "SUPER SMASH BURGAME" : "Burgame Amateur",
    main: event === "pro",
    events,
    entrants: event === "pro" ? 42 : 15,
    top: [
      {
        id: "p1",
        tag: event === "pro" ? "Wesker" : "Mauserrr",
        placement: 1,
        seed: 1,
      },
    ],
    upsets: [],
    overperformers: [],
  };
}

it("switches between the main and the amateur bracket", async () => {
  const fetchMock = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => summary(url.includes("event=ama") ? "ama" : "pro"),
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(<TournamentSummaryBlock id="t1" />);
  expect(await screen.findByText("Wesker")).toBeInTheDocument();
  expect(
    screen.getByRole("tab", { name: /SUPER SMASH BURGAME/ }),
  ).toHaveAttribute("aria-selected", "true");
  fireEvent.click(screen.getByRole("tab", { name: /Burgame Amateur/ }));
  expect(await screen.findByText("Mauserrr")).toBeInTheDocument();
  expect(
    screen.getByText(/Evento secundario: no cuenta para el ranking/),
  ).toBeInTheDocument();
  expect(String(fetchMock.mock.calls.at(-1)?.[0])).toContain("?event=ama");
});

it("tells readers an event is secondary", () => {
  render(<MainEventFlag event={{ id: "ama", main: false }} />);
  expect(screen.getByText(/Evento secundario/)).toBeInTheDocument();
  cleanup();
  const { container } = render(
    <MainEventFlag event={{ id: "pro", main: true }} />,
  );
  expect(container).toBeEmptyDOMElement();
});

it("lets organizers choose the main event and go back to the rule", async () => {
  saveAdmin({ key: "k", name: "Org" });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ main: true, main_set: true }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ main: false, main_set: false }),
    });
  vi.stubGlobal("fetch", fetchMock);
  render(<MainEventFlag event={{ id: "ama", main: false, main_set: false }} />);
  expect(screen.getByText("(automático)")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(
    await screen.findByRole("button", { name: "Volver a automático" }),
  );
  expect(await screen.findByText("(automático)")).toBeInTheDocument();
  expect(screen.getByRole("checkbox")).not.toBeChecked();
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toMatch(/\/events\/ama\/main$/);
  expect(JSON.parse(String(init.body))).toEqual({ main: true });
  expect(
    JSON.parse(
      String((fetchMock.mock.calls[1] as [string, RequestInit])[1].body),
    ),
  ).toEqual({ main: null });
});
