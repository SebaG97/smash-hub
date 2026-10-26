"use client";

import Link from "next/link";
import { Fragment, useCallback, useEffect, useState } from "react";
import type { SeedingRow, SeedingView } from "../lib/api";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");
const KEY_STORE = "seeding-admin";

const classLabels: Record<string, string> = {
  played: "Jugados",
  played_unscored: "Jugados sin puntaje",
  bye: "Pase libre (BYE)",
  dq: "Descalificación",
  not_played: "No disputados",
  placeholder: "Pendientes",
  no_valid_winner: "Sin ganador válido",
  inconsistent_score: "Puntaje inconsistente",
  excluded_test_event: "Evento de prueba",
};
const actionLabels: Record<string, string> = {
  sets: "Descargando sets",
  inscritos: "Descargando inscritos",
};

function day(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      })
    : "—";
}
function moment(value: string | null) {
  return value
    ? new Date(value).toLocaleString("es-PY", {
        timeZone: "America/Asuncion",
        dateStyle: "short",
        timeStyle: "short",
      })
    : "—";
}
function inputDate(value: string) {
  return new Date(value).toLocaleDateString("en-CA", {
    timeZone: "America/Asuncion",
  });
}
// Dates typed in the page are Asunción calendar days (UTC−3, no DST since 2024).
function fromInput(value: string) {
  return `${value}T00:00:00-03:00`;
}
function num(value: number | null, digits = 0) {
  return value === null
    ? "—"
    : value.toLocaleString("es-PY", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
}

type Admin = { key: string; name: string };

function readAdmin(): Admin | null {
  try {
    const raw = sessionStorage.getItem(KEY_STORE);
    return raw ? (JSON.parse(raw) as Admin) : null;
  } catch {
    return null;
  }
}

async function send(
  admin: Admin,
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  return fetch(`${api}/seeding/${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${admin.key}`,
      "X-Admin-Name": admin.name,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

async function problem(r: Response) {
  try {
    const body = (await r.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* non-JSON error */
  }
  return `La API respondió ${r.status}.`;
}

function AdminLogin({
  slug,
  onLogin,
}: {
  slug: string;
  onLogin: (admin: Admin) => void;
}) {
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  return (
    <form
      className="seeding-admin"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        const admin = { key: key.trim(), name: name.trim() || "admin" };
        try {
          const r = await send(admin, "GET", `${slug}/session`);
          if (!r.ok) return setError(await problem(r));
          try {
            sessionStorage.setItem(KEY_STORE, JSON.stringify(admin));
          } catch {
            /* storage blocked: the key lives only in memory */
          }
          onLogin(admin);
        } catch {
          setError("No se pudo contactar a la API.");
        }
      }}
    >
      <strong>Modo organizador</strong>
      <label>
        Tu nombre
        <input
          value={name}
          maxLength={60}
          onChange={(e) => setName(e.target.value)}
          placeholder="Para el registro de cambios"
        />
      </label>
      <label>
        Clave de administración
        <input
          type="password"
          value={key}
          autoComplete="current-password"
          onChange={(e) => setKey(e.target.value)}
          required
        />
      </label>
      <button className="primary-button" type="submit">
        Entrar
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}

function Recalculate({
  view,
  admin,
  onDone,
}: {
  view: SeedingView;
  admin: Admin;
  onDone: (message: string) => void;
}) {
  const [from, setFrom] = useState(
    inputDate(view.run?.window_start || view.window_start),
  );
  const [to, setTo] = useState(
    inputDate(view.run?.window_end || view.event_date),
  );
  const [refresh, setRefresh] = useState(false);
  const [busy, setBusy] = useState(false);
  const running = view.refresh.status === "RUNNING";
  return (
    <form
      className="seeding-tools"
      onSubmit={async (e) => {
        e.preventDefault();
        if (
          refresh &&
          !window.confirm(
            "Se van a descargar de start.gg los sets de todos los inscritos. Tarda varios minutos y reemplaza los datos actuales. ¿Continuar?",
          )
        )
          return;
        setBusy(true);
        const r = await send(admin, "POST", `${view.slug}/recalculate`, {
          window_start: fromInput(from),
          window_end: refresh ? undefined : fromInput(to),
          refresh,
        }).catch(() => null);
        setBusy(false);
        if (!r) return onDone("No se pudo contactar a la API.");
        if (!r.ok) return onDone(await problem(r));
        onDone(
          r.status === 202
            ? "Descarga de start.gg iniciada. La tabla se actualiza sola al terminar."
            : "Seeding recalculado. Los ajustes manuales se conservaron.",
        );
      }}
    >
      <label>
        Desde
        <input
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          required
        />
      </label>
      <label>
        Hasta (exclusivo)
        <input
          type="date"
          value={to}
          disabled={refresh}
          onChange={(e) => setTo(e.target.value)}
          required
        />
      </label>
      <label className="seeding-check">
        <input
          type="checkbox"
          checked={refresh}
          onChange={(e) => setRefresh(e.target.checked)}
        />
        Bajar datos nuevos de start.gg (5 a 10 minutos)
      </label>
      <button className="primary-button" disabled={busy || running}>
        {busy ? "Procesando…" : "Recalcular"}
      </button>
    </form>
  );
}

function MoveForm({
  row,
  total,
  onMove,
}: {
  row: SeedingRow;
  total: number;
  onMove: (seed: number, reason: string) => void;
}) {
  const [seed, setSeed] = useState(String(row.seed));
  const [reason, setReason] = useState(row.override?.reason || "");
  return (
    <form
      className="seeding-move"
      onSubmit={(e) => {
        e.preventDefault();
        onMove(Number(seed), reason.trim());
      }}
    >
      <label>
        Mover al seed
        <input
          type="number"
          min={1}
          max={total}
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          required
        />
      </label>
      <label>
        Motivo
        <input
          value={reason}
          minLength={3}
          maxLength={300}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Por qué se ajusta"
          required
        />
      </label>
      <button className="primary-button">Guardar</button>
    </form>
  );
}

function Details({ row }: { row: SeedingRow }) {
  return (
    <div className="seeding-details">
      <h4>¿Por qué está en el seed {row.seed}?</h4>
      <ul>
        {row.override && (
          <li>
            <strong>Ajuste manual</strong> de {row.override.actor} (el método lo
            dejaba {row.seed_algorithm}.º): {row.override.reason}
          </li>
        )}
        {row.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      {Object.keys(row.circuits || {}).length > 0 && (
        <p>
          Sets por circuito:{" "}
          {Object.entries(row.circuits)
            .map(([c, n]) => `${c} ${n}`)
            .join(" · ")}
        </p>
      )}
      {row.flags.length > 0 && <p>Alertas: {row.flags.join(" · ")}</p>}
    </div>
  );
}

function DataPanel({ view }: { view: SeedingView }) {
  const run = view.run;
  return (
    <section className="seeding-data" aria-label="Datos analizados">
      <h2>Datos analizados</h2>
      <dl>
        <div>
          <dt>Período</dt>
          <dd>
            {run
              ? `${day(run.window_start)} al ${day(run.window_end)} (exclusivo)`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>Datos de start.gg hasta</dt>
          <dd>{moment(view.data_cutoff)}</dd>
        </div>
        <div>
          <dt>Inscritos</dt>
          <dd>{view.dataset.entrants}</dd>
        </div>
        <div>
          <dt>Sets usados en el cálculo</dt>
          <dd>
            {run ? num(run.set_count) : "—"} de {num(view.dataset.sets)}{" "}
            descargados
          </dd>
        </div>
        <div>
          <dt>Eventos con sets usados</dt>
          <dd>
            {run
              ? `${run.event_count} (${run.offline_event_count} offline)`
              : "—"}
          </dd>
        </div>
        <div>
          <dt>Jugadores en el rating</dt>
          <dd>{run ? num(run.player_count) : "—"} (inscritos y rivales)</dd>
        </div>
        <div>
          <dt>Último cálculo</dt>
          <dd>{run ? `${moment(run.created_at)} · ${run.actor}` : "—"}</dd>
        </div>
      </dl>
      <details>
        <summary>Cómo se calcula y qué se excluye</summary>
        <ul>
          <li>
            Se analizan los sets de Ultimate Singles de cada inscrito en
            start.gg dentro del período. No se cuenta el propio evento.
          </li>
          <li>
            Solo cuentan los sets jugados con un ganador válido. Clasificación
            de los sets descargados:{" "}
            {Object.entries(view.dataset.classifications)
              .map(([c, n]) => `${classLabels[c] || c} ${num(n)}`)
              .join(" · ")}
            .
          </li>
          <li>
            <strong>Glicko-2</strong> (períodos semanales) mide la fuerza por
            enfrentamientos directos. Se usa el valor conservador, rating −
            {run?.parameters.conservative_k ?? 2}·RD, para que una muestra chica
            no quede arriba por suerte.
          </li>
          <li>
            <strong>Posiciones</strong>: promedio de los{" "}
            {run?.parameters.placement_top_events ?? 3} mejores eventos offline
            de ≥{run?.parameters.placement_min_field ?? 8} inscritos, medido en
            rondas superadas (log2 inscritos/posición). Permite comparar
            circuitos que no juegan entre sí.
          </li>
          <li>
            El seed del método promedia los dos puestos (
            {num((run?.parameters.rating_weight ?? 0.5) * 100)} % rating). Los
            jugadores sin sets van al final en orden alfabético.
          </li>
        </ul>
        {view.merges.length > 0 && (
          <p>
            IDs fusionados:{" "}
            {view.merges
              .map((m) => `${m.from_player_id} → ${m.tag || m.to_player_id}`)
              .join(" · ")}
          </p>
        )}
        {view.duplicates.length > 0 && (
          <p>
            Inscripciones duplicadas omitidas:{" "}
            {view.duplicates
              .map(
                (d) =>
                  `${d.player_id} (se conserva ${d.tag || d.kept_player_id})`,
              )
              .join(" · ")}
          </p>
        )}
      </details>
    </section>
  );
}

export function SeedingBoard({ slug }: { slug: string }) {
  const [view, setView] = useState<SeedingView | null>(null);
  const [error, setError] = useState("");
  // The first render is always the loading state, so reading storage here cannot
  // cause a hydration mismatch.
  const [admin, setAdmin] = useState<Admin | null>(() =>
    typeof window === "undefined" ? null : readAdmin(),
  );
  const [open, setOpen] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let active = true;
    fetch(`${api}/seeding/${encodeURIComponent(slug)}`)
      .then(async (r) => {
        if (!r.ok)
          throw new Error(
            r.status === 404 ? "No existe este seeding." : "No se pudo cargar.",
          );
        const data = (await r.json()) as SeedingView;
        if (active) {
          setView(data);
          setError("");
        }
      })
      .catch((e: unknown) => {
        if (active)
          setError(e instanceof Error ? e.message : "No se pudo cargar.");
      });
    return () => {
      active = false;
    };
  }, [slug, version]);

  const running = view?.refresh.status === "RUNNING";
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [running, load]);

  async function act(method: string, path: string, body?: unknown) {
    if (!admin) return;
    const r = await send(admin, method, path, body).catch(() => null);
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (r.status === 401) {
      setAdmin(null);
      try {
        sessionStorage.removeItem(KEY_STORE);
      } catch {
        /* ignore */
      }
    }
    if (!r.ok) return setMessage(await problem(r));
    setMessage("");
    load();
  }

  if (error)
    return (
      <div role="alert" className="competition-page">
        <p>{error}</p>
        <Link className="primary-button" href="/seeding">
          Volver
        </Link>
      </div>
    );
  if (!view)
    return (
      <p role="status" className="competition-page">
        Cargando seeding…
      </p>
    );

  const total = view.seeds.length;
  const manual = view.seeds.filter((s) => s.override).length;
  return (
    <div className="competition-page seeding-page">
      <p className="eyebrow">SEEDING · PROPUESTA PARA LA ORGANIZACIÓN</p>
      <h1>{view.name}</h1>
      <p className="seeding-lead">
        Evento el {day(view.event_date)} · {total} jugadores · {manual}{" "}
        {manual === 1 ? "ajuste manual" : "ajustes manuales"}
        {view.startgg_event_slug && (
          <>
            {" · "}
            <a
              href={`https://www.start.gg/${view.startgg_event_slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Ver en start.gg ↗
            </a>
          </>
        )}
      </p>

      <div className="seeding-actions">
        <a
          className="primary-button"
          href={`${api}/seeding/${encodeURIComponent(slug)}/export.csv`}
        >
          Exportar CSV
        </a>
        <details className="seeding-push">
          <summary>Subir a start.gg</summary>
          <p>
            Por seguridad, la API no escribe en start.gg. Con la clave de la
            cuenta organizadora, desde la carpeta del proyecto:
          </p>
          <pre>
            {`docker compose run --rm api python -m app.cli.seeding push --slug ${view.slug}`}
          </pre>
          <p>
            Eso solo simula y muestra el resultado. Para escribir, repetirlo con{" "}
            <code>--confirm</code>. El token de start.gg tiene que ser de un
            administrador del torneo.
          </p>
        </details>
      </div>

      {running && (
        <p role="status" className="seeding-banner">
          {actionLabels[view.refresh.progress?.step || ""] || "Procesando"}
          {view.refresh.progress?.total
            ? `: ${view.refresh.progress.done} de ${view.refresh.progress.total} jugadores`
            : "…"}
        </p>
      )}
      {view.refresh.status === "FAILED" && (
        <p role="alert" className="seeding-banner">
          La última descarga de start.gg falló ({view.refresh.error}). Los datos
          anteriores siguen vigentes.
        </p>
      )}

      {admin ? (
        <section className="seeding-admin" aria-label="Herramientas">
          <p>
            Editando como <strong>{admin.name}</strong>.{" "}
            <button
              className="link-button"
              onClick={() => {
                setAdmin(null);
                try {
                  sessionStorage.removeItem(KEY_STORE);
                } catch {
                  /* ignore */
                }
              }}
            >
              Salir
            </button>
          </p>
          <Recalculate
            view={view}
            admin={admin}
            onDone={(text) => {
              setMessage(text);
              load();
            }}
          />
        </section>
      ) : (
        <AdminLogin slug={slug} onLogin={setAdmin} />
      )}
      {message && (
        <p role="status" className="seeding-banner">
          {message}
        </p>
      )}

      <DataPanel view={view} />

      <section aria-label="Seeds" className="data-section">
        <h2>Seeds</h2>
        <div className="seeding-table-wrap">
          <table className="seeding-table">
            <thead>
              <tr>
                <th scope="col">Seed</th>
                <th scope="col">Jugador</th>
                <th scope="col">Circuito</th>
                <th scope="col">Rating ± RD</th>
                <th scope="col">Posiciones</th>
                <th scope="col">W-L</th>
                <th scope="col">Confianza</th>
                <th scope="col">Alertas</th>
                {admin && <th scope="col">Mover</th>}
              </tr>
            </thead>
            <tbody>
              {view.seeds.map((row) => (
                <Fragment key={row.player_id}>
                  <tr className={row.override ? "is-manual" : undefined}>
                    <td>
                      <strong>{row.seed}</strong>
                      {row.seed !== row.seed_algorithm && (
                        <small> (método {row.seed_algorithm})</small>
                      )}
                    </td>
                    <td>
                      <button
                        className="link-button"
                        aria-expanded={open === row.player_id}
                        onClick={() =>
                          setOpen(open === row.player_id ? null : row.player_id)
                        }
                      >
                        {row.gamer_tag}
                      </button>
                      {row.override && <span className="tag">manual</span>}
                    </td>
                    <td>{row.main_circuit || "—"}</td>
                    <td>
                      {row.rating === null
                        ? "—"
                        : `${num(row.rating)} ± ${num(row.rd)}`}
                    </td>
                    <td>{num(row.placement_score, 2)}</td>
                    <td>
                      {row.wins}-{row.losses}
                    </td>
                    <td>{row.confidence}</td>
                    <td className="seeding-flags">{row.flags.join(" · ")}</td>
                    {admin && (
                      <td className="seeding-arrows">
                        <button
                          aria-label={`Subir a ${row.gamer_tag}`}
                          disabled={row.seed === 1}
                          onClick={() =>
                            act("PUT", `${slug}/overrides/${row.player_id}`, {
                              seed: row.seed - 1,
                              reason:
                                row.override?.reason ||
                                "Ajuste manual desde la página",
                            })
                          }
                        >
                          ↑
                        </button>
                        <button
                          aria-label={`Bajar a ${row.gamer_tag}`}
                          disabled={row.seed === total}
                          onClick={() =>
                            act("PUT", `${slug}/overrides/${row.player_id}`, {
                              seed: row.seed + 1,
                              reason:
                                row.override?.reason ||
                                "Ajuste manual desde la página",
                            })
                          }
                        >
                          ↓
                        </button>
                      </td>
                    )}
                  </tr>
                  {open === row.player_id && (
                    <tr className="seeding-open">
                      <td colSpan={admin ? 9 : 8}>
                        <Details row={row} />
                        {admin && (
                          <div className="seeding-edit">
                            <MoveForm
                              row={row}
                              total={total}
                              onMove={(seed, reason) =>
                                act(
                                  "PUT",
                                  `${slug}/overrides/${row.player_id}`,
                                  {
                                    seed,
                                    reason,
                                  },
                                )
                              }
                            />
                            {row.override && (
                              <button
                                className="link-button"
                                onClick={() =>
                                  act(
                                    "DELETE",
                                    `${slug}/overrides/${row.player_id}`,
                                  )
                                }
                              >
                                Quitar ajuste manual (volver al{" "}
                                {row.seed_algorithm}.º del método)
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export function SeedingList() {
  const [items, setItems] = useState<
    { slug: string; name: string; event_date: string }[] | null
  >(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    fetch(`${api}/seeding`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then(setItems)
      .catch(() => setError(true));
  }, []);
  return (
    <div className="competition-page">
      <p className="eyebrow">ORGANIZACIÓN DE EVENTOS</p>
      <h1>Seeding</h1>
      {error && <p role="alert">No se pudieron cargar los seedings.</p>}
      {!items && !error && <p role="status">Cargando…</p>}
      {items && items.length === 0 && (
        <p>Todavía no hay seedings. Se crean con el comando de seeding.</p>
      )}
      <div className="data-grid">
        {items?.map((p) => (
          <article className="data-card" key={p.slug}>
            <h3>
              <Link href={`/seeding/${p.slug}`}>{p.name} ↗</Link>
            </h3>
            <p>Evento el {day(p.event_date)}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
