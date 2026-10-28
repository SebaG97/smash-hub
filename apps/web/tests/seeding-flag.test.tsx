import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { SeedingFlag } from "../src/components/mains";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

afterEach(() => {
  cleanup();
  clearAdmin();
  vi.unstubAllGlobals();
});

it("shows nothing to readers while the seeding is reliable", () => {
  const { container } = render(<SeedingFlag tournamentId="t1" initial />);
  expect(container).toBeEmptyDOMElement();
});

it("tells readers when a tournament's seeding was discarded", () => {
  render(<SeedingFlag tournamentId="t2" initial={false} />);
  expect(
    screen.getByText(/no cuenta para sorpresas ni emblemas/),
  ).toBeInTheDocument();
});

it("lets organizers mark a badly seeded tournament", async () => {
  saveAdmin({ key: "k", name: "Org" });
  const fetchMock = vi.fn(async () => ({ ok: true, json: async () => ({}) }));
  vi.stubGlobal("fetch", fetchMock);
  render(<SeedingFlag tournamentId="t1" initial />);
  const box = screen.getByRole("checkbox", { name: /Seeding mal hecho/ });
  expect(box).not.toBeChecked();
  fireEvent.click(box);
  await vi.waitFor(() => expect(box).toBeChecked());
  const [url, init] = fetchMock.mock.calls[0] as unknown as [
    string,
    RequestInit,
  ];
  expect(url).toContain("/tournaments/t1/seeding");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(String(init.body))).toEqual({ reliable: false });
});
