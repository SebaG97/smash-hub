"use client";

import Link from "next/link";
import type React from "react";
import { useRouter } from "next/navigation";
import { MainIcons, WinBar, mainColor } from "./mains";
import { ShareImage } from "./share-image";
import { TournamentLogo, type TournamentImages } from "./tournament-art";
import {
  adminHeaders,
  clearAdmin,
  saveAdmin,
  useAdmin,
  type Admin,
} from "../lib/admin";
import { Fragment, useCallback, useEffect, useState } from "react";
import type {
  PublicSeedingView,
  SeedingProjectSummary,
  SeedingRow,
  SeedingView,
} from "../lib/api";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

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
  sets: "Descargando sets de los inscritos",
  inscritos: "Descargando inscritos",
  torneos: "Descargando torneos",
  personajes: "Bajando los personajes de cada jugador",
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

async function send(
  admin: Admin,
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  return fetch(`${api}/seeding${path ? `/${path}` : ""}`, {
    method,
    headers: {
      Authorization: `Bearer ${admin.key}`,
      "X-Admin-Name": admin.name,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function problem(r: Response) {
  try {
    const body = (await r.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* non-JSON error */
  }
  return `La API respondió ${r.status}.`;
}

export function AdminLogin({ onLogin }: { onLogin?: (admin: Admin) => void }) {
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
          const r = await send(admin, "GET", "session");
          if (!r.ok) return setError(await problem(r));
          saveAdmin(admin);
          onLogin?.(admin);
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
  const [resetMoves, setResetMoves] = useState(false);
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
            view.kind === "ranking"
              ? "Se van a descargar de start.gg todos los torneos presenciales del período. Tarda varios minutos y reemplaza los datos actuales. ¿Continuar?"
              : "Se van a descargar de start.gg los sets de todos los inscritos. Tarda varios minutos y reemplaza los datos actuales. ¿Continuar?",
          )
        )
          return;
        setBusy(true);
        const r = await send(admin, "POST", `${view.slug}/recalculate`, {
          window_start: fromInput(from),
          window_end: refresh ? undefined : fromInput(to),
          refresh,
          reset_overrides: resetMoves || undefined,
        }).catch(() => null);
        setBusy(false);
        if (!r) return onDone("No se pudo contactar a la API.");
        if (!r.ok) return onDone(await problem(r));
        onDone(
          r.status === 202
            ? "Descarga de start.gg iniciada. La tabla se actualiza sola al terminar."
            : view.kind === "ranking"
              ? "Ranking recalculado."
              : resetMoves
                ? "Seeding recalculado sin ajustes manuales."
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
      {view.kind === "seeding" && (
        <label className="seeding-check">
          <input
            type="checkbox"
            checked={resetMoves}
            onChange={(e) => setResetMoves(e.target.checked)}
          />
          Quitar los ajustes manuales (todos vuelven al puesto del cálculo)
        </label>
      )}
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

function scoreText(row: SeedingRow, method: string) {
  const score = row.scores?.[method] ?? null;
  if (score === null) return "—";
  if (method === "combined") return num(score, 3);
  if (method === "points") return num(score, 1);
  if (method === "wilson") return `${num(score, 1)} %`;
  return num(score);
}

function Details({ row, method }: { row: SeedingRow; method: string }) {
  const reasons = row.reasons_by_method?.[method] || row.reasons;
  const place = row.ranks?.[method];
  return (
    <div className="seeding-details">
      <h4>
        {place
          ? `¿Por qué queda ${place}.º con este método?`
          : "¿Por qué está en este puesto?"}
      </h4>
      <ul>
        {row.override && (
          <li>
            <strong>Ajuste manual</strong> de {row.override.actor} (el método lo
            dejaba {row.seed_algorithm}.º): {row.override.reason}
          </li>
        )}
        {reasons.map((reason) => (
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
  const ranking = view.kind === "ranking";
  return (
    <section className="seeding-data" aria-label="Datos analizados">
      <h2>Datos analizados</h2>
      <dl>
        <div>
          <dt>Período</dt>
          <dd>
            {run
              ? `${day(run.window_start)} al ${day(run.window_end)} (exclusivo)`
              : `${day(view.window_start)} al ${day(view.event_date)}`}
          </dd>
        </div>
        <div>
          <dt>Datos de start.gg hasta</dt>
          <dd>{moment(view.data_cutoff)}</dd>
        </div>
        <div>
          <dt>{ranking ? "Jugadores con sets" : "Inscritos"}</dt>
          <dd>{num(view.dataset.entrants)}</dd>
        </div>
        <div>
          <dt>Sets usados en el cálculo</dt>
          <dd>
            {run ? num(run.set_count) : "—"} de {num(view.dataset.sets)}{" "}
            descargados
          </dd>
        </div>
        <div>
          <dt>{ranking ? "Torneos" : "Eventos con sets usados"}</dt>
          <dd>
            {run
              ? ranking
                ? `${run.event_count} presenciales`
                : `${run.event_count} (${run.offline_event_count} offline)`
              : "—"}
          </dd>
        </div>
        {!ranking && (
          <div>
            <dt>Jugadores en el rating</dt>
            <dd>{run ? num(run.player_count) : "—"} (inscritos y rivales)</dd>
          </div>
        )}
        <div>
          <dt>Último cálculo</dt>
          <dd>{run ? `${moment(run.created_at)} · ${run.actor}` : "—"}</dd>
        </div>
      </dl>
      <details>
        <summary>Cómo se calcula y qué se excluye</summary>
        <ul>
          <li>
            {ranking
              ? `Se analizan todos los sets de Ultimate Singles de los torneos presenciales jugados en ${view.country_code === "PY" ? "Paraguay" : view.country_code} dentro del período.`
              : "Se analizan los sets de Ultimate Singles de cada inscrito en start.gg dentro del período. No se cuenta el propio evento."}
          </li>
          <li>
            Solo cuentan los sets jugados con un ganador válido. Clasificación
            de los sets descargados:{" "}
            {Object.entries(view.dataset.classifications)
              .map(([c, n]) => `${classLabels[c] || c} ${num(n)}`)
              .join(" · ")}
            .
          </li>
          {ranking && (view.excluded_tournaments?.length ?? 0) > 0 && (
            <li>
              Torneos desmarcados en «Torneos» que no cuentan:{" "}
              {view.excluded_tournaments!.join(" · ")}.
            </li>
          )}
          {ranking && (run?.parameters.min_sets ?? 0) > 0 && (
            <li>
              Para entrar al ranking hacen falta al menos{" "}
              {run?.parameters.min_sets} sets en el período.
            </li>
          )}
          {view.methods.map((m) => (
            <li key={m.id}>
              <strong>{m.label}</strong>
              {m.id === view.method ? " (método oficial)" : ""}: {m.description}
            </li>
          ))}
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

function MethodPicker({
  view,
  value,
  onChange,
  admin,
  onAdopt,
}: {
  view: SeedingView;
  value: string;
  onChange: (method: string) => void;
  admin: Admin | null;
  onAdopt: (method: string) => void;
}) {
  const selected = view.methods.find((m) => m.id === value);
  const official = view.methods.find((m) => m.id === view.method);
  const preview = value !== view.method;
  return (
    <section className="seeding-methods" aria-label="Método de cálculo">
      <label>
        Ver con el método
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {view.methods.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
              {m.id === view.method ? " · oficial" : ""}
            </option>
          ))}
        </select>
      </label>
      {selected && <p>{selected.description}</p>}
      {preview && (
        <p className="seeding-preview">
          <strong>Vista previa:</strong> así quedaría el orden con{" "}
          {selected?.label}. El orden oficial sigue siendo {official?.label}
          {view.kind === "seeding" ? ", con sus ajustes manuales" : ""}.{" "}
          {admin && (
            <button
              className="primary-button"
              onClick={() => onAdopt(value)}
              type="button"
            >
              Usar como método oficial
            </button>
          )}
        </p>
      )}
    </section>
  );
}

function IdentityPanel({
  view,
  act,
}: {
  view: SeedingView;
  act: (method: string, path: string, body?: unknown) => Promise<boolean>;
}) {
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [dupe, setDupe] = useState("");
  const [keep, setKeep] = useState("");
  const players = [...view.seeds].sort((a, b) =>
    a.gamer_tag.localeCompare(b.gamer_tag),
  );
  const seeding = view.kind === "seeding";
  const candidates = view.merge_candidates || [];
  return (
    <section className="seeding-identities" aria-label="Identidades">
      <h2>Identidades</h2>
      <p className="seeding-lead">
        Une IDs de start.gg que son la misma persona (por ejemplo, inscripciones
        sin cuenta). Nunca se fusiona solo: cada cambio queda en el registro y
        el cálculo se rehace al instante.
      </p>
      {candidates.length > 0 && (
        <>
          <h3>Posibles IDs de la misma persona</h3>
          <ul className="seeding-candidates">
            {candidates.map((c) => (
              <li key={`${c.source}-${c.target}`}>
                <span>
                  ID {c.source} («{c.source_tag}», {c.counted_sets} sets
                  contados) → <strong>{c.target_tag}</strong> ({c.target})
                </span>
                <button
                  className="link-button"
                  onClick={() =>
                    act("PUT", `${view.slug}/merges`, {
                      from_player_id: c.source,
                      to_player_id: c.target,
                    })
                  }
                >
                  Fusionar
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <form
        className="seeding-move"
        onSubmit={async (e) => {
          e.preventDefault();
          if (
            await act("PUT", `${view.slug}/merges`, {
              from_player_id: source.trim(),
              to_player_id: target,
            })
          )
            setSource("");
        }}
      >
        <label>
          ID de start.gg a fusionar
          <input
            value={source}
            inputMode="numeric"
            pattern="[0-9]{1,20}"
            onChange={(e) => setSource(e.target.value)}
            placeholder="Ej. 5363782"
            required
          />
        </label>
        <label>
          Es el jugador
          <select
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            required
          >
            <option value="">Elegir…</option>
            {players.map((p) => (
              <option key={p.player_id} value={p.player_id}>
                {p.gamer_tag} ({p.player_id})
              </option>
            ))}
          </select>
        </label>
        <button className="primary-button">Fusionar</button>
      </form>
      {view.merges.length > 0 && (
        <ul className="seeding-candidates">
          {view.merges.map((m) => (
            <li key={m.from_player_id}>
              <span>
                ID {m.from_player_id} → {m.tag || m.to_player_id}
              </span>
              <button
                className="link-button"
                onClick={() =>
                  act("DELETE", `${view.slug}/merges/${m.from_player_id}`)
                }
              >
                Deshacer
              </button>
            </li>
          ))}
        </ul>
      )}
      {seeding && (
        <>
          <h3>Inscripciones duplicadas</h3>
          <form
            className="seeding-move"
            onSubmit={async (e) => {
              e.preventDefault();
              if (
                await act("PUT", `${view.slug}/duplicates`, {
                  player_id: dupe,
                  keep_player_id: keep,
                })
              )
                setDupe("");
            }}
          >
            <label>
              Inscripción duplicada
              <select
                value={dupe}
                onChange={(e) => setDupe(e.target.value)}
                required
              >
                <option value="">Elegir…</option>
                {players.map((p) => (
                  <option key={p.player_id} value={p.player_id}>
                    {p.gamer_tag} ({p.player_id})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Se conserva
              <select
                value={keep}
                onChange={(e) => setKeep(e.target.value)}
                required
              >
                <option value="">Elegir…</option>
                {players.map((p) => (
                  <option key={p.player_id} value={p.player_id}>
                    {p.gamer_tag} ({p.player_id})
                  </option>
                ))}
              </select>
            </label>
            <button className="primary-button">Marcar duplicada</button>
          </form>
          {view.duplicates.length > 0 && (
            <ul className="seeding-candidates">
              {view.duplicates.map((d) => (
                <li key={d.player_id}>
                  <span>
                    {d.player_id} omitida (se conserva{" "}
                    {d.tag || d.kept_player_id})
                  </span>
                  <button
                    className="link-button"
                    onClick={() =>
                      act("DELETE", `${view.slug}/duplicates/${d.player_id}`)
                    }
                  >
                    Deshacer
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

function PublicBoard({ view }: { view: PublicSeedingView }) {
  const [open, setOpen] = useState<number | null>(null);
  const ranking = view.kind === "ranking";
  return (
    <div className="competition-page seeding-page">
      <Link className="back-link" href={ranking ? "/rankings" : "/seeding"}>
        ← {ranking ? "Rankings" : "Seeding"}
      </Link>
      <h1>{view.name}</h1>
      <p className="seeding-lead">
        {ranking
          ? `${view.seeds.length} jugadores, del ${day(view.run?.window_start || view.window_start)} al ${day(view.run?.window_end || view.event_date)}. Método: ${view.method_label}.`
          : `${view.seeds.length} jugadores. Evento el ${day(view.event_date)}.`}
        {view.data_cutoff &&
          ` Resultados de start.gg hasta el ${day(view.data_cutoff)}.`}
        {view.startgg_event_slug && (
          <>
            {" "}
            <a
              href={`https://www.start.gg/${view.startgg_event_slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Ver el evento en start.gg
            </a>
          </>
        )}
      </p>
      <ShareImage
        endpoint={`/og/${ranking ? "ranking" : "seeding"}/${view.slug}`}
        filename={`${view.slug}.png`}
        label="Descargar imagen para redes"
        rows={view.seeds.map((s) => ({
          place: s.seed,
          tag: s.gamer_tag,
          mains: s.mains,
        }))}
      />
      {ranking && (view.run?.parameters.min_sets ?? 0) > 0 && (
        <p className="seeding-lead">
          Entran los jugadores con al menos {view.run?.parameters.min_sets} sets
          en el período, en {view.run?.event_count} torneos presenciales.
        </p>
      )}
      <section
        aria-label={ranking ? "Ranking" : "Seeds"}
        className="data-section"
      >
        <div className="seeding-table-wrap">
          <table className="seeding-table">
            <thead>
              <tr>
                <th scope="col">{ranking ? "Puesto" : "Seed"}</th>
                <th scope="col">Jugador</th>
                {ranking && <th scope="col">Puntaje</th>}
                {ranking && <th scope="col">W-L</th>}
              </tr>
            </thead>
            <tbody>
              {view.seeds.map((row) => (
                <Fragment key={row.seed}>
                  <tr
                    data-place={row.seed}
                    style={
                      mainColor(row.mains)
                        ? ({
                            "--main": mainColor(row.mains),
                          } as React.CSSProperties)
                        : undefined
                    }
                  >
                    <td>
                      <strong>{row.seed}</strong>
                    </td>
                    <td>
                      {ranking ? (
                        <button
                          className="link-button"
                          aria-expanded={open === row.seed}
                          onClick={() =>
                            setOpen(open === row.seed ? null : row.seed)
                          }
                        >
                          {row.gamer_tag}
                        </button>
                      ) : (
                        row.gamer_tag
                      )}{" "}
                      <MainIcons mains={row.mains} size={26} />
                    </td>
                    {ranking && (
                      <td>
                        {row.score === null || row.score === undefined
                          ? "—"
                          : num(row.score, view.method === "combined" ? 3 : 0)}
                      </td>
                    )}
                    {ranking && (
                      <td>
                        <WinBar wins={row.wins} losses={row.losses} />
                      </td>
                    )}
                  </tr>
                  {ranking && open === row.seed && row.reasons && (
                    <tr className="seeding-open">
                      <td colSpan={4}>
                        <div className="seeding-details">
                          <h4>¿Por qué queda {row.seed}.º?</h4>
                          <ul>
                            {row.reasons.map((reason) => (
                              <li key={reason}>{reason}</li>
                            ))}
                          </ul>
                        </div>
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

export function SeedingBoard({
  slug,
  base = "seeding",
}: {
  slug: string;
  base?: "seeding" | "rankings";
}) {
  const [view, setView] = useState<SeedingView | PublicSeedingView | null>(
    null,
  );
  const [error, setError] = useState("");
  const admin = useAdmin();
  const [open, setOpen] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const [version, setVersion] = useState(0);
  const load = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let active = true;
    fetch(`${api}/seeding/${encodeURIComponent(slug)}`, {
      headers: adminHeaders(admin),
    })
      .then(async (r) => {
        if (r.status === 401) clearAdmin();
        if (!r.ok)
          throw new Error(
            r.status === 404 ? "No existe esta página." : "No se pudo cargar.",
          );
        const data = (await r.json()) as SeedingView | PublicSeedingView;
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
  }, [slug, version, admin]);

  const running = !!view && !view.public && view.refresh.status === "RUNNING";
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(load, 4000);
    return () => clearInterval(timer);
  }, [running, load]);

  async function act(method: string, path: string, body?: unknown) {
    if (!admin) return false;
    const r = await send(admin, method, path, body).catch(() => null);
    if (!r) {
      setMessage("No se pudo contactar a la API.");
      return false;
    }
    if (r.status === 401) clearAdmin();
    if (!r.ok) {
      setMessage(await problem(r));
      return false;
    }
    setMessage("");
    load();
    return true;
  }

  if (error)
    return (
      <div role="alert" className="competition-page">
        <p>{error}</p>
        <Link className="primary-button" href={`/${base}`}>
          Volver
        </Link>
      </div>
    );
  if (!view)
    return (
      <p role="status" className="competition-page">
        Cargando…
      </p>
    );
  if (view.public) return <PublicBoard view={view} />;

  async function exportCsv() {
    const r = await fetch(
      `${api}/seeding/${encodeURIComponent(slug)}/export.csv`,
      { headers: adminHeaders(admin) },
    ).catch(() => null);
    if (!r || !r.ok) return setMessage("No se pudo exportar.");
    const url = URL.createObjectURL(await r.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slug}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const ranking = view.kind === "ranking";
  const official = view.method || "combined";
  const method = preview || official;
  const previewing = method !== official;
  const canMove = !ranking && !!admin && !previewing;
  let rows = view.seeds;
  if (previewing)
    rows = [...rows].sort(
      (a, b) =>
        (a.ranks?.[method] ?? Infinity) - (b.ranks?.[method] ?? Infinity) ||
        b.sets - a.sets,
    );
  const hidden = ranking && !showAll ? rows.filter((r) => !r.eligible) : [];
  if (hidden.length) rows = rows.filter((r) => r.eligible);
  const total = view.seeds.length;
  const manual = view.seeds.filter((s) => s.override).length;
  const methodLabel =
    view.methods.find((m) => m.id === method)?.label || method;
  const columns = canMove ? 9 : 8;
  return (
    <div className="competition-page seeding-page">
      <p className="eyebrow">
        {view.published
          ? "Publicado: lo ve cualquier visitante."
          : "Borrador: solo lo ven los organizadores."}
      </p>
      <h1>{view.name}</h1>
      <p className="seeding-lead">
        {ranking ? (
          <>
            Período del {day(view.window_start)} al {day(view.event_date)} ·{" "}
            {num(view.seeds.filter((s) => s.eligible).length)} jugadores en el
            ranking
          </>
        ) : (
          <>
            Evento el {day(view.event_date)} · {total} jugadores · {manual}{" "}
            {manual === 1 ? "ajuste manual" : "ajustes manuales"}
          </>
        )}
        {view.startgg_event_slug && (
          <>
            {" · "}
            <a
              href={`https://www.start.gg/${view.startgg_event_slug}`}
              target="_blank"
              rel="noreferrer"
            >
              Ver en start.gg
            </a>
          </>
        )}
      </p>

      <div className="seeding-actions">
        <button className="primary-button" onClick={exportCsv}>
          Exportar CSV
        </button>
        <button
          className="primary-button"
          onClick={async () => {
            if (
              await act("PUT", `${slug}/publish`, {
                published: !view.published,
              })
            )
              setMessage(
                view.published
                  ? "Ya no es visible para el público."
                  : "Publicado: el público ya puede verlo.",
              );
          }}
        >
          {view.published ? "Despublicar" : "Publicar"}
        </button>
      </div>

      {running && (
        <p role="status" className="seeding-banner">
          {actionLabels[view.refresh.progress?.step || ""] || "Procesando"}
          {view.refresh.progress?.total
            ? `: ${view.refresh.progress.done} de ${view.refresh.progress.total}`
            : "…"}
        </p>
      )}
      {view.refresh.status === "FAILED" && (
        <p role="alert" className="seeding-banner">
          La última descarga de start.gg falló ({view.refresh.error}). Los datos
          anteriores siguen vigentes.
        </p>
      )}

      {admin && (
        <section className="seeding-admin" aria-label="Herramientas">
          <p>
            Editando como <strong>{admin.name}</strong>.
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
      )}
      {message && (
        <p role="status" className="seeding-banner">
          {message}
        </p>
      )}

      {view.methods?.length > 0 && view.run && (
        <MethodPicker
          view={view}
          value={method}
          onChange={(m) => setPreview(m === official ? null : m)}
          admin={admin}
          onAdopt={async (m) => {
            if (
              await act("POST", `${slug}/recalculate`, {
                method: m,
              })
            ) {
              setPreview(null);
              setMessage(
                `${view.methods.find((x) => x.id === m)?.label} es ahora el método oficial.`,
              );
            }
          }}
        />
      )}

      <DataPanel view={view} />
      {admin && view.dataset.entrants > 0 && (
        <IdentityPanel view={view} act={act} />
      )}

      <section
        aria-label={ranking ? "Ranking" : "Seeds"}
        className="data-section"
      >
        <h2>{ranking ? "Ranking" : "Seeds"}</h2>
        <div className="seeding-table-wrap">
          <table className="seeding-table">
            <thead>
              <tr>
                <th scope="col">{ranking ? "Puesto" : "Seed"}</th>
                <th scope="col">Jugador</th>
                <th scope="col">Circuito</th>
                <th scope="col">{methodLabel}</th>
                <th scope="col">Glicko-2 ± RD</th>
                <th scope="col">W-L</th>
                <th scope="col">Confianza</th>
                <th scope="col">Alertas</th>
                {canMove && <th scope="col">Mover</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const place = previewing
                  ? (row.ranks?.[method] ?? null)
                  : ranking
                    ? index + 1
                    : row.seed;
                return (
                  <Fragment key={row.player_id}>
                    <tr
                      className={row.override ? "is-manual" : undefined}
                      data-place={place ?? undefined}
                    >
                      <td>
                        <strong>{place ?? "—"}</strong>
                        {previewing && !ranking && (
                          <small> (oficial {row.seed})</small>
                        )}
                        {!previewing && row.seed !== row.seed_algorithm && (
                          <small> (método {row.seed_algorithm})</small>
                        )}
                      </td>
                      <td>
                        <button
                          className="link-button"
                          aria-expanded={open === row.player_id}
                          onClick={() =>
                            setOpen(
                              open === row.player_id ? null : row.player_id,
                            )
                          }
                        >
                          {row.gamer_tag}
                        </button>{" "}
                        <MainIcons mains={row.mains} size={20} />
                        {row.override && <span className="tag">manual</span>}
                      </td>
                      <td>{row.main_circuit || "—"}</td>
                      <td>{scoreText(row, method)}</td>
                      <td>
                        {row.rating === null
                          ? "—"
                          : `${num(row.rating)} ± ${num(row.rd)}`}
                      </td>
                      <td>
                        {row.wins}-{row.losses}
                      </td>
                      <td>{row.confidence}</td>
                      <td className="seeding-flags">{row.flags.join(" · ")}</td>
                      {canMove && (
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
                        <td colSpan={columns}>
                          <Details row={row} method={method} />
                          {canMove && (
                            <div className="seeding-edit">
                              <MoveForm
                                row={row}
                                total={total}
                                onMove={(seed, reason) =>
                                  act(
                                    "PUT",
                                    `${slug}/overrides/${row.player_id}`,
                                    { seed, reason },
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
                );
              })}
            </tbody>
          </table>
        </div>
        {ranking && (hidden.length > 0 || showAll) && (
          <p className="seeding-lead">
            <button
              className="link-button"
              onClick={() => setShowAll(!showAll)}
            >
              {showAll
                ? "Ocultar jugadores con pocos sets"
                : `Mostrar ${hidden.length} jugadores con menos de ${view.run?.parameters.min_sets ?? 0} sets`}
            </button>
          </p>
        )}
      </section>
    </div>
  );
}

function localDay(offsetDays: number) {
  return new Date(Date.now() + offsetDays * 86400000).toLocaleDateString(
    "en-CA",
    { timeZone: "America/Asuncion" },
  );
}

type UpcomingEvent = {
  name: string;
  url: string;
  images?: TournamentImages;
  starts_at: string | null;
  city: string | null;
  event: {
    name: string;
    slug: string;
    url: string;
    entrants: number | null;
  } | null;
};

/** Upcoming tournaments from start.gg, to start their seeding in one click. */
function UpcomingEvents({
  existing,
  onPick,
}: {
  existing: SeedingProjectSummary[];
  onPick: (t: UpcomingEvent) => void;
}) {
  const [items, setItems] = useState<UpcomingEvent[] | null>(null);
  useEffect(() => {
    fetch(`${api}/insights/calendar`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then((d: { items: UpcomingEvent[] }) =>
        setItems(d.items.filter((t) => t.event)),
      )
      .catch(() => setItems([]));
  }, []);
  if (!items?.length) return null;
  const done = new Map(existing.map((p) => [p.startgg_event_slug, p.slug]));
  return (
    <section className="seeding-upcoming" aria-labelledby="upcoming-title">
      <h2 id="upcoming-title">Próximos torneos</h2>
      <ul>
        {items.map((t) => {
          const event = t.event!;
          const seeding = done.get(event.slug);
          return (
            <li key={event.slug}>
              <TournamentLogo images={t.images} size={44} />
              <span>
                <strong>{t.name}</strong>
                <small>
                  {[
                    t.starts_at && day(t.starts_at),
                    t.city,
                    event.entrants != null
                      ? `${event.entrants} inscritos`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </small>
              </span>
              <a href={event.url} target="_blank" rel="noreferrer">
                Ver en start.gg
              </a>
              {seeding ? (
                <Link href={`/seeding/${seeding}`}>Abrir su seeding</Link>
              ) : (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => onPick(t)}
                >
                  Usar este torneo
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function NewProjectForm({
  kind,
  admin,
  existing = [],
}: {
  kind: "seeding" | "ranking";
  admin: Admin;
  existing?: SeedingProjectSummary[];
}) {
  const router = useRouter();
  const ranking = kind === "ranking";
  const [name, setName] = useState("");
  const [eventUrl, setEventUrl] = useState("");
  const [country, setCountry] = useState("PY");
  // Defaults: the last 365 days, in Asunción calendar days.
  const [from, setFrom] = useState(() => localDay(-365));
  const [to, setTo] = useState(() => localDay(0));
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pick = (t: UpcomingEvent) => {
    setName(`${t.name} · ${t.event!.name}`.slice(0, 200));
    setEventUrl(t.event!.url);
    if (t.starts_at) {
      // Data up to the event day, starting a year before it (Asunción days).
      const date = new Date(t.starts_at).toLocaleDateString("en-CA", {
        timeZone: "America/Asuncion",
      });
      setTo(date);
      setFrom(
        new Date(Date.parse(`${date}T12:00:00Z`) - 365 * 86400000)
          .toISOString()
          .slice(0, 10),
      );
    }
  };
  return (
    <>
      {!ranking && <UpcomingEvents existing={existing} onPick={pick} />}
      <form
        className="seeding-admin seeding-new"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          const r = await send(admin, "POST", "", {
            kind,
            name: name.trim(),
            event_url: ranking ? undefined : eventUrl.trim(),
            country: ranking ? country.trim() : undefined,
            window_start: fromInput(from),
            end: fromInput(to),
          }).catch(() => null);
          setBusy(false);
          if (!r) return setError("No se pudo contactar a la API.");
          if (!r.ok) return setError(await problem(r));
          const created = (await r.json()) as { slug: string };
          router.push(`/${ranking ? "rankings" : "seeding"}/${created.slug}`);
        }}
      >
        <strong>{ranking ? "Nuevo ranking" : "Nuevo seeding"}</strong>
        <label>
          Nombre
          <input
            value={name}
            minLength={3}
            maxLength={200}
            onChange={(e) => setName(e.target.value)}
            placeholder={
              ranking ? "Ranking Paraguay 2027" : "Torneo · Ultimate Singles"
            }
            required
          />
        </label>
        {ranking ? (
          <label>
            País (código)
            <input
              value={country}
              maxLength={2}
              onChange={(e) => setCountry(e.target.value.toUpperCase())}
              required
            />
          </label>
        ) : (
          <label>
            Link del evento en start.gg
            <input
              value={eventUrl}
              onChange={(e) => setEventUrl(e.target.value)}
              placeholder="https://www.start.gg/tournament/…/event/…"
              required
            />
          </label>
        )}
        <label>
          {ranking ? "Desde" : "Datos desde"}
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            required
          />
        </label>
        <label>
          {ranking ? "Hasta (exclusivo)" : "Fecha del evento"}
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            required
          />
        </label>
        <button className="primary-button" disabled={busy}>
          {busy ? "Creando…" : "Crear y bajar datos"}
        </button>
        {error && <p role="alert">{error}</p>}
      </form>
    </>
  );
}

export function SeedingList({
  kind = "seeding",
}: {
  kind?: "seeding" | "ranking";
}) {
  const [items, setItems] = useState<SeedingProjectSummary[] | null>(null);
  const [error, setError] = useState(false);
  const admin = useAdmin();
  const ranking = kind === "ranking";
  useEffect(() => {
    fetch(`${api}/seeding?kind=${kind}`, { headers: adminHeaders(admin) })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then(setItems)
      .catch(() => setError(true));
  }, [kind, admin]);
  return (
    <div className="competition-page">
      <h1>{ranking ? "Rankings" : "Seeding"}</h1>
      {admin && (
        <NewProjectForm kind={kind} admin={admin} existing={items ?? []} />
      )}
      {error && <p role="alert">No se pudieron cargar los datos.</p>}
      {!items && !error && <p role="status">Cargando…</p>}
      {items && items.length === 0 && (
        <p>
          {ranking
            ? "Todavía no hay rankings publicados."
            : "Todavía no hay seedings publicados."}
        </p>
      )}
      <div className="data-grid">
        {items?.map((p) => (
          <article className="data-card" key={p.slug}>
            <h3>
              <Link href={`/${ranking ? "rankings" : "seeding"}/${p.slug}`}>
                {p.name}
              </Link>
            </h3>
            {admin && !p.published && <span className="tag">borrador</span>}
            <p>
              {ranking
                ? `Del ${day(p.window_start)} al ${day(p.event_date)}`
                : `Evento el ${day(p.event_date)}`}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
