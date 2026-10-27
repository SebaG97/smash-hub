"use client";

import Link from "next/link";
import type React from "react";
import type { Main } from "../lib/api";
import { Resource } from "./competition-browser";
import { MainIcons, WinBar, mainColor } from "./mains";
import { ShareImage } from "./share-image";

type Ref = { id: string; tag: string | null; mains?: Main[] };
export type Badge = { id: string; name: string; why: string };
export type PlayerInsights = {
  records: {
    biggest_upset: {
      opponent_id: string;
      opponent: string | null;
      tournament: string;
      tournament_id: string;
      round: string | null;
      factor: number;
      seed: number | null;
      opponent_seed: number | null;
      date: string;
    } | null;
    best_streak: number;
    current_streak: number;
    comebacks: number;
    titles: number;
    top8: number;
    tournaments: number;
    best_overperformance: {
      tournament: string;
      tournament_id: string;
      seed: number;
      placement: number;
    } | null;
    main_rival: { id: string; tag: string | null; sets: number } | null;
  };
  badges: Badge[];
};
type Upset = {
  winner: Ref;
  loser: Ref;
  factor: number;
  winner_seed: number | null;
  loser_seed: number | null;
  tournament?: string;
  tournament_id?: string;
  round?: string | null;
  date?: string;
};
type Leader = Ref & { value: number };
export type PlayerOfMonth = Ref & {
  wins: number;
  losses: number;
  upsets: number;
  titles: number;
  since: string;
  until: string;
};
type CommunityRecords = {
  player_of_month: PlayerOfMonth | null;
  streaks: Leader[];
  rivalries: { a: Ref; b: Ref; sets: number; a_wins: number; b_wins: number }[];
  upsets: Upset[];
  comebacks: Leader[];
  most_active: Leader[];
  titles: Leader[];
};
type TournamentSummary = {
  entrants: number | null;
  top: (Ref & { placement: number; seed: number | null })[];
  upsets: Upset[];
  overperformers: (Ref & { seed: number; placement: number })[];
};
type CalendarItem = {
  name: string;
  url: string;
  starts_at: string | null;
  city: string | null;
  venue: string | null;
  attendees: number | null;
};

const BADGE_TONE: Record<string, string> = {
  lider: "gold",
  trofeos: "gold",
  campeon: "gold",
  david: "fire",
  remontadas: "fire",
  racha: "fire",
  top8: "bone",
  incansable: "bone",
  especialista: "bone",
  camaleon: "bone",
  nuevo: "bone",
};

function day(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "";
}

function tint(mains?: Main[]) {
  const color = mainColor(mains);
  return color ? ({ "--main": color } as React.CSSProperties) : undefined;
}

function PlayerLink({ p, size = 26 }: { p: Ref; size?: number }) {
  return (
    <span className="who">
      <MainIcons mains={p.mains?.slice(0, 1)} size={size} />
      <Link href={`/players/${p.id}`}>{p.tag}</Link>
    </span>
  );
}

/** Profile: badges earned and personal records. */
export function PlayerAchievements({ id }: { id: string }) {
  return (
    <Resource<PlayerInsights> path={`insights/players/${id}`} optional>
      {(d) => (
        <>
          <section aria-labelledby="badges-title">
            <h2 id="badges-title">Emblemas</h2>
            {d.badges.length ? (
              <ul className="badges">
                {d.badges.map((b) => (
                  <li key={b.id} data-tone={BADGE_TONE[b.id] ?? "bone"}>
                    <strong>{b.name}</strong>
                    <span>{b.why}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="seeding-lead">
                Todavía no ganó emblemas. Se consiguen ganando torneos, dando
                sorpresas, remontando sets o encadenando victorias.
              </p>
            )}
          </section>
          <section aria-labelledby="records-title">
            <h2 id="records-title">Récords</h2>
            <dl className="facts">
              <div>
                <dt>Racha más larga</dt>
                <dd>{d.records.best_streak} sets seguidos</dd>
              </div>
              <div>
                <dt>Racha actual</dt>
                <dd>{d.records.current_streak} sets</dd>
              </div>
              <div>
                <dt>Remontadas</dt>
                <dd>{d.records.comebacks} sets</dd>
              </div>
              <div>
                <dt>Títulos</dt>
                <dd>{d.records.titles}</dd>
              </div>
              {d.records.biggest_upset && (
                <div className="fact-wide">
                  <dt>Mayor sorpresa</dt>
                  <dd>
                    Siendo seed {d.records.biggest_upset.seed} le ganó a{" "}
                    <Link
                      href={`/players/${d.records.biggest_upset.opponent_id}`}
                    >
                      {d.records.biggest_upset.opponent}
                    </Link>{" "}
                    (seed {d.records.biggest_upset.opponent_seed}) en{" "}
                    {d.records.biggest_upset.tournament}.
                  </dd>
                </div>
              )}
              {d.records.best_overperformance && (
                <div className="fact-wide">
                  <dt>Mejor actuación</dt>
                  <dd>
                    Entró como seed {d.records.best_overperformance.seed} y
                    terminó {d.records.best_overperformance.placement}.º en{" "}
                    <Link
                      href={`/tournaments/${d.records.best_overperformance.tournament_id}`}
                    >
                      {d.records.best_overperformance.tournament}
                    </Link>
                    .
                  </dd>
                </div>
              )}
              {d.records.main_rival && (
                <div className="fact-wide">
                  <dt>Rival más frecuente</dt>
                  <dd>
                    <Link href={`/players/${d.records.main_rival.id}`}>
                      {d.records.main_rival.tag}
                    </Link>
                    , {d.records.main_rival.sets} sets.
                  </dd>
                </div>
              )}
            </dl>
          </section>
        </>
      )}
    </Resource>
  );
}

function UpsetRow({ u }: { u: Upset }) {
  return (
    <li>
      <span className="factor" title="Factor de sorpresa">
        +{u.factor}
      </span>
      <span>
        <PlayerLink p={u.winner} /> <small>(seed {u.winner_seed})</small> le
        ganó a <PlayerLink p={u.loser} /> <small>(seed {u.loser_seed})</small>
        {u.tournament && (
          <small>
            {" "}
            en{" "}
            <Link href={`/tournaments/${u.tournament_id}`}>{u.tournament}</Link>
          </small>
        )}
      </span>
    </li>
  );
}

function LeaderList({
  title,
  rows,
  unit,
}: {
  title: string;
  rows: Leader[];
  unit: string;
}) {
  return (
    <section>
      <h3>{title}</h3>
      <ol className="leaders">
        {rows.map((r) => (
          <li key={r.id} style={tint(r.mains)}>
            <PlayerLink p={r} />
            <span>
              {r.value} {unit}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function PlayerOfMonthCard({ p }: { p: PlayerOfMonth }) {
  return (
    <div className="spotlight" style={tint(p.mains)}>
      <MainIcons mains={p.mains?.slice(0, 1)} size={72} />
      <div>
        <p className="eyebrow">Jugador del mes</p>
        <h3>
          <Link href={`/players/${p.id}`}>{p.tag}</Link>
        </h3>
        <p>
          {p.wins} sets ganados, {p.upsets}{" "}
          {p.upsets === 1 ? "sorpresa" : "sorpresas"} y {p.titles}{" "}
          {p.titles === 1 ? "título" : "títulos"} entre el {day(p.since)} y el{" "}
          {day(p.until)}.
        </p>
      </div>
      <WinBar wins={p.wins} losses={p.losses} />
    </div>
  );
}

/** /estadisticas: community records and curiosities. */
export function RecordsPage() {
  return (
    <div className="competition-page">
      <h1>Récords y curiosidades</h1>
      <p className="seeding-lead">
        Salen de todos los torneos importados. Una sorpresa es ganarle a alguien
        con mejor seed: el número indica cuántas rondas de bracket de diferencia
        había entre los dos.
      </p>
      <Resource<CommunityRecords> path="insights/records">
        {(d) => (
          <>
            {d.player_of_month && <PlayerOfMonthCard p={d.player_of_month} />}
            <section>
              <h2>Mayores sorpresas</h2>
              <ol className="upsets">
                {d.upsets.map((u, i) => (
                  <UpsetRow key={i} u={u} />
                ))}
              </ol>
            </section>
            <section>
              <h2>Rivalidades clásicas</h2>
              <ol className="leaders">
                {d.rivalries.map((r) => (
                  <li key={`${r.a.id}-${r.b.id}`}>
                    <span className="rivalry">
                      <PlayerLink p={r.a} /> <strong>{r.a_wins}</strong>
                      <span>–</span>
                      <strong>{r.b_wins}</strong> <PlayerLink p={r.b} />
                    </span>
                    <span>{r.sets} sets</span>
                  </li>
                ))}
              </ol>
            </section>
            <div className="record-columns">
              <LeaderList
                title="Rachas más largas"
                rows={d.streaks}
                unit="sets seguidos"
              />
              <LeaderList
                title="Más remontadas"
                rows={d.comebacks}
                unit="sets"
              />
              <LeaderList title="Más títulos" rows={d.titles} unit="torneos" />
              <LeaderList
                title="Más activos"
                rows={d.most_active}
                unit="torneos"
              />
            </div>
          </>
        )}
      </Resource>
    </div>
  );
}

/** Tournament page: top 8 with mains, upsets and who beat their seed. */
export function TournamentSummaryBlock({ id }: { id: string }) {
  return (
    <Resource<TournamentSummary> path={`insights/tournaments/${id}`} optional>
      {(s) => (
        <section className="tournament-summary" aria-label="Resumen">
          <h2>Resultados</h2>
          <ol className="standings">
            {s.top.map((p) => (
              <li key={p.id} style={tint(p.mains)}>
                <span className="place">{p.placement}</span>
                <span>
                  <Link href={`/players/${p.id}`}>{p.tag}</Link>{" "}
                  <MainIcons mains={p.mains} size={28} />
                </span>
                <small>seed {p.seed ?? "–"}</small>
              </li>
            ))}
          </ol>
          <ShareImage
            endpoint={`/og/tournament/${id}`}
            filename={`top-${id}.png`}
            label="Descargar imagen del top"
            rowsPath={`insights/tournaments/${id}?limit=12`}
          />
          {s.upsets.length > 0 && (
            <>
              <h3>Sorpresas</h3>
              <ol className="upsets">
                {s.upsets.map((u, i) => (
                  <UpsetRow key={i} u={u} />
                ))}
              </ol>
            </>
          )}
          {s.overperformers.length > 0 && (
            <>
              <h3>Rindieron por encima de su seed</h3>
              <ul className="leaders">
                {s.overperformers.map((p) => (
                  <li key={p.id} style={tint(p.mains)}>
                    <PlayerLink p={p} />
                    <span>
                      seed {p.seed}, terminó {p.placement}.º
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </Resource>
  );
}

/** Home: upcoming tournaments in Paraguay from start.gg. */
export function UpcomingTournaments() {
  return (
    <Resource<{ items: CalendarItem[] }> path="insights/calendar" optional>
      {(d) =>
        d.items.length ? (
          <ul className="recent">
            {d.items.slice(0, 5).map((t) => (
              <li key={t.url}>
                <time dateTime={t.starts_at ?? undefined}>
                  {t.starts_at
                    ? new Date(t.starts_at).toLocaleDateString("es-PY", {
                        timeZone: "America/Asuncion",
                        day: "numeric",
                        month: "short",
                      })
                    : ""}
                </time>
                <a href={t.url} target="_blank" rel="noreferrer">
                  {t.name}
                </a>
                <span>
                  {t.city ?? ""}
                  {t.attendees ? `, ${t.attendees} inscritos` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="seeding-lead">No hay torneos anunciados en start.gg.</p>
        )
      }
    </Resource>
  );
}
