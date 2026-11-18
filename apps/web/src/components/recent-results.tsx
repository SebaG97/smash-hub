"use client";

import Link from "next/link";
import { useState } from "react";
import { Resource } from "./competition-browser";
import { MainIcons } from "./mains";
import type { CompetitiveMatch, Main, Page } from "../lib/api";

const STEP = 20;
const MAX = 100;

function day(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "Fecha no disponible";
}

function icons(list?: { name: string; icon: string | null }[]): Main[] {
  return (list ?? []).map((c) => ({
    character: c.name,
    icon: c.icon,
    games: 0,
    share: 0,
  }));
}

type Group = {
  key: string;
  first: CompetitiveMatch;
  matches: CompetitiveMatch[];
};

/** Consecutive sets of the same event, kept in the order the API sent them. */
export function groupByEvent(matches: CompetitiveMatch[]): Group[] {
  const groups: Group[] = [];
  for (const m of matches) {
    const key = `${m.tournament_id}:${m.event_id}`;
    const last = groups.at(-1);
    if (last && last.key === key) last.matches.push(m);
    else groups.push({ key, first: m, matches: [m] });
  }
  return groups;
}

function ResultLine({
  match,
  playerId,
  filters,
  h2h,
}: {
  match: CompetitiveMatch;
  playerId: string;
  filters: string;
  h2h: boolean;
}) {
  const won = match.result === "W";
  const scored =
    match.score !== null &&
    match.opponent_score !== null &&
    match.score >= 0 &&
    match.opponent_score >= 0;
  return (
    <li className={`result-line ${won ? "is-win" : "is-loss"}`}>
      <span
        className="result-badge"
        aria-label={won ? "Victoria" : "Derrota"}
        title={won ? "Victoria" : "Derrota"}
      >
        {won ? "G" : "P"}
      </span>
      <span className="result-chars result-mine">
        <MainIcons mains={icons(match.characters)} size={26} />
      </span>
      <span className="result-score">
        {scored
          ? `${match.score}–${match.opponent_score}`
          : won
            ? "Ganó"
            : "Perdió"}
      </span>
      <span className="result-chars">
        <MainIcons mains={icons(match.opponent_characters)} size={26} />
      </span>
      <span className="result-opponent">
        <span>
          <span className="result-vs">{won ? "a " : "con "}</span>
          {match.opponents.map((o, i) => (
            <span key={o.id}>
              {i > 0 && " / "}
              <Link href={`/players/${o.id}`}>{o.tag}</Link>
            </span>
          ))}
          {match.upset && (
            <span className="tag-upset">
              {won ? "Sorpresa" : "Lo sorprendieron"}
            </span>
          )}
        </span>
        <small>
          {match.round_label || "Ronda no disponible"}
          {match.opponent_seed ? ` · seed ${match.opponent_seed}` : ""}
        </small>
      </span>
      {h2h && match.opponents.length === 1 && (
        <Link
          className="result-h2h"
          href={`/players/${playerId}/vs/${match.opponents[0].id}?${filters}`}
          aria-label={`Head-to-Head con ${match.opponents[0].tag}`}
        >
          H2H
        </Link>
      )}
    </li>
  );
}

/** Sets grouped by tournament, newest first as the API sends them. */
export function ResultGroups({
  matches,
  playerId,
  filters,
  h2h = true,
}: {
  matches: CompetitiveMatch[];
  playerId: string;
  filters: string;
  /** Link each rival's Head-to-Head (not inside a Head-to-Head). */
  h2h?: boolean;
}) {
  return (
    <div className="result-groups">
      {groupByEvent(matches).map((g) => {
        const wins = g.matches.filter((m) => m.result === "W").length;
        const losses = g.matches.length - wins;
        return (
          <section
            key={g.key}
            className="result-group"
            aria-label={g.first.tournament_name}
          >
            <header>
              <span>
                <Link href={`/tournaments/${g.first.tournament_id}`}>
                  {g.first.tournament_name}
                </Link>
                <small>
                  {g.first.event_name} · {day(g.first.completed_at)}
                </small>
              </span>
              <span
                className="result-tally"
                title={`${wins} ganados y ${losses} perdidos en este evento`}
              >
                <span className="result-dots" aria-hidden="true">
                  {[...g.matches].reverse().map((m) => (
                    <i
                      key={m.id}
                      className={m.result === "W" ? "is-win" : "is-loss"}
                    />
                  ))}
                </span>
                {wins}–{losses}
              </span>
            </header>
            <ol className="result-list">
              {g.matches.map((m) => (
                <ResultLine
                  key={m.id}
                  match={m}
                  playerId={playerId}
                  filters={filters}
                  h2h={h2h}
                />
              ))}
            </ol>
          </section>
        );
      })}
    </div>
  );
}

/** The latest sets of a player in the chosen scope, with "show more". */
export function RecentResults({
  id,
  filters,
}: {
  id: string;
  filters: string;
}) {
  const [size, setSize] = useState(STEP);
  return (
    <section className="data-section" aria-label="Últimos resultados">
      <h2>Últimos resultados</h2>
      <Resource<Page<CompetitiveMatch>>
        path={`players/${id}/matches?${filters}&page=1&page_size=${size}`}
      >
        {(data) =>
          data.items.length === 0 ? (
            <p className="seeding-lead">No hay sets en este ámbito.</p>
          ) : (
            <>
              <ResultGroups
                matches={data.items}
                playerId={id}
                filters={filters}
              />
              <p className="seeding-lead result-more">
                {data.items.length} de {data.total} sets.{" "}
                {data.items.length < data.total && size < MAX && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setSize(Math.min(size + STEP, MAX))}
                  >
                    Ver más
                  </button>
                )}
              </p>
            </>
          )
        }
      </Resource>
    </section>
  );
}
