"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { SeedingRow } from "../lib/api";
import { adminHeaders, useAdmin } from "../lib/admin";

/** Organizers choose each player's flag for the seeding images (Mission 32). */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

const COUNTRIES: [string, string][] = [
  ["PY", "Paraguay"],
  ["AR", "Argentina"],
  ["BR", "Brasil"],
  ["BO", "Bolivia"],
  ["CL", "Chile"],
  ["UY", "Uruguay"],
  ["PE", "Perú"],
  ["CO", "Colombia"],
  ["EC", "Ecuador"],
  ["VE", "Venezuela"],
  ["PA", "Panamá"],
  ["CR", "Costa Rica"],
  ["MX", "México"],
  ["US", "Estados Unidos"],
  ["ES", "España"],
];

const COUNTRY_NAMES = Object.fromEntries(COUNTRIES);

type RosterRow = {
  player_id: string;
  startgg_player_id: string;
  tag: string;
  country: string | null;
  foreign: boolean;
  profile_country: string | null;
  tournaments: number;
  last_tournament: string | null;
};
type Roster = {
  items: RosterRow[];
  total: number;
  page: number;
  page_size: number;
  home: string;
  foreign: number;
};

const SHOW = [
  ["all", "Todos"],
  ["foreign", "Extranjeros"],
  ["chosen", "Con bandera elegida"],
  ["unset", "Sin bandera"],
] as const;

/**
 * /admin/nacionalidades: every hub player and their flag, in one place (ADR-024).
 * A flag of another country leaves them out of the ranking, the player of the month and
 * achievements; their sets still count for the rest.
 */
export function CountryAdmin() {
  const admin = useAdmin();
  const [q, setQ] = useState("");
  const [tournament, setTournament] = useState("");
  const [show, setShow] = useState<(typeof SHOW)[number][0]>("all");
  const [page, setPage] = useState(1);
  const [roster, setRoster] = useState<Roster | null>(null);
  const [tournaments, setTournaments] = useState<
    { id: string; name: string }[]
  >([]);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");

  useEffect(() => {
    fetch(`${api}/tournaments?page_size=100`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setTournaments(d?.items ?? []))
      .catch(() => setTournaments([]));
  }, []);

  const load = useCallback(async () => {
    if (!admin) return;
    const params = new URLSearchParams({ q, show, page: String(page) });
    if (tournament) params.set("tournament", tournament);
    const r = await fetch(`${api}/seeding/countries?${params}`, {
      credentials: "include",
      headers: adminHeaders(admin),
    }).catch(() => null);
    if (!r || !r.ok) return setError("No se pudo cargar la lista.");
    setError("");
    setRoster((await r.json()) as Roster);
  }, [admin, q, show, page, tournament]);

  useEffect(() => {
    const timer = setTimeout(load, 250); // while typing the tag
    return () => clearTimeout(timer);
  }, [load]);

  if (!admin)
    return (
      <p role="alert">Necesitás una cuenta de administrador para ver esto.</p>
    );

  async function choose(row: RosterRow, country: string) {
    setError("");
    setSaved("");
    const r = await fetch(`${api}/seeding/countries/${row.startgg_player_id}`, {
      method: "PUT",
      credentials: "include",
      headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
      body: JSON.stringify({ country: country || null }),
    }).catch(() => null);
    if (!r || !r.ok)
      return setError(`No se pudo guardar la bandera de ${row.tag}.`);
    setSaved(
      `${row.tag}: ${country ? `${flagEmoji(country)} ${COUNTRY_NAMES[country] ?? country}` : "sin bandera (local)"}.`,
    );
    load();
  }

  const pages = roster
    ? Math.max(1, Math.ceil(roster.total / roster.page_size))
    : 1;
  return (
    <section className="country-admin" aria-label="Nacionalidades">
      <p className="seeding-lead">
        Elegí la bandera de cada jugador una sola vez y vale para todo el hub.{" "}
        <strong>
          Un país que no sea Paraguay lo deja fuera del ranking, del jugador del
          mes, de los logros y de los récords
        </strong>{" "}
        (sus sets siguen contando para los demás). Sin bandera cuenta como
        local. «start.gg dice» es el país que el jugador puso en su perfil, si
        algún seeding lo leyó: sirve de pista, no se aplica solo.
      </p>
      <div className="seeding-tools">
        <label>
          Buscar tag{" "}
          <input
            value={q}
            maxLength={60}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label>
          Torneo{" "}
          <select
            value={tournament}
            onChange={(e) => {
              setTournament(e.target.value);
              setPage(1);
            }}
          >
            <option value="">Todos</option>
            {tournaments.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Mostrar{" "}
          <select
            value={show}
            onChange={(e) => {
              setShow(e.target.value as typeof show);
              setPage(1);
            }}
          >
            {SHOW.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {error && <p role="alert">{error}</p>}
      {saved && <p role="status">Guardado. {saved}</p>}
      {!roster ? (
        <p role="status">Cargando…</p>
      ) : (
        <>
          <p className="seeding-lead">
            {roster.total} {roster.total === 1 ? "jugador" : "jugadores"}
            {roster.foreign ? ` · ${roster.foreign} marcados de otro país` : ""}
            .
          </p>
          <div className="seeding-table-wrap">
            <table className="seeding-table">
              <thead>
                <tr>
                  <th scope="col">Jugador</th>
                  <th scope="col">Torneos</th>
                  <th scope="col">Último</th>
                  <th scope="col">start.gg dice</th>
                  <th scope="col">Bandera</th>
                </tr>
              </thead>
              <tbody>
                {roster.items.map((row) => (
                  <tr
                    key={row.player_id}
                    data-foreign={row.foreign || undefined}
                  >
                    <td>
                      <Link href={`/players/${row.player_id}`}>{row.tag}</Link>
                      {row.foreign && <small> · fuera del ranking</small>}
                    </td>
                    <td>{row.tournaments}</td>
                    <td>{row.last_tournament?.slice(0, 10) ?? "—"}</td>
                    <td>{row.profile_country ?? "—"}</td>
                    <td>
                      <select
                        aria-label={`Bandera de ${row.tag}`}
                        value={row.country ?? ""}
                        onChange={(e) => choose(row, e.target.value)}
                      >
                        <option value="">Sin bandera (local)</option>
                        {COUNTRIES.map(([code, name]) => (
                          <option key={code} value={code}>
                            {flagEmoji(code)} {name}
                          </option>
                        ))}
                        {row.country && !COUNTRY_NAMES[row.country] && (
                          <option value={row.country}>{row.country}</option>
                        )}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <p className="home-more">
              <button
                type="button"
                className="link-button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                ← Anterior
              </button>{" "}
              Página {page} de {pages}{" "}
              <button
                type="button"
                className="link-button"
                disabled={page >= pages}
                onClick={() => setPage(page + 1)}
              >
                Siguiente →
              </button>
            </p>
          )}
        </>
      )}
    </section>
  );
}

/** "PY" → 🇵🇾 */
export function flagEmoji(code: string) {
  return String.fromCodePoint(
    ...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65),
  );
}

export function FlagPicker({
  rows,
  onChange,
}: {
  rows: SeedingRow[];
  onChange: () => void;
}) {
  const admin = useAdmin();
  const [all, setAll] = useState(false);
  const [error, setError] = useState("");
  if (!admin) return null;
  const missing = rows.filter((r) => !r.country);
  const shown = all ? rows : missing;

  async function choose(row: SeedingRow, country: string) {
    setError("");
    const r = await fetch(`${api}/seeding/countries/${row.player_id}`, {
      method: "PUT",
      credentials: "include",
      headers: {
        ...adminHeaders(admin),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ country: country || null }),
    }).catch(() => null);
    if (!r || !r.ok) return setError("No se pudo guardar la bandera.");
    onChange();
  }

  return (
    <section className="flag-picker" aria-labelledby="flags-title">
      <h3 id="flags-title">Banderas</h3>
      <p className="seeding-lead">
        Por defecto va la bandera del circuito donde más compite cada jugador.
        Los que juegan sobre todo online no tienen: elegila acá. Queda guardada
        para todos los seedings.{" "}
        <strong>
          Elegir otro país que no sea Paraguay deja al jugador fuera del
          ranking, del jugador del mes y de los logros
        </strong>{" "}
        (sus sets siguen contando para los demás).
        {missing.length > 0 && !all
          ? ` ${missing.length} sin bandera en este top.`
          : ""}
      </p>
      {shown.length > 0 && (
        <ul>
          {shown.map((row) => (
            <li key={row.player_id}>
              <span className="flag-seed">{row.seed}</span>
              <span className="flag-tag">{row.gamer_tag}</span>
              <small>
                {row.main_circuit === "ONLINE"
                  ? "juega online"
                  : row.main_circuit
                    ? `circuito ${row.main_circuit}`
                    : "sin datos"}
              </small>
              <select
                aria-label={`Bandera de ${row.gamer_tag}`}
                value={row.country_chosen ? (row.country ?? "") : ""}
                onChange={(e) => choose(row, e.target.value)}
              >
                <option value="">
                  {row.country && !row.country_chosen
                    ? `${flagEmoji(row.country)} ${row.country} (circuito)`
                    : "Sin bandera"}
                </option>
                {COUNTRIES.map(([code, name]) => (
                  <option key={code} value={code}>
                    {flagEmoji(code)} {name}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      )}
      <button
        type="button"
        className="link-button"
        onClick={() => setAll(!all)}
      >
        {all
          ? "Mostrar solo los que no tienen bandera"
          : "Cambiar la bandera de cualquiera del top"}
      </button>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
