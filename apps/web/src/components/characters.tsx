"use client";

import Link from "next/link";
import { useState } from "react";
import type React from "react";
import type { Main } from "../lib/api";
import { characterColor } from "../lib/characters";
import { Resource } from "./competition-browser";
import { MainIcons, WinBar } from "./mains";

type CharacterStats = {
  character: string;
  games: number;
  share: number;
  win_rate: number;
  players: number;
  top_players: {
    id: string;
    tag: string | null;
    games: number;
    win_rate: number;
    mains?: Main[];
  }[];
};
type Matchup = {
  character: string;
  games: number;
  wins: number;
  win_rate: number;
};

/** Matchups worth highlighting need a few games behind them. */
const MIN_GAMES = 5;

function stock(character: string, size: number) {
  return <MainIcons mains={[{ character, games: 0, share: 0 }]} size={size} />;
}

function tint(character: string) {
  const color = characterColor(character);
  return color ? ({ "--main": color } as React.CSSProperties) : undefined;
}

function percent(value: number) {
  return `${value.toLocaleString("es-PY", { maximumFractionDigits: 1 })} %`;
}

/** /personajes: what the scene plays, how it does and who plays it most. */
export function CharactersPage() {
  const [query, setQuery] = useState("");
  return (
    <div className="competition-page">
      <h1>Personajes de la escena</h1>
      <p className="seeding-lead">
        Partidas de singles de los torneos importados, según los personajes que
        cargaron los organizadores en start.gg. El % de victorias cuenta
        partidas, no sets; en los espejos gana uno y pierde el otro.
      </p>
      <Resource<{
        items: CharacterStats[];
        games: number;
      }> path="insights/characters">
        {(d) => {
          const q = query.trim().toLowerCase();
          const rows = d.items
            .map((c, i) => ({ ...c, rank: i + 1 }))
            .filter((c) => !q || c.character.toLowerCase().includes(q));
          return (
            <>
              <p>
                {d.games.toLocaleString("es-PY")} partidas con {d.items.length}{" "}
                personajes distintos.
              </p>
              <label className="character-search">
                Buscar personaje{" "}
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Pikachu"
                />
              </label>
              <ol className="character-rows">
                {rows.map((c) => (
                  <li key={c.character} style={tint(c.character)}>
                    <span className="place">{c.rank}</span>
                    {stock(c.character, 48)}
                    <span className="character-name">
                      <strong>{c.character}</strong>
                      <small>
                        {c.games.toLocaleString("es-PY")} partidas (
                        {percent(c.share)}), {c.players}{" "}
                        {c.players === 1 ? "jugador" : "jugadores"}
                      </small>
                    </span>
                    <span className="character-rate">
                      <WinBar
                        wins={Math.round((c.win_rate * c.games) / 100)}
                        losses={
                          c.games - Math.round((c.win_rate * c.games) / 100)
                        }
                      />
                      <small>{percent(c.win_rate)} de victorias</small>
                    </span>
                    <span className="character-players">
                      {c.top_players.map((p) => (
                        <Link key={p.id} href={`/players/${p.id}`}>
                          {p.tag}{" "}
                          <small>
                            {p.games} p., {percent(p.win_rate)}
                          </small>
                        </Link>
                      ))}
                    </span>
                  </li>
                ))}
              </ol>
              {rows.length === 0 && (
                <p className="seeding-lead">Ningún personaje coincide.</p>
              )}
            </>
          );
        }}
      </Resource>
    </div>
  );
}

/** Profile, Rivales tab: record against each opposing character. */
export function PlayerMatchups({ id }: { id: string }) {
  const [all, setAll] = useState(false);
  return (
    <Resource<{ items: Matchup[] }>
      path={`insights/players/${id}/matchups`}
      optional
    >
      {(d) => {
        if (!d.items.length) return null;
        const solid = d.items.filter((m) => m.games >= MIN_GAMES);
        const byRate = [...solid].sort(
          (a, b) => b.win_rate - a.win_rate || b.games - a.games,
        );
        const best = byRate[0];
        const worst = byRate.length > 1 ? byRate[byRate.length - 1] : null;
        const rows = all ? d.items : d.items.slice(0, 12);
        return (
          <section aria-labelledby="matchups-title" className="matchups">
            <h2 id="matchups-title">Contra cada personaje</h2>
            {best && worst && best.character !== worst.character && (
              <p className="matchup-summary">
                Le va mejor contra <strong>{best.character}</strong> (
                {percent(best.win_rate)} en {best.games} partidas) y peor contra{" "}
                <strong>{worst.character}</strong> ({percent(worst.win_rate)} en{" "}
                {worst.games}).
              </p>
            )}
            <ol className="leaders">
              {rows.map((m) => (
                <li key={m.character} style={tint(m.character)}>
                  <span className="who">
                    {stock(m.character, 28)}
                    <span>{m.character}</span>
                  </span>
                  <span className="matchup-record">
                    <WinBar wins={m.wins} losses={m.games - m.wins} />
                    <small>{percent(m.win_rate)}</small>
                  </span>
                </li>
              ))}
            </ol>
            {d.items.length > rows.length && (
              <button
                type="button"
                className="link-button"
                onClick={() => setAll(true)}
              >
                Ver los {d.items.length} personajes
              </button>
            )}
            <p className="seeding-lead">
              Cuenta partidas, no sets. Los destacados necesitan al menos{" "}
              {MIN_GAMES} partidas.
            </p>
          </section>
        );
      }}
    </Resource>
  );
}
