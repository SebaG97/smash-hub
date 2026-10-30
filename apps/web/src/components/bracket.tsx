"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { characterIcon } from "../lib/characters";
import { Resource } from "./competition-browser";
import { Prefix } from "./prefix";

/** Brackets of past events and the projection of an upcoming one (Mission 25). */

export type BracketCharacter = { name: string; icon: string | null };
export type BracketSide = {
  tag: string | null;
  prefix: string | null;
  id: string | null;
  seed: number | null;
  score: number | null;
  winner: boolean;
  characters: BracketCharacter[];
};
export type BracketSet = {
  id: string;
  round: number;
  label: string | null;
  row: number;
  to?: string | null;
  status: string;
  completed_at: string | null;
  sides: BracketSide[];
  games: {
    number: number;
    winner: number | null;
    characters: (BracketCharacter | null)[];
  }[];
};
export type BracketColumn = {
  round: number;
  label: string | null;
  sets: BracketSet[];
};
export type BracketGroup = {
  id: string;
  name: string;
  type: string;
  winners: BracketColumn[];
  losers: BracketColumn[];
  height: number;
};
export type Bracket = { projected: boolean; groups: BracketGroup[] };

// Card size and spacing, in pixels.
const WIDTH = 196;
const GAP = 36;
const ROW = 66;
const CARD = 56;
const HEAD = 28;

/** Bracket of one imported event, for the tournament page. */
export function EventBracket({ eventId }: { eventId: string }) {
  return (
    <Resource<Bracket> path={`events/${eventId}/bracket`} optional>
      {(b) => (
        <section className="bracket-section" aria-labelledby="bracket-title">
          <h2 id="bracket-title">Bracket</h2>
          <BracketView key={eventId} bracket={b} />
        </section>
      )}
    </Resource>
  );
}

export function BracketView({ bracket }: { bracket: Bracket }) {
  const groups = bracket.groups ?? [];
  // The last phase (the final bracket, "Top 8") is the one people want to see first.
  const [group, setGroup] = useState(groups[groups.length - 1]?.id);
  const [open, setOpen] = useState<string | null>(null);
  const current = groups.find((g) => g.id === group) ?? groups[0];
  if (!current) return null;
  const all = [...current.winners, ...current.losers].flatMap((c) => c.sets);
  const chosen = all.find((s) => s.id === open);
  return (
    <div className="bracket">
      {groups.length > 1 && (
        <div className="event-tabs" role="tablist" aria-label="Fases">
          {groups.map((g) => (
            <button
              key={g.id}
              type="button"
              role="tab"
              aria-selected={g.id === current.id}
              onClick={() => {
                setGroup(g.id);
                setOpen(null);
              }}
            >
              {g.name}
            </button>
          ))}
        </div>
      )}
      {(
        [
          ["winners", current.type === "ROUND_ROBIN" ? null : "Winners"],
          ["losers", "Losers"],
        ] as const
      ).map(([side, title]) =>
        current[side].length ? (
          <div key={side} className="bracket-side">
            {title && current.losers.length > 0 && <h3>{title}</h3>}
            <Tree
              columns={current[side]}
              projected={bracket.projected}
              open={open}
              onOpen={(id) => setOpen(id === open ? null : id)}
            />
          </div>
        ) : null,
      )}
      {chosen && <SetDetail set={chosen} />}
    </div>
  );
}

function Tree({
  columns,
  projected,
  open,
  onOpen,
}: {
  columns: BracketColumn[];
  projected: boolean;
  open: string | null;
  onOpen: (id: string) => void;
}) {
  const where = new Map<string, { x: number; y: number }>();
  columns.forEach((c, i) =>
    c.sets.forEach((s) =>
      where.set(s.id, { x: i * (WIDTH + GAP), y: HEAD + s.row * ROW }),
    ),
  );
  const rows = Math.max(...columns.flatMap((c) => c.sets.map((s) => s.row)));
  const width = columns.length * (WIDTH + GAP) - GAP;
  const height = HEAD + (rows + 1) * ROW;
  const lines = columns.flatMap((c) =>
    c.sets.flatMap((s) => {
      const from = where.get(s.id)!;
      const to = s.to ? where.get(s.to) : undefined;
      if (!to) return [];
      const x1 = from.x + WIDTH;
      const y1 = from.y + CARD / 2;
      const x2 = to.x;
      const y2 = to.y + CARD / 2;
      const mid = x2 - GAP / 2;
      return [`M${x1} ${y1}H${mid}V${y2}H${x2}`];
    }),
  );
  return (
    <div className="bracket-scroll">
      <div className="bracket-tree" style={{ width, height }}>
        <svg width={width} height={height} aria-hidden="true">
          {lines.map((d) => (
            <path key={d} d={d} />
          ))}
        </svg>
        {columns.map((c, i) => (
          <p
            key={c.round}
            className="bracket-round"
            style={{ left: i * (WIDTH + GAP), width: WIDTH }}
          >
            {c.label}
          </p>
        ))}
        {columns.map((c, i) =>
          c.sets.map((s) => (
            <SetCard
              key={s.id}
              set={s}
              guess={projected && i > 0}
              open={open === s.id}
              onOpen={() => onOpen(s.id)}
              style={{
                left: where.get(s.id)!.x,
                top: where.get(s.id)!.y,
                width: WIDTH,
                height: CARD,
              }}
            />
          )),
        )}
      </div>
    </div>
  );
}

function SetCard({
  set,
  guess,
  open,
  onOpen,
  style,
}: {
  set: BracketSet;
  guess: boolean;
  open: boolean;
  onOpen: () => void;
  style: React.CSSProperties;
}) {
  const dq = set.status === "dq";
  const label = set.sides.map((s) => s.tag ?? "?").join(" contra ");
  return (
    <button
      type="button"
      className={`bracket-set${guess ? " guess" : ""}${open ? " open" : ""}`}
      style={style}
      aria-expanded={open}
      aria-label={label}
      onClick={onOpen}
    >
      {set.sides.map((side, i) => (
        <span key={i} className={side.winner ? "won" : undefined}>
          <small className="bracket-seed">{side.seed ?? ""}</small>
          <span className="bracket-name">
            <Prefix prefix={side.prefix} />
            {side.tag ?? "—"}
          </span>
          <Icons characters={side.characters} />
          <b>{dq && !side.winner ? "DQ" : (side.score ?? "")}</b>
        </span>
      ))}
    </button>
  );
}

function Icons({
  characters,
  size = 18,
}: {
  characters: (BracketCharacter | null)[];
  size?: number;
}) {
  return (
    <span className="bracket-chars">
      {characters.slice(0, 3).map((c, i) => {
        const src = c && (characterIcon(c.name) ?? c.icon);
        return c && src ? (
          <img
            key={`${c.name}-${i}`}
            src={src}
            alt={c.name}
            title={c.name}
            width={size}
            height={size}
            loading="lazy"
          />
        ) : null;
      })}
    </span>
  );
}

function SetDetail({ set }: { set: BracketSet }) {
  const [a, b] = set.sides;
  // Big brackets push the detail far below the card that opened it.
  const box = useRef<HTMLElement>(null);
  useEffect(() => {
    box.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, [set.id]);
  const when = set.completed_at
    ? new Date(set.completed_at).toLocaleString("es-PY", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;
  return (
    <section ref={box} className="bracket-detail" aria-label="Detalle del set">
      <h3>
        <Player side={a} /> {a.score ?? "–"} – {b.score ?? "–"}{" "}
        <Player side={b} />
      </h3>
      <p className="seeding-lead">
        {set.status === "projected"
          ? "Cruce proyectado según el seeding publicado."
          : [set.status === "dq" ? "Ganó por DQ" : null, when]
              .filter(Boolean)
              .join(" · ")}
      </p>
      {set.games.length > 0 ? (
        <ol className="bracket-games">
          {set.games.map((g) => (
            <li key={g.number}>
              <span>Partida {g.number}</span>
              <Icons characters={[g.characters[0]]} size={26} />
              <span>contra</span>
              <Icons characters={[g.characters[1]]} size={26} />
              <small>
                {g.winner ? `gana ${set.sides[g.winner - 1].tag}` : ""}
              </small>
            </li>
          ))}
        </ol>
      ) : (
        set.status !== "projected" && (
          <p className="seeding-lead">
            No se cargaron los personajes de este set en start.gg.
          </p>
        )
      )}
    </section>
  );
}

function Player({ side }: { side: BracketSide }) {
  const name = (
    <>
      <Prefix prefix={side.prefix} />
      {side.tag ?? "—"}
    </>
  );
  return side.id ? <Link href={`/players/${side.id}`}>{name}</Link> : name;
}
