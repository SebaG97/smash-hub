"use client";

import { useEffect, useState } from "react";
import { adminHeaders, useAdmin } from "../lib/admin";
import { characterRender } from "../lib/characters";
import {
  CARDS,
  FORMATS,
  MISSING,
  type Format,
  type Ref,
  type Social,
} from "../lib/tournament-social";
import { save, zip } from "../lib/zip";
import { CostumeOptions } from "./mains";
import { problem } from "./seeding-board";

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

/** Everyone who appears in the images, once, in the order they show up. */
function people(d: Social) {
  const seen = new Map<string, Ref>();
  const add = (r?: Ref | null) => {
    if (r?.id && r.mains?.length && !seen.has(r.id)) seen.set(r.id, r);
  };
  d.summary.top.forEach(add);
  d.champion_path.forEach((p) => add(p.opponent));
  [...d.grand_final, ...d.upsets, ...d.close_sets].forEach((s) => {
    add(s.winner);
    add(s.loser);
  });
  [...d.over, ...d.under, ...d.newcomers.returns].forEach(add);
  d.rivalries.forEach((r) => {
    add(r.a);
    add(r.b);
  });
  return [...seen.values()];
}

/**
 * Organizers' panel on a tournament page (SH-SOCIAL-01): the 13 social media images,
 * in the format they choose, to preview, download one by one or all at once, and the
 * costume of each player's main (saved on the player, it applies to every image).
 */
export function TournamentSocial({
  id,
  event,
}: {
  id: string;
  event: string | null;
}) {
  const admin = useAdmin();
  const [open, setOpen] = useState(false);
  if (!admin) return null;
  return (
    <section className="social-images" aria-label="Imágenes para redes">
      <p className="home-more">
        <button
          type="button"
          className="primary-button"
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? "Cerrar imágenes para redes" : "Imágenes para redes"}
        </button>
      </p>
      {open && <Panel id={id} event={event} />}
    </section>
  );
}

function Panel({ id, event }: { id: string; event: string | null }) {
  const admin = useAdmin();
  const [data, setData] = useState<Social | null>(null);
  const [failed, setFailed] = useState(false);
  const [format, setFormat] = useState<Format>("portrait");
  const [under, setUnder] = useState(false);
  const [shown, setShown] = useState<Record<string, boolean>>({});
  // Bumped after a costume change so previews and downloads skip the cache.
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState("");

  useEffect(() => {
    let active = true;
    fetch(
      `${api}/insights/tournaments/${id}/social${event ? `?event=${event}` : ""}`,
    )
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!active) return;
        setData(d);
        setFailed(!d);
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, [id, event, version]);

  if (failed)
    return (
      <p role="alert">
        No se pudieron leer los datos del torneo para las imágenes.
      </p>
    );
  if (!data) return <p role="status">Cargando datos del torneo…</p>;

  const url = (key: string) => {
    const query = new URLSearchParams({ format });
    if (event) query.set("event", event);
    if (key === "seeds" && under) query.set("under", "1");
    if (version) query.set("v", String(version));
    return `/og/tournament/${id}/${key}?${query}`;
  };
  const name = (key: string) =>
    `${data.tournament.slug.replace(/\W+/g, "-")}-${key}-${format}.png`;
  const ready = CARDS.filter((c) => c.has(data));

  /** Every available image in one ZIP, numbered in the carousel's order. */
  async function downloadAll() {
    setError("");
    setBusy(true);
    const files: { name: string; data: Uint8Array }[] = [];
    const failed: string[] = [];
    for (const [i, card] of ready.entries()) {
      setProgress(`Generando ${i + 1} de ${ready.length}: ${card.title}…`);
      const r = await fetch(url(card.key)).catch(() => null);
      if (!r?.ok) {
        failed.push(card.title);
        continue;
      }
      files.push({
        name: `${String(files.length + 1).padStart(2, "0")}-${name(card.key)}`,
        data: new Uint8Array(await r.arrayBuffer()),
      });
    }
    setProgress("");
    setBusy(false);
    if (failed.length)
      setError(`No se pudieron generar: ${failed.join(", ")}.`);
    if (!files.length) return;
    save(
      zip(files),
      `${data!.tournament.slug.replace(/\W+/g, "-")}-${format}.zip`,
    );
  }

  async function saveCostume(player: Ref, character: string, costume: number) {
    setError("");
    setBusy(true);
    const r = await fetch(`${api}/players/${player.id}/costume`, {
      method: "PUT",
      credentials: "include",
      headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
      body: JSON.stringify({ character, costume }),
    }).catch(() => null);
    setBusy(false);
    if (!r) return setError("No se pudo contactar a la API.");
    if (!r.ok) return setError(await problem(r));
    setVersion((v) => v + 1);
  }

  return (
    <div className="social-panel">
      <p className="seeding-lead">
        Imágenes con el estilo del hub para subir a redes. Las que no tienen
        datos suficientes aparecen desactivadas con el motivo.
      </p>
      <div className="social-options">
        <label>
          Formato{" "}
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as Format)}
          >
            {Object.entries(FORMATS).map(([key, f]) => (
              <option key={key} value={key}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={under}
            onChange={(e) => setUnder(e.target.checked)}
          />{" "}
          En «Por encima de su seed», sumar a los que terminaron por debajo
        </label>
        <button
          type="button"
          className="primary-button"
          disabled={busy || !ready.length}
          onClick={downloadAll}
        >
          {busy && progress
            ? "Generando…"
            : `Descargar todas en un ZIP (${ready.length})`}
        </button>
      </div>
      {progress && <p role="status">{progress}</p>}
      {error && <p role="alert">{error}</p>}
      <ul className="social-cards">
        {CARDS.map((card) => {
          const ok = card.has(data);
          return (
            <li key={card.key} className={ok ? undefined : "unavailable"}>
              <strong>{card.title}</strong>
              <small>{ok ? card.hint : MISSING[card.key]}</small>
              {ok && (
                <span className="share-actions">
                  <button
                    type="button"
                    className="link-button"
                    aria-expanded={Boolean(shown[card.key])}
                    onClick={() =>
                      setShown((s) => ({ ...s, [card.key]: !s[card.key] }))
                    }
                  >
                    {shown[card.key] ? "Ocultar" : "Ver"}
                  </button>
                  <a
                    className="link-button"
                    href={url(card.key)}
                    download={name(card.key)}
                  >
                    Descargar
                  </a>
                </span>
              )}
              {ok && shown[card.key] && (
                <img
                  src={url(card.key)}
                  alt={`Vista previa: ${card.title}`}
                  loading="lazy"
                />
              )}
            </li>
          );
        })}
      </ul>
      <Colors players={people(data)} busy={busy} onChoose={saveCostume} />
    </div>
  );
}

function Colors({
  players,
  busy,
  onChoose,
}: {
  players: Ref[];
  busy: boolean;
  onChoose: (player: Ref, character: string, costume: number) => void;
}) {
  const [picking, setPicking] = useState<string | null>(null);
  const colorable = players.filter((p) =>
    characterRender(p.mains![0].character),
  );
  if (!colorable.length) return null;
  return (
    <details className="account-history">
      <summary>Colores de los personajes ({colorable.length})</summary>
      <p className="seeding-lead">
        El traje elegido se guarda en la ficha del jugador y vale para todas las
        imágenes del hub (el jugador también lo puede cambiar desde su cuenta).
      </p>
      <ol className="share-slots social-colors">
        {colorable.map((p) => {
          const main = p.mains![0];
          const src = characterRender(main.character, main.costume ?? 1, 160);
          return (
            <li key={p.id}>
              {src ? (
                <img src={src} alt="" />
              ) : (
                <span className="share-blank" />
              )}
              <strong>{p.tag}</strong>
              <span className="share-actions">
                <button
                  type="button"
                  className="link-button"
                  aria-expanded={picking === p.id}
                  onClick={() => setPicking(picking === p.id ? null : p.id)}
                >
                  {picking === p.id ? "Listo" : "Color"}
                </button>
              </span>
              {picking === p.id && (
                <div className="share-costumes">
                  <CostumeOptions
                    character={main.character}
                    chosen={main.costume ?? 1}
                    busy={busy}
                    onChoose={(n) => onChoose(p, main.character, n)}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </details>
  );
}
