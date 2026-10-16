"use client";

import Link from "next/link";
import { useState } from "react";
import { Collection, Resource } from "./competition-browser";
import type {
  CompetitiveMatch,
  FrequentOpponent,
  HeadToHead,
  PlayerDetail,
  Scope,
  Statistics,
} from "../lib/api";

function date(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
      })
    : "Fecha no disponible";
}
function rate(value: number | null) {
  return value === null ? "No calculable" : `${value} %`;
}

function ScopeFilters({
  scopes,
  scope,
  onScope,
  from,
  to,
  onFrom,
  onTo,
}: {
  scopes: Scope[];
  scope: string;
  onScope: (value: string) => void;
  from: string;
  to: string;
  onFrom: (value: string) => void;
  onTo: (value: string) => void;
}) {
  return (
    <div className="pagination">
      <label>
        Videojuego y modalidad{" "}
        <select value={scope} onChange={(e) => onScope(e.target.value)}>
          {scopes.map((s) => (
            <option
              key={`${s.game_id}:${s.mode}`}
              value={`${s.game_id}:${s.mode}`}
            >
              {s.game_name} · {s.mode === "singles" ? "Singles" : "Dobles"}
            </option>
          ))}
        </select>
      </label>
      <label>
        Desde (hora local){" "}
        <input
          type="datetime-local"
          value={from}
          onChange={(e) => onFrom(e.target.value)}
        />
      </label>
      <label>
        Hasta, exclusivo (hora local){" "}
        <input
          type="datetime-local"
          value={to}
          onChange={(e) => onTo(e.target.value)}
        />
      </label>
    </div>
  );
}

function query(scope: string, from: string, to: string) {
  const [game_id, mode] = scope.split(":");
  const values = new URLSearchParams({ game_id, mode });
  if (from) values.set("date_from", new Date(from).toISOString());
  if (to) values.set("date_to", new Date(to).toISOString());
  return values.toString();
}

export function CompetitiveMatchCard({ match }: { match: CompetitiveMatch }) {
  return (
    <>
      <h3>
        {match.result === "W" ? "Victoria" : "Derrota"} ·{" "}
        {match.opponents.map((p) => p.tag).join(" / ")}
      </h3>
      <p>
        {match.score === null || match.opponent_score === null
          ? "Puntuación no disponible"
          : `${match.score} – ${match.opponent_score}`}{" "}
        · {match.round_label || "Ronda no disponible"}
      </p>
      <p>
        <Link href={`/tournaments/${match.tournament_id}`}>
          {match.tournament_name}
        </Link>{" "}
        · {date(match.completed_at)}
      </p>
      <p>
        <Link href={`/events/${match.event_id}`}>{match.event_name}</Link> · Set
        elegible
      </p>
      {match.source_url && (
        <a href={match.source_url} target="_blank" rel="noreferrer">
          Fuente: {match.source || "Origen"}
        </a>
      )}
    </>
  );
}

export function PlayerStatistics({
  id,
  scopes,
}: {
  id: string;
  scopes: Scope[];
}) {
  const [selected, setSelected] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const scope =
    selected || (scopes[0] ? `${scopes[0].game_id}:${scopes[0].mode}` : "");
  if (!scope)
    return (
      <section className="data-section">
        <h2>Estadísticas</h2>
        <p>No hay una modalidad confirmada para consultar estadísticas.</p>
      </section>
    );
  const filters = query(scope, from, to);
  const invalid = from && to && new Date(from) >= new Date(to);
  return (
    <section className="data-section" aria-label="Estadísticas competitivas">
      <h2>Estadísticas competitivas</h2>
      <ScopeFilters
        scopes={scopes}
        scope={scope}
        onScope={setSelected}
        from={from}
        to={to}
        onFrom={setFrom}
        onTo={setTo}
      />
      {scope.endsWith(":doubles") && (
        <p>
          Dobles: resultados del equipo al que perteneció el jugador. Los
          rivales son miembros de los equipos contrarios.
        </p>
      )}
      {invalid ? (
        <p role="alert">La fecha inicial debe ser anterior a la final.</p>
      ) : (
        <>
          <Resource<Statistics> path={`players/${id}/statistics?${filters}`}>
            {(s) => (
              <div className="data-card">
                {s.sets_played === 0 && (
                  <p>No hay sets elegibles en este ámbito.</p>
                )}
                <p>
                  {s.sets_played} sets jugados · {s.wins} victorias · {s.losses}{" "}
                  derrotas
                </p>
                <p>Porcentaje de victorias: {rate(s.win_rate)}</p>
                <p>
                  {s.tournaments_played} torneos disputados ·{" "}
                  {s.tournaments_registered} torneos con inscripción
                </p>
                <p>
                  Mejor placement final:{" "}
                  {s.best_final_placement ?? "No disponible"}
                </p>
                <p>
                  {s.unique_opponents} rivales únicos · Primer set:{" "}
                  {date(s.first_set_at)} · Último set: {date(s.last_set_at)}
                </p>
              </div>
            )}
          </Resource>
          <Collection<FrequentOpponent>
            key={`opponents-${filters}`}
            title="Rivales frecuentes"
            path={`players/${id}/opponents?${filters}`}
            render={(r) => (
              <>
                <h3>
                  <Link href={`/players/${id}/vs/${r.opponent.id}?${filters}`}>
                    {r.opponent.tag} · Ver Head-to-Head ↗
                  </Link>
                </h3>
                <p>
                  {r.sets_played} sets · {r.wins} victorias · {r.losses}{" "}
                  derrotas · {rate(r.win_rate)}
                </p>
                <p>Último enfrentamiento: {date(r.last_encounter_at)}</p>
              </>
            )}
          />
          <Collection<CompetitiveMatch>
            key={`matches-${filters}`}
            title="Últimos resultados"
            path={`players/${id}/matches?${filters}`}
            render={(match) => <CompetitiveMatchCard match={match} />}
          />
        </>
      )}
    </section>
  );
}

export function HeadToHeadPage({
  id,
  opponentId,
  initialGame,
  initialMode,
  initialFrom = "",
  initialTo = "",
}: {
  id: string;
  opponentId: string;
  initialGame?: string;
  initialMode?: string;
  initialFrom?: string;
  initialTo?: string;
}) {
  return (
    <div className="competition-page">
      <Link href={`/players/${id}`}>← Perfil de jugador</Link>
      <h1>Head-to-Head</h1>
      {id === opponentId ? (
        <p role="alert">Un jugador no puede enfrentarse a sí mismo.</p>
      ) : (
        <Resource<PlayerDetail> path={`players/${id}`}>
          {(p) => (
            <Comparison
              key={`${id}:${opponentId}`}
              id={id}
              opponentId={opponentId}
              scopes={p.scopes || []}
              initialGame={initialGame}
              initialMode={initialMode}
              initialFrom={initialFrom}
              initialTo={initialTo}
            />
          )}
        </Resource>
      )}
    </div>
  );
}

function localInput(value: string) {
  const parsed = new Date(value);
  if (!value || Number.isNaN(parsed.getTime())) return "";
  return new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

function Comparison({
  id,
  opponentId,
  scopes,
  initialGame,
  initialMode,
  initialFrom,
  initialTo,
}: {
  id: string;
  opponentId: string;
  scopes: Scope[];
  initialGame?: string;
  initialMode?: string;
  initialFrom: string;
  initialTo: string;
}) {
  const initial =
    scopes.find((s) => s.game_id === initialGame && s.mode === initialMode) ||
    scopes[0];
  const [selected, setSelected] = useState(
    initial ? `${initial.game_id}:${initial.mode}` : "",
  );
  const [from, setFrom] = useState(localInput(initialFrom));
  const [to, setTo] = useState(localInput(initialTo));
  const [page, setPage] = useState(1);
  if (!selected) return <p>No hay una modalidad confirmada para comparar.</p>;
  const filters = query(selected, from, to);
  return (
    <>
      <ScopeFilters
        scopes={scopes}
        scope={selected}
        onScope={(v) => {
          setSelected(v);
          setPage(1);
        }}
        from={from}
        to={to}
        onFrom={(v) => {
          setFrom(v);
          setPage(1);
        }}
        onTo={(v) => {
          setTo(v);
          setPage(1);
        }}
      />
      {selected.endsWith(":doubles") && (
        <p>
          Dobles: se comparan resultados de equipos opuestos a los que
          pertenecieron estos jugadores.
        </p>
      )}
      {from && to && new Date(from) >= new Date(to) ? (
        <p role="alert">La fecha inicial debe ser anterior a la final.</p>
      ) : (
        <Resource<HeadToHead>
          path={`players/${id}/head-to-head/${opponentId}?${filters}&page=${page}`}
        >
          {(h) => (
            <>
              <h2>
                <Link href={`/players/${h.player_a.id}`}>{h.player_a.tag}</Link>{" "}
                vs.{" "}
                <Link href={`/players/${h.player_b.id}`}>{h.player_b.tag}</Link>
              </h2>
              <p>
                {h.encounters} enfrentamientos · Marcador histórico: {h.wins_a}{" "}
                – {h.wins_b}
              </p>
              <p>
                {h.player_a.tag}: {rate(h.win_rate_a)} · {h.player_b.tag}:{" "}
                {rate(h.win_rate_b)}
              </p>
              <p>
                Primero: {date(h.first_encounter_at)} · Último:{" "}
                {date(h.last_encounter_at)}
              </p>
              {h.encounters === 0 ? (
                <p>
                  No hay enfrentamientos elegibles entre estos jugadores en este
                  ámbito.
                </p>
              ) : (
                <>
                  <h2>Historial de enfrentamientos</h2>
                  <div className="data-grid">
                    {h.history.items.map((match) => (
                      <article className="data-card" key={match.id}>
                        <CompetitiveMatchCard match={match} />
                      </article>
                    ))}
                  </div>
                  <div className="pagination">
                    <button
                      disabled={page === 1}
                      onClick={() => setPage(page - 1)}
                    >
                      Anterior
                    </button>
                    <span>Página {page}</span>
                    <button
                      disabled={page * h.history.page_size >= h.history.total}
                      onClick={() => setPage(page + 1)}
                    >
                      Siguiente
                    </button>
                  </div>
                </>
              )}
            </>
          )}
        </Resource>
      )}
    </>
  );
}
