import { describe, expect, it } from "vitest";
import { characterIcon } from "../src/lib/characters";

describe("character icons", () => {
  it("maps start.gg names, including internal game names", () => {
    expect(characterIcon("Ryu")).toBe("/characters/ryu.svg");
    expect(characterIcon("Incineroar")).toBe("/characters/gaogaen.svg");
    expect(characterIcon("Pyra & Mythra")).toBe("/characters/homura.svg");
    expect(characterIcon("Mr. Game & Watch")).toBe(
      "/characters/mr_game_and_watch.svg",
    );
    expect(characterIcon("King K. Rool")).toBe("/characters/king_k_rool.svg");
    expect(characterIcon("Mii Gunner")).toBe("/characters/mii_fighter.svg");
  });

  it("returns null when there is no local icon", () => {
    expect(characterIcon("Random Character")).toBeNull();
  });
});
