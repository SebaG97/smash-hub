"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { ImportPanel } from "./import-panel";
import { characterColor, characterIcon } from "../lib/characters";
import { MainIcons, RankingFlag, mainColor } from "./mains";
import { PlayerStatistics } from "./player-statistics";
import type {
  Page,
  Tournament,
  Event,
  Entrant,
  Match,
  Player,
  PlayerDetail,
} from "../lib/api";

const api = process.env.NEXT_PUBLIC_API_URL || "/api/v1";
const labels: Record<string, string> = {
  not_played: "No disputado",
  in_progress: "En curso",
  unknown: "Estado por revisar",
  pending: "Pendiente",
  completed: "Finalizado",
  dq: "Descalificación",
  bye: "Pase libre",
  incomplete: "Resultado incompleto",
  COMPLETED: "Finalizado",
  ACTIVE: "En curso",
  CREATED: "Creado",
  READY: "Preparado",
};
function status(value: string | null) {
  return value ? labels[value] || value : "Estado no disponible";
}
function date(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
      })
    : "Fecha no disponible";
}

export function Resource<T>({
  path,
  children,
}: {
  path: string;
  children: (data: T) => ReactNode;
}) {
  const [state, setState] = useState<{
    path: string;
    data?: T;
    error?: string;
    loading: boolean;
  }>({ path, loading: true });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const timer = setTimeout(() => controller.abort(), 12000);
    fetch(`${api.replace(/\/$/, "")}/${path}`, { signal: controller.signal })
      .then(async (r) => {
        if (!r.ok)
          throw new Error(
            r.status === 404
              ? "No se encontró este registro."
              : "No se pudieron cargar los datos.",
          );
        const data = (await r.json()) as T;
        if (active) setState({ path, data, loading: false });
      })
      .catch((error: unknown) => {
        if (active)
          setState({
            path,
            loading: false,
            error:
              error instanceof Error &&
              error.message === "No se encontró este registro."
                ? error.message
                : "No se pudieron cargar los datos.",
          });
      })
      .finally(() => clearTimeout(timer));
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, retry]);
  if (state.path !== path || state.loading)
    return <p role="status">Cargando datos…</p>;
  if (state.error)
    return (
      <div role="alert">
        <p>{state.error}</p>
        <button
          className="primary-button"
          onClick={() => {
            setState({ path, loading: true });
            setRetry(retry + 1);
          }}
        >
          Reintentar
        </button>
      </div>
    );
  return state.data !== undefined ? children(state.data) : null;
}

export function Collection<T>({
  path,
  title,
  render,
  search = false,
  initialQuery = "",
}: {
  path: string;
  title: string;
  render: (item: T) => ReactNode;
  search?: boolean;
  initialQuery?: string;
}) {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState(initialQuery);
  return (
    <section aria-label={title} className="data-section">
      <h2>{title}</h2>
      {search && (
        <label className="search-label">
          Buscar
          <input
            type="search"
            maxLength={120}
            value={q}
            placeholder="Nombre o tag"
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
      )}
      <Resource<Page<T>>
        path={`${path}${path.includes("?") ? "&" : "?"}page=${page}&page_size=20${search ? `&q=${encodeURIComponent(q)}` : ""}`}
      >
        {(data) => (
          <>
            {data.items.length === 0 ? (
              <p>No hay registros disponibles.</p>
            ) : (
              <div className="data-grid">
                {data.items.map((item, i) => (
                  <article
                    className="data-card"
                    key={(item as { id?: string }).id || i}
                  >
                    {render(item)}
                  </article>
                ))}
              </div>
            )}
            <div className="pagination">
              <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                Anterior
              </button>
              <span>
                Página {page} · {data.total} registros
              </span>
              <button
                disabled={page * data.page_size >= data.total}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </Resource>
    </section>
  );
}

export function Tournaments() {
  return (
    <div className="competition-page">
      <h1>Torneos</h1>
      <ImportPanel />
      <Collection<Tournament>
        title="Todos los torneos"
        path="tournaments"
        search
        render={(t) => (
          <>
            <h3>
              <Link href={`/tournaments/${t.id}`}>{t.name}</Link>
            </h3>
            <p>
              {date(t.starts_at)}. {t.participant_count} jugadores,{" "}
              {t.entrant_count} inscripciones en{" "}
              {t.games.join(", ") || "un videojuego sin datos"}.{" "}
              {status(t.status)}.
            </p>
            <RankingFlag
              tournamentId={t.id}
              initial={t.counts_for_ranking !== false}
            />
          </>
        )}
      />
    </div>
  );
}
function EventCard(e: Event) {
  return (
    <>
      <h3>
        <Link href={`/events/${e.id}`}>{e.name}</Link>
      </h3>
      <p>
        {e.game} ·{" "}
        {e.team_size === 1 ? "Individual" : `Equipos de ${e.team_size}`}
      </p>
      <p>
        {e.entrant_count} entrants · {status(e.status)}
      </p>
    </>
  );
}
export function TournamentPage({ id }: { id: string }) {
  return (
    <div className="competition-page">
      <Link href="/tournaments">← Torneos</Link>
      <Resource<Tournament> path={`tournaments/${id}`}>
        {(t) => (
          <>
            <h1>{t.name}</h1>
            <p>
              {date(t.starts_at)} · {status(t.status)}
            </p>
            <p>
              {[t.location?.city, t.location?.country_code]
                .filter(Boolean)
                .join(", ")}
            </p>
            <p>
              {t.participant_count} participantes · {t.entrant_count}{" "}
              inscripciones a eventos
            </p>
            <p>Fuente: {t.source || "No disponible"}</p>
            <Collection<Event>
              title="Eventos y resultados"
              path={`tournaments/${id}/events`}
              render={EventCard}
            />
          </>
        )}
      </Resource>
    </div>
  );
}
export function EventPage({ id }: { id: string }) {
  return (
    <div className="competition-page">
      <Resource<Event> path={`events/${id}`}>
        {(e) => (
          <>
            <Link href={`/tournaments/${e.tournament_id}`}>← Torneo</Link>
            <h1>{e.name}</h1>
            <p>
              {e.game} ·{" "}
              {e.team_size === 1 ? "Individual" : `Equipos de ${e.team_size}`} ·{" "}
              {status(e.status)}
            </p>
            <Collection<Entrant>
              title="Participantes y equipos"
              path={`events/${id}/entrants`}
              search
              render={(entrant) => (
                <>
                  <h3>{entrant.name}</h3>
                  <p>
                    Placement: {entrant.placement ?? "No disponible"} · Seed:{" "}
                    {entrant.seed ?? "No disponible"}
                  </p>
                  <ul>
                    {entrant.members.map((m) => (
                      <li key={m.player_id}>
                        <Link href={`/players/${m.player_id}`}>{m.tag}</Link>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            />
            <Collection<Match>
              title="Sets y resultados"
              path={`events/${id}/sets`}
              render={(match) => <MatchCard match={match} />}
            />
            <Collection<Match>
              title="Posiciones del bracket y rondas no disputadas"
              path={`events/${id}/sets?view=bracket`}
              render={(match) => <MatchCard match={match} />}
            />
          </>
        )}
      </Resource>
    </div>
  );
}
export function Players({ initialQuery = "" }: { initialQuery?: string }) {
  return (
    <div className="competition-page">
      <h1>Jugadores</h1>
      <Collection<Player>
        path="players"
        title="Todos los jugadores"
        search
        initialQuery={initialQuery}
        render={(p) => (
          <>
            <h3>
              <Link href={`/players/${p.id}`}>{p.tag}</Link>{" "}
              <MainIcons mains={p.mains} />
            </h3>
            {p.mains && p.mains.length > 0 && (
              <p>
                {p.mains
                  .map((m) => `${m.character} ${Math.round(m.share)} %`)
                  .join(", ")}
              </p>
            )}
          </>
        )}
      />
    </div>
  );
}
export function PlayerPage({ id }: { id: string }) {
  const [page, setPage] = useState(1);
  return (
    <div className="competition-page">
      <Link href="/players">← Jugadores</Link>
      <Resource<PlayerDetail> path={`players/${id}?page=${page}`}>
        {(p) => (
          <>
            <header
              className="player-hero"
              style={
                mainColor(p.mains)
                  ? ({ "--main": mainColor(p.mains) } as React.CSSProperties)
                  : undefined
              }
            >
              <MainIcons mains={p.mains?.slice(0, 1)} size={88} />
              <div>
                <h1>{p.tag}</h1>
                {p.mains && p.mains.length > 0 && (
                  <p>Juega sobre todo {p.mains[0].character}.</p>
                )}
              </div>
            </header>
            {p.mains && p.mains.length > 0 && (
              <section className="player-mains" aria-label="Mains">
                <h2>Mains</h2>
                <ul>
                  {p.mains.map((m) => (
                    <li key={m.character}>
                      <strong>
                        {(characterIcon(m.character) || m.icon) && (
                          <MainIcons mains={[m]} size={28} />
                        )}{" "}
                        {m.character}
                      </strong>
                      <span
                        className="main-bar"
                        style={{
                          width: `${Math.max(4, m.share)}%`,
                          background: characterColor(m.character) ?? undefined,
                        }}
                        aria-hidden="true"
                      />
                      <small>
                        {Math.round(m.share)} % · {m.games}{" "}
                        {m.games === 1 ? "partida" : "partidas"}
                      </small>
                    </li>
                  ))}
                </ul>
                <p className="seeding-lead">
                  Según los personajes que los torneos cargaron en start.gg
                  (partidas de singles).
                </p>
              </section>
            )}
            <PlayerStatistics key={id} id={id} scopes={p.scopes || []} />
            <h2>Tags conocidos</h2>
            <p>{p.aliases.join(" · ") || "Sin tags adicionales"}</p>
            <h2>Historial competitivo</h2>
            {p.history.items.length === 0 ? (
              <p>No hay historial disponible.</p>
            ) : (
              <div className="data-grid">
                {p.history.items.map((h) => (
                  <article className="data-card" key={h.event_id}>
                    <h3>
                      <Link href={`/tournaments/${h.tournament_id}`}>
                        {h.tournament_name}
                      </Link>
                    </h3>
                    <Link href={`/events/${h.event_id}`}>{h.event_name}</Link>
                    <p>
                      Tag histórico: {h.tag} · {h.entrant_name}
                    </p>
                    <p>Placement: {h.placement ?? "No disponible"}</p>
                  </article>
                ))}
              </div>
            )}
            <div className="pagination">
              <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                Anterior
              </button>
              <span>Página {page}</span>
              <button
                disabled={page * p.history.page_size >= p.history.total}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
            </div>
          </>
        )}
      </Resource>
    </div>
  );
}

export function MatchCard({ match }: { match: Match }) {
  const special = {
    bye: "Pase libre · Sin partido jugado",
    dq: "Descalificación · Excluido de victorias y derrotas jugadas",
    placeholder: "Posición del bracket sin enfrentamiento",
    conditional_unused: "Reset condicional no utilizado",
  };
  const bracket =
    match.resolution === "placeholder" ||
    match.resolution === "conditional_unused";
  return (
    <>
      <h3>{match.round_label || "Ronda no disponible"}</h3>
      <p>
        {match.resolution in special
          ? special[match.resolution as keyof typeof special]
          : status(match.status)}
      </p>
      {bracket ? (
        <p>No representa un partido pendiente entre dos oponentes.</p>
      ) : (
        <>
          {match.status === "completed" &&
            match.resolution === "unresolved" && (
              <p>
                Final informado sin evidencia suficiente del resultado jugado.
              </p>
            )}
          <ul>
            {match.sides.map((s, i) => (
              <li key={i}>
                {s.name || "Esperando oponente"} · {s.score ?? "Sin puntuación"}
                {s.is_winner
                  ? match.resolution === "bye" || match.resolution === "dq"
                    ? " · Avanza"
                    : " · Ganador informado"
                  : ""}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
