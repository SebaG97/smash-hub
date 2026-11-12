"use client";

import { useEffect, useState } from "react";
import { problem } from "./seeding-board";
import { adminHeaders, useAdmin, type Admin } from "../lib/admin";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

type Tier = "far" | "week" | "day" | "live" | "finished";

export type SyncTournament = {
  slug: string;
  name: string;
  /** The start the hub goes by: confirmed by an administrator, else start.gg's. */
  starts_at: string | null;
  startgg_starts_at?: string | null;
  start_confirmed?: boolean;
  start_confirmed_by?: string | null;
  tracked: boolean;
  reason: "calendar" | "seeding" | "manual";
  in_calendar: boolean;
  tier: Tier;
  next_sync_at: string | null;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_status: "completed" | "failed" | null;
  last_error: string | null;
  failures: number;
};

export type SyncRun = {
  id: string;
  kind: "tournament" | "discovery";
  slug: string | null;
  trigger: "auto" | "manual";
  actor: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at: string | null;
  counts: Record<string, number>;
  warnings: string[];
  error: string | null;
};

export type SyncStatus = {
  enabled: boolean;
  tournaments: SyncTournament[];
  runs: SyncRun[];
};

const TIERS: Record<Tier, string> = {
  far: "Lejano",
  week: "Esta semana",
  day: "Próximas 24 h",
  live: "En curso",
  finished: "Terminado",
};

const REASONS = {
  calendar: "calendario",
  seeding: "seeding",
  manual: "manual",
};

function when(value: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("es-PY", {
    timeZone: "America/Asuncion",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** "12 inscripciones nuevas, 3 actualizadas…" from a run's counts. */
export function summary(counts: Record<string, number>) {
  const parts = Object.entries(counts)
    .filter(([key, n]) => n > 0 && key.includes("_"))
    .map(([key, n]) => `${key.replace("_", " ")}: ${n}`);
  return parts.length ? parts.join(", ") : "sin cambios";
}

async function call(
  admin: Admin,
  method: string,
  path: string,
  body?: unknown,
) {
  return fetch(`${api}/sync${path}`, {
    method,
    credentials: "include",
    headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** Organizer tool (ADR-022): what the hub copied from start.gg and when, and a way to
 * sync a tournament right now. */
export function SyncPanel() {
  const admin = useAdmin();
  const [state, setState] = useState<SyncStatus | null>(null);
  const [link, setLink] = useState("");
  const [startSlug, setStartSlug] = useState("");
  const [startDay, setStartDay] = useState("");
  const [startTime, setStartTime] = useState("");
  const [message, setMessage] = useState("");
  const [tick, setTick] = useState(0);
  const running = state?.runs.some((r) => r.status === "running") ?? false;

  useEffect(() => {
    if (!admin) return;
    let active = true;
    call(admin, "GET", "")
      .then(async (r) => {
        if (!active || !r.ok) return;
        const body = (await r.json()) as Partial<SyncStatus>;
        // Only a well-formed answer replaces what is shown (an older API has no /sync).
        if (Array.isArray(body.tournaments) && Array.isArray(body.runs))
          setState(body as SyncStatus);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [admin, tick]);

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setTick((t) => t + 1), 4000);
    return () => clearInterval(timer);
  }, [running]);

  async function send(method: string, path: string, body?: unknown) {
    if (!admin) return;
    setMessage("");
    const r = await call(admin, method, path, body).catch(() => null);
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (!r.ok) return setMessage(await problem(r));
    setTick((t) => t + 1);
  }

  if (!admin) return null;
  return (
    <section
      className="seeding-admin sync-panel"
      aria-label="Sincronización con start.gg"
    >
      <h2>Sincronización con start.gg</h2>
      <p>
        Previas, pools y brackets se leen de la copia local, que se actualiza
        sola según qué tan cerca está cada torneo.{" "}
        {state &&
          (state.enabled ? (
            <strong>La sincronización automática está encendida.</strong>
          ) : (
            <strong>
              La sincronización automática está apagada: solo se actualiza a
              mano.
            </strong>
          ))}
      </p>
      <form
        className="seeding-tools"
        onSubmit={(e) => {
          e.preventDefault();
          send("POST", "/tournaments", { tournament: link.trim() });
        }}
      >
        <label>
          Link del torneo
          <input
            value={link}
            onChange={(e) => setLink(e.target.value)}
            placeholder="https://www.start.gg/tournament/…"
            required
          />
        </label>
        <button className="primary-button" disabled={running || !link.trim()}>
          Sincronizar ahora
        </button>
        <button
          type="button"
          className="link-button"
          disabled={running}
          onClick={() => send("POST", "/discover")}
        >
          Buscar próximos torneos
        </button>
      </form>
      {message && <p role="alert">{message}</p>}
      {running && <p role="status">Sincronizando con start.gg…</p>}
      {state && state.tournaments.length > 0 && (
        <div className="seeding-table-wrap">
          <table className="seeding-table">
            <thead>
              <tr>
                <th>Torneo</th>
                <th>Estado</th>
                <th>Última sincronización</th>
                <th>Próxima</th>
                <th>Seguimiento</th>
              </tr>
            </thead>
            <tbody>
              {state.tournaments.map((t) => (
                <tr key={t.slug}>
                  <td>
                    {t.name}
                    <br />
                    <small>{REASONS[t.reason]}</small>
                  </td>
                  <td>
                    {TIERS[t.tier]}
                    <br />
                    <small>
                      Inicio {when(t.starts_at)}
                      {t.start_confirmed
                        ? ` (confirmado; start.gg dice ${when(t.startgg_starts_at ?? null)})`
                        : " (según start.gg)"}
                    </small>
                  </td>
                  <td>
                    {when(t.last_success_at)}
                    {t.last_status === "failed" && (
                      <>
                        <br />
                        <small role="note">
                          Falló {when(t.last_attempt_at)}: {t.last_error}
                          {t.failures > 1 && ` (${t.failures} seguidas)`}
                        </small>
                      </>
                    )}
                  </td>
                  <td>{t.tracked ? when(t.next_sync_at) : "—"}</td>
                  <td>
                    <button
                      className="link-button"
                      disabled={running}
                      onClick={() =>
                        send("POST", "/tournaments", { tournament: t.slug })
                      }
                    >
                      Sincronizar
                    </button>{" "}
                    ·{" "}
                    <button
                      className="link-button"
                      onClick={() =>
                        send("PUT", `/tournaments/${t.slug}/tracking`, {
                          tracked: !t.tracked,
                        })
                      }
                    >
                      {t.tracked ? "Dejar de seguir" : "Seguir"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {state && state.tournaments.length > 0 && (
        <form
          className="seeding-tools"
          aria-label="Confirmar inicio"
          onSubmit={(e) => {
            e.preventDefault();
            send("PUT", `/tournaments/${startSlug}/start`, {
              starts_at: `${startDay}T${startTime}`,
            });
          }}
        >
          <label>
            Torneo
            <select
              value={startSlug}
              onChange={(e) => setStartSlug(e.target.value)}
              required
            >
              <option value="">Elegí un torneo</option>
              {state.tournaments.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Día
            <input
              type="date"
              value={startDay}
              onChange={(e) => setStartDay(e.target.value)}
              required
            />
          </label>
          <label>
            Hora de Paraguay
            <input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              required
            />
          </label>
          <button className="primary-button">Confirmar inicio</button>
          <button
            type="button"
            className="link-button"
            disabled={!startSlug}
            onClick={() => send("PUT", `/tournaments/${startSlug}/start`, {})}
          >
            Usar el de start.gg
          </button>
          <small>
            Si start.gg tiene mal la hora de inicio: el horario de
            sincronización, las previas y los Prodes que se abran después usan
            esta. El dato de start.gg no se modifica.
          </small>
        </form>
      )}
      {state && state.runs.length > 0 && (
        <details>
          <summary>Últimas ejecuciones</summary>
          <ul>
            {state.runs.map((r) => (
              <li key={r.id}>
                {when(r.started_at)} ·{" "}
                {r.kind === "discovery" ? "calendario" : r.slug} ·{" "}
                {r.trigger === "manual" ? r.actor : "automática"} ·{" "}
                {r.status === "running"
                  ? "en curso"
                  : r.status === "failed"
                    ? `falló (${r.error})`
                    : summary(r.counts)}
                {r.warnings.length > 0 && ` · avisos: ${r.warnings.join(", ")}`}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
