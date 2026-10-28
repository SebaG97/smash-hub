"use client";

import { useState } from "react";
import { useAdmin } from "../lib/admin";
import { problem } from "./seeding-board";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

/** Logo and banner links from start.gg (hosted there). */
export type TournamentImages = { profile?: string; banner?: string } | null;

/** The tournament's square logo, or nothing when start.gg has none. */
export function TournamentLogo({
  images,
  size = 40,
}: {
  images?: TournamentImages;
  size?: number;
}) {
  if (!images?.profile) return null;
  return (
    <img
      className="tournament-logo"
      src={images.profile}
      alt=""
      width={size}
      height={size}
      loading="lazy"
      referrerPolicy="no-referrer"
    />
  );
}

/** The tournament's start.gg banner (2:1), or nothing when it has none. */
export function TournamentBanner({
  images,
  name,
}: {
  images?: TournamentImages;
  name: string;
}) {
  if (!images?.banner) return null;
  return (
    <img
      className="tournament-banner"
      src={images.banner}
      alt={`Banner de ${name}`}
      referrerPolicy="no-referrer"
    />
  );
}

/** Organizers: read logos and banners of tournaments imported before they were kept. */
export function TournamentImagesButton() {
  const admin = useAdmin();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [done, setDone] = useState(false);
  if (!admin || done) return message ? <p role="status">{message}</p> : null;
  return (
    <p className="ranking-flag">
      <button
        type="button"
        className="link-button"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setMessage("");
          const r = await fetch(`${api}/tournaments/images`, {
            method: "POST",
            headers: {
              Authorization: `Bearer ${admin.key}`,
              "X-Admin-Name": admin.name,
            },
          }).catch(() => null);
          setBusy(false);
          if (!r) return setMessage("No se pudo contactar a la API.");
          if (!r.ok) return setMessage(await problem(r));
          const d = (await r.json()) as { updated: number; remaining: number };
          setDone(d.remaining === 0);
          setMessage(
            d.remaining
              ? `Listo: ${d.updated} con imágenes. Faltan ${d.remaining}, tocá de nuevo para seguir.`
              : `Listo: ${d.updated} con imágenes. Ya no falta ninguno; recargá la página para verlos.`,
          );
        }}
      >
        {busy ? "Trayendo imágenes…" : "Traer logos y banners de start.gg"}
      </button>
      {message && <small role="status"> {message}</small>}
    </p>
  );
}
