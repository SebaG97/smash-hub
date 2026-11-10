"use client";

import Link from "next/link";
import { useState } from "react";
import type React from "react";
import type { Main } from "../lib/api";
import { BracketView, ProjectionNotes, type Bracket } from "./bracket";
import { Resource } from "./competition-browser";
import { flagEmoji } from "./flag-picker";
import { MainIcons, WinBar, mainColor } from "./mains";
import { Prefix } from "./prefix";
import {
  TournamentBanner,
  TournamentLogo,
  type TournamentImages,
} from "./tournament-art";

type Person = {
  // Only set when the hub's seeding of this event is published.
  seed: number | null;
  tag: string;
  id: string | null;
  startgg_player_id?: string;
  ranked: boolean;
  wins?: number;
  losses?: number;
  recent_wins?: number;
  recent_losses?: number;
  streak?: number;
  mains?: Main[];
  prefix?: string | null;
  /** Flag from the published seeding (chosen by organizers or where they play most). */
  country?: string | null;
  // What the published seeding read from start.gg, for entrants without hub results.
  startgg?: StartggProfile;
};
type StartggProfile = {
  wins: number;
  losses: number;
  events: number;
  country: string | null;
  last_event: string | null;
  best: {
    placement: number;
    entrants: number | null;
    tournament: string;
    date: string;
  }[];
  mains: Main[];
};
type Ref = { id: string | null; tag: string; seed: number | null };
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
    images?: TournamentImages;
  };
  event: { name: string; entrants: number } | null;
  seeding: { source: "seeding" | "none"; label: string };
  entrants: Person[];
  favorites: Person[];
  on_fire: Person[];
  crossings: { stage: string; a: Ref; b: Ref; h2h: HeadToHead }[];
  rivalries: { a: Ref; b: Ref; sets: number; h2h: HeadToHead }[];
  newcomers: { count: number; tags: string[] };
  bracket?: Bracket | null;
};

function day(value: string | null, long = false) {
  // A bare date (2026-10-19) is read as UTC midnight, which is the previous day in
  // Asunción; noon keeps it on the right day.
  const at =
    value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00Z` : value;
  return at
    ? new Date(at).toLocaleDateString("es-PY", {
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

function key(p: {
  id: string | null;
  tag: string;
  startgg_player_id?: string;
}) {
  return p.startgg_player_id ?? p.id ?? p.tag;
}

function Tag({
  p,
}: {
  p: { id: string | null; tag: string; prefix?: string | null };
}) {
  return (
    <>
      <Prefix prefix={p.prefix} />
      {p.id ? <Link href={`/players/${p.id}`}>{p.tag}</Link> : p.tag}
    </>
  );
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
      {/* The first load after a deploy waits for start.gg's bracket (~20 s); later
          ones are served from the API's cache. */}
      <Resource<TournamentPreview>
        path={`insights/upcoming/${slug}`}
        timeout={45000}
      >
        {(d) => <PreviewBody d={d} slug={slug} />}
      </Resource>
    </div>
  );
}

const COUNTRIES = new Intl.DisplayNames(["es"], { type: "region" });

function countryName(code: string) {
  try {
    return COUNTRIES.of(code) ?? code;
  } catch {
    return code;
  }
}

function Flag({ code }: { code?: string | null }) {
  if (!code || !/^[A-Za-z]{2}$/.test(code)) return null;
  const name = countryName(code.toUpperCase());
  return (
    <span className="flag" role="img" aria-label={name} title={name}>
      {flagEmoji(code)}
    </span>
  );
}

/** Lowercase without accents, so "jose" finds "José". */
function fold(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function matches(query: string, tag: string, prefix?: string | null) {
  const q = fold(query.trim());
  return !q || fold(`${prefix ?? ""} ${tag}`).includes(q);
}

type Tab = [id: string, label: string];

function PreviewBody({ d, slug }: { d: TournamentPreview; slug: string }) {
  const official = d.seeding.source === "seeding";
  const tabs: Tab[] = [
    ["resumen", "Resumen"],
    ...(official && d.event ? ([["pools", "Pools"]] as Tab[]) : []),
    ...(d.bracket ? ([["bracket", "Bracket"]] as Tab[]) : []),
    ["seeds", official ? "Seeds" : "Inscritos"],
  ];
  // The tab lives in the address (#pools) so a shared link opens on it.
  // The page only renders on the client, once the preview has loaded.
  const [tab, setTab] = useState(
    () => window.location.hash.slice(1) || "resumen",
  );
  const current = tabs.some(([id]) => id === tab) ? tab : "resumen";
  const choose = (id: string) => {
    setTab(id);
    window.history.replaceState(null, "", `#${id}`);
  };
  const [query, setQuery] = useState("");
  const countries = new Set(
    d.entrants.map((p) => p.country?.toUpperCase()).filter(Boolean),
  );
  const foreign = d.entrants.filter(
    (p) => p.country && p.country.toUpperCase() !== "PY",
  ).length;

  return (
    <>
      <TournamentBanner images={d.tournament.images} name={d.tournament.name} />
      <h1 className="tournament-title">
        {!d.tournament.images?.banner && (
          <TournamentLogo images={d.tournament.images} size={64} />
        )}
        Previa: {d.tournament.name}
      </h1>
      <p className="seeding-lead">
        {[
          day(d.tournament.starts_at, true),
          d.tournament.venue,
          d.tournament.city,
        ]
          .filter(Boolean)
          .join(", ")}
        {d.event ? ` · ${d.event.name}` : ""}.{" "}
        <a href={d.tournament.url} target="_blank" rel="noreferrer">
          Ver en start.gg
        </a>
      </p>
      {!d.event ? (
        <p>Todavía no tiene un evento de singles de Ultimate.</p>
      ) : d.entrants.length === 0 ? (
        <p>Todavía no hay inscritos.</p>
      ) : (
        <>
          <ul className="preview-stats" aria-label="En números">
            <li>
              <strong>{d.event.entrants}</strong> inscritos
            </li>
            {countries.size > 1 && (
              <li>
                <strong>{countries.size}</strong> países
              </li>
            )}
            {foreign > 0 && (
              <li>
                <strong>{foreign}</strong> de afuera
              </li>
            )}
            <li className={official ? "ok" : undefined}>
              {official ? "Seeding oficial publicado" : "Seeding sin publicar"}
            </li>
          </ul>
          <div
            className="tabs"
            role="tablist"
            aria-label="Secciones de la previa"
          >
            {tabs.map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="tab"
                id={`tab-${id}`}
                aria-selected={current === id}
                aria-controls={`panel-${id}`}
                onClick={() => choose(id)}
              >
                {label}
              </button>
            ))}
          </div>
          {(current === "pools" || current === "seeds") && (
            <p className="preview-search">
              <input
                type="search"
                aria-label="Buscar jugador"
                placeholder="Buscá un jugador…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </p>
          )}
          <div
            role="tabpanel"
            id={`panel-${current}`}
            aria-labelledby={`tab-${current}`}
          >
            {current === "resumen" && <Summary d={d} official={official} />}
            {current === "pools" && <PoolsTab slug={slug} query={query} />}
            {current === "bracket" && d.bracket && (
              <section aria-label="Bracket proyectado">
                <ProjectionNotes bracket={d.bracket} />
                <BracketView bracket={d.bracket} first />
              </section>
            )}
            {current === "seeds" && (
              <SeedsTab d={d} official={official} query={query} />
            )}
          </div>
        </>
      )}
    </>
  );
}

function Summary({ d, official }: { d: TournamentPreview; official: boolean }) {
  const empty =
    !d.favorites.length &&
    !d.on_fire.length &&
    !d.crossings.length &&
    !d.rivalries.length;
  return (
    <>
      {!official && (
        <p className="seeding-lead">
          {d.seeding.label}. Los seeds, los pools, los favoritos y los cruces
          aparecen cuando se publique.
        </p>
      )}
      {empty && official && (
        <p className="seeding-lead">Todavía no hay datos para el resumen.</p>
      )}
      <div className="preview-grid">
        {d.favorites.length > 0 && (
          <section aria-labelledby="favorites-title">
            <h2 id="favorites-title">Favoritos</h2>
            <ol className="standings">
              {d.favorites.map((p) => (
                <li key={key(p)} style={tint(p.mains)}>
                  <span className="place">{p.seed}</span>
                  <span>
                    <Flag code={p.country} /> <Tag p={p} />{" "}
                    <MainIcons mains={p.mains} size={28} />
                  </span>
                  <Record p={p} />
                </li>
              ))}
            </ol>
          </section>
        )}
        {d.on_fire.length > 0 && (
          <section aria-labelledby="fire-title">
            <h2 id="fire-title">Vienen en racha</h2>
            <ol className="leaders">
              {d.on_fire.map((p) => (
                <li key={key(p)} style={tint(p.mains)}>
                  <span className="who">
                    <MainIcons mains={p.mains?.slice(0, 1)} size={26} />
                    <Tag p={p} />
                  </span>
                  <span>
                    {p.streak} sets ganados seguidos
                    {p.seed ? `, seed ${p.seed}` : ""}
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
                <li key={`${key(r.a)}-${key(r.b)}`}>
                  <small>{r.sets} sets entre ellos</small>
                  <H2H a={r.a} b={r.b} h2h={r.h2h} />
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </>
  );
}

/** Hub record, or the published seeding's start.gg one for players the hub lacks. */
function Record({ p }: { p: Person }) {
  if (p.wins || p.losses) return <WinBar wins={p.wins} losses={p.losses} />;
  if (p.startgg && p.startgg.wins + p.startgg.losses > 0)
    return (
      <span
        className="startgg-record"
        title="Sets de start.gg que usó el seeding oficial"
      >
        {p.startgg.wins}–{p.startgg.losses} <small>start.gg</small>
      </span>
    );
  return <>–</>;
}

const PAGE_SIZE = 32;

function SeedsTab({
  d,
  official,
  query,
}: {
  d: TournamentPreview;
  official: boolean;
  query: string;
}) {
  const [page, setPage] = useState(0);
  const [searched, setSearched] = useState(query);
  if (searched !== query) {
    // A new search starts on its first page.
    setSearched(query);
    setPage(0);
  }
  const rows = d.entrants.filter((p) => matches(query, p.tag, p.prefix));
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const at = Math.min(page, pages - 1);
  const shown = rows.slice(at * PAGE_SIZE, (at + 1) * PAGE_SIZE);
  return (
    <section aria-label={official ? "Seeds" : "Inscritos"}>
      <p className="seeding-lead">
        {d.seeding.label}.
        {!official &&
          " Los seeds aparecen cuando se publique; mientras tanto, el orden es por resultados en el hub."}
      </p>
      {rows.length === 0 ? (
        <p>Nadie coincide con «{query}».</p>
      ) : (
        <>
          <table className="preview-entrants">
            <thead>
              <tr>
                {official && <th scope="col">Seed</th>}
                <th scope="col">Jugador</th>
                <th scope="col">Récord</th>
                <th scope="col">Últimos 60 días</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((p) => (
                <tr key={key(p)} style={tint(p.mains)}>
                  {official && <td className="place">{p.seed}</td>}
                  <td>
                    <span className="who">
                      <MainIcons mains={p.mains?.slice(0, 1)} size={24} />
                      <Flag code={p.country} />
                      <Tag p={p} />
                    </span>
                  </td>
                  <td>
                    <Record p={p} />
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
          <Pager page={at} pages={pages} total={rows.length} onPage={setPage} />
        </>
      )}
    </section>
  );
}

function Pager({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (page: number) => void;
}) {
  if (pages <= 1) return null;
  const range = (i: number) =>
    `${i * PAGE_SIZE + 1}–${Math.min(total, (i + 1) * PAGE_SIZE)}`;
  return (
    <nav className="pager" aria-label="Páginas de seeds">
      <button
        type="button"
        disabled={page === 0}
        onClick={() => onPage(page - 1)}
      >
        ← Anterior
      </button>
      {Array.from({ length: pages }, (_, i) => (
        <button
          key={i}
          type="button"
          aria-current={i === page ? "page" : undefined}
          onClick={() => onPage(i)}
        >
          {range(i)}
        </button>
      ))}
      <button
        type="button"
        disabled={page === pages - 1}
        onClick={() => onPage(page + 1)}
      >
        Siguiente →
      </button>
    </nav>
  );
}

type PublicPoolPlayer = {
  seed: number;
  pool_seed: number | null;
  player_id: string;
  id: string | null;
  tag: string;
  prefix: string | null;
  mains: Main[];
  country: string | null;
};
type PublicPools = {
  phase: string;
  pools: { id: string; name: string; players: PublicPoolPlayer[] }[];
};

/** The official seeding laid on start.gg's pools, read only. */
function PoolsTab({ slug, query }: { slug: string; query: string }) {
  return (
    <Resource<PublicPools>
      path={`insights/upcoming/${slug}/pools`}
      timeout={45000}
    >
      {(data) => {
        const searching = query.trim() !== "";
        const pools = data.pools
          .map((pool) => ({
            ...pool,
            found: new Set(
              pool.players
                .filter((p) => matches(query, p.tag, p.prefix))
                .map((p) => p.player_id),
            ),
          }))
          .filter((pool) => !searching || pool.found.size > 0);
        return (
          <section aria-label="Pools">
            <p className="seeding-lead">
              {data.phase}: el seeding oficial repartido en los pools de
              start.gg. El número de la izquierda es el seed dentro del pool.
            </p>
            {pools.length === 0 ? (
              <p>Nadie coincide con «{query}».</p>
            ) : (
              <div className="pool-grid public-pools">
                {pools.map((pool) => (
                  <section key={pool.id} aria-label={pool.name}>
                    <h3>{pool.name}</h3>
                    <ol>
                      {pool.players.map((p) => (
                        <li
                          key={p.player_id}
                          className={`pool-player${
                            searching && pool.found.has(p.player_id)
                              ? " match"
                              : ""
                          }`}
                        >
                          <span className="pool-seed">
                            {p.pool_seed ?? "–"}
                          </span>
                          <span className="pool-name">
                            <Flag code={p.country} /> <Tag p={p} />
                          </span>
                          <MainIcons mains={p.mains} size={20} />
                          <small>seed {p.seed}</small>
                        </li>
                      ))}
                    </ol>
                  </section>
                ))}
              </div>
            )}
          </section>
        );
      }}
    </Resource>
  );
}
