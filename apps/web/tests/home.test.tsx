import React from "react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Home from "../src/app/page";
import { BackendStatus } from "../src/components/backend-status";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("public foundation", () => {
  it("exposes all four modules and declares the absence of results", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "La comunidad",
    );
    for (const title of ["Jugadores", "Torneos", "Rankings", "Estadísticas"])
      expect(
        screen.getByRole("link", { name: new RegExp(title) }),
      ).toBeInTheDocument();
    expect(
      screen.getByText(/Sin resultados cargados todavía/),
    ).toBeInTheDocument();
  });
  it("reports readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ready" }),
      }),
    );
    render(<BackendStatus />);
    expect(await screen.findByText("Backend disponible")).toBeInTheDocument();
  });
  it("handles connection errors without exposing details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret")));
    render(<BackendStatus />);
    expect(
      await screen.findByText("Backend no disponible"),
    ).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});
