"use client";

import { useState } from "react";
import type { Main } from "../lib/api";
import {
  characterColor,
  characterIcon,
  characterRender,
} from "../lib/characters";
import { problem } from "./seeding-board";
import { useAdmin } from "../lib/admin";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

/** Stock icons of a player's most used characters: local SVGs, else start.gg's image. */
export function MainIcons({
  mains,
  size = 22,
}: {
  mains?: Main[];
  size?: number;
}) {
  if (!mains || mains.length === 0) return null;
  return (
    <span className="main-icons">
      {mains.map((m) => {
        const src = characterIcon(m.character) ?? m.icon;
        return src ? (
          <img
            key={m.character}
            src={src}
            alt={m.character}
            title={`${m.character}, ${Math.round(m.share)} %`}
            width={size}
            height={size}
            loading="lazy"
          />
        ) : (
          <span
            key={m.character}
            className="main-icon-text"
            title={`${Math.round(m.share)} %`}
          >
            {m.character}
          </span>
        );
      })}
    </span>
  );
}

/** "Counts for the ranking" flag: a checkbox for organizers, a label for everyone. */
export function RankingFlag({
  tournamentId,
  initial,
}: {
  tournamentId: string;
  initial: boolean;
}) {
  const [counts, setCounts] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const admin = useAdmin();
  if (!admin)
    return (
      <p className={counts ? "ranking-flag on" : "ranking-flag"}>
        {counts ? "✓ Cuenta para el ranking" : "No cuenta para el ranking"}
      </p>
    );
  return (
    <p className="ranking-flag">
      <label>
        <input
          type="checkbox"
          checked={counts}
          disabled={busy}
          onChange={async (e) => {
            const next = e.target.checked;
            setBusy(true);
            setError("");
            const r = await fetch(
              `${api}/tournaments/${tournamentId}/ranking`,
              {
                method: "PUT",
                headers: {
                  Authorization: `Bearer ${admin.key}`,
                  "X-Admin-Name": admin.name,
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({ counts: next }),
              },
            ).catch(() => null);
            setBusy(false);
            if (!r) return setError("No se pudo contactar a la API.");
            if (!r.ok) return setError(await problem(r));
            setCounts(next);
          }}
        />{" "}
        Cuenta para el ranking
      </label>
      {busy && <small> Recalculando rankings…</small>}
      {error && <small role="alert"> {error}</small>}
    </p>
  );
}

/**
 * Organizers mark tournaments whose start.gg seeding did not reflect the players'
 * level; they stop producing upsets and "beat their seed" records (and badges).
 */
/**
 * Main or secondary bracket of a tournament (Mission 20). Readers see a tag on secondary
 * events; organizers get the checkbox, and can hand the call back to the automatic rule.
 */
export function MainEventFlag({
  event,
}: {
  event: { id: string; main?: boolean | null; main_set?: boolean };
}) {
  const [state, setState] = useState({
    main: event.main ?? null,
    set: event.main_set ?? false,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const admin = useAdmin();
  if (state.main === null) return null;
  if (!admin)
    return state.main ? null : (
      <p className="ranking-flag">
        Evento secundario: no cuenta para el ranking ni para títulos.
      </p>
    );
  const save = async (main: boolean | null) => {
    setBusy(true);
    setError("");
    const r = await fetch(`${api}/events/${event.id}/main`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${admin.key}`,
        "X-Admin-Name": admin.name,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ main }),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await problem(r));
    const saved = (await r.json()) as { main: boolean; main_set: boolean };
    setState({ main: saved.main, set: saved.main_set });
  };
  return (
    <p className="ranking-flag">
      <label>
        <input
          type="checkbox"
          checked={state.main}
          disabled={busy}
          onChange={(e) => save(e.target.checked)}
        />{" "}
        Evento principal: cuenta para el ranking y los títulos
      </label>
      {state.set ? (
        <button
          type="button"
          className="link-button"
          disabled={busy}
          onClick={() => save(null)}
        >
          Volver a automático
        </button>
      ) : (
        <small> (automático)</small>
      )}
      {error && <small role="alert"> {error}</small>}
    </p>
  );
}

export function SeedingFlag({
  tournamentId,
  initial,
}: {
  tournamentId: string;
  initial: boolean;
}) {
  const [reliable, setReliable] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const admin = useAdmin();
  if (!admin)
    return reliable ? null : (
      <p className="ranking-flag">
        El seeding de este torneo no reflejaba el nivel de los jugadores, así
        que no cuenta para sorpresas ni emblemas.
      </p>
    );
  return (
    <p className="ranking-flag">
      <label>
        <input
          type="checkbox"
          checked={!reliable}
          disabled={busy}
          onChange={async (e) => {
            const next = !e.target.checked;
            setBusy(true);
            setError("");
            const r = await fetch(
              `${api}/tournaments/${tournamentId}/seeding`,
              {
                method: "PUT",
                headers: {
                  Authorization: `Bearer ${admin.key}`,
                  "X-Admin-Name": admin.name,
                  "Content-Type": "application/json",
                },
                body: JSON.stringify({ reliable: next }),
              },
            ).catch(() => null);
            setBusy(false);
            if (!r) return setError("No se pudo contactar a la API.");
            if (!r.ok) return setError(await problem(r));
            setReliable(next);
          }}
        />{" "}
        Seeding mal hecho: no cuenta para sorpresas
      </label>
      {error && <small role="alert"> {error}</small>}
    </p>
  );
}

/** Wins and losses as a split bar: green share of sets won, red share lost. */
export function WinBar({ wins, losses }: { wins?: number; losses?: number }) {
  const w = wins ?? 0;
  const l = losses ?? 0;
  const total = w + l;
  return (
    <span
      className="winbar"
      title={
        total ? `${Math.round((100 * w) / total)} % de sets ganados` : undefined
      }
    >
      <span className="winbar-text">
        {w}–{l}
      </span>
      {total > 0 && (
        <span className="winbar-track" aria-hidden="true">
          <span style={{ width: `${(100 * w) / total}%` }} />
        </span>
      )}
    </span>
  );
}

/** Signature color of a player's first main, for row stripes and the profile. */
export function mainColor(mains?: Main[]): string | undefined {
  const first = mains?.[0]?.character;
  return (first && characterColor(first)) || undefined;
}

/** Organizers choose which of the 8 official costumes the share images show. */
export function CostumePicker({
  playerId,
  mains,
}: {
  playerId: string;
  mains: Main[];
}) {
  const admin = useAdmin();
  const [chosen, setChosen] = useState<Record<string, number>>(() =>
    Object.fromEntries(mains.map((m) => [m.character, m.costume ?? 1])),
  );
  const [error, setError] = useState("");
  const options = mains.filter((m) => characterRender(m.character)).slice(0, 2);
  if (!admin || !options.length) return null;
  async function choose(character: string, costume: number) {
    setError("");
    const r = await fetch(`${api}/players/${playerId}/costume`, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${admin!.key}`,
        "X-Admin-Name": admin!.name,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ character, costume }),
    }).catch(() => null);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await problem(r));
    setChosen((c) => ({ ...c, [character]: costume }));
  }
  return (
    <section aria-labelledby="costume-title" className="costumes">
      <h2 id="costume-title">Traje en las imágenes</h2>
      <p className="seeding-lead">
        Elegí el color con el que aparece en las imágenes para redes. Solo lo
        ven los organizadores.
      </p>
      {options.map((m) => (
        <div key={m.character} role="group" aria-label={m.character}>
          <h3>{m.character}</h3>
          <div className="costume-options">
            {Array.from({ length: 8 }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={chosen[m.character] === n}
                aria-label={`${m.character}, traje ${n}`}
                onClick={() => choose(m.character, n)}
              >
                <img
                  src={characterRender(m.character, n, 160)!}
                  alt=""
                  loading="lazy"
                />
                <span>{n}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
