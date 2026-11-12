import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { PreviewsList } from "../src/components/previews-list";

const path = { current: "/previas" };
vi.mock("next/navigation", () => ({ usePathname: () => path.current }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function serve(status: number, body: unknown) {
  const fetchMock = vi.fn(
    async (url: string) =>
      new Response(url ? JSON.stringify(body) : null, { status }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const tournament = (name: string, slug: string, extra = {}) => ({
  name,
  slug,
  url: `https://www.start.gg/tournament/${slug}`,
  starts_at: "2026-11-22T15:00:00+00:00",
  city: "Asunción",
  venue: null,
  attendees: 24,
  images: null,
  ...extra,
});

describe("/previas", () => {
  it("lists every upcoming tournament with a link to its previa", async () => {
    const fetchMock = serve(200, {
      items: [
        tournament("Center Stage 2026", "center-stage-2026-1"),
        tournament("Smash Fest 12", "smash-fest-12", { starts_at: null }),
      ],
    });
    render(<PreviewsList />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando");
    expect(
      await screen.findByRole("link", { name: "Center Stage 2026" }),
    ).toHaveAttribute("href", "/previa/center-stage-2026-1");
    expect(screen.getByRole("link", { name: "Smash Fest 12" })).toHaveAttribute(
      "href",
      "/previa/smash-fest-12",
    );
    expect(
      screen.getByRole("link", { name: "Ver la previa de Smash Fest 12" }),
    ).toHaveAttribute("href", "/previa/smash-fest-12");
    expect(screen.getByText("Fecha a confirmar")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/insights\/calendar$/);
  });

  it("says so when no tournament is announced", async () => {
    serve(200, { items: [] });
    render(<PreviewsList />);
    expect(
      await screen.findByText(/No hay torneos anunciados/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "torneos anteriores" }),
    ).toHaveAttribute("href", "/tournaments");
  });

  it("warns when start.gg is unavailable or the API fails", async () => {
    serve(200, { items: [], unavailable: true });
    const { unmount } = render(<PreviewsList />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "start.gg no respondió",
    );
    unmount();
    serve(500, {});
    render(<PreviewsList />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No se pudieron cargar los datos.",
    );
    expect(
      screen.getByRole("button", { name: "Reintentar" }),
    ).toBeInTheDocument();
  });

  it("is in the main menu, marked on the list and on each previa", async () => {
    const { NavLinks } = await import("../src/components/nav-links");
    for (const current of ["/previas", "/previa/center-stage-2026-1"]) {
      path.current = current;
      const { unmount } = render(<NavLinks />);
      expect(screen.getByRole("link", { name: "Previas" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(screen.getByRole("link", { name: "Previas" })).toHaveAttribute(
        "href",
        "/previas",
      );
      unmount();
    }
    path.current = "/seeding";
    render(<NavLinks />);
    const order = screen.getAllByRole("link").map((a) => a.textContent);
    expect(order.slice(-3)).toEqual(["Seeding", "Previas", "Prode"]);
  });
});
