"use client";

import Link from "next/link";
import { useState } from "react";
import { Resource } from "./competition-browser";
import { MainIcons } from "./mains";
import { characterColor } from "../lib/characters";
import type { Main } from "../lib/api";

type Ref = {
  name: string;
  player_id: string | null;
  seed: number | null;
  score: string | null;
  round: string | null;
};
export type StandingRow = {
  id: string;
  name: string;
  seed: number | null;
  placement: number | null;
  prefix: string | null;
  members: { player_id: string; tag: string }[];
  wins: number;
  losses: number;
  games_won: number;
  games_lost: number;
  performance: number | null;
  upsets: number;
  eliminated_by: Ref | null;
  best_win: Ref | null;
  characters: { name: string; icon: string | null; games: number }[];
};
export type Standings = {
  event: { id: string; name: string; entrants: number; team_size: number };
  reliable: boolean;
  sets: number;
  entrants: StandingRow[];
};

type Filter = "all" | "over" | "upsets";

function mains(row: StandingRow, count = 1): Main[] {
  return row.characters.slice(0, count).map((c) => ({
    character: c.name,
    icon: c.icon,
    games: c.games,
    share: 0,
  }));
}

function Name({ row }: { row: StandingRow }) {
  const single = row.members.length === 1 ? row.members[0] : null;
  return (
    <span className="standing-name">
      {row.prefix && <span className="tag-prefix">{row.prefix}</span>}
      {single ? (
        <Link href={`/players/${single.player_id}`}>{row.name}</Link>
      ) : (
        row.name
      )}
    </span>
  );
}

function Opponent({ who }: { who: Ref }) {
  return (
    <>
      {who.player_id ? (
        <Link href={`/players/${who.player_id}`}>{who.name}</Link>
      ) : (
        who.name
      )}
      {who.score && ` ${who.score}`}
    </>
  );
}

/** ▲2 when they finished two placement tiers above their seed. */
export function Performance({ value }: { value: number | null }) {
  if (value === null) return <span className="perf perf-none">—</span>;
  if (value === 0)
    return (
      <span className="perf perf-even" title="Terminó donde lo ubicaba su seed">
        =
      </span>
    );
  const up = value > 0;
  return (
    <span
      className={`perf ${up ? "perf-up" : "perf-down"}`}
      title={
        up
          ? `Terminó ${value} ${value === 1 ? "escalón" : "escalones"} arriba de lo que esperaba su seed`
          : `Terminó ${-value} ${value === -1 ? "escalón" : "escalones"} abajo de lo que esperaba su seed`
      }
    >
      {up ? "▲" : "▼"}
      {Math.abs(value)}
    </span>
  );
}

function Podium({ rows }: { rows: StandingRow[] }) {
  const top = [1, 2, 3]
    .map((place) => rows.find((r) => r.placement === place))
    .filter((r): r is StandingRow => !!r);
  if (top.length < 2) return null;
  // Second, first, third: the winner stands in the middle.
  const order = [top[1], top[0], top[2]].filter(Boolean);
  return (
    <ol className="podium" aria-label="Podio">
      {order.map((r) => (
        <li
          key={r.id}
          className={`podium-${r.placement}`}
          style={
            {
              "--main":
                (r.characters[0] && characterColor(r.characters[0].name)) ??
                "var(--line)",
            } as React.CSSProperties
          }
        >
          <span className="place">{r.placement}</span>
          <MainIcons mains={mains(r)} size={r.placement === 1 ? 72 : 56} />
          <Name row={r} />
          <small>
            {r.wins}–{r.losses} en sets
            {r.seed ? ` · seed ${r.seed}` : ""}
          </small>
        </li>
      ))}
    </ol>
  );
}

function Row({ row }: { row: StandingRow }) {
  return (
    <li
      className="standing-row"
      style={
        {
          "--main":
            (row.characters[0] && characterColor(row.characters[0].name)) ??
            "var(--line)",
        } as React.CSSProperties
      }
    >
      <span className="place">{row.placement ?? "–"}</span>
      <span className="standing-icons">
        <MainIcons mains={mains(row, 2)} size={30} />
      </span>
      <span className="standing-who">
        <Name row={row} />
        <small>
          {row.seed ? `seed ${row.seed}` : "sin seed"}
          {row.members.length > 1 &&
            ` · ${row.members.map((m) => m.tag).join(" / ")}`}
        </small>
      </span>
      <Performance value={row.performance} />
      <span className="standing-record">
        <strong>
          {row.wins}–{row.losses}
        </strong>
        <small>
          games {row.games_won}–{row.games_lost}
        </small>
      </span>
      <span className="standing-story">
        {row.best_win && (
          <span>
            <span className="story-label">Mejor victoria</span>{" "}
            <Opponent who={row.best_win} />
            {row.best_win.seed ? ` (seed ${row.best_win.seed})` : ""}
            {row.upsets > 0 && (
              <span className="tag-upset">
                {row.upsets === 1 ? "1 sorpresa" : `${row.upsets} sorpresas`}
              </span>
            )}
          </span>
        )}
        {row.eliminated_by && (
          <span>
            <span className="story-label">Lo eliminó</span>{" "}
            <Opponent who={row.eliminated_by} />
            {row.eliminated_by.round && ` · ${row.eliminated_by.round}`}
          </span>
        )}
        {row.placement === 1 && (
          <span className="story-champion">
            {row.losses === 0 ? "Campeón invicto" : "Campeón"}
          </span>
        )}
      </span>
    </li>
  );
}

function groupLabel(place: number | null) {
  return place === null ? "Sin posición final" : `${place}.º puesto`;
}

export function StandingsView({ data }: { data: Standings }) {
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const needle = q.trim().toLowerCase();
  const rows = data.entrants.filter(
    (r) =>
      (!needle ||
        r.name.toLowerCase().includes(needle) ||
        r.members.some((m) => m.tag.toLowerCase().includes(needle))) &&
      (filter === "all" ||
        (filter === "over" && (r.performance ?? 0) > 0) ||
        (filter === "upsets" && r.upsets > 0)),
  );
  const groups: { place: number | null; rows: StandingRow[] }[] = [];
  for (const r of rows) {
    const last = groups.at(-1);
    if (last && last.place === r.placement) last.rows.push(r);
    else groups.push({ place: r.placement, rows: [r] });
  }
  const anyUpsets = data.entrants.some((r) => r.upsets > 0);
  const unit = data.event.team_size === 1 ? "jugadores" : "equipos";
  return (
    <div className="event-standings">
      {!needle && filter === "all" && <Podium rows={data.entrants} />}
      <div className="set-filters">
        <label className="search-label">
          Buscar
          <input
            type="search"
            value={q}
            maxLength={60}
            placeholder="Tag"
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <div className="segmented" role="group" aria-label="Mostrar">
          {(
            [
              ["all", "Todos"],
              ["over", "Superaron su seed"],
              ...(anyUpsets ? ([["upsets", "Dieron sorpresas"]] as const) : []),
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="seeding-lead" role="status">
        {rows.length === data.entrants.length
          ? `${rows.length} ${unit} · ${data.sets} sets jugados.`
          : `${rows.length} de ${data.entrants.length} ${unit}.`}{" "}
        ▲/▼: cuántos escalones del bracket terminó arriba o abajo de su seed.
      </p>
      {groups.length === 0 ? (
        <p className="seeding-lead">Nadie coincide con la búsqueda.</p>
      ) : (
        groups.map((g) => (
          <section
            key={g.place ?? "none"}
            className="standing-group"
            aria-label={groupLabel(g.place)}
          >
            {g.rows.length > 1 && <h3>{groupLabel(g.place)}</h3>}
            <ol className="standing-list">
              {g.rows.map((r) => (
                <Row key={r.id} row={r} />
              ))}
            </ol>
          </section>
        ))
      )}
    </div>
  );
}

export function EventStandings({ eventId }: { eventId: string }) {
  return (
    <Resource<Standings> path={`events/${eventId}/standings`}>
      {(data) =>
        data.entrants.length ? (
          <StandingsView data={data} />
        ) : (
          <p className="seeding-lead">Este evento no tiene inscriptos.</p>
        )
      }
    </Resource>
  );
}
