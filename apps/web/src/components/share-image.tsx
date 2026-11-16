"use client";

import { useEffect, useState } from "react";
import type { Main } from "../lib/api";
import { adminHeaders, useAdmin } from "../lib/admin";
import { characterIcon, characterRender } from "../lib/characters";
import { CostumeOptions } from "./mains";
import { problem } from "./seeding-board";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");
const MAX_BYTES = 5 * 1024 * 1024;

export type ShareRow = {
  place: number;
  tag: string | null;
  mains?: Main[];
  /** start.gg player id: lets organizers change the main's costume from the editor. */
  startggId?: string;
};

function thumbnail(main?: Main) {
  if (!main) return null;
  return (
    characterRender(main.character, main.costume ?? 1, 160) ??
    characterIcon(main.character) ??
    main.icon ??
    null
  );
}

/**
 * Download link for a share image, only for organizers (readers never see it). They can
 * also replace the render of any place with their own picture; uploads are used for that
 * image only, never stored.
 */
export function ShareImage({
  endpoint,
  filename,
  label,
  rows,
  rowsPath,
  onCostume,
}: {
  endpoint: string;
  filename: string;
  label: string;
  rows?: ShareRow[];
  /** API path whose `top` lists the rows, fetched when the editor opens. */
  rowsPath?: string;
  /** Called after a costume is saved, so the page reloads its rows. */
  onCostume?: () => void;
}) {
  const admin = useAdmin();
  const [open, setOpen] = useState(false);
  if (!admin) return null;
  return (
    <div className="share-image">
      <p className="home-more">
        <a className="primary-button" href={endpoint} download={filename}>
          {label}
        </a>
        <button
          type="button"
          className="link-button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? "Cerrar personalización" : "Personalizar imagen"}
        </button>
      </p>
      {open && (
        <Editor
          endpoint={endpoint}
          filename={filename}
          rows={rows}
          rowsPath={rowsPath}
          onCostume={onCostume}
        />
      )}
    </div>
  );
}

function Editor({
  endpoint,
  filename,
  rows: given,
  rowsPath,
  onCostume,
}: {
  endpoint: string;
  filename: string;
  rows?: ShareRow[];
  rowsPath?: string;
  onCostume?: () => void;
}) {
  const admin = useAdmin();
  const [loaded, setLoaded] = useState<ShareRow[] | null>(null);
  const [files, setFiles] = useState<Record<number, File>>({});
  const [previews, setPreviews] = useState<Record<number, string>>({});
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  // Costumes saved from here, shown before the page reloads its rows.
  const [costumes, setCostumes] = useState<Record<string, number>>({});
  const [picking, setPicking] = useState<number | null>(null);
  const rows = (given ?? loaded ?? []).slice(0, 12).map((row) => {
    const main = row.mains?.[0];
    const saved = row.startggId && main && costumes[row.startggId];
    return saved
      ? { ...row, mains: [{ ...main, costume: saved }, ...row.mains!.slice(1)] }
      : row;
  });

  async function saveCostume(
    row: ShareRow,
    character: string,
    costume: number,
  ) {
    setError("");
    setBusy(true);
    const r = await fetch(`${api}/seeding/costumes/${row.startggId}`, {
      method: "PUT",
      credentials: "include",
      headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
      body: JSON.stringify({ character, costume }),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await problem(r));
    setCostumes((c) => ({ ...c, [row.startggId!]: costume }));
    setResult(null); // a generated image no longer matches
    onCostume?.();
  }

  useEffect(() => {
    if (given || !rowsPath) return;
    let active = true;
    fetch(`${api}/${rowsPath}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => active && setLoaded(d?.top ?? []))
      .catch(() => active && setLoaded([]));
    return () => {
      active = false;
    };
  }, [given, rowsPath]);

  // Object URLs live until they are replaced or the editor closes.
  useEffect(
    () => () => Object.values(previews).forEach(URL.revokeObjectURL),
    [previews],
  );
  useEffect(() => () => void (result && URL.revokeObjectURL(result)), [result]);

  function choose(index: number, file: File | undefined) {
    setError("");
    if (!file) return;
    if (!file.type.startsWith("image/"))
      return setError(`El archivo de la fila ${index + 1} no es una imagen.`);
    if (file.size > MAX_BYTES)
      return setError(`La imagen de la fila ${index + 1} pesa más de 5 MB.`);
    setFiles((f) => ({ ...f, [index]: file }));
    setPreviews((p) => ({ ...p, [index]: URL.createObjectURL(file) }));
  }

  function remove(index: number) {
    const without = <T,>(all: Record<number, T>) =>
      Object.fromEntries(
        Object.entries(all).filter(([k]) => Number(k) !== index),
      ) as Record<number, T>;
    setFiles(without);
    setPreviews(without);
  }

  async function generate() {
    setBusy(true);
    setError("");
    const form = new FormData();
    for (const [index, file] of Object.entries(files))
      form.append(`image-${index}`, file);
    const r = await fetch(endpoint, {
      method: "POST",
      credentials: "include",
      headers: adminHeaders(admin),
      body: form,
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo generar la imagen.");
    if (!r.ok)
      return setError((await r.text()) || "No se pudo generar la imagen.");
    setResult(URL.createObjectURL(await r.blob()));
  }

  if (!given && rowsPath && loaded === null)
    return <p role="status">Cargando puestos…</p>;
  return (
    <section className="share-editor" aria-label="Personalizar imagen">
      <p className="seeding-lead">
        Por defecto cada puesto lleva el render de su main. Podés cambiar el de
        cualquier puesto por una imagen tuya: las fotos llenan la tarjeta y los
        PNG con fondo transparente se ubican como el render. Las imágenes no se
        guardan en el hub.
        {rows.some((r) => r.startggId) &&
          " Con «Color» elegís el traje del main: ese sí se guarda en la ficha del jugador y vale para todas las imágenes (el jugador también lo puede cambiar desde su cuenta)."}
      </p>
      <ol className="share-slots">
        {rows.map((row, i) => {
          const main = row.mains?.[0];
          const preview = previews[i] ?? thumbnail(main);
          const canColor = Boolean(
            row.startggId && main && characterRender(main.character),
          );
          return (
            <li key={`${row.place}-${row.tag}-${i}`}>
              <span className="place">{row.place}</span>
              {preview ? (
                <img src={preview} alt="" />
              ) : (
                <span className="share-blank" aria-hidden="true" />
              )}
              <strong>{row.tag}</strong>
              <span className="share-actions">
                <label className="link-button">
                  {files[i] ? "Cambiar" : "Subir imagen"}
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/gif,image/avif"
                    aria-label={`Imagen para ${row.tag ?? `la fila ${i + 1}`}`}
                    onChange={(e) => {
                      choose(i, e.target.files?.[0]);
                      e.target.value = "";
                    }}
                  />
                </label>
                {files[i] && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => remove(i)}
                  >
                    Usar el render
                  </button>
                )}
                {canColor && !files[i] && (
                  <button
                    type="button"
                    className="link-button"
                    aria-expanded={picking === i}
                    onClick={() => setPicking(picking === i ? null : i)}
                  >
                    {picking === i ? "Listo" : "Color"}
                  </button>
                )}
              </span>
              {canColor && picking === i && (
                <div className="share-costumes">
                  <CostumeOptions
                    character={main!.character}
                    chosen={main!.costume ?? 1}
                    busy={busy}
                    onChoose={(n) => saveCostume(row, main!.character, n)}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <p className="home-more">
        <button
          type="button"
          className="primary-button"
          disabled={busy}
          onClick={generate}
        >
          {busy ? "Generando…" : "Generar imagen"}
        </button>
      </p>
      {error && <p role="alert">{error}</p>}
      {result && (
        <figure className="share-result">
          <img src={result} alt="Vista previa de la imagen personalizada" />
          <figcaption>
            <a className="primary-button" href={result} download={filename}>
              Descargar imagen personalizada
            </a>
          </figcaption>
        </figure>
      )}
    </section>
  );
}
