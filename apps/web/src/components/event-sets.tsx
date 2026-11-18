"use client";

import { useMemo, useState } from "react";
import { characterColor } from "../lib/characters";
import {
  CharacterIcons,
  SetDetail,
  type Bracket,
  type BracketSet,
  type BracketSide,
} from "./bracket";
import { Collection, MatchCard, Resource } from "./competition-browser";
import { Prefix } from "./prefix";
import type { Match } from "../lib/api";

/** Every set of an event, round by round, with search, filters and upsets. */

// Placements a double-elimination bracket can produce; seeds map onto the same tiers
// (the same rule as the API's upset factor, app/insights/engine.py).
const TIERS = [
  1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769,
  1025,
];

function tier(seed: number) {
  let i = 0;
  while (i + 1 < TIERS.length && TIERS[i + 1] <= seed) i++;
  return i;
}

/** How many bracket tiers better the loser was seeded; 0 when it is no upset. */
export function upsetFactor(set: BracketSet) {
  if (set.status !== "played") return 0;
  const winner = set.sides.find((s) => s.winner);
  const loser = set.sides.find((s) => !s.winner);
  if (!winner?.seed || !loser?.seed) return 0;
  return Math.max(tier(winner.seed) - tier(loser.seed), 0);
}

export type SetRow = {
  set: BracketSet;
  phase: number;
  side: "winners" | "losers" | null;
  upset: number;
};
export type RoundSection = {
  key: string;
  title: string;
  phase: number;
  side: "winners" | "losers" | null;
  rows: SetRow[];
};

const SHOWN = new Set([
  "played",
  "dq",
  "live",
  "called",
  "pending",
  "unresolved",
]);

/** Rounds with sets between two known players, the latest first (final on top). */
export function roundSections(
  bracket: Bracket,
  reliable = true,
): RoundSection[] {
  const groups = bracket.groups ?? [];
  const sections: (RoundSection & { latest: string; column: number })[] = [];
  groups.forEach((g, phase) => {
    const sides =
      g.type === "ROUND_ROBIN"
        ? ([[null, g.winners]] as const)
        : ([
            ["winners", g.winners],
            ["losers", g.losers],
          ] as const);
    for (const [side, columns] of sides) {
      columns.forEach((column, index) => {
        const rows = column.sets
          .filter(
            (s) =>
              SHOWN.has(s.status) &&
              s.sides.length === 2 &&
              s.sides.every((x) => x.tag),
          )
          .sort((a, b) => a.row - b.row)
          .map((set) => ({
            set,
            phase,
            side,
            upset: reliable ? upsetFactor(set) : 0,
          }));
        if (!rows.length) return;
        const label = column.label || `Ronda ${Math.abs(column.round)}`;
        sections.push({
          key: `${g.id}|${side}|${column.round}`,
          title: groups.length > 1 ? `${g.name} · ${label}` : label,
          phase,
          side,
          rows,
          column: index,
          latest: rows
            .map((r) => r.set.completed_at ?? "")
            .sort()
            .at(-1)!,
        });
      });
    }
  });
  return sections
    .sort(
      (a, b) =>
        b.phase - a.phase ||
        // Played rounds by when they ended; rounds still to play after them.
        (b.latest > a.latest ? 1 : b.latest < a.latest ? -1 : 0) ||
        b.column - a.column ||
        (a.side === "losers" ? 1 : 0) - (b.side === "losers" ? 1 : 0),
    )
    .map(({ key, title, phase, side, rows }) => ({
      key,
      title,
      phase,
      side,
      rows,
    }));
}

function name(side: BracketSide) {
  return `${side.prefix ? `${side.prefix} ` : ""}${side.tag ?? ""}`.toLowerCase();
}

export function EventSets({
  eventId,
  reliable = true,
}: {
  eventId: string;
  /** False when organizers flagged the seeding as unreliable: no upsets then. */
  reliable?: boolean;
}) {
  return (
    <Resource<Bracket>
      path={`events/${eventId}/bracket`}
      notFound={
        // Events imported without bracket layout: the plain list of sets.
        <Collection<Match>
          title="Sets y resultados"
          path={`events/${eventId}/sets`}
          render={(match) => <MatchCard match={match} />}
        />
      }
    >
      {(b) => <SetBrowser key={eventId} bracket={b} reliable={reliable} />}
    </Resource>
  );
}

export function SetBrowser({
  bracket,
  reliable = true,
}: {
  bracket: Bracket;
  reliable?: boolean;
}) {
  const sections = useMemo(
    () => roundSections(bracket, reliable),
    [bracket, reliable],
  );
  const phases = bracket.groups ?? [];
  const [q, setQ] = useState("");
  const [phase, setPhase] = useState<number | "all">("all");
  const [side, setSide] = useState<"all" | "winners" | "losers">("all");
  const [upsets, setUpsets] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  const all = sections.flatMap((s) => s.rows);
  if (!all.length)
    return <p className="seeding-lead">Este evento no tiene sets cargados.</p>;
  const hasLosers = all.some((r) => r.side === "losers");
  const hasUpsets = all.some((r) => r.upset > 0);
  const needle = q.trim().toLowerCase();

  const shown = sections
    .filter((s) => phase === "all" || s.phase === phase)
    .filter((s) => side === "all" || s.side === side)
    .map((s) => ({
      ...s,
      rows: s.rows.filter(
        (r) =>
          (!upsets || r.upset > 0) &&
          (!needle || r.set.sides.some((x) => name(x).includes(needle))),
      ),
    }))
    .filter((s) => s.rows.length);
  const count = shown.reduce((n, s) => n + s.rows.length, 0);

  // Searching one player: their record in the event.
  const matched = new Set(
    needle
      ? shown.flatMap((s) =>
          s.rows.flatMap((r) =>
            r.set.sides
              .filter((x) => name(x).includes(needle))
              .map((x) => x.tag!),
          ),
        )
      : [],
  );
  const player = matched.size === 1 ? [...matched][0] : null;
  const record = player
    ? shown
        .flatMap((s) => s.rows)
        .filter((r) => r.set.status === "played" || r.set.status === "dq")
        .reduce(
          (acc, r) => {
            const me = r.set.sides.find((x) => x.tag === player);
            if (me) acc[me.winner ? 0 : 1]++;
            return acc;
          },
          [0, 0],
        )
    : null;

  return (
    <div className="set-browser">
      <div className="set-filters">
        <label className="search-label">
          Jugador
          <input
            type="search"
            value={q}
            maxLength={60}
            placeholder="Buscar por tag"
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        {phases.length > 1 && (
          <label>
            Fase
            <select
              value={phase}
              onChange={(e) =>
                setPhase(
                  e.target.value === "all" ? "all" : Number(e.target.value),
                )
              }
            >
              <option value="all">Todas</option>
              {phases.map((g, i) => (
                <option key={g.id} value={i}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
        )}
        {hasLosers && (
          <div className="segmented" role="group" aria-label="Lado del bracket">
            {(
              [
                ["all", "Todo"],
                ["winners", "Winners"],
                ["losers", "Losers"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                aria-pressed={side === key}
                onClick={() => setSide(key)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
        {hasUpsets && (
          <label className="check-label">
            <input
              type="checkbox"
              checked={upsets}
              onChange={(e) => setUpsets(e.target.checked)}
            />
            Solo sorpresas
          </label>
        )}
      </div>
      <p className="seeding-lead" role="status">
        {count === all.length
          ? `${count} sets.`
          : `${count} de ${all.length} sets.`}
        {player && record && (
          <>
            {" "}
            <strong>{player}</strong> fue {record[0]}-{record[1]} en este
            evento.
          </>
        )}
      </p>
      {shown.map((s) => (
        <section key={s.key} className="set-round">
          <h3>
            {s.title}
            <small>
              {s.rows.length} {s.rows.length === 1 ? "set" : "sets"}
            </small>
          </h3>
          <ul className="set-list">
            {s.rows.map((r) => (
              <SetLine
                key={r.set.id}
                row={r}
                open={open === r.set.id}
                onOpen={() => setOpen(open === r.set.id ? null : r.set.id)}
              />
            ))}
          </ul>
        </section>
      ))}
      {!count && (
        <p className="seeding-lead">Ningún set coincide con estos filtros.</p>
      )}
    </div>
  );
}

function SetLine({
  row,
  open,
  onOpen,
}: {
  row: SetRow;
  open: boolean;
  onOpen: () => void;
}) {
  const { set, upset } = row;
  const [a, b] = set.sides;
  const winner = set.sides.find((s) => s.winner);
  const loser = set.sides.find((s) => !s.winner);
  const color = winner?.characters[0]
    ? characterColor(winner.characters[0].name)
    : undefined;
  const state =
    set.status === "live"
      ? "En juego"
      : set.status === "called"
        ? "Llamados"
        : set.status === "pending" || set.status === "unresolved"
          ? "Por jugar"
          : null;
  const dq = set.status === "dq";
  const score = (side: BracketSide) =>
    dq && !side.winner ? "DQ" : (side.score ?? "–");
  return (
    <li
      className={`set-line${open ? " open" : ""}${upset ? " upset" : ""}`}
      style={color ? ({ "--main": color } as React.CSSProperties) : undefined}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-label={`${a.tag} ${score(a)}, ${b.tag} ${score(b)}`}
        onClick={onOpen}
      >
        <Side side={a} />
        <span className="set-score">
          <b className={a.winner ? "won" : undefined}>{score(a)}</b>
          <span aria-hidden="true">–</span>
          <b className={b.winner ? "won" : undefined}>{score(b)}</b>
        </span>
        <Side side={b} mirror />
        <span className="set-tags">
          {upset > 0 && winner && loser && (
            <span
              className="tag-upset"
              title={`Seed ${winner.seed} le ganó al seed ${loser.seed}`}
            >
              Sorpresa
            </span>
          )}
          {state && <span className="tag-state">{state}</span>}
        </span>
      </button>
      {open && (
        <div className="set-open">
          {upset > 0 && winner && loser && (
            <p className="seeding-lead">
              Sorpresa: {winner.tag} (seed {winner.seed}) le ganó a {loser.tag}{" "}
              (seed {loser.seed}), que debía terminar {upset}{" "}
              {upset === 1 ? "ronda" : "rondas"} de bracket más arriba.
            </p>
          )}
          <SetDetail set={set} heading={false} />
        </div>
      )}
    </li>
  );
}

function Side({
  side,
  mirror = false,
}: {
  side: BracketSide;
  mirror?: boolean;
}) {
  return (
    <span
      className={`set-side${side.winner ? " won" : ""}${mirror ? " mirror" : ""}`}
    >
      <small className="set-seed">{side.seed ?? ""}</small>
      <span className="set-name">
        <Prefix prefix={side.prefix} />
        {side.tag}
      </span>
      <CharacterIcons characters={side.characters} />
    </span>
  );
}
