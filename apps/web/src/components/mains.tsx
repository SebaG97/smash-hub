"use client";

import { useState } from "react";
import type { Main } from "../lib/api";
import { characterColor, characterIcon } from "../lib/characters";
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
