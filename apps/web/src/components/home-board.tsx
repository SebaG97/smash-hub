"use client";

import Link from "next/link";
import type React from "react";
import { useEffect, useState } from "react";
import type { Page, PublicSeedingView, Tournament } from "../lib/api";
import { UpcomingTournaments } from "./insights";
import { MainIcons, WinBar, mainColor } from "./mains";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

function shortDate(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "short",
      })
    : "";
}

/** Home: the published ranking's top 8 and the latest tournaments. */
export function HomeBoard() {
  const [ranking, setRanking] = useState<PublicSeedingView | null>(null);
  const [tournaments, setTournaments] = useState<Tournament[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    fetch(`${api}/seeding?kind=ranking`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then(async (items: { slug: string }[]) => {
        if (!items.length) return;
        const r = await fetch(`${api}/seeding/${items[0].slug}`);
        if (r.ok && active) setRanking((await r.json()) as PublicSeedingView);
      })
      .catch(() => active && setFailed(true));
    fetch(`${api}/tournaments?page_size=6`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then((page: Page<Tournament>) => active && setTournaments(page.items))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);

  const top = ranking?.seeds.slice(0, 8) ?? [];
  return (
    <div className="home-columns">
      <section aria-labelledby="ranking-title">
        <h2 id="ranking-title">{ranking?.name ?? "Ranking"}</h2>
        {top.length > 0 ? (
          <>
            <ol className="standings">
              {top.map((row) => (
                <li
                  key={row.seed}
                  style={
                    mainColor(row.mains)
                      ? ({
                          "--main": mainColor(row.mains),
                        } as React.CSSProperties)
                      : undefined
                  }
                >
                  <span className="place">{row.seed}</span>
                  <span>
                    <Link href={`/rankings/${ranking!.slug}`}>
                      {row.gamer_tag}
                    </Link>{" "}
                    <MainIcons mains={row.mains} size={30} />
                  </span>
                  <WinBar wins={row.wins} losses={row.losses} />
                </li>
              ))}
            </ol>
            <p className="home-more">
              <Link
                className="primary-button"
                href={`/rankings/${ranking!.slug}`}
              >
                Ver ranking completo
              </Link>
              <small>
                Método: {ranking!.method_label}. Torneos presenciales del último
                año.
              </small>
            </p>
          </>
        ) : (
          <p className="seeding-lead">
            {failed
              ? "No se pudo cargar el ranking. Prueba recargar la página."
              : ranking
                ? "El ranking todavía no tiene jugadores."
                : "Cargando el ranking…"}
          </p>
        )}
      </section>
      <section aria-labelledby="recent-title">
        <h2 id="next-title">Próximos torneos</h2>
        <UpcomingTournaments />
        <h2 id="recent-title">Últimos torneos</h2>
        {tournaments && tournaments.length > 0 ? (
          <ul className="recent">
            {tournaments.map((t) => (
              <li key={t.id}>
                <time dateTime={t.starts_at ?? undefined}>
                  {shortDate(t.starts_at)}
                </time>
                <Link href={`/tournaments/${t.id}`}>{t.name}</Link>
                <span>{t.participant_count} jugadores</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="seeding-lead">
            {tournaments ? "Todavía no hay torneos importados." : "Cargando…"}
          </p>
        )}
        <form className="home-search" action="/players" role="search">
          <label>
            Buscar un jugador
            <input
              name="q"
              type="search"
              placeholder="Tag del jugador"
              maxLength={120}
            />
          </label>
          <button className="primary-button" type="submit">
            Buscar
          </button>
        </form>
        <p className="home-more">
          <Link href="/tournaments">Todos los torneos</Link>
        </p>
      </section>
    </div>
  );
}
