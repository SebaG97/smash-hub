"use client";

import { useCallback, useEffect, useState } from "react";
import type { Main } from "../lib/api";
import { adminHeaders, useAdmin } from "../lib/admin";
import { MainIcons } from "./mains";
import { Prefix } from "./prefix";

/** Seeding by pools (Mission 29): organizers see and move players pool by pool. */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

export type PoolPlayer = {
  seed: number;
  pool_seed?: number;
  player_id: string;
  tag: string;
  prefix: string | null;
  mains: Main[];
  rating: number | null;
  ranking: number | null;
  startgg_seed: number | null;
  /** Circuit where the player competes most ("PY", "ONLINE"…), for the image's flag. */
  circuit?: string | null;
  /** Flag chosen by organizers, else the circuit's country (Mission 32). */
  country?: string | null;
};

export type Pools = {
  phase: string;
  pools: {
    id: string;
    name: string;
    players: PoolPlayer[];
    top20: number;
    rating: number | null;
  }[];
  outside: PoolPlayer[];
  warnings: { kind: string; seeds: number[]; text: string }[];
  missing: string[];
  startgg_seeded: boolean;
};

async function message(r: Response) {
  const body = await r.json().catch(() => null);
  return typeof body?.detail === "string"
    ? body.detail
    : "No se pudo completar la acción.";
}

export function PoolBoard({
  slug,
  onChange,
  startOpen = false,
}: {
  slug: string;
  /** Called after the seeding changed, so the list below reloads too. */
  onChange?: () => void;
  /** Load the pools right away (its own tab) instead of behind a button. */
  startOpen?: boolean;
}) {
  const admin = useAdmin();
  const [open, setOpen] = useState(startOpen);
  const [data, setData] = useState<Pools | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(startOpen);
  const [picked, setPicked] = useState<PoolPlayer | null>(null);
  const [version, setVersion] = useState(0);
  const [fresh, setFresh] = useState(false);

  useEffect(() => {
    if (!open || !admin) return;
    let active = true;
    fetch(`${api}/seeding/${slug}/pools${fresh ? "?fresh=true" : ""}`, {
      headers: adminHeaders(admin),
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(await message(r));
        const body = (await r.json()) as Pools;
        if (active) {
          setData(body);
          setError("");
        }
      })
      .catch((e: Error) => active && setError(e.message))
      .finally(() => active && setBusy(false));
    return () => {
      active = false;
    };
  }, [open, admin, slug, version, fresh]);

  const reload = useCallback((fromStartgg = false) => {
    setBusy(true);
    setFresh(fromStartgg);
    setVersion((v) => v + 1);
  }, []);

  const [note, setNote] = useState("");

  async function post(path: string, body?: unknown) {
    setBusy(true);
    const r = await fetch(`${api}/seeding/${slug}/pools/${path}`, {
      method: "POST",
      headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).catch(() => null);
    if (!r || !r.ok) {
      setBusy(false);
      setError(r ? await message(r) : "No se pudo contactar a la API.");
      return false;
    }
    const done = await r.json().catch(() => ({}));
    setNote(
      done.missing?.length
        ? `Se copió el orden de start.gg, pero ${done.missing.length} inscriptos todavía no tienen datos en el hub y quedan corridos: bajá datos nuevos, recalculá y volvé a traerlo.`
        : done.placed
          ? `Se copió el orden de start.gg (${done.placed} jugadores).`
          : "",
    );
    setPicked(null);
    reload();
    onChange?.();
    return true;
  }

  function choose(player: PoolPlayer) {
    if (busy) return;
    if (!picked) return setPicked(player);
    if (picked.player_id === player.player_id) return setPicked(null);
    void post("swap", { a: picked.player_id, b: player.player_id });
  }

  if (!admin) return null;
  if (!open)
    return (
      <section className="pool-board" aria-labelledby="pools-title">
        <h2 id="pools-title">Armar por pools</h2>
        <p className="seeding-lead">
          El seeding repartido en los pools que ya armó start.gg: quién cae en
          cada pool, cuán cargado está y los cruces de primera ronda a revisar.
        </p>
        <button
          type="button"
          className="primary-button"
          onClick={() => {
            setBusy(true);
            setOpen(true);
          }}
        >
          Ver por pools
        </button>
      </section>
    );

  const flagged = new Set(data?.warnings.flatMap((w) => w.seeds) ?? []);
  return (
    <section className="pool-board" aria-labelledby="pools-title">
      <h2 id="pools-title">Armar por pools</h2>
      <p className="seeding-lead">
        Tocá un jugador y después otro para que cambien de lugar (y de seed).
        Los cambios quedan como ajustes manuales del seeding. No se escribe nada
        en start.gg.
      </p>
      <p className="seeding-actions">
        <button
          type="button"
          className="link-button"
          disabled={busy}
          onClick={() => reload(true)}
        >
          Actualizar desde start.gg
        </button>
        {data?.startgg_seeded && (
          <button
            type="button"
            className="link-button"
            disabled={busy}
            onClick={() => {
              if (
                window.confirm(
                  "Se copia el orden que está cargado en start.gg y se reemplazan todos los ajustes manuales del hub. ¿Continuar?",
                )
              )
                void post("adopt");
            }}
          >
            Traer el seeding de start.gg
          </button>
        )}
        <button
          type="button"
          className="link-button"
          onClick={() => setOpen(false)}
        >
          Cerrar
        </button>
      </p>
      {busy && <p role="status">Leyendo start.gg…</p>}
      {error && <p role="alert">{error}</p>}
      {note && <p role="status">{note}</p>}
      {picked && (
        <p role="status" className="pool-picked">
          Elegiste a <strong>{picked.tag}</strong> (seed {picked.seed}). Tocá a
          otro jugador para cambiarlos de lugar, o tocalo de nuevo para
          cancelar.
        </p>
      )}
      {data && (
        <>
          {data.missing.length > 0 && (
            <p className="seeding-lead">
              {data.missing.length} inscriptos de start.gg todavía no están en
              el seeding del hub ({data.missing.slice(0, 6).join(", ")}
              {data.missing.length > 6 ? "…" : ""}): marcá «Bajar datos nuevos»
              y recalculá.
            </p>
          )}
          {data.warnings.length > 0 && (
            <ul className="pool-warnings">
              {data.warnings.map((w) => (
                <li key={`${w.kind}-${w.seeds.join("-")}`}>{w.text}</li>
              ))}
            </ul>
          )}
          <div className="pool-grid">
            {data.pools.map((pool) => (
              <section key={pool.id} aria-label={pool.name}>
                <h3>{pool.name}</h3>
                <p className="pool-summary">
                  {pool.players.length} jugadores · {pool.top20} del top 20
                  {pool.rating ? ` · rating medio ${pool.rating}` : ""}
                </p>
                <ol>
                  {pool.players.map((p) => (
                    <PoolRow
                      key={p.player_id}
                      player={p}
                      picked={picked?.player_id === p.player_id}
                      flagged={flagged.has(p.seed)}
                      onPick={() => choose(p)}
                    />
                  ))}
                </ol>
              </section>
            ))}
          </div>
          {data.outside.length > 0 && (
            <section aria-label="Sin pool">
              <h3>Sin lugar en start.gg</h3>
              <p className="seeding-lead">
                Hay más jugadores en el seeding que lugares en start.gg.
              </p>
              <ol className="pool-outside">
                {data.outside.map((p) => (
                  <PoolRow
                    key={p.player_id}
                    player={p}
                    picked={picked?.player_id === p.player_id}
                    flagged={false}
                    onPick={() => choose(p)}
                  />
                ))}
              </ol>
            </section>
          )}
        </>
      )}
    </section>
  );
}

function PoolRow({
  player: p,
  picked,
  flagged,
  onPick,
}: {
  player: PoolPlayer;
  picked: boolean;
  flagged: boolean;
  onPick: () => void;
}) {
  const differs = p.startgg_seed !== null && p.startgg_seed !== p.seed;
  return (
    <li>
      <button
        type="button"
        className={`pool-player${picked ? " picked" : ""}${flagged ? " flagged" : ""}`}
        aria-pressed={picked}
        aria-label={`${p.tag}, seed ${p.seed}`}
        onClick={onPick}
      >
        <span className="pool-seed">{p.pool_seed ?? "–"}</span>
        <span className="pool-name">
          <Prefix prefix={p.prefix} />
          {p.tag}
        </span>
        <MainIcons mains={p.mains} size={20} />
        <small>
          seed {p.seed}
          {p.ranking ? ` · #${p.ranking}` : ""}
        </small>
        {differs && (
          <small className="pool-startgg" title="Seed cargado en start.gg">
            start.gg {p.startgg_seed}
          </small>
        )}
      </button>
    </li>
  );
}
