"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminHeaders, useAdmin } from "../lib/admin";
import { apiFetch, signInHref, useMe, type Me } from "../lib/session";

/** Prode: predictions on upcoming tournaments (Mission SH-PRODE-01, ADR-020). */

type Candidate = {
  startgg_player_id: string;
  tag: string;
  prefix: string | null;
  seed: number | null;
  id: string | null;
  withdrawn: boolean;
};
type Picks = {
  champion: string | null;
  runner_up: string | null;
  top8: string[];
};
type RankingRow = {
  rank: number;
  user_id: string;
  name: string;
  points: number;
  exact_hits: number;
  hits: number;
  picks: Partial<Picks>;
};
export type Contest = {
  id: string;
  tournament_slug: string;
  name: string;
  event_name: string | null;
  status: "open" | "locked" | "settled" | "void";
  locks_at: string | null;
  settled_at: string | null;
  rules: Record<string, number>;
  participants: number;
  candidates: Candidate[];
  mine: Picks;
  results: Partial<Record<"champion" | "runner_up" | "top8", string[]>>;
  ranking: RankingRow[];
};
export type Achievement = {
  kind: string;
  title: string;
  detail: string;
  rare: boolean;
  contest: string | null;
  tournament_slug: string | null;
};

/** What each achievement asks for; the backend (app/prode/engine.py) awards them. */
export const ACHIEVEMENTS: [title: string, how: string, rare?: boolean][] = [
  ["Oráculo", "Acertar al campeón."],
  ["Ojo clínico", "Acertar al subcampeón."],
  ["Contra la corriente", "Acertar un campeón que no era el seed 1."],
  ["Profeta del batacazo", "Acertar un campeón de seed 5 o peor.", true],
  ["Vidente del Top 8", "Acertar los 8 del Top 8.", true],
  ["Pleno", "Campeón, subcampeón y Top 8 exactos.", true],
  ["Fe en sí mismo", "Elegirte campeón a vos mismo."],
  ["Profecía autocumplida", "Elegirte campeón… y ganar el torneo.", true],
  ["Campeón del Prode", "Ganar el Prode de un torneo."],
  ["Podio del Prode", "Terminar 2.º o 3.º en el Prode de un torneo."],
  ["Habitué del Prode", "Jugar 3 Prodes."],
  ["Dinastía", "Ganar 2 Prodes.", true],
];

const WHEN = new Intl.DateTimeFormat("es-PY", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "America/Asuncion",
});

function when(iso: string | null) {
  return iso ? WHEN.format(new Date(iso)) : null;
}

async function detail(r: Response) {
  try {
    const body = (await r.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}

/** Loads one API path with the session cookie; `replace` swaps in a newer answer. */
function useLoad<T>(path: string) {
  const [state, setState] = useState<{
    path: string;
    data?: T;
    status?: number;
    loading: boolean;
  }>({ path, loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let active = true;
    apiFetch(path)
      .then(async (r) => {
        const data = r.ok ? ((await r.json()) as T) : undefined;
        if (active) setState({ path, data, status: r.status, loading: false });
      })
      .catch(() => {
        if (active) setState({ path, status: 0, loading: false });
      });
    return () => {
      active = false;
    };
  }, [path, tick]);
  const loading = state.loading || state.path !== path;
  return {
    data: loading ? undefined : state.data,
    status: loading ? undefined : state.status,
    loading,
    reload: () => setTick((t) => t + 1),
    replace: (data: T) => setState({ path, data, status: 200, loading: false }),
  };
}

function label(c: Candidate) {
  const name = c.prefix ? `${c.prefix} | ${c.tag}` : c.tag;
  return c.seed ? `${c.seed} · ${name}` : name;
}

/** The Prode tab of a tournament preview. */
export function ProdeTab({ slug }: { slug: string }) {
  const admin = useAdmin();
  const me = useMe();
  const { data, status, loading, reload, replace } = useLoad<Contest>(
    `prode/tournaments/${slug}`,
  );
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  if (loading) return <p role="status">Cargando el Prode…</p>;

  async function organizer(path: string, body?: object) {
    setBusy(true);
    setProblem(null);
    const r = await apiFetch(path, {
      method: "POST",
      headers: adminHeaders(admin),
      body: body ? JSON.stringify(body) : undefined,
    }).catch(() => null);
    setBusy(false);
    if (r?.ok) replace((await r.json()) as Contest);
    else setProblem((r && (await detail(r))) ?? "No se pudo completar.");
  }

  if (status === 404 || !data) {
    return (
      <section aria-label="Prode" className="prode">
        {status === 404 ? (
          <p className="seeding-lead">
            Todavía no hay Prode para este torneo. Cuando los organizadores lo
            abran vas a poder pronosticar campeón, subcampeón y Top 8.
          </p>
        ) : (
          <div role="alert">
            <p>No se pudo cargar el Prode.</p>
            <button className="primary-button" onClick={reload}>
              Reintentar
            </button>
          </div>
        )}
        {admin && status === 404 && (
          <button
            className="primary-button"
            disabled={busy}
            onClick={() => organizer(`prode/tournaments/${slug}`)}
          >
            {busy ? "Abriendo…" : "Abrir Prode"}
          </button>
        )}
        {problem && <p role="alert">{problem}</p>}
      </section>
    );
  }
  return (
    <section aria-label="Prode" className="prode">
      <ContestHead contest={data} />
      {data.status === "open" ? (
        <PicksForm
          key={data.id}
          contest={data}
          me={me}
          onSaved={(next) => replace(next)}
        />
      ) : (
        <ContestResults contest={data} me={me} />
      )}
      {admin && (
        <div className="prode-admin" aria-label="Organizadores">
          <h3>Organizadores</h3>
          <div className="prode-actions">
            {data.status === "open" && (
              <button
                disabled={busy}
                onClick={() => organizer(`prode/contests/${data.id}/lock`)}
              >
                Cerrar ahora
              </button>
            )}
            {data.status === "locked" && (
              <button
                disabled={busy}
                onClick={() =>
                  organizer(`prode/contests/${data.id}/reopen`, {
                    locks_at: null,
                  })
                }
              >
                Reabrir (sin cierre automático)
              </button>
            )}
            {data.status !== "open" && (
              <button
                className="primary-button"
                disabled={busy}
                onClick={() => organizer(`prode/contests/${data.id}/settle`)}
              >
                {busy
                  ? "Calculando…"
                  : data.status === "settled"
                    ? "Volver a liquidar"
                    : "Liquidar con start.gg"}
              </button>
            )}
            <button
              disabled={busy}
              onClick={() => {
                if (window.confirm("¿Anular este Prode? No suma puntos."))
                  void organizer(`prode/contests/${data.id}/void`);
              }}
            >
              Anular
            </button>
          </div>
          <p className="seeding-lead">
            Liquidar lee el Top 8 final de start.gg; se puede repetir después de
            una corrección y recalcula todo.
          </p>
        </div>
      )}
      {problem && <p role="alert">{problem}</p>}
    </section>
  );
}

function ContestHead({ contest }: { contest: Contest }) {
  const r = contest.rules;
  const status = {
    open: contest.locks_at
      ? `Abierto: cierra el ${when(contest.locks_at)}.`
      : "Abierto.",
    locked: "Cerrado: ya no se pueden cambiar los pronósticos.",
    settled: "Terminado: puntos y logros repartidos.",
    void: "Anulado.",
  }[contest.status];
  return (
    <>
      <p className="seeding-lead">
        <strong>{status}</strong> {contest.participants}{" "}
        {contest.participants === 1 ? "persona juega" : "personas juegan"}.
        Campeón {r.champion} pts · subcampeón {r.runner_up} pts · cada acierto
        del Top 8, {r.top8} pts. El premio son <Link href="/prode">logros</Link>{" "}
        para tu perfil.
      </p>
    </>
  );
}

function PicksForm({
  contest,
  me,
  onSaved,
}: {
  contest: Contest;
  me: Me | null;
  onSaved: (contest: Contest) => void;
}) {
  const [champion, setChampion] = useState(contest.mine.champion ?? "");
  const [runnerUp, setRunnerUp] = useState(contest.mine.runner_up ?? "");
  const [top8, setTop8] = useState<string[]>(contest.mine.top8);
  const [query, setQuery] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const byId = new Map(contest.candidates.map((c) => [c.startgg_player_id, c]));
  const active = contest.candidates.filter((c) => !c.withdrawn);
  const q = query.trim().toLowerCase();
  const shown = active.filter(
    (c) => !q || `${c.prefix ?? ""} ${c.tag}`.toLowerCase().includes(q),
  );

  if (me && !me.user) {
    return (
      <div className="prode-login">
        <p>Para jugar el Prode ingresá con tu cuenta de Smash Hub.</p>
        <p>
          <Link className="primary-button" href={signInHref()}>
            Ingresar
          </Link>{" "}
          <Link href="/registro">o creá una cuenta gratis</Link>
        </p>
      </div>
    );
  }

  function options(exclude: string) {
    const list = active.filter((c) => c.startgg_player_id !== exclude);
    return list.map((c) => (
      <option key={c.startgg_player_id} value={c.startgg_player_id}>
        {label(c)}
      </option>
    ));
  }

  function gone(id: string) {
    const c = byId.get(id);
    return c?.withdrawn ? (
      <small className="prode-warning">
        {c.tag} se dio de baja: elegí a otra persona.
      </small>
    ) : null;
  }

  async function save() {
    setSaving(true);
    setMessage(null);
    const r = await apiFetch(`prode/contests/${contest.id}/picks`, {
      method: "PUT",
      body: JSON.stringify({
        champion: champion || null,
        runner_up: runnerUp || null,
        top8,
      }),
    }).catch(() => null);
    setSaving(false);
    if (r?.ok) {
      onSaved((await r.json()) as Contest);
      setMessage("¡Guardado! Podés cambiarlo hasta el cierre.");
    } else {
      setMessage((r && (await detail(r))) ?? "No se pudo guardar.");
    }
  }

  return (
    <form
      className="prode-form"
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <div className="prode-podium">
        <label>
          <span>Campeón</span>
          <select
            value={champion}
            onChange={(e) => setChampion(e.target.value)}
          >
            <option value="">Elegí…</option>
            {options(runnerUp)}
          </select>
          {gone(champion)}
        </label>
        <label>
          <span>Subcampeón</span>
          <select
            value={runnerUp}
            onChange={(e) => setRunnerUp(e.target.value)}
          >
            <option value="">Elegí…</option>
            {options(champion)}
          </select>
          {gone(runnerUp)}
        </label>
      </div>
      <fieldset className="prode-top8">
        <legend>
          Top 8 <span aria-live="polite">({top8.length}/8)</span>
        </legend>
        {top8.length > 0 && (
          <ul className="prode-chosen" aria-label="Tu Top 8">
            {top8.map((id) => (
              <li key={id} className={byId.get(id)?.withdrawn ? "gone" : ""}>
                {byId.get(id)?.tag ?? id}
                <button
                  type="button"
                  aria-label={`Sacar a ${byId.get(id)?.tag ?? id}`}
                  onClick={() => setTop8(top8.filter((x) => x !== id))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        <input
          type="search"
          aria-label="Buscar jugador para el Top 8"
          placeholder="Buscá un jugador…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <ul className="prode-pool">
          {shown.map((c) => {
            const on = top8.includes(c.startgg_player_id);
            return (
              <li key={c.startgg_player_id}>
                <button
                  type="button"
                  aria-pressed={on}
                  disabled={!on && top8.length >= 8}
                  onClick={() =>
                    setTop8(
                      on
                        ? top8.filter((x) => x !== c.startgg_player_id)
                        : [...top8, c.startgg_player_id],
                    )
                  }
                >
                  {label(c)}
                </button>
              </li>
            );
          })}
        </ul>
      </fieldset>
      <p className="prode-save">
        <button className="primary-button" type="submit" disabled={saving}>
          {saving ? "Guardando…" : "Guardar pronóstico"}
        </button>
        {message && <span role="status">{message}</span>}
      </p>
    </form>
  );
}

function ContestResults({ contest, me }: { contest: Contest; me: Me | null }) {
  const byId = new Map(contest.candidates.map((c) => [c.startgg_player_id, c]));
  const name = (id: string | null | undefined) =>
    id ? (byId.get(id)?.tag ?? id) : "—";
  const results = contest.results;
  const right = (kind: "champion" | "runner_up" | "top8", id: string) =>
    results[kind] ? (results[kind]!.includes(id) ? "hit" : "miss") : undefined;
  const mine = contest.mine;
  const played = Boolean(mine.champion || mine.runner_up || mine.top8.length);
  return (
    <>
      {results.champion && (
        <dl className="facts">
          <div>
            <dt>Campeón</dt>
            <dd>{name(results.champion[0])}</dd>
          </div>
          <div>
            <dt>Subcampeón</dt>
            <dd>{name(results.runner_up?.[0])}</dd>
          </div>
          <div className="fact-wide">
            <dt>Top 8</dt>
            <dd>{(results.top8 ?? []).map(name).join(", ")}</dd>
          </div>
        </dl>
      )}
      {me?.user && played && (
        <section aria-labelledby="mine-title">
          <h3 id="mine-title">Tu pronóstico</h3>
          <ul className="prode-mine">
            {mine.champion && (
              <li data-result={right("champion", mine.champion)}>
                Campeón: {name(mine.champion)}
              </li>
            )}
            {mine.runner_up && (
              <li data-result={right("runner_up", mine.runner_up)}>
                Subcampeón: {name(mine.runner_up)}
              </li>
            )}
            {mine.top8.map((id) => (
              <li key={id} data-result={right("top8", id)}>
                Top 8: {name(id)}
              </li>
            ))}
          </ul>
        </section>
      )}
      <h3>Ranking del Prode</h3>
      {contest.ranking.length === 0 ? (
        <p className="seeding-lead">Nadie jugó este Prode.</p>
      ) : (
        <div className="seeding-table-wrap">
          <table className="seeding-table prode-ranking">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Pronosticador</th>
                <th scope="col">Puntos</th>
                <th scope="col">Aciertos</th>
                <th scope="col">Su campeón</th>
              </tr>
            </thead>
            <tbody>
              {contest.ranking.map((r) => (
                <tr
                  key={r.user_id}
                  className={me?.user?.id === r.user_id ? "me" : undefined}
                >
                  <td>{r.rank}</td>
                  <td>
                    <Link href={`/prode/u/${r.user_id}`}>{r.name}</Link>
                  </td>
                  <td>{r.points}</td>
                  <td>{r.hits}</td>
                  <td>{name(r.picks.champion)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

export function AchievementList({ items }: { items: Achievement[] }) {
  return (
    <ul className="badges">
      {items.map((a, i) => (
        <li
          key={`${a.kind}-${a.contest}-${i}`}
          data-tone={a.rare ? "gold" : "fire"}
        >
          <strong>{a.title}</strong>
          <span>{a.detail}</span>
        </li>
      ))}
    </ul>
  );
}

type Overview = {
  contests: {
    id: string;
    tournament_slug: string;
    name: string;
    status: Contest["status"];
    locks_at: string | null;
    participants: number;
  }[];
  leaderboard: {
    rank: number;
    user_id: string;
    name: string;
    points: number;
    contests: number;
    precision: number | null;
  }[];
};

const STATUS = {
  open: "Abierto",
  locked: "Cerrado",
  settled: "Terminado",
  void: "Anulado",
};

/** /prode: open contests, the community leaderboard and the achievements. */
export function ProdePage() {
  const me = useMe();
  const { data, status, loading, reload } = useLoad<Overview>("prode");
  return (
    <div className="competition-page prode-page">
      <h1>Prode</h1>
      <p className="seeding-lead">
        Pronosticá campeón, subcampeón y Top 8 de los torneos antes de que
        empiecen. Es gratis: el premio son logros para tu perfil y, si sos
        jugador, también para tu ficha del hub.
      </p>
      {me && !me.user && (
        <p>
          <Link className="primary-button" href={signInHref("/prode")}>
            Ingresar
          </Link>{" "}
          <Link href="/registro">o creá una cuenta gratis</Link>
        </p>
      )}
      {me?.user && (
        <p>
          <Link href={`/prode/u/${me.user.id}`}>Ver mi perfil del Prode →</Link>
        </p>
      )}
      {loading ? (
        <p role="status">Cargando…</p>
      ) : !data || status !== 200 ? (
        <div role="alert">
          <p>No se pudieron cargar los datos.</p>
          <button className="primary-button" onClick={reload}>
            Reintentar
          </button>
        </div>
      ) : (
        <>
          <section aria-labelledby="contests-title">
            <h2 id="contests-title">Torneos</h2>
            {data.contests.length === 0 ? (
              <p className="seeding-lead">
                Todavía no hay Prodes. Se abren desde la previa de cada torneo.
              </p>
            ) : (
              <ul className="prode-contests">
                {data.contests.map((c) => (
                  <li key={c.id}>
                    <Link href={`/previa/${c.tournament_slug}#prode`}>
                      {c.name}
                    </Link>
                    <span data-status={c.status}>{STATUS[c.status]}</span>
                    <small>
                      {c.participants}{" "}
                      {c.participants === 1 ? "participante" : "participantes"}
                      {c.status === "open" && c.locks_at
                        ? ` · cierra el ${when(c.locks_at)}`
                        : ""}
                    </small>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-labelledby="leaderboard-title">
            <h2 id="leaderboard-title">Ranking de la comunidad</h2>
            {data.leaderboard.length === 0 ? (
              <p className="seeding-lead">
                Aparece cuando termine el primer Prode.
              </p>
            ) : (
              <div className="seeding-table-wrap">
                <table className="seeding-table prode-ranking">
                  <thead>
                    <tr>
                      <th scope="col">#</th>
                      <th scope="col">Pronosticador</th>
                      <th scope="col">Puntos</th>
                      <th scope="col">Prodes</th>
                      <th scope="col">Precisión</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.leaderboard.map((r) => (
                      <tr
                        key={r.user_id}
                        className={
                          me?.user?.id === r.user_id ? "me" : undefined
                        }
                      >
                        <td>{r.rank}</td>
                        <td>
                          <Link href={`/prode/u/${r.user_id}`}>{r.name}</Link>
                        </td>
                        <td>{r.points}</td>
                        <td>{r.contests}</td>
                        <td>
                          {r.precision === null ? "—" : `${r.precision}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
      <section aria-labelledby="catalog-title">
        <h2 id="catalog-title">Logros</h2>
        <ul className="badges">
          {ACHIEVEMENTS.map(([title, how, rare]) => (
            <li key={title} data-tone={rare ? "gold" : "fire"}>
              <strong>
                {title}
                {rare ? " ★" : ""}
              </strong>
              <span>{how}</span>
            </li>
          ))}
        </ul>
        <p className="seeding-lead">★ Logro raro.</p>
      </section>
    </div>
  );
}

type Profile = {
  id: string;
  name: string;
  player_id: string | null;
  points: number;
  contests: number;
  precision: number | null;
  achievements: Achievement[];
  history: {
    tournament_slug: string;
    name: string;
    rank: number;
    points: number;
    hits: number;
    picks: number;
  }[];
};

/** /prode/u/[id]: a forecaster's public profile. */
export function ProdeProfile({ id }: { id: string }) {
  const { data, status, loading, reload } = useLoad<Profile>(
    `prode/users/${id}`,
  );
  if (loading) return <p role="status">Cargando…</p>;
  if (status === 404) return <p>No existe ese pronosticador.</p>;
  if (!data)
    return (
      <div role="alert">
        <p>No se pudieron cargar los datos.</p>
        <button className="primary-button" onClick={reload}>
          Reintentar
        </button>
      </div>
    );
  return (
    <div className="competition-page prode-page">
      <p>
        <Link href="/prode">← Prode</Link>
      </p>
      <h1>{data.name}</h1>
      {data.player_id && (
        <p>
          <Link href={`/players/${data.player_id}`}>
            Ver su ficha de jugador →
          </Link>
        </p>
      )}
      <dl className="facts">
        <div>
          <dt>Puntos</dt>
          <dd>{data.points}</dd>
        </div>
        <div>
          <dt>Prodes jugados</dt>
          <dd>{data.contests}</dd>
        </div>
        <div>
          <dt>Precisión</dt>
          <dd>{data.precision === null ? "—" : `${data.precision}%`}</dd>
        </div>
      </dl>
      <h2>Logros</h2>
      {data.achievements.length ? (
        <AchievementList items={data.achievements} />
      ) : (
        <p className="seeding-lead">Todavía no ganó logros del Prode.</p>
      )}
      <h2>Historial</h2>
      {data.history.length === 0 ? (
        <p className="seeding-lead">
          Todavía no terminó ningún Prode que haya jugado.
        </p>
      ) : (
        <ul className="prode-contests">
          {data.history.map((h) => (
            <li key={h.tournament_slug}>
              <Link href={`/previa/${h.tournament_slug}#prode`}>{h.name}</Link>
              <span>{h.rank}.º</span>
              <small>
                {h.points} pts · {h.hits}/{h.picks} aciertos
              </small>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Player profile: Prode achievements of the start.gg account behind the player. */
export function PlayerProdeAchievements({ id }: { id: string }) {
  const { data } = useLoad<{
    user_id: string | null;
    achievements: Achievement[];
  }>(`prode/players/${id}/achievements`);
  if (!data?.achievements.length) return null;
  return (
    <section aria-labelledby="prode-badges-title">
      <h2 id="prode-badges-title">Logros del Prode</h2>
      <AchievementList items={data.achievements} />
      {data.user_id && (
        <p>
          <Link href={`/prode/u/${data.user_id}`}>
            Ver su perfil del Prode →
          </Link>
        </p>
      )}
    </section>
  );
}
