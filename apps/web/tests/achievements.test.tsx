import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import {
  AchievementDetailPage,
  AchievementsAdmin,
  AchievementsPage,
  MyAchievements,
  PlayerAchievementsBlock,
  type Catalog,
  type Entry,
} from "../src/components/achievements";
import { setMe } from "../src/lib/session";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  setMe({ user: null, legacy_admin_key: false });
});

function entry(extra: Partial<Entry>): Entry {
  return {
    id: "mbarete",
    scope: "player",
    category: "competitivos",
    name: "Mbarete",
    description: "Campeón sin perder un set.",
    condition: "Ganar un principal de 16 o más sin perder un set.",
    rarity: "epico",
    status: "active",
    kind: "permanent",
    secret: false,
    humor: false,
    origin: "paraguaya",
    collection: null,
    universe: "main16",
    partial: false,
    legacy: false,
    tone: null,
    pending: null,
    available: true,
    category_name: "Competitivos y brackets",
    rarity_name: "Épico",
    collection_name: null,
    stats: {
      holders: 3,
      universe: 120,
      percent: 2.5,
      label: "Escaso",
      note: null,
    },
    mine: false,
    revealed: true,
    ...extra,
  };
}

const CATALOG: Catalog = {
  categories: {
    competitivos: "Competitivos y brackets",
    prode: "Prode",
    secretos: "Secretos y especiales",
  },
  rarities: {
    comun: "Común",
    raro: "Raro",
    epico: "Épico",
    legendario: "Legendario",
  },
  collections: {
    spike: { name: "Régimen de Spike", owned: 0, total: 5, active: false },
  },
  progress: null,
  achievements: [
    entry({}),
    entry({
      id: "oracle",
      scope: "prode",
      category: "prode",
      name: "Oráculo",
      rarity: "comun",
      legacy: true,
      stats: {
        holders: 0,
        universe: 10,
        percent: null,
        label: "Nadie todavía",
        note: null,
      },
    }),
    entry({
      id: "indulto",
      category: "secretos",
      name: "???",
      description: "Logro secreto. Se revela al conseguirlo.",
      condition: null,
      secret: true,
      revealed: false,
      stats: {
        holders: 2,
        universe: 12,
        percent: null,
        label: "Muestra chica",
        note: "Solo 12 elegibles",
      },
    }),
    entry({
      id: "vbash_rojo",
      category: "secretos",
      name: "vBash rojo",
      status: "pending",
      available: false,
      pending: "start.gg no informa el color.",
      stats: {
        holders: 0,
        universe: null,
        percent: null,
        label: "Pendiente",
        note: null,
      },
    }),
  ],
};

function serve(routes: Record<string, unknown>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const match = Object.keys(routes)
        .sort((a, b) => b.length - a.length)
        .find((k) => url.split("?")[0].endsWith(k));
      if (match === undefined)
        return { ok: false, status: 404, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => routes[match] };
    }),
  );
  return calls;
}

it("shows the catalog with honest statistics, secrets and filters", async () => {
  serve({ "achievements/catalog": CATALOG });
  render(<AchievementsPage />);
  expect(await screen.findByRole("heading", { name: "Logros" })).toBeVisible();
  expect(screen.getByText("Mbarete")).toBeVisible();
  expect(screen.getByText(/2,5 % · Escaso · 3 personas/)).toBeVisible();
  expect(screen.getByText("Nadie todavía")).toBeVisible();
  // Secret: no name, no condition; small sample: no percentage.
  expect(screen.getByText("???")).toBeVisible();
  expect(screen.getByText(/2 personas · Muestra chica/)).toBeVisible();
  expect(screen.getByText("Próximamente")).toBeVisible();
  expect(
    screen.getByText("Se activa cuando la organización lo confirme"),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Ingresar" })).toBeVisible();

  fireEvent.click(
    within(screen.getByRole("group", { name: "Categoría" })).getByRole(
      "button",
      { name: "Prode" },
    ),
  );
  expect(screen.queryByText("Mbarete")).toBeNull();
  expect(screen.getByText("Oráculo")).toBeVisible();
  expect(screen.getByText("1 logro")).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: "Todas" }));
  fireEvent.click(screen.getByRole("button", { name: "Secretos" }));
  expect(screen.getByText("???")).toBeVisible();
  expect(screen.queryByText("Oráculo")).toBeNull();
});

it("details an achievement with the first verifiable holder and the reader's own", async () => {
  serve({
    "achievements/mbarete": {
      ...entry({ mine: true }),
      stats: {
        holders: 3,
        universe: 120,
        percent: 2.5,
        label: "Escaso",
        note: null,
        first: {
          at: "2025-05-10T20:00:00+00:00",
          holders: [{ id: "p1", name: "Ana" }],
          verified: true,
        },
      },
      recent: [
        {
          player_id: "p2",
          name: "Beto",
          detail: "Ganó Open sin perder un set.",
          event_at: "2026-03-01T20:00:00+00:00",
          recognized_at: "2026-11-12T20:00:00+00:00",
        },
      ],
      my_awards: [
        {
          id: "a1",
          achievement_id: "mbarete",
          source: "player",
          name: "Mbarete",
          rarity: "epico",
          category: "competitivos",
          detail: "Ganó Center Stage sin perder un set.",
          event_at: "2026-11-14T22:00:00+00:00",
          recognized_at: "2026-11-15T10:00:00+00:00",
          backfilled: true,
          manual: false,
          reason: null,
          hidden: false,
        },
      ],
    },
  });
  render(<AchievementDetailPage id="mbarete" />);
  expect(await screen.findByRole("heading", { name: "Mbarete" })).toBeVisible();
  expect(screen.getByText("Primero en conseguirlo")).toBeVisible();
  expect(screen.getByText(/Ana ·/)).toBeVisible();
  expect(screen.getByRole("link", { name: "Beto" })).toHaveAttribute(
    "href",
    "/players/p2",
  );
  expect(
    screen.getByText("Ganó Center Stage sin perder un set."),
  ).toBeVisible();
  expect(screen.getByText(/Reconocido retroactivamente/)).toBeVisible();
});

it("explains why a pending achievement is not awarded", async () => {
  serve({
    "achievements/vbash_rojo": {
      ...CATALOG.achievements[3],
      recent: [],
      my_awards: [],
    },
  });
  render(<AchievementDetailPage id="vbash_rojo" />);
  expect(
    await screen.findByText(/Todavía no se otorga: start.gg no informa/),
  ).toBeVisible();
});

const MINE = {
  player_id: "p1",
  achievements: ["mbarete", "ndeee", "kane_o", "bautismo"].map((id, i) => ({
    id: `a${i}`,
    achievement_id: id,
    source: "player",
    name: id.toUpperCase(),
    rarity: "raro",
    category: "competitivos",
    detail: `Detalle ${id}`,
    event_at: null,
    recognized_at: null,
    backfilled: false,
    manual: false,
    reason: null,
    hidden: false,
  })),
  prode: [],
  showcase: [{ slot: 1, achievement_id: "ndeee", source: "player" }],
};

it("lets the owner pick three for the showcase and hide one", async () => {
  const calls = serve({
    "achievements/me": MINE,
    "achievements/me/showcase": { showcase: [] },
    "achievements/me/visibility": { updated: 1, hidden: true },
  });
  render(<MyAchievements />);
  const ndeee = await screen.findByRole("checkbox", { name: /NDEEE/ });
  expect(ndeee).toBeChecked();
  fireEvent.click(screen.getByRole("checkbox", { name: /MBARETE/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /KANE_O/ }));
  // Three chosen: the fourth cannot be added.
  expect(screen.getByRole("checkbox", { name: /BAUTISMO/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Guardar vitrina" }));
  await screen.findByText("Vitrina guardada.");
  const put = calls.find((c) => c.url.endsWith("achievements/me/showcase"));
  expect(put?.init?.method).toBe("PUT");
  expect(
    (put?.init?.headers as Record<string, string>)["X-Requested-With"],
  ).toBe("smashhub");
  expect(JSON.parse(String(put?.init?.body)).items).toEqual([
    { source: "player", achievement_id: "ndeee" },
    { source: "player", achievement_id: "mbarete" },
    { source: "player", achievement_id: "kane_o" },
  ]);
  fireEvent.click(
    screen.getAllByRole("button", { name: "Ocultar de mi perfil" })[0],
  );
  await screen.findByText("Ocultado de tu perfil público.");
  const hide = calls.find((c) => c.url.endsWith("achievements/me/visibility"));
  expect(JSON.parse(String(hide?.init?.body))).toEqual({
    source: "player",
    achievement_id: "mbarete",
    hidden: true,
  });
});

it("shows the old badges until the engine has evaluated, then the showcase", async () => {
  serve({
    "achievements/players/p1": {
      player_id: "p1",
      user_id: null,
      showcase: { automatic: true, items: [] },
      achievements: [],
      prode: [],
      progress: {},
      collections: {},
      states: [],
    },
  });
  render(<PlayerAchievementsBlock id="p1" fallback={<p>Emblemas viejos</p>} />);
  expect(await screen.findByText("Emblemas viejos")).toBeVisible();
  cleanup();
  const award = MINE.achievements[0];
  serve({
    "achievements/players/p1": {
      player_id: "p1",
      user_id: "u1",
      showcase: { automatic: false, items: [award] },
      achievements: [award],
      prode: [],
      progress: {},
      collections: {},
      states: [
        {
          achievement_id: "lider",
          name: "Líder indiscutible",
          detail: "N.º 1",
        },
      ],
    },
  });
  render(<PlayerAchievementsBlock id="p1" fallback={<p>Emblemas viejos</p>} />);
  expect(await screen.findByRole("heading", { name: "Vitrina" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Ahora mismo" })).toBeVisible();
  expect(screen.getByText("Líder indiscutible")).toBeVisible();
  expect(screen.queryByText("Emblemas viejos")).toBeNull();
});

it("gives organizers the engine status and a recalculation", async () => {
  setMe({
    user: {
      id: "u9",
      username: "org",
      display_name: "Org",
      name: "Org",
      role: "admin",
      email: null,
      player: null,
    },
    legacy_admin_key: false,
  });
  const calls = serve({
    "achievements/admin/status": {
      auto: false,
      interval_seconds: 21600,
      catalog: { total: 109, active: 87, manual: 4, pending: 18 },
      player_achievements: { active: 40 },
      prode_achievements: {},
      subjects: [],
      runs: [],
    },
    "achievements/admin/grants": { grants: [], manual: [] },
    "achievements/admin/recalculate": { started: true },
  });
  render(<AchievementsAdmin />);
  expect(
    await screen.findByText(/109 en el catálogo: 87 automáticos/),
  ).toBeVisible();
  expect(screen.getByText(/evaluación automática está apagada/)).toBeVisible();
  // Only superadmins register reference people.
  expect(screen.queryByLabelText(/ID de jugador de start.gg/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Recalcular ahora" }));
  await waitFor(() =>
    expect(
      calls.some(
        (c) =>
          c.url.endsWith("achievements/admin/recalculate") &&
          c.init?.method === "POST",
      ),
    ).toBe(true),
  );
});
