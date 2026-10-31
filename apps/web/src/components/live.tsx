"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Main } from "../lib/api";
import { BracketView, type BracketGroup } from "./bracket";
import { MainIcons } from "./mains";
import { Prefix } from "./prefix";
import { ShareImage } from "./share-image";
import { TournamentBanner, type TournamentImages } from "./tournament-art";

/** Tournaments being played, straight from start.gg (Mission 27). */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");
const REFRESH_MS = 60_000;

export type LiveItem = {
  name: string;
  slug: string;
  url: string;
  starts_at: string;
  city: string | null;
  images?: TournamentImages;
  active: boolean;
};

export type LiveTop = {
  placement: number;
  tag: string | null;
  prefix: string | null;
  id: string | null;
  seed: number | null;
  mains: Main[];
};

export type LiveTournament = {
  tournament: {
    name: string;
    slug: string;
    url: string;
    starts_at: string | null;
    city: string | null;
    images?: TournamentImages;
  };
  events: { id: string; name: string; entrants: number | null }[];
  event: { id: string; name: string; entrants: number | null };
  final: boolean;
  top: LiveTop[];
  projected: false;
  groups: BracketGroup[];
  current: string | null;
  updated_at: string;
  stale?: boolean;
};

/** Home notice: only shows while a tournament is on or just ended. */
export function LiveNotice() {
  const [items, setItems] = useState<LiveItem[]>([]);
  useEffect(() => {
    let active = true;
    fetch(`${api}/live`)
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => active && setItems(d.items ?? []))
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  if (!items.length) return null;
  return (
    <ul className="live-notice">
      {items.map((t) => (
        <li key={t.slug}>
          <Link href={`/en-vivo/${t.slug}`}>
            <span className={t.active ? "live-dot on" : "live-dot"}>
              {t.active ? "En vivo" : "Recién jugado"}
            </span>
            <strong>{t.name}</strong>
            <span>Ver bracket y resultados →</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function time(value: string) {
  return new Date(value).toLocaleTimeString("es-PY", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function LivePage({ slug }: { slug: string }) {
  const [event, setEvent] = useState<string | null>(null);
  const [state, setState] = useState<{
    data?: LiveTournament;
    error?: string;
  }>({});
  useEffect(() => {
    let active = true;
    const path = `${api}/live/${slug}${event ? `?event=${event}` : ""}`;
    const load = () => {
      if (document.hidden) return;
      fetch(path)
        .then(async (r) => {
          if (!r.ok)
            throw new Error(
              r.status === 404
                ? "Este torneo no está en vivo."
                : "start.gg no respondió; probamos de nuevo en un minuto.",
            );
          const data = (await r.json()) as LiveTournament;
          if (active) setState({ data });
        })
        .catch((e: Error) => {
          // A failed refresh keeps the last reading on screen.
          if (active) setState((s) => (s.data ? s : { error: e.message }));
        });
    };
    load();
    const timer = setInterval(load, REFRESH_MS);
    document.addEventListener("visibilitychange", load);
    return () => {
      active = false;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", load);
    };
  }, [slug, event]);
  const d = state.data;
  if (!d)
    return (
      <div className="competition-page">
        <p role={state.error ? "alert" : "status"}>
          {state.error ?? "Leyendo start.gg…"}
        </p>
      </div>
    );
  const query = event ? `?event=${event}` : "";
  return (
    <div className="competition-page">
      <TournamentBanner images={d.tournament.images} name={d.tournament.name} />
      <h1 className="tournament-title">{d.tournament.name}</h1>
      <p className="seeding-lead">
        <span className={d.final ? "live-dot" : "live-dot on"}>
          {d.final ? "Terminó" : "En vivo"}
        </span>{" "}
        Actualizado a las {time(d.updated_at)} · Datos de{" "}
        <a href={d.tournament.url} target="_blank" rel="noreferrer">
          start.gg
        </a>
        , tal como los cargan los árbitros. Lo oficial se publica al importar el
        torneo.
      </p>
      {d.events.length > 1 && (
        <div className="event-tabs" role="tablist" aria-label="Eventos">
          {d.events.map((e) => (
            <button
              key={e.id}
              type="button"
              role="tab"
              aria-selected={e.id === d.event.id}
              onClick={() => setEvent(e.id)}
            >
              {e.name}
              {e.entrants ? <small>{e.entrants} jugadores</small> : null}
            </button>
          ))}
        </div>
      )}
      {d.top.length > 0 && (
        <section aria-labelledby="live-top">
          <h2 id="live-top">{d.final ? "Top" : "Posiciones hasta ahora"}</h2>
          <ol className="standings">
            {d.top.slice(0, 8).map((p) => (
              <li key={`${p.placement}-${p.tag}`}>
                <span className="place">{p.placement}</span>
                <span>
                  <Prefix prefix={p.prefix} />
                  {p.id ? (
                    <Link href={`/players/${p.id}`}>{p.tag}</Link>
                  ) : (
                    p.tag
                  )}{" "}
                  <MainIcons mains={p.mains} size={28} />
                </span>
                <small>seed {p.seed ?? "–"}</small>
              </li>
            ))}
          </ol>
          <ShareImage
            key={`${d.event.id}-${d.final}`}
            endpoint={`/og/en-vivo/${slug}${query}`}
            filename={`top-${slug}.png`}
            label={
              d.final
                ? "Descargar imagen del top"
                : "Descargar top parcial (no es definitivo)"
            }
            rows={d.top.slice(0, 12).map((p) => ({
              place: p.placement,
              tag: p.tag,
              mains: p.mains,
            }))}
          />
        </section>
      )}
      {d.groups.length > 0 ? (
        <section className="bracket-section" aria-labelledby="live-bracket">
          <h2 id="live-bracket">Bracket</h2>
          <BracketView
            key={d.event.id}
            bracket={{ projected: false, groups: d.groups }}
            initial={d.current}
          />
        </section>
      ) : (
        <p className="seeding-lead">start.gg todavía no armó el bracket.</p>
      )}
    </div>
  );
}
