import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { AdminPanel } from "../src/components/admin-panel";
import { SeedingBoard } from "../src/components/seeding-board";
import type {
  PublicSeedingView,
  SeedingRow,
  SeedingView,
} from "../src/lib/api";

function signIn() {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function row(seed: number, tag: string, extra: Partial<SeedingRow> = {}) {
  return {
    seed,
    seed_algorithm: seed,
    player_id: String(seed),
    gamer_tag: tag,
    rating: 1800 - seed,
    rd: 60,
    conservative: 1680 - seed,
    placement_score: 4.5,
    best_placements: [],
    wins: 10,
    losses: 2,
    sets: 12,
    offline_sets: 12,
    events: 4,
    offline_events: 4,
    last_event: "2026-10-11",
    main_circuit: "PY",
    circuits: { PY: 12 },
    confidence: "alta",
    combined: 0.9,
    rank_conservative: seed,
    rank_placement: seed,
    merged_sets: 0,
    elo: 1600 - seed,
    bradley_terry: 1700 + seed,
    points: 50,
    win_rate: 83.3,
    wilson: 55.2,
    eligible: true,
    scores: { combined: 0.9, elo: 1600 - seed, bradley_terry: 1700 + seed },
    // Bradley-Terry reverses the order, to check the preview.
    ranks: { combined: seed, elo: seed, bradley_terry: 3 - seed },
    reasons_by_method: {
      combined: [`Razón de ${tag}`],
      bradley_terry: [`BT de ${tag}`],
    },
    flags: [],
    reasons: [`Razón de ${tag}`],
    override: null,
    ...extra,
  } satisfies SeedingRow;
}

const view: SeedingView = {
  slug: "cs",
  name: "Center Stage",
  kind: "seeding",
  country_code: null,
  published: true,
  method: "combined",
  methods: [
    { id: "combined", label: "Combinado", description: "Mezcla" },
    { id: "elo", label: "Elo", description: "Clásico" },
    {
      id: "bradley_terry",
      label: "Bradley-Terry",
      description: "Todos a la vez",
    },
  ],
  startgg_event_slug: "tournament/cs/event/singles",
  event_date: "2026-11-14T03:00:00Z",
  window_start: "2025-11-14T03:00:00Z",
  data_cutoff: "2026-10-21T19:58:48Z",
  refresh: { status: "IDLE", started_at: null, progress: null, error: null },
  dataset: {
    entrants: 2,
    sets: 30,
    counted_sets: 20,
    events: 5,
    offline_events: 4,
    classifications: { played: 20, bye: 10 },
  },
  merges: [],
  duplicates: [],
  run: {
    id: "r",
    created_at: "2026-10-26T15:00:00Z",
    actor: "cli",
    algorithm_version: "v1",
    parameters: { conservative_k: 2, rating_weight: 0.5 },
    window_start: "2025-11-14T03:00:00Z",
    window_end: "2026-11-14T03:00:00Z",
    data_cutoff: "2026-10-21T19:58:48Z",
    set_count: 20,
    event_count: 5,
    offline_event_count: 4,
    player_count: 9,
  },
  seeds: [
    row(1, "Ace"),
    row(2, "Bee", {
      seed_algorithm: 1,
      override: {
        player_id: "2",
        seed: 2,
        reason: "Conocido local",
        actor: "Org",
        updated_at: null,
      },
    }),
  ],
};

describe("seeding board", () => {
  it("shows data window, explanations and manual adjustments", async () => {
    signIn();
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(view)))),
    );
    render(<SeedingBoard slug="cs" />);
    expect(
      await screen.findByRole("heading", { name: "Center Stage" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/14\/11\/2025 al 14\/11\/2026/),
    ).toBeInTheDocument();
    expect(screen.getByText(/\(método 1\)/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Exportar CSV" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Despublicar" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Bee" }));
    expect(screen.getByText("Razón de Bee")).toBeInTheDocument();
    expect(screen.getByText(/Conocido local/)).toBeInTheDocument();
  });

  it("moves a player with the stored admin key", async () => {
    signIn();
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.endsWith("/session"))
          return Promise.resolve(
            new Response(JSON.stringify({ actor: "Org" })),
          );
        if (init?.method === "PUT")
          return Promise.resolve(
            new Response(JSON.stringify({ status: "moved" })),
          );
        return Promise.resolve(new Response(JSON.stringify(view)));
      }),
    );
    render(<SeedingBoard slug="cs" />);
    await screen.findByRole("heading", { name: "Center Stage" });
    const down = await screen.findByRole("button", { name: "Bajar a Ace" });
    fireEvent.click(down);
    await waitFor(() =>
      expect(calls.some((c) => c.init?.method === "PUT")).toBe(true),
    );
    const put = calls.find((c) => c.init?.method === "PUT")!;
    expect(put.url).toContain("/seeding/cs/overrides/1");
    expect(JSON.parse(String(put.init?.body))).toMatchObject({ seed: 2 });
    expect((put.init?.headers as Record<string, string>).Authorization).toBe(
      "Bearer secret-key",
    );
  });

  it("previews another method and adopts it as official", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    sessionStorage.setItem(
      "seeding-admin",
      JSON.stringify({ key: "secret-key", name: "Org" }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ url, init });
        return Promise.resolve(
          new Response(
            JSON.stringify(
              init?.method === "POST" ? { status: "recalculated" } : view,
            ),
          ),
        );
      }),
    );
    render(<SeedingBoard slug="cs" />);
    await screen.findByRole("heading", { name: "Center Stage" });
    fireEvent.change(screen.getByLabelText("Ver con el método"), {
      target: { value: "bradley_terry" },
    });
    expect(screen.getByText(/Vista previa/)).toBeInTheDocument();
    const names = screen
      .getAllByRole("button", { name: /^(Ace|Bee)$/ })
      .map((b) => b.textContent);
    expect(names).toEqual(["Bee", "Ace"]);
    // Manual moves are only offered on the official order.
    expect(screen.queryByRole("button", { name: /Bajar a/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Bee" }));
    expect(screen.getByText("BT de Bee")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Usar como método oficial" }),
    );
    await waitFor(() =>
      expect(calls.some((c) => c.init?.method === "POST")).toBe(true),
    );
    const post = calls.find((c) => c.init?.method === "POST")!;
    expect(post.url).toContain("/seeding/cs/recalculate");
    expect(JSON.parse(String(post.init?.body))).toEqual({
      method: "bradley_terry",
    });
  });

  it("shows rankings without manual moves and hides low-activity players", async () => {
    const ranking: SeedingView = {
      ...view,
      kind: "ranking",
      country_code: "PY",
      name: "Ranking Paraguay",
      run: { ...view.run!, parameters: { min_sets: 10 } },
      seeds: [
        row(1, "Ace"),
        row(2, "Bee"),
        row(3, "Cid", { eligible: false, flags: ["menos de 10 sets"] }),
      ],
    };
    sessionStorage.setItem(
      "seeding-admin",
      JSON.stringify({ key: "secret-key", name: "Org" }),
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(ranking)))),
    );
    render(<SeedingBoard slug="rk" base="rankings" />);
    await screen.findByRole("heading", { name: "Ranking Paraguay" });
    expect(screen.getByText(/RANKING · PARAGUAY/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cid" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Bajar a/ })).toBeNull();
    fireEvent.click(
      screen.getByRole("button", {
        name: /Mostrar 1 jugadores con menos de 10/,
      }),
    );
    expect(screen.getByRole("button", { name: "Cid" })).toBeInTheDocument();
  });

  it("shows readers a clean published seeding without tools", async () => {
    const calls: RequestInit[] = [];
    const publicView: PublicSeedingView = {
      slug: "cs",
      name: "Center Stage",
      kind: "seeding",
      country_code: null,
      published: true,
      public: true,
      method: "combined",
      method_label: "Combinado",
      startgg_event_slug: null,
      event_date: "2026-11-14T03:00:00Z",
      window_start: "2025-11-14T03:00:00Z",
      data_cutoff: null,
      run: null,
      seeds: [
        {
          seed: 1,
          gamer_tag: "Ace",
          mains: [
            {
              character: "Ryu",
              icon: "https://images.start.gg/r.png",
              games: 9,
              share: 90,
            },
          ],
        },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push(init || {});
        return Promise.resolve(new Response(JSON.stringify(publicView)));
      }),
    );
    render(<SeedingBoard slug="cs" />);
    await screen.findByRole("heading", { name: "Center Stage" });
    expect(screen.getByRole("img", { name: "Ryu" })).toBeInTheDocument();
    for (const tool of [/Exportar/, /Publicar/, /Recalcular/, /Entrar/])
      expect(screen.queryByRole("button", { name: tool })).toBeNull();
    expect(screen.queryByText(/Datos analizados/)).toBeNull();
    expect(
      (calls[0].headers as Record<string, string>).Authorization,
    ).toBeUndefined();
  });

  it("signs in from /admin and shows the tools", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify({ actor: "Org" }))),
      ),
    );
    render(<AdminPanel />);
    fireEvent.change(screen.getByLabelText("Tu nombre"), {
      target: { value: "Org" },
    });
    fireEvent.change(screen.getByLabelText("Clave de administración"), {
      target: { value: "secret-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText(/Sesión iniciada como/)).toBeInTheDocument();
    expect(JSON.parse(sessionStorage.getItem("seeding-admin")!)).toEqual({
      key: "secret-key",
      name: "Org",
    });
    fireEvent.click(screen.getByRole("button", { name: "Salir" }));
    expect(
      await screen.findByLabelText("Clave de administración"),
    ).toBeInTheDocument();
  });
});
