import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { WinBar, mainColor } from "../src/components/mains";
import { characterColor } from "../src/lib/characters";

vi.mock("next/navigation", () => ({ usePathname: () => "/rankings/rk" }));

afterEach(cleanup);

describe("color pass", () => {
  it("takes each character's signature color", () => {
    expect(characterColor("Ryu")).toBe("#df170f");
    expect(characterColor("Kirby")).toBe("#ef8fb6");
    expect(characterColor("Random Character")).toBeNull();
    expect(mainColor([{ character: "Ryu", games: 1, share: 100 }])).toBe(
      "#df170f",
    );
    expect(mainColor([])).toBeUndefined();
  });

  it("shows wins and losses with a split bar", () => {
    render(<WinBar wins={3} losses={1} />);
    expect(screen.getByText("3–1")).toBeInTheDocument();
    expect(screen.getByTitle("75 % de sets ganados")).toBeInTheDocument();
  });

  it("marks the current section in the menu", async () => {
    const { NavLinks } = await import("../src/components/nav-links");
    render(<NavLinks />);
    expect(screen.getByRole("link", { name: "Rankings" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Jugadores" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
