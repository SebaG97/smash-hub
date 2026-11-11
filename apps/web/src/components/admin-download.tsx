"use client";

import { useState } from "react";
import { adminHeaders, useAdmin } from "../lib/admin";

/**
 * Download an image that needs the organizer's key (drafts are not public): the request
 * carries the key, so it is fetched and saved instead of being a plain link (Mission 31).
 */
export function AdminDownload({
  endpoint,
  filename,
  label,
}: {
  endpoint: string;
  filename: string;
  label: string;
}) {
  const admin = useAdmin();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!admin) return null;
  async function download() {
    setBusy(true);
    setError("");
    const r = await fetch(endpoint, {
      method: "POST",
      credentials: "include",
      headers: adminHeaders(admin),
    }).catch(() => null);
    setBusy(false);
    if (!r || !r.ok)
      return setError(
        (r && (await r.text())) || "No se pudo generar la imagen.",
      );
    const url = URL.createObjectURL(await r.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <p className="home-more">
      <button
        type="button"
        className="primary-button"
        disabled={busy}
        onClick={download}
      >
        {busy ? "Generando…" : label}
      </button>
      {error && <span role="alert"> {error}</span>}
    </p>
  );
}
