"use client";

import Link from "next/link";
import { MainIcons } from "./mains";
import { characterColor } from "../lib/characters";
import type { Breakdown, Statistics, WinLoss } from "../lib/api";

const TIERS: Record<Breakdown["vs_ranking"][number]["tier"], string> = {
  top10: "Top 10",
  top25: "Puestos 11 a 25",
  ranked: "Puesto 26 o más",
  unranked: "Sin puesto en el ranking",
};
const MONTHS = [
  "ene",
  "feb",
  "mar",
  "abr",
  "may",
  "jun",
  "jul",
  "ago",
  "sep",
  "oct",
  "nov",
  "dic",
];

function percent(wins: number, losses: number) {
  const total = wins + losses;
  return total ? Math.round((100 * wins) / total) : null;
}
function day(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : "sin fecha";
}
function score(s: number | null, o: number | null) {
  return s === null || o === null || s < 0 || o < 0 ? "" : `${s}–${o}`;
}
function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`;
}

/** Victories and defeats as one split bar, with both numbers written next to it. */
export function RecordBar({
  label,
  wins,
  losses,
  hint,
}: WinLoss & { label: React.ReactNode; hint?: string }) {
  const total = wins + losses;
  const rate = percent(wins, losses);
  return (
    <li
      className="record-row"
      title={
        total
          ? `${wins} ganados y ${losses} perdidos (${rate} %)`
          : "Sin sets todavía"
      }
    >
      <span className="record-label">
        {label}
        {hint && <small>{hint}</small>}
      </span>
      <span className="record-track" aria-hidden="true">
        {total > 0 ? (
          <>
            {wins > 0 && (
              <span className="record-w" style={{ flexGrow: wins }} />
            )}
            {losses > 0 && (
              <span className="record-l" style={{ flexGrow: losses }} />
            )}
          </>
        ) : (
          <span className="record-empty" />
        )}
      </span>
      <span className="record-value">
        {total ? (
          <>
            <strong>
              {wins}–{losses}
            </strong>
            <small>{rate} %</small>
          </>
        ) : (
          <small>—</small>
        )}
      </span>
    </li>
  );
}

function Tiles({ s, b }: { s: Statistics; b: Breakdown }) {
  const rate = percent(b.record.wins, b.record.losses);
  const games = percent(b.games.wins, b.games.losses);
  const streak = b.current_streak;
  return (
    <div className="stat-hero">
      <div
        className="stat-ring"
        style={{ "--rate": `${rate ?? 0}%` } as React.CSSProperties}
        role="img"
        aria-label={
          rate === null
            ? "Sin sets para calcular el porcentaje"
            : `Ganó el ${rate} % de sus sets`
        }
      >
        <strong>{rate === null ? "—" : `${rate} %`}</strong>
        <span>sets ganados</span>
      </div>
      <dl className="stat-tiles">
        <div>
          <dt>Récord</dt>
          <dd>
            {b.record.wins}–{b.record.losses}
          </dd>
        </div>
        <div>
          <dt>Games</dt>
          <dd>
            {games === null ? "—" : `${games} %`}
            <small>
              {b.games.wins}–{b.games.losses}
            </small>
          </dd>
        </div>
        <div>
          <dt>Racha actual</dt>
          <dd
            className={
              streak.result === "W"
                ? "is-win"
                : streak.result === "L"
                  ? "is-loss"
                  : ""
            }
          >
            {streak.result
              ? `${streak.length} ${streak.result === "W" ? (streak.length === 1 ? "victoria" : "victorias") : streak.length === 1 ? "derrota" : "derrotas"}`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>Mejor racha</dt>
          <dd>{plural(b.best_win_streak, "victoria", "victorias")}</dd>
        </div>
        <div>
          <dt>Torneos</dt>
          <dd>{s.tournaments_played}</dd>
        </div>
        <div>
          <dt>Rivales distintos</dt>
          <dd>{s.unique_opponents}</dd>
        </div>
        <div>
          <dt>Mejor posición</dt>
          <dd>
            {s.best_final_placement ? `${s.best_final_placement}.º` : "—"}
          </dd>
        </div>
        <div>
          <dt>Jugando desde</dt>
          <dd className="stat-small">{day(s.first_set_at)}</dd>
        </div>
      </dl>
    </div>
  );
}

function Form({ b }: { b: Breakdown }) {
  if (!b.form.length) return null;
  return (
    <section className="stat-block" aria-labelledby="form-title">
      <h3 id="form-title">Últimos {b.form.length} sets</h3>
      <ol className="form-line">
        {b.form.map((f, i) => (
          <li
            key={i}
            className={f.result === "W" ? "is-win" : "is-loss"}
            title={`${f.result === "W" ? "Le ganó a" : "Perdió con"} ${f.opponents.join(" / ")} ${score(f.score, f.opponent_score)} · ${f.tournament_name}, ${day(f.completed_at)}`}
          >
            <span>{f.result === "W" ? "G" : "P"}</span>
            <small>{f.opponents.join(" / ")}</small>
          </li>
        ))}
      </ol>
      <p className="stat-note">
        De más viejo a más nuevo. G ganó, P perdió; pasá el mouse para ver el
        rival y el torneo.
      </p>
    </section>
  );
}

function monthLabel(month: string, index: number) {
  const [year, number] = month.split("-").map(Number);
  const name = MONTHS[number - 1];
  return index === 0 || number === 1
    ? `${name} ${String(year).slice(2)}`
    : name;
}

function Months({ b }: { b: Breakdown }) {
  if (b.months.length < 2) return null;
  const top = Math.max(1, ...b.months.map((m) => Math.max(m.wins, m.losses)));
  return (
    <section className="stat-block" aria-labelledby="months-title">
      <h3 id="months-title">Mes a mes</h3>
      <div className="month-chart" role="list">
        {b.months.map((m, i) => (
          <div
            key={m.month}
            className="month"
            role="listitem"
            title={`${monthLabel(m.month, 0)}: ${m.wins} ganados, ${m.losses} perdidos`}
            aria-label={`${monthLabel(m.month, 0)}: ${m.wins} ganados, ${m.losses} perdidos`}
          >
            <span className="month-up">
              {m.wins > 0 && <small>{m.wins}</small>}
              <span
                className="month-w"
                style={{ height: `${(100 * m.wins) / top}%` }}
              />
            </span>
            <span className="month-down">
              <span
                className="month-l"
                style={{ height: `${(100 * m.losses) / top}%` }}
              />
              {m.losses > 0 && <small>{m.losses}</small>}
            </span>
            <span className="month-name">{monthLabel(m.month, i)}</span>
          </div>
        ))}
      </div>
      <p className="stat-note">
        <span className="key key-w" /> sets ganados arriba ·{" "}
        <span className="key key-l" /> perdidos abajo
      </p>
    </section>
  );
}

function Placements({ b }: { b: Breakdown }) {
  if (!b.placements.length) return null;
  const rows = [...b.placements].reverse().slice(0, 12);
  return (
    <section className="stat-block" aria-labelledby="placements-title">
      <h3 id="placements-title">Torneo por torneo</h3>
      <ol className="placement-chart">
        {rows.map((p) => {
          const beat =
            p.entrants && p.entrants > 1
              ? Math.round(
                  (100 * (p.entrants - p.placement)) / (p.entrants - 1),
                )
              : null;
          return (
            <li
              key={`${p.tournament_id}-${p.event_name}`}
              className={p.placement === 1 ? "is-champion" : undefined}
            >
              <span className="place">{p.placement}</span>
              <span className="placement-name">
                <Link href={`/tournaments/${p.tournament_id}`}>
                  {p.tournament_name}
                </Link>
                <small>
                  {p.entrants ? `de ${p.entrants}` : ""} · {day(p.starts_at)}
                </small>
              </span>
              <span
                className="placement-track"
                title={
                  beat === null
                    ? undefined
                    : `Quedó por encima del ${beat} % de los inscriptos`
                }
              >
                {beat !== null && (
                  <span style={{ width: `${Math.max(beat, 2)}%` }} />
                )}
              </span>
              <small className="placement-beat">
                {beat === null ? "" : `superó al ${beat} %`}
              </small>
            </li>
          );
        })}
      </ol>
      <p className="stat-note">
        La barra es la parte del bracket que quedó por debajo: llena es ganar el
        torneo.
      </p>
    </section>
  );
}

function VsRanking({ b }: { b: Breakdown }) {
  if (!b.vs_ranking.length) return null;
  return (
    <section className="stat-block" aria-labelledby="tiers-title">
      <h3 id="tiers-title">Contra quién gana</h3>
      <ul className="record-list">
        {b.vs_ranking.map((t) => (
          <RecordBar key={t.tier} label={TIERS[t.tier]} {...t} />
        ))}
      </ul>
      <p className="stat-note">
        Según el puesto actual de cada rival en {b.ranking ?? "el ranking"}.
      </p>
    </section>
  );
}

function BestWins({ b }: { b: Breakdown }) {
  if (!b.best_wins.length) return null;
  return (
    <section className="stat-block" aria-labelledby="wins-title">
      <h3 id="wins-title">Mejores victorias</h3>
      <ol className="best-wins">
        {b.best_wins.map((w, i) => (
          <li key={i}>
            <span className="rank-badge">{w.place}.º</span>
            <span>
              <span>
                <strong>
                  {w.opponents.map((o, j) => (
                    <span key={o.id}>
                      {j > 0 && " / "}
                      <Link href={`/players/${o.id}`}>{o.tag}</Link>
                    </span>
                  ))}
                </strong>{" "}
                {score(w.score, w.opponent_score)}
              </span>
              <small>
                <Link href={`/tournaments/${w.tournament_id}`}>
                  {w.tournament_name}
                </Link>
                , {day(w.completed_at)}
              </small>
            </span>
          </li>
        ))}
      </ol>
      <p className="stat-note">
        Rivales con mejor puesto en el ranking actual.
      </p>
    </section>
  );
}

function HowItGoes({ b }: { b: Breakdown }) {
  const total = b.scores.reduce((n, s) => n + s.sets, 0);
  const top = Math.max(1, ...b.scores.map((s) => s.sets));
  return (
    <section className="stat-block" aria-labelledby="how-title">
      <h3 id="how-title">Cómo se definen sus sets</h3>
      <ul className="record-list">
        <RecordBar
          label="Winners"
          hint="lado de ganadores"
          {...b.winners_side}
        />
        <RecordBar
          label="Losers"
          hint="después de perder uno"
          {...b.losers_side}
        />
        <RecordBar label="Al último game" hint="2–1, 3–2…" {...b.deciding} />
      </ul>
      {total > 0 && (
        <>
          <h4>Marcadores</h4>
          <ul className="score-chart">
            {b.scores.map((s) => {
              const won = s.score > s.opponent_score;
              return (
                <li
                  key={`${s.score}-${s.opponent_score}`}
                  title={`${plural(s.sets, "set", "sets")} terminó ${s.score}–${s.opponent_score}`}
                >
                  <span className="score-name">
                    {s.score}–{s.opponent_score}
                  </span>
                  <span className="score-track">
                    <span
                      className={won ? "record-w" : "record-l"}
                      style={{ width: `${(100 * s.sets) / top}%` }}
                    />
                  </span>
                  <span className="score-count">{s.sets}</span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}

function Characters({ b }: { b: Breakdown }) {
  if (!b.characters.length) return null;
  const top = Math.max(...b.characters.map((c) => c.games));
  return (
    <section className="stat-block" aria-labelledby="chars-title">
      <h3 id="chars-title">Personajes</h3>
      <ul className="record-list">
        {b.characters.slice(0, 6).map((c) => (
          <RecordBar
            key={c.character}
            label={
              <span
                className="char-label"
                style={
                  {
                    "--main": characterColor(c.character) ?? "var(--line)",
                    "--usage": `${(100 * c.games) / top}%`,
                  } as React.CSSProperties
                }
              >
                <MainIcons
                  mains={[
                    {
                      character: c.character,
                      icon: c.icon,
                      games: c.games,
                      share: 0,
                    },
                  ]}
                  size={28}
                />
                <span>
                  {c.character}
                  <small>{plural(c.games, "game", "games")}</small>
                </span>
              </span>
            }
            wins={c.wins}
            losses={c.losses}
          />
        ))}
      </ul>
      <p className="stat-note">Games ganados y perdidos con cada personaje.</p>
    </section>
  );
}

/** The visual statistics of one scope (game, mode, dates). */
export function PlayerCharts({ s, b }: { s: Statistics; b: Breakdown }) {
  if (s.sets_played === 0)
    return <p className="stat-empty">No hay sets elegibles en este ámbito.</p>;
  return (
    <div className="player-charts">
      <Tiles s={s} b={b} />
      <Form b={b} />
      <div className="stat-grid">
        <Months b={b} />
        <HowItGoes b={b} />
        <VsRanking b={b} />
        <BestWins b={b} />
        <Placements b={b} />
        <Characters b={b} />
      </div>
    </div>
  );
}
