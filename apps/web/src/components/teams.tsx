"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Main } from "../lib/api";
import { useAdmin, type Admin } from "../lib/admin";
import { Resource } from "./competition-browser";
import { MainIcons, mainColor } from "./mains";
import { problem } from "./seeding-board";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

type Member = {
  id: string;
  tag: string | null;
  ranking: number | null;
  wins: number;
  losses: number;
  mains?: Main[];
};
type TeamResult = {
  id: string;
  tag: string | null;
  placement: number;
  entrants: number | null;
  tournament: string;
  tournament_id: string;
  date: string;
};
export type Team = {
  key: string;
  name: string;
  members: Member[];
  titles: number;
  top8: number;
  ranked: number;
  results: TeamResult[];
};

function day(value: string) {
  return new Date(`${value}T12:00:00Z`).toLocaleDateString("es-PY", {
    timeZone: "America/Asuncion",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function tint(mains?: Main[]) {
  const color = mainColor(mains);
  return color ? ({ "--main": color } as React.CSSProperties) : undefined;
}

function Stats({ t }: { t: Team }) {
  return (
    <p className="seeding-lead">
      {t.members.length} {t.members.length === 1 ? "jugador" : "jugadores"} ·{" "}
      {t.titles} {t.titles === 1 ? "título" : "títulos"} · {t.top8} top 8 ·{" "}
      {t.ranked} en el top 20 del ranking (último año)
    </p>
  );
}

function Roster({ members }: { members: Member[] }) {
  return (
    <ol className="standings">
      {members.map((m) => (
        <li key={m.id} style={tint(m.mains)}>
          <span className="place">{m.ranking ?? "–"}</span>
          <span>
            <Link href={`/players/${m.id}`}>{m.tag}</Link>{" "}
            <MainIcons mains={m.mains} size={28} />
          </span>
          <small>
            {m.wins}–{m.losses}
          </small>
        </li>
      ))}
    </ol>
  );
}

/** /equipos: the scene's teams, from the prefixes organizers approved. */
export function TeamsPage() {
  return (
    <div className="competition-page">
      <h1>Equipos</h1>
      <p className="seeding-lead">
        Salen del prefijo que cada jugador usa al inscribirse en start.gg (por
        ejemplo «BG | Wesker»), tomado de sus últimos torneos. El número es su
        puesto en el ranking.
      </p>
      <Resource<{ items: Team[] }> path="teams">
        {(d) =>
          d.items.length ? (
            <div className="team-grid">
              {d.items.map((t) => (
                <article className="data-card" key={t.key}>
                  <h2>
                    <Link href={`/equipos/${encodeURIComponent(t.key)}`}>
                      {t.name}
                    </Link>
                  </h2>
                  <Stats t={t} />
                  <Roster members={t.members.slice(0, 6)} />
                  {t.members.length > 6 && (
                    <p>
                      <Link href={`/equipos/${encodeURIComponent(t.key)}`}>
                        Ver los {t.members.length} jugadores
                      </Link>
                    </p>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <p>Todavía no hay equipos.</p>
          )
        }
      </Resource>
      <PrefixReview />
    </div>
  );
}

/** /equipos/[key]: one team, its roster and its recent top 8s. */
export function TeamPage({ teamKey }: { teamKey: string }) {
  return (
    <div className="competition-page">
      <p>
        <Link href="/equipos">← Equipos</Link>
      </p>
      <Resource<Team> path={`teams/${encodeURIComponent(teamKey)}`}>
        {(t) => (
          <>
            <h1>{t.name}</h1>
            <Stats t={t} />
            <section aria-labelledby="roster-title">
              <h2 id="roster-title">Jugadores</h2>
              <Roster members={t.members} />
            </section>
            <section aria-labelledby="results-title">
              <h2 id="results-title">Top 8 recientes</h2>
              {t.results.length ? (
                <ol className="leaders">
                  {t.results.map((r) => (
                    <li key={`${r.tournament_id}-${r.id}`}>
                      <span>
                        {r.placement}.º{" "}
                        <Link href={`/players/${r.id}`}>{r.tag}</Link> en{" "}
                        <Link href={`/tournaments/${r.tournament_id}`}>
                          {r.tournament}
                        </Link>
                      </span>
                      <span>
                        de {r.entrants ?? "?"}, {day(r.date)}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p>Sin top 8 en el último año.</p>
              )}
            </section>
          </>
        )}
      </Resource>
    </div>
  );
}

type SeenPrefix = {
  key: string;
  example: string;
  players: number;
  last_seen: string | null;
  status: "team" | "alias" | "shown" | "hidden" | null;
  name: string | null;
  team: string | null;
};

const STATUS_LABEL = {
  team: "Equipo",
  alias: "Parte de un equipo",
  shown: "Mostrar junto al tag",
  hidden: "Ocultar",
} as const;

async function call(
  admin: Admin,
  method: string,
  path: string,
  body?: unknown,
) {
  return fetch(`${api}/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${admin.key}`,
      "X-Admin-Name": admin.name,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  }).catch(() => null);
}

/** Organizers: review every prefix; until approved, a prefix is never shown. */
function PrefixReview() {
  const admin = useAdmin();
  const [items, setItems] = useState<SeenPrefix[] | null>(null);
  const [pending, setPending] = useState(0);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const load = () => setVersion((v) => v + 1);
  useEffect(() => {
    if (!admin) return;
    call(admin, "GET", "prefixes")
      .then((r) => (r?.ok ? r.json() : null))
      .then(
        (d: { items: SeenPrefix[]; tournaments_to_read: number } | null) => {
          if (!d) return;
          setItems(d.items);
          setPending(d.tournaments_to_read);
        },
      );
  }, [admin, version]);
  if (!admin) return null;
  const teams = (items ?? []).filter((p) => p.status === "team");
  const save = async (p: SeenPrefix, change: Partial<SeenPrefix>) => {
    const next = { ...p, ...change };
    if (!next.status) return;
    setMessage("");
    const r = await call(
      admin,
      "PUT",
      `prefixes/${encodeURIComponent(p.key)}`,
      {
        status: next.status,
        name: next.name || next.example,
        team: next.status === "alias" ? next.team || teams[0]?.key : null,
      },
    );
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (!r.ok) return setMessage(await problem(r));
    load();
  };
  return (
    <section className="prefix-review" aria-labelledby="prefix-title">
      <h2 id="prefix-title">Prefijos (solo organizadores)</h2>
      <p className="seeding-lead">
        Un prefijo sin revisar no se muestra en ningún lado. «Equipo» le da su
        página; «Parte de un equipo» une variantes (por ejemplo «G0» con «GO»);
        «Mostrar junto al tag» lo muestra sin página; «Ocultar» lo esconde.
      </p>
      {pending > 0 && (
        <p>
          <button
            type="button"
            className="link-button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              const r = await call(admin, "POST", "prefixes/fetch");
              setBusy(false);
              if (!r?.ok) return setMessage("start.gg no respondió.");
              load();
            }}
          >
            {busy
              ? "Leyendo prefijos…"
              : `Traer prefijos de start.gg (${pending} torneos sin leer)`}
          </button>
        </p>
      )}
      {message && <p role="alert">{message}</p>}
      {items && (
        <table className="preview-entrants">
          <thead>
            <tr>
              <th scope="col">Prefijo</th>
              <th scope="col">Jugadores</th>
              <th scope="col">Decisión</th>
              <th scope="col">Nombre o equipo</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.key}>
                <td>
                  {p.example}
                  {!p.status && <small className="tag"> sin revisar</small>}
                </td>
                <td>{p.players}</td>
                <td>
                  <select
                    aria-label={`Decisión para ${p.example}`}
                    value={p.status ?? ""}
                    onChange={(e) =>
                      save(p, {
                        status: e.target.value as SeenPrefix["status"],
                      })
                    }
                  >
                    <option value="" disabled>
                      Elegir…
                    </option>
                    {Object.entries(STATUS_LABEL).map(([value, label]) => (
                      <option
                        key={value}
                        value={value}
                        disabled={value === "alias" && !teams.length}
                      >
                        {label}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  {p.status === "alias" ? (
                    <select
                      aria-label={`Equipo de ${p.example}`}
                      value={p.team ?? ""}
                      onChange={(e) => save(p, { team: e.target.value })}
                    >
                      {teams
                        .filter((t) => t.key !== p.key)
                        .map((t) => (
                          <option key={t.key} value={t.key}>
                            {t.name}
                          </option>
                        ))}
                    </select>
                  ) : p.status === "team" || p.status === "shown" ? (
                    <input
                      aria-label={`Nombre de ${p.example}`}
                      defaultValue={p.name ?? p.example}
                      maxLength={40}
                      onBlur={(e) =>
                        e.target.value.trim() &&
                        e.target.value !== p.name &&
                        save(p, { name: e.target.value.trim() })
                      }
                    />
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
