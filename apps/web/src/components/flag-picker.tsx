"use client";

import { useState } from "react";
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
        para todos los seedings.
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
