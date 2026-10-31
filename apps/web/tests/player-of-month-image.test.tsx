import React from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  PlayerOfMonthCard,
  type PlayerOfMonth,
} from "../src/components/insights";
import { resultLines } from "../src/lib/og-player-of-month";

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});

const month = {
  month: "2026-10",
  label: "octubre de 2026",
  in_progress: false,
  months: ["2026-10"],
  regions: [
    {
      region: "cde",
      name: "Ciudad del Este",
      winner: {
        id: "m",
        tag: "MasterHand",
        points: 33,
        results: [
          {
            tournament: "SaN's 10 (2026)",
            tournament_id: "t",
            placement: 3,
            entrants: 16,
            seed: 10,
            upsets: 4,
            top10_wins: 0,
            points: 33,
          },
        ],
      },
      runners: [],
    },
    { region: "central", name: "Gran Asunción", winner: null, runners: [] },
  ],
} as unknown as PlayerOfMonth;

it("explains a result in words", () => {
  expect(
    resultLines({
      tournament: "SaN's 10 (2026)",
      placement: 3,
      entrants: 16,
      seed: 10,
      upsets: 4,
      wins: [
        { tag: "Nhorko", seed: 2 },
        { tag: "Sapphire", seed: 6 },
        { tag: "Cry", seed: 7 },
      ],
    }),
  ).toEqual({
    title: "3.º de 16 en SaN's 10 (2026)",
    facts: "Era seed 10 · 4 sorpresas",
    beaten: "Le ganó a Nhorko (seed 2), Sapphire (seed 6) y Cry (seed 7)",
  });
  expect(
    resultLines({
      tournament: "Copa",
      placement: 1,
      entrants: null,
      seed: null,
      upsets: 1,
    }),
  ).toEqual({ title: "1.º en Copa", facts: "1 sorpresa", beaten: "" });
});

it("offers the image to organizers only", () => {
  const { unmount } = render(<PlayerOfMonthCard p={month} />);
  expect(screen.queryByRole("link", { name: /Descargar imagen/ })).toBeNull();
  unmount();
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  render(<PlayerOfMonthCard p={month} />);
  expect(
    screen.getByRole("link", { name: "Descargar imagen del jugador del mes" }),
  ).toHaveAttribute("href", "/og/jugador-del-mes?month=2026-10");
});
