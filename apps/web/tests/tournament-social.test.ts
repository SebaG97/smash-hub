import { describe, expect, it } from "vitest";
import {
  CARDS,
  MISSING,
  cardOf,
  isFormat,
  type Social,
} from "../src/lib/tournament-social";

const empty: Social = {
  tournament: {
    id: "t",
    name: "Open",
    slug: "open",
    starts_at: null,
    city: null,
  },
  summary: { event_id: "e", event: null, main: true, entrants: 8, top: [] },
  champion: null,
  champion_path: [],
  grand_final: [],
  upsets: [],
  over: [],
  under: [],
  close_sets: [],
  numbers: {
    entrants: 8,
    sets: 0,
    games: 0,
    full_length: 0,
    sweeps: 0,
    comebacks: 0,
    upsets: 0,
    biggest_upset: 0,
    characters: 0,
    top_character: null,
  },
  characters: { games: 0, coverage: null, items: [] },
  newcomers: { debuts: [], debut_count: 0, returns: [] },
  rivalries: [],
  ranking: null,
  achievements: [],
  prode: null,
};

describe("tournament social images", () => {
  it("lists 13 images, each with a reason when it cannot be made", () => {
    expect(CARDS).toHaveLength(13);
    for (const card of CARDS) {
      expect(card.has(empty)).toBe(false);
      expect(MISSING[card.key]).toBeTruthy();
    }
  });

  it("enables an image only when it has something to show", () => {
    const few = { ...empty, characters: { games: 9, coverage: 10, items: [] } };
    expect(cardOf("personajes")!.has(few)).toBe(false);
    const enough = { ...few, characters: { ...few.characters, games: 10 } };
    expect(cardOf("personajes")!.has(enough)).toBe(true);
    const moved = {
      ...empty,
      ranking: { slug: "r", name: "R", up: [], down: [], entered: [] },
    };
    expect(cardOf("ranking")!.has(moved)).toBe(false);
    expect(cardOf("nada")).toBeNull();
  });

  it("accepts only the known formats", () => {
    expect(isFormat("story")).toBe(true);
    expect(isFormat("poster")).toBe(false);
    expect(isFormat(null)).toBe(false);
  });
});
