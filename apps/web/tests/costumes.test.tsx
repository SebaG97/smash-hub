import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CostumePicker } from "../src/components/mains";
import { characterRender } from "../src/lib/characters";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

afterEach(() => {
  cleanup();
  clearAdmin();
  vi.unstubAllGlobals();
});

const mains = [
  { character: "Ryu", games: 87, share: 30, costume: 3 },
  { character: "Ken", games: 73, share: 25 },
  { character: "Random Character", games: 2, share: 1 },
];

it("builds render paths only for known characters", () => {
  expect(characterRender("Ryu", 3, 160)).toBe("/renders/ryu/3?w=160");
  expect(characterRender("Bowser")).toBe("/renders/bowser/1?w=320");
  expect(characterRender("Random Character")).toBeNull();
});

it("is hidden from readers", () => {
  const { container } = render(<CostumePicker playerId="p1" mains={mains} />);
  expect(container).toBeEmptyDOMElement();
});

it("lets organizers choose one of the 8 costumes", async () => {
  saveAdmin({ key: "k", name: "Org" });
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  vi.stubGlobal("fetch", fetchMock);
  render(<CostumePicker playerId="p1" mains={mains} />);
  expect(screen.getByRole("group", { name: "Ryu" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Ken" })).toBeInTheDocument();
  expect(screen.getAllByRole("button")).toHaveLength(16);
  expect(screen.getByRole("button", { name: "Ryu, traje 3" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  fireEvent.click(screen.getByRole("button", { name: "Ken, traje 5" }));
  expect(
    await screen.findByRole("button", {
      name: "Ken, traje 5",
      pressed: true,
    }),
  ).toBeInTheDocument();
  const [url, init] = fetchMock.mock.calls[0] as unknown as [
    string,
    RequestInit,
  ];
  expect(url).toContain("/players/p1/costume");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(String(init.body))).toEqual({
    character: "Ken",
    costume: 5,
  });
});
