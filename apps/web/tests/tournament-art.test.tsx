import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  TournamentImagesButton,
  TournamentLogo,
} from "../src/components/tournament-art";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

afterEach(() => {
  cleanup();
  clearAdmin();
  vi.unstubAllGlobals();
});

it("shows the logo only when start.gg has one", () => {
  const { container, rerender } = render(<TournamentLogo images={{}} />);
  expect(container).toBeEmptyDOMElement();
  rerender(
    <TournamentLogo images={{ profile: "https://images.start.gg/l.png" }} />,
  );
  expect(container.querySelector("img")).toHaveAttribute(
    "src",
    "https://images.start.gg/l.png",
  );
});

it("lets organizers read missing images in batches", async () => {
  const { container } = render(<TournamentImagesButton />);
  expect(container).toBeEmptyDOMElement();
  cleanup();
  saveAdmin({ key: "k", name: "Org" });
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ updated: 28, checked: 30, remaining: 4 }),
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ updated: 3, checked: 4, remaining: 0 }),
    });
  vi.stubGlobal("fetch", fetchMock);
  render(<TournamentImagesButton />);
  const button = screen.getByRole("button", {
    name: "Traer logos y banners de start.gg",
  });
  fireEvent.click(button);
  expect(await screen.findByRole("status")).toHaveTextContent("Faltan 4");
  fireEvent.click(
    screen.getByRole("button", { name: "Traer logos y banners de start.gg" }),
  );
  expect(await screen.findByText(/Ya no falta ninguno/)).toBeInTheDocument();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(fetchMock.mock.calls[0][0]).toMatch(/\/tournaments\/images$/);
});
