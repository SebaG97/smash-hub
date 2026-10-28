"use client";

import Link from "next/link";
import type React from "react";
import type { Main } from "../lib/api";
import { Resource } from "./competition-browser";
import { MainIcons, WinBar, mainColor } from "./mains";

type Person = {
  seed: number;
  tag: string;
  id: string | null;
  ranked: boolean;
  wins?: number;
  losses?: number;
  recent_wins?: number;
  recent_losses?: number;
  streak?: number;
  mains?: Main[];
};
type Ref = { id: string | null; tag: string; seed: number };
type HeadToHead = {
  a_wins: number;
  b_wins: number;
  last: {
    tournament: string;
    tournament_id: string;
    date: string;
    winner: string | null;
  };
} | null;
export type TournamentPreview = {
  tournament: {
    name: string;
    slug: string;
    url: string;
    starts_at: string | null;
    city: string | null;
    venue: string | null;
    attendees: number | null;
  };
  event: { name: string; entrants: number } | null;
  seeding: { source: "seeding" | "ranking" | "results"; label: string };
  entrants: Person[];
  favorites: Person[];
  on_fire: Person[];
  crossings: { stage: string; a: Ref; b: Ref; h2h: HeadToHead }[];
  rivalries: { a: Ref; b: Ref; sets: number; h2h: HeadToHead }[];
  newcomers: { count: number; tags: string[] };
};

function day(value: string | null, long = false) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        weekday: long ? "long" : undefined,
        day: "numeric",
        month: long ? "long" : "short",
        year: "numeric",
      })
    : "";
}

function tint(mains?: Main[]) {
  const color = mainColor(mains);
  return color ? ({ "--main": color } as React.CSSProperties) : undefined;
}

function Tag({ p }: { p: { id: string | null; tag: string } }) {
  return p.id ? <Link href={`/players/${p.id}`}>{p.tag}</Link> : <>{p.tag}</>;
}

function H2H({ a, b, h2h }: { a: Ref; b: Ref; h2h: HeadToHead }) {
  if (!h2h) return <p className="seeding-lead">Nunca se cruzaron en el hub.</p>;
  return (
    <p>
      <strong>
        {a.tag} {h2h.a_wins}–{h2h.b_wins} {b.tag}
      </strong>
      . La última vez ganó {h2h.last.winner}, en{" "}
      <Link href={`/tournaments/${h2h.last.tournament_id}`}>
        {h2h.last.tournament}
      </Link>{" "}
      ({day(h2h.last.date)}).
    </p>
  );
}

/** /previa/[slug]: what to expect from an upcoming tournament. */
export function TournamentPreviewPage({ slug }: { slug: string }) {
  return (
    <div className="competition-page tournament-preview">
      <p>
        <Link href="/">← Inicio</Link>
      </p>
      <Resource<TournamentPreview> path={`insights/upcoming/${slug}`}>
        {(d) => (
          <>
            <h1>Previa: {d.tournament.name}</h1>
            <p className="seeding-lead">
              {[
                day(d.tournament.starts_at, true),
                d.tournament.venue,
                d.tournament.city,
              ]
                .filter(Boolean)
                .join(", ")}
              .{" "}
              {d.event
                ? `${d.event.entrants} inscritos en ${d.event.name}.`
                : "Todavía no tiene un evento de singles de Ultimate."}{" "}
              <a href={d.tournament.url} target="_blank" rel="noreferrer">
                Ver en start.gg
              </a>
            </p>
            {d.entrants.length === 0 ? (
              <p>Todavía no hay inscritos.</p>
            ) : (
              <>
                <section aria-labelledby="favorites-title">
                  <h2 id="favorites-title">Favoritos</h2>
                  <ol className="standings">
                    {d.favorites.map((p) => (
                      <li key={p.seed} style={tint(p.mains)}>
                        <span className="place">{p.seed}</span>
                        <span>
                          <Tag p={p} /> <MainIcons mains={p.mains} size={28} />
                        </span>
                        <WinBar wins={p.wins} losses={p.losses} />
                      </li>
                    ))}
                  </ol>
                </section>
                {d.on_fire.length > 0 && (
                  <section aria-labelledby="fire-title">
                    <h2 id="fire-title">Vienen en racha</h2>
                    <ol className="leaders">
                      {d.on_fire.map((p) => (
                        <li key={p.seed} style={tint(p.mains)}>
                          <span className="who">
                            <MainIcons mains={p.mains?.slice(0, 1)} size={26} />
                            <Tag p={p} />
                          </span>
                          <span>
                            {p.streak} sets ganados seguidos, seed {p.seed}
                          </span>
                        </li>
                      ))}
                    </ol>
                  </section>
                )}
                {d.crossings.length > 0 && (
                  <section aria-labelledby="crossings-title">
                    <h2 id="crossings-title">Cruces probables</h2>
                    <p className="seeding-lead">
                      Si se cumplen los seeds, así se cruza el top 8 del lado de
                      winners.
                    </p>
                    <ul className="crossings">
                      {d.crossings.map((c) => (
                        <li key={`${c.a.seed}-${c.b.seed}`}>
                          <small>{c.stage}</small>
                          <span className="crossing-pair">
                            <span className="place">{c.a.seed}</span>
                            <Tag p={c.a} />
                            <span>vs</span>
                            <span className="place">{c.b.seed}</span>
                            <Tag p={c.b} />
                          </span>
                          <H2H a={c.a} b={c.b} h2h={c.h2h} />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {d.rivalries.length > 0 && (
                  <section aria-labelledby="rivalries-title">
                    <h2 id="rivalries-title">Rivalidades en el cuadro</h2>
                    <ul className="crossings">
                      {d.rivalries.map((r) => (
                        <li key={`${r.a.seed}-${r.b.seed}`}>
                          <small>{r.sets} sets entre ellos</small>
                          <H2H a={r.a} b={r.b} h2h={r.h2h} />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {d.newcomers.count > 0 && (
                  <section aria-labelledby="new-title">
                    <h2 id="new-title">Sin resultados en el hub</h2>
                    <p>
                      {d.newcomers.count}{" "}
                      {d.newcomers.count === 1
                        ? "inscrito no tiene"
                        : "inscritos no tienen"}{" "}
                      sets en los torneos importados (primer torneo, o jugadores
                      de afuera): {d.newcomers.tags.join(", ")}
                      {d.newcomers.count > d.newcomers.tags.length
                        ? " y más"
                        : ""}
                      .
                    </p>
                  </section>
                )}
                <section aria-labelledby="entrants-title">
                  <h2 id="entrants-title">Inscritos y seeds proyectados</h2>
                  <p className="seeding-lead">
                    {d.seeding.label}.
                    {d.seeding.source !== "seeding" &&
                      " Es una proyección del hub, no el seeding oficial del torneo."}
                  </p>
                  <table className="preview-entrants">
                    <thead>
                      <tr>
                        <th scope="col">Seed</th>
                        <th scope="col">Jugador</th>
                        <th scope="col">Récord</th>
                        <th scope="col">Últimos 60 días</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.entrants.map((p) => (
                        <tr key={p.seed} style={tint(p.mains)}>
                          <td className="place">{p.seed}</td>
                          <td>
                            <span className="who">
                              <MainIcons
                                mains={p.mains?.slice(0, 1)}
                                size={24}
                              />
                              <Tag p={p} />
                            </span>
                          </td>
                          <td>
                            {p.wins || p.losses ? (
                              <WinBar wins={p.wins} losses={p.losses} />
                            ) : (
                              "–"
                            )}
                          </td>
                          <td>
                            {p.recent_wins || p.recent_losses
                              ? `${p.recent_wins}–${p.recent_losses}`
                              : "–"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
              </>
            )}
          </>
        )}
      </Resource>
    </div>
  );
}
