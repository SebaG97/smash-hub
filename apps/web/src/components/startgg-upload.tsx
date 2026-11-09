"use client";

import { useState } from "react";
import { adminHeaders, useAdmin } from "../lib/admin";

/**
 * Upload the hub's seeding to start.gg (Mission 30). Two checks before writing: the
 * organizer reviews every change and then types the seeding's slug. The server also
 * refuses if anything changed since the review, and reads start.gg back afterwards.
 */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

export type UploadPlan = {
  enabled: boolean;
  phase: { id: string; name: string };
  confirm_text: string;
  changes: { tag: string | null; before: number; after: number }[];
  unchanged: number;
  not_seeded: string[];
  not_on_startgg: string[];
  digest: string;
};

type Result = {
  changed: number;
  verified: boolean;
  wrong: { tag: string | null; expected: number; found: number | null }[];
};

async function detail(r: Response) {
  const body = await r.json().catch(() => null);
  return typeof body?.detail === "string"
    ? body.detail
    : "No se pudo completar la acción.";
}

export function StartggUpload({
  slug,
  onDone,
}: {
  slug: string;
  onDone?: () => void;
}) {
  const admin = useAdmin();
  const [plan, setPlan] = useState<UploadPlan | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  async function review() {
    setBusy(true);
    setError("");
    setResult(null);
    setReviewed(false);
    setTyped("");
    const r = await fetch(`${api}/seeding/${slug}/startgg`, {
      headers: adminHeaders(admin),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await detail(r));
    setPlan((await r.json()) as UploadPlan);
  }

  async function upload() {
    if (!plan) return;
    setBusy(true);
    setError("");
    const r = await fetch(`${api}/seeding/${slug}/startgg`, {
      method: "POST",
      headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
      body: JSON.stringify({ digest: plan.digest, confirm: typed }),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await detail(r));
    setResult((await r.json()) as Result);
    setPlan(null);
    onDone?.();
  }

  if (!admin) return null;
  const blocked =
    plan &&
    (!plan.enabled || plan.not_seeded.length > 0 || !plan.changes.length);
  return (
    <section className="startgg-upload" aria-labelledby="upload-title">
      <h3 id="upload-title">Subir a start.gg</h3>
      {!plan && (
        <>
          <p className="seeding-lead">
            Escribe este seeding en start.gg. Primero se muestran todos los
            cambios; no se escribe nada hasta confirmar dos veces.
          </p>
          <button
            type="button"
            className="primary-button"
            disabled={busy}
            onClick={review}
          >
            {busy ? "Leyendo start.gg…" : "Revisar cambios para subir"}
          </button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
      {result && (
        <p
          role="status"
          className={result.verified ? "upload-ok" : "upload-bad"}
        >
          {result.verified
            ? `Listo: se cambiaron ${result.changed} seeds y se verificó leyendo start.gg de nuevo.`
            : `Se subió, pero ${result.wrong.length} seeds no quedaron como se esperaba (${result.wrong
                .slice(0, 5)
                .map(
                  (w) => `${w.tag}: ${w.found ?? "?"} en vez de ${w.expected}`,
                )
                .join(", ")}). Revisalo en start.gg.`}
        </p>
      )}
      {plan && (
        <div className="upload-plan">
          <p>
            Fase <strong>{plan.phase.name}</strong>: cambian{" "}
            <strong>{plan.changes.length}</strong> seeds y {plan.unchanged}{" "}
            quedan igual.
          </p>
          {!plan.enabled && (
            <p role="alert">
              Subir a start.gg está apagado en el servidor. Se activa con
              STARTGG_SEEDING_WRITES=true en DigitalOcean.
            </p>
          )}
          {plan.not_seeded.length > 0 && (
            <p role="alert">
              {plan.not_seeded.length} inscriptos de start.gg no tienen seed en
              el hub ({plan.not_seeded.slice(0, 6).join(", ")}): bajá datos
              nuevos y recalculá antes de subir.
            </p>
          )}
          {plan.not_on_startgg.length > 0 && (
            <p className="seeding-lead">
              No figuran inscriptos en start.gg y se ignoran:{" "}
              {plan.not_on_startgg.slice(0, 8).join(", ")}
              {plan.not_on_startgg.length > 8 ? "…" : ""}.
            </p>
          )}
          {plan.changes.length > 0 && (
            <table className="upload-changes">
              <thead>
                <tr>
                  <th>Jugador</th>
                  <th>Ahora en start.gg</th>
                  <th>Queda</th>
                </tr>
              </thead>
              <tbody>
                {plan.changes.map((c) => (
                  <tr key={`${c.tag}-${c.before}`}>
                    <td>{c.tag}</td>
                    <td>{c.before}</td>
                    <td>{c.after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!blocked && (
            <>
              <label className="upload-check">
                <input
                  type="checkbox"
                  checked={reviewed}
                  onChange={(e) => setReviewed(e.target.checked)}
                />{" "}
                1. Revisé los {plan.changes.length} cambios y quiero escribirlos
                en start.gg.
              </label>
              <label className="upload-check">
                2. Escribí <code>{plan.confirm_text}</code> para confirmar
                <input
                  value={typed}
                  disabled={!reviewed}
                  onChange={(e) => setTyped(e.target.value)}
                  autoComplete="off"
                  aria-label="Texto de confirmación"
                />
              </label>
            </>
          )}
          <p className="seeding-actions">
            {!blocked && (
              <button
                type="button"
                className="primary-button danger"
                disabled={
                  busy || !reviewed || typed.trim() !== plan.confirm_text
                }
                onClick={upload}
              >
                {busy ? "Subiendo…" : "Subir a start.gg"}
              </button>
            )}
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => setPlan(null)}
            >
              Cancelar
            </button>
          </p>
        </div>
      )}
    </section>
  );
}
