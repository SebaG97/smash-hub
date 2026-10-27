"use client";

import { useState } from "react";
import type { Main } from "../lib/api";
import { problem } from "./seeding-board";
import { useAdmin } from "../lib/admin";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

/** Stock icons of a player's most used characters (start.gg images). */
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
      {mains.map((m) =>
        m.icon ? (
          <img
            key={m.character}
            src={m.icon}
            alt={m.character}
            title={`${m.character} · ${Math.round(m.share)} %`}
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
        ),
      )}
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
