"use client";

import { useEffect, useState } from "react";
import { AdminLogin, readAdmin, problem, type Admin } from "./seeding-board";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

type ImportStatus = {
  status: "idle" | "discovering" | "importing" | "completed" | "failed";
  total?: number | null;
  done?: number;
  current?: string | null;
  error?: string;
  results: {
    slug: string;
    name: string;
    status: "completed" | "failed";
    error?: string;
    conflicts?: number;
  }[];
};

function localDay(offsetDays: number) {
  return new Date(Date.now() + offsetDays * 86400000).toLocaleDateString(
    "en-CA",
    { timeZone: "America/Asuncion" },
  );
}

async function call(
  admin: Admin,
  method: string,
  path: string,
  body?: unknown,
) {
  return fetch(`${api}/imports/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${admin.key}`,
      "X-Admin-Name": admin.name,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** Organizer tool: import every Paraguayan tournament of a period, or pasted links. */
export function ImportPanel() {
  const [admin, setAdmin] = useState<Admin | null>(() =>
    typeof window === "undefined" ? null : readAdmin(),
  );
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState(() => localDay(-365));
  const [to, setTo] = useState(() => localDay(1));
  const [links, setLinks] = useState("");
  const [state, setState] = useState<ImportStatus | null>(null);
  const [message, setMessage] = useState("");
  const [tick, setTick] = useState(0);

  const running =
    state?.status === "discovering" || state?.status === "importing";

  useEffect(() => {
    if (!admin || !open) return;
    let active = true;
    call(admin, "GET", "status")
      .then(async (r) => {
        if (active && r.ok) setState((await r.json()) as ImportStatus);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [admin, open, tick]);

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setTick((t) => t + 1), 4000);
    return () => clearInterval(timer);
  }, [running]);

  async function start(body: unknown) {
    if (!admin) return;
    setMessage("");
    const r = await call(admin, "POST", "startgg", body).catch(() => null);
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (!r.ok) return setMessage(await problem(r));
    setTick((t) => t + 1);
  }

  if (!open)
    return (
      <p>
        <button className="link-button" onClick={() => setOpen(true)}>
          Organizadores: importar torneos desde start.gg
        </button>
      </p>
    );
  if (!admin) return <AdminLogin onLogin={setAdmin} />;
  return (
    <section
      className="seeding-admin seeding-import"
      aria-label="Importar torneos"
    >
      <p>
        <strong>Importar torneos de start.gg</strong>. Trae resultados,
        jugadores y los personajes de cada partida. Se puede repetir: los
        torneos ya importados solo se actualizan.
      </p>
      <form
        className="seeding-tools"
        onSubmit={(e) => {
          e.preventDefault();
          start({
            source: "country",
            country: "PY",
            window_start: `${from}T00:00:00-03:00`,
            end: `${to}T00:00:00-03:00`,
          });
        }}
      >
        <label>
          Desde
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            required
          />
        </label>
        <label>
          Hasta (exclusivo)
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            required
          />
        </label>
        <button className="primary-button" disabled={running}>
          Importar todos los de Paraguay
        </button>
      </form>
      <form
        className="seeding-tools"
        onSubmit={(e) => {
          e.preventDefault();
          start({
            source: "links",
            urls: links
              .split(/\s+/)
              .map((l) => l.trim())
              .filter(Boolean),
          });
        }}
      >
        <label className="seeding-links">
          O pega links de torneos (uno por línea)
          <textarea
            value={links}
            rows={3}
            onChange={(e) => setLinks(e.target.value)}
            placeholder="https://www.start.gg/tournament/…"
          />
        </label>
        <button className="primary-button" disabled={running || !links.trim()}>
          Importar links
        </button>
      </form>
      {message && <p role="alert">{message}</p>}
      {state && state.status !== "idle" && (
        <div role="status" className="seeding-banner">
          {running ? (
            <p>
              {state.status === "discovering"
                ? "Buscando torneos en start.gg…"
                : `Importando ${state.done ?? 0} de ${state.total ?? "?"}: ${state.current ?? ""}`}
            </p>
          ) : (
            <p>
              {state.status === "completed"
                ? `Importación terminada: ${state.results.filter((r) => r.status === "completed").length} torneos importados, ${state.results.filter((r) => r.status === "failed").length} con error.`
                : `La importación se detuvo (${state.error}).`}
            </p>
          )}
          {state.results.some((r) => r.status === "failed") && (
            <ul>
              {state.results
                .filter((r) => r.status === "failed")
                .map((r) => (
                  <li key={r.slug}>
                    {r.name}: {r.error}
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
