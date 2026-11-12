"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { adminHeaders, useAdmin, type Admin } from "../lib/admin";
import { apiFetch, errorText, signInHref, useMe } from "../lib/session";

/**
 * Achievements (SH-ACH-01). The catalog, rarities and statistics come from the API
 * (GET /achievements/catalog): nothing about them is repeated here. Pages only read;
 * the backend evaluates in the background.
 */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

export type Rarity = "comun" | "raro" | "epico" | "legendario";
export type Stats = {
  holders: number;
  universe: number | null;
  percent: number | null;
  label: string;
  note: string | null;
  coverage?: number | null;
  first?: {
    at: string | null;
    holders: { id: string; name: string | null }[];
    verified: boolean;
  } | null;
  computed_at?: string | null;
};
export type Entry = {
  id: string;
  scope: "player" | "prode";
  category: string;
  name: string;
  description: string;
  condition: string | null;
  rarity: Rarity;
  status: "active" | "manual" | "pending";
  kind: "permanent" | "state" | "limited";
  secret: boolean;
  humor: boolean;
  origin: string;
  collection: string | null;
  universe: string;
  partial: boolean;
  legacy: boolean;
  tone: string | null;
  pending: string | null;
  available: boolean;
  category_name: string;
  rarity_name: string;
  collection_name: string | null;
  stats: Stats;
  mine: boolean;
  revealed: boolean;
};
type Progress = Record<string, { name: string; owned: number; total: number }>;
type Collections = Record<
  string,
  { name: string; owned: number; total: number; active: boolean }
>;
export type Catalog = {
  categories: Record<string, string>;
  rarities: Record<Rarity, string>;
  collections: Collections;
  progress: Progress | null;
  achievements: Entry[];
};
export type Award = {
  id: string;
  achievement_id: string;
  source: "player" | "prode";
  name: string;
  rarity: Rarity;
  category: string | null;
  detail: string | null;
  evidence?: Record<string, unknown>;
  event_at: string | null;
  recognized_at: string | null;
  backfilled: boolean;
  manual: boolean;
  reason: string | null;
  hidden: boolean;
  contest?: string | null;
  tournament_slug?: string | null;
  opponent?: { id: string; tag: string | null } | null;
};
export type AchievementProfile = {
  player_id: string | null;
  user_id: string | null;
  showcase: { automatic: boolean; items: Award[] };
  achievements: Award[];
  prode: Award[];
  progress: Progress;
  collections: Collections;
  states?: { achievement_id: string; name: string; detail: string }[];
};

const RARITY_ORDER: Rarity[] = ["legendario", "epico", "raro", "comun"];
const RARITY_NAMES: Record<Rarity, string> = {
  comun: "Común",
  raro: "Raro",
  epico: "Épico",
  legendario: "Legendario",
};
const DAY = new Intl.DateTimeFormat("es-PY", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "America/Asuncion",
});

function day(iso: string | null | undefined) {
  return iso ? DAY.format(new Date(iso)) : null;
}

/** One API path with the session cookie (so the reader's secrets are revealed). */
function useLoad<T>(path: string | null) {
  const [state, setState] = useState<{
    path: string | null;
    data?: T;
    status?: number;
  }>({ path: null });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let active = true;
    apiFetch(path)
      .then(async (r) => {
        const data = r.ok ? ((await r.json()) as T) : undefined;
        if (active) setState({ path, data, status: r.status });
      })
      .catch(() => {
        if (active) setState({ path, status: 0 });
      });
    return () => {
      active = false;
    };
  }, [path, tick]);
  const loading = Boolean(path) && state.path !== path;
  return {
    data: loading ? undefined : state.data,
    status: loading ? undefined : state.status,
    loading,
    reload: () => setTick((t) => t + 1),
  };
}

function Failed({ reload }: { reload: () => void }) {
  return (
    <div role="alert">
      <p>No se pudieron cargar los logros.</p>
      <button className="primary-button" onClick={reload}>
        Reintentar
      </button>
    </div>
  );
}

export function RarityTag({ rarity }: { rarity: Rarity }) {
  return (
    <span className="ach-rarity" data-rarity={rarity}>
      {RARITY_NAMES[rarity]}
    </span>
  );
}

/** «Nadie todavía», «Muestra chica» or «12 % · Escaso» with the absolute count. */
export function StatLine({ stats }: { stats: Stats }) {
  const people =
    stats.holders === 1 ? "1 persona" : `${stats.holders} personas`;
  if (stats.percent !== null)
    return (
      <span className="ach-stat">
        {stats.percent.toLocaleString("es-PY")} % · {stats.label} · {people}
      </span>
    );
  if (stats.holders === 0 || stats.label === "Pendiente")
    return <span className="ach-stat">{stats.label}</span>;
  return (
    <span className="ach-stat" title={stats.note ?? undefined}>
      {stats.label === people ? people : `${people} · ${stats.label}`}
    </span>
  );
}

function AchievementCard({ entry }: { entry: Entry }) {
  return (
    <li
      className="ach-card"
      data-rarity={entry.rarity}
      data-mine={entry.mine ? "true" : undefined}
      data-off={!entry.available ? "true" : undefined}
    >
      <Link href={`/logros/${entry.id}`}>
        <strong>{entry.name}</strong>
      </Link>
      <span className="ach-desc">{entry.description}</span>
      <span className="ach-meta">
        <RarityTag rarity={entry.rarity} />
        {entry.mine && <span className="ach-owned">Lo tenés</span>}
        {entry.kind === "state" && <span className="ach-flag">Estado</span>}
        {entry.kind === "limited" && (
          <span className="ach-flag">Edición limitada</span>
        )}
        {entry.status === "manual" && (
          <span className="ach-flag">Lo otorga la organización</span>
        )}
        {entry.status === "pending" ? (
          <span className="ach-flag">Próximamente</span>
        ) : !entry.available ? (
          <span className="ach-flag">Colección sin activar</span>
        ) : (
          <StatLine stats={entry.stats} />
        )}
      </span>
    </li>
  );
}

function Bar({ owned, total }: { owned: number; total: number }) {
  return (
    <progress
      className="ach-bar"
      value={owned}
      max={Math.max(total, 1)}
      aria-label={`${owned} de ${total}`}
    />
  );
}

type Filter = "todos" | "mios" | "faltan" | "secretos";
const FILTERS: [Filter, string][] = [
  ["todos", "Todos"],
  ["mios", "Obtenidos"],
  ["faltan", "Me faltan"],
  ["secretos", "Secretos"],
];

function Chips<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (value: T) => void;
}) {
  return (
    <div className="ach-chips" role="group" aria-label={label}>
      {options.map(([key, name]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

/** /logros: the whole catalog with filters, progress and collections. */
export function AchievementsPage() {
  const me = useMe();
  const { data, loading, reload } = useLoad<Catalog>("achievements/catalog");
  const [category, setCategory] = useState("todas");
  const [rarity, setRarity] = useState<Rarity | "todas">("todas");
  const [filter, setFilter] = useState<Filter>("todos");
  const shown = useMemo(() => {
    if (!data) return [];
    return data.achievements.filter(
      (a) =>
        (category === "todas" || a.category === category) &&
        (rarity === "todas" || a.rarity === rarity) &&
        (filter === "todos" ||
          (filter === "mios" && a.mine) ||
          (filter === "faltan" && !a.mine && a.status !== "pending") ||
          (filter === "secretos" && a.secret)),
    );
  }, [data, category, rarity, filter]);
  if (loading) return <p role="status">Cargando…</p>;
  if (!data || !Array.isArray(data.achievements))
    return <Failed reload={reload} />;
  const owned = data.achievements.filter((a) => a.mine).length;
  const groups = Object.entries(data.categories)
    .map(([key, name]) => ({
      key,
      name,
      items: shown.filter((a) => a.category === key),
    }))
    .filter((g) => g.items.length);
  return (
    <div className="competition-page ach-page">
      <h1>Logros</h1>
      <p className="seeding-lead">
        {data.achievements.length} logros de la escena de Smash de Paraguay: por
        jugar, por ganar, por pronosticar en el Prode y algunos que se
        descubren. Los de jugador salen de los resultados oficiales importados
        de start.gg; los del Prode, de cada Prode liquidado.
      </p>
      {me?.user ? (
        data.progress && (
          <section aria-labelledby="progress-title">
            <h2 id="progress-title">
              Tu progreso: {owned} {owned === 1 ? "logro" : "logros"}
            </h2>
            <ul className="ach-progress">
              {Object.entries(data.progress).map(([key, p]) => (
                <li key={key}>
                  <span>{p.name}</span>
                  <Bar owned={p.owned} total={p.total} />
                  <small>
                    {p.owned}/{p.total}
                  </small>
                </li>
              ))}
            </ul>
            {!me.user.player && (
              <p className="seeding-lead">
                Los logros de jugador aparecen cuando vinculás tu cuenta con tu
                ficha en <Link href="/cuenta">Mi cuenta</Link>.
              </p>
            )}
          </section>
        )
      ) : (
        <p>
          <Link className="primary-button" href={signInHref("/logros")}>
            Ingresar
          </Link>{" "}
          para ver tu progreso y los secretos que ya descubriste.
        </p>
      )}
      <section aria-labelledby="collections-title">
        <h2 id="collections-title">Colecciones</h2>
        <ul className="ach-progress">
          {Object.entries(data.collections).map(([key, c]) => (
            <li key={key}>
              <span>{c.name}</span>
              {c.active ? (
                <>
                  <Bar owned={c.owned} total={c.total} />
                  <small>
                    {c.owned}/{c.total}
                  </small>
                </>
              ) : (
                <small>Se activa cuando la organización lo confirme</small>
              )}
            </li>
          ))}
        </ul>
      </section>
      <section aria-labelledby="catalog-title">
        <h2 id="catalog-title">Catálogo</h2>
        <Chips
          label="Categoría"
          value={category}
          options={[["todas", "Todas"], ...Object.entries(data.categories)]}
          onChange={setCategory}
        />
        <Chips<Rarity | "todas">
          label="Rareza"
          value={rarity}
          options={[
            ["todas", "Toda rareza"],
            ...RARITY_ORDER.map((r): [Rarity, string] => [r, RARITY_NAMES[r]]),
          ]}
          onChange={setRarity}
        />
        <Chips
          label="Desbloqueo"
          value={filter}
          options={FILTERS}
          onChange={setFilter}
        />
        <p className="ach-count" role="status">
          {shown.length} {shown.length === 1 ? "logro" : "logros"}
        </p>
        {groups.map((g) => (
          <div key={g.key} className="ach-group">
            <h3>{g.name}</h3>
            <ul className="ach-grid">
              {g.items.map((a) => (
                <AchievementCard key={a.id} entry={a} />
              ))}
            </ul>
          </div>
        ))}
        {shown.length === 0 && (
          <p className="seeding-lead">Ningún logro con esos filtros.</p>
        )}
      </section>
    </div>
  );
}

type Detail = Entry & {
  recent: {
    player_id?: string;
    user_id?: string;
    name: string | null;
    detail: string | null;
    contest?: string | null;
    event_at: string | null;
    recognized_at: string | null;
  }[];
  my_awards: Award[];
};

function holderHref(h: { player_id?: string; user_id?: string }) {
  return h.player_id ? `/players/${h.player_id}` : `/prode/u/${h.user_id}`;
}

/** /logros/[id]: one achievement with its statistics and who has it. */
export function AchievementDetailPage({ id }: { id: string }) {
  const { data, status, loading, reload } = useLoad<Detail>(
    `achievements/${id}`,
  );
  if (loading) return <p role="status">Cargando…</p>;
  if (status === 404) return <p>No existe ese logro.</p>;
  if (!data) return <Failed reload={reload} />;
  const first = data.stats.first;
  return (
    <div className="competition-page ach-page">
      <p>
        <Link href="/logros">← Logros</Link>
      </p>
      <div className="ach-hero" data-rarity={data.rarity}>
        <p className="ach-kicker">
          {data.category_name}
          {data.collection_name ? ` · ${data.collection_name}` : ""}
        </p>
        <h1>{data.name}</h1>
        <p>{data.description}</p>
        <p className="ach-meta">
          <RarityTag rarity={data.rarity} />
          {data.secret && <span className="ach-flag">Secreto</span>}
          {data.humor && <span className="ach-flag">Humor</span>}
          {data.kind === "state" && (
            <span className="ach-flag">Estado: se puede perder</span>
          )}
          {data.kind === "limited" && (
            <span className="ach-flag">Edición limitada</span>
          )}
        </p>
      </div>
      {data.revealed && data.condition && (
        <section aria-labelledby="condition-title">
          <h2 id="condition-title">Cómo se consigue</h2>
          <p>{data.condition}</p>
          {data.status === "manual" && (
            <p className="seeding-lead">
              Lo otorga la organización, con un motivo público.
            </p>
          )}
          {data.partial && (
            <p className="seeding-lead">
              Depende de datos que no todos los sets tienen (por ejemplo, los
              personajes reportados en start.gg).
            </p>
          )}
        </section>
      )}
      {data.status === "pending" ? (
        <p className="seeding-lead" role="note">
          Todavía no se otorga: {data.pending}
        </p>
      ) : !data.available ? (
        <p className="seeding-lead" role="note">
          Esta colección se activa cuando la organización confirme la identidad
          y el consentimiento de la persona a la que hace referencia.
        </p>
      ) : (
        <section aria-labelledby="stats-title">
          <h2 id="stats-title">Quiénes lo tienen</h2>
          <dl className="facts">
            <div>
              <dt>Personas</dt>
              <dd>{data.stats.holders}</dd>
            </div>
            <div>
              <dt>Rareza en la escena</dt>
              <dd>
                {data.stats.percent !== null
                  ? `${data.stats.percent.toLocaleString("es-PY")} % · ${data.stats.label}`
                  : data.stats.label}
              </dd>
            </div>
            {data.stats.universe !== null && (
              <div>
                <dt>Elegibles</dt>
                <dd>{data.stats.universe}</dd>
              </div>
            )}
            {first && (
              <div className="fact-wide">
                <dt>
                  {first.verified
                    ? "Primero en conseguirlo"
                    : "Primer registro en Smash Hub"}
                </dt>
                <dd>
                  {first.holders.map((h) => h.name ?? "?").join(", ")} ·{" "}
                  {day(first.at)}
                </dd>
              </div>
            )}
          </dl>
          {data.stats.note && (
            <p className="seeding-lead">{data.stats.note}.</p>
          )}
          {data.recent.length > 0 && (
            <ul className="ach-holders">
              {data.recent.map((h, i) => (
                <li key={`${h.player_id ?? h.user_id}-${i}`}>
                  <Link href={holderHref(h)}>{h.name ?? "?"}</Link>
                  <span>{h.detail}</span>
                  {h.event_at && <small>{day(h.event_at)}</small>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      {data.my_awards.length > 0 && (
        <section aria-labelledby="mine-title">
          <h2 id="mine-title">Tu logro</h2>
          <ul className="ach-holders">
            {data.my_awards.map((a) => (
              <li key={a.id}>
                <strong>{a.detail ?? a.name}</strong>
                <span>
                  {a.event_at && `Pasó el ${day(a.event_at)}. `}
                  {a.recognized_at &&
                    `${a.backfilled ? "Reconocido retroactivamente" : "Reconocido"} el ${day(a.recognized_at)}.`}
                  {a.manual && a.reason ? ` Motivo: ${a.reason}` : ""}
                </span>
                {a.hidden && <small>Oculto en tu perfil público</small>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function AwardItem({ award }: { award: Award }) {
  return (
    <li className="ach-card" data-rarity={award.rarity}>
      <Link href={`/logros/${award.achievement_id}`}>
        <strong>{award.name}</strong>
      </Link>
      <span className="ach-desc">{award.detail}</span>
      <span className="ach-meta">
        <RarityTag rarity={award.rarity} />
        {award.source === "prode" && <span className="ach-flag">Prode</span>}
        {award.event_at && <small>{day(award.event_at)}</small>}
      </span>
    </li>
  );
}

export function ShowcaseBlock({
  showcase,
  title = "Vitrina",
}: {
  showcase: AchievementProfile["showcase"];
  title?: string;
}) {
  if (!showcase.items.length) return null;
  return (
    <section aria-labelledby="showcase-title" className="ach-showcase">
      <h2 id="showcase-title">{title}</h2>
      <ul className="ach-vitrina">
        {showcase.items.map((a) => (
          <li key={`${a.source}-${a.achievement_id}`} data-rarity={a.rarity}>
            <Link href={`/logros/${a.achievement_id}`}>
              <strong>{a.name}</strong>
            </Link>
            <RarityTag rarity={a.rarity} />
          </li>
        ))}
      </ul>
      {showcase.automatic && (
        <p className="ach-note">Elegidos automáticamente: los más raros.</p>
      )}
    </section>
  );
}

/** Player record: showcase, current states and achievements. Until the backend has
 * evaluated anything, `fallback` (the old badges) is shown instead. */
export function PlayerAchievementsBlock({
  id,
  fallback,
}: {
  id: string;
  fallback?: ReactNode;
}) {
  const { data, loading } = useLoad<AchievementProfile>(
    `achievements/players/${id}`,
  );
  if (loading) return null;
  // Only a well-formed answer with achievements replaces the old badges.
  if (
    !data ||
    !Array.isArray(data.achievements) ||
    !Array.isArray(data.prode) ||
    (data.achievements.length === 0 && data.prode.length === 0)
  )
    return <>{fallback}</>;
  const all = [...data.achievements];
  return (
    <>
      <ShowcaseBlock showcase={data.showcase} />
      {data.states && data.states.length > 0 && (
        <section aria-labelledby="states-title">
          <h2 id="states-title">Ahora mismo</h2>
          <ul className="badges">
            {data.states.map((s) => (
              <li key={s.achievement_id} data-tone="gold">
                <strong>{s.name}</strong>
                <span>{s.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section aria-labelledby="badges-title">
        <h2 id="badges-title">
          Logros <small>({all.length})</small>
        </h2>
        <ul className="ach-grid">
          {all.map((a) => (
            <AwardItem key={a.id} award={a} />
          ))}
        </ul>
        <p>
          <Link href="/logros">Ver todos los logros →</Link>
        </p>
      </section>
    </>
  );
}

/** Prode profile: the account's showcase, if it has achievements. */
export function UserShowcase({ id }: { id: string }) {
  const { data } = useLoad<AchievementProfile>(`achievements/users/${id}`);
  if (!data || !Array.isArray(data.showcase?.items)) return null;
  return <ShowcaseBlock showcase={data.showcase} />;
}

type Mine = {
  player_id: string | null;
  achievements: Award[];
  prode: Award[];
  showcase: {
    slot: number;
    achievement_id: string;
    source: "player" | "prode";
  }[];
};

function key(a: { source: string; achievement_id: string }) {
  return `${a.source}:${a.achievement_id}`;
}

/** Mi cuenta: the owner picks the showcase and hides achievements. */
export function MyAchievements() {
  const { data, loading, reload } = useLoad<Mine>("achievements/me");
  const [picked, setPicked] = useState<string[] | null>(null);
  const [message, setMessage] = useState("");
  if (loading) return <p role="status">Cargando…</p>;
  if (!data || !Array.isArray(data.achievements) || !Array.isArray(data.prode))
    return <Failed reload={reload} />;
  const all = [...data.achievements, ...data.prode];
  const unique = Array.from(new Map(all.map((a) => [key(a), a])).values());
  const chosen = picked ?? (data.showcase ?? []).map(key);
  if (unique.length === 0)
    return (
      <p className="seeding-lead">
        Todavía no tenés logros.{" "}
        {data.player_id
          ? "Aparecen cuando se procesan los resultados de tus torneos."
          : "Vinculá tu ficha de jugador o jugá un Prode para empezar."}{" "}
        <Link href="/logros">Ver el catálogo</Link>
      </p>
    );

  function toggle(k: string) {
    setMessage("");
    setPicked((now) => {
      const list = now ?? chosen;
      if (list.includes(k)) return list.filter((x) => x !== k);
      return list.length >= 3 ? list : [...list, k];
    });
  }

  async function save() {
    const items = chosen.map((k) => {
      const [source, achievement_id] = k.split(":");
      return { source, achievement_id };
    });
    const r = await apiFetch("achievements/me/showcase", {
      method: "PUT",
      body: JSON.stringify({ items }),
    }).catch(() => null);
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (!r.ok) return setMessage(await errorText(r));
    setMessage("Vitrina guardada.");
    setPicked(null);
    reload();
  }

  async function hide(a: Award, hidden: boolean) {
    const r = await apiFetch("achievements/me/visibility", {
      method: "PUT",
      body: JSON.stringify({
        source: a.source,
        achievement_id: a.achievement_id,
        hidden,
      }),
    }).catch(() => null);
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (!r.ok) return setMessage(await errorText(r));
    setMessage(hidden ? "Ocultado de tu perfil público." : "Visible otra vez.");
    reload();
  }

  return (
    <>
      <p className="seeding-lead">
        Elegí hasta 3 logros para tu vitrina ({chosen.length}/3). Se muestran en
        tu ficha y en tu perfil del Prode. También podés ocultar cualquiera de
        tu perfil público.
      </p>
      <ul className="ach-mine">
        {unique.map((a) => {
          const k = key(a);
          const position = chosen.indexOf(k);
          return (
            <li key={k} data-rarity={a.rarity}>
              <label>
                <input
                  type="checkbox"
                  checked={position >= 0}
                  disabled={position < 0 && chosen.length >= 3}
                  onChange={() => toggle(k)}
                />{" "}
                <strong>{a.name}</strong>
                {position >= 0 && <small> · lugar {position + 1}</small>}
              </label>
              <span>{a.detail}</span>
              <button
                type="button"
                className="link-button"
                onClick={() => hide(a, !a.hidden)}
              >
                {a.hidden ? "Mostrar en mi perfil" : "Ocultar de mi perfil"}
              </button>
            </li>
          );
        })}
      </ul>
      <p>
        <button className="primary-button" type="button" onClick={save}>
          Guardar vitrina
        </button>
      </p>
      {message && <p role="status">{message}</p>}
    </>
  );
}

/** /prode: what each Prode achievement asks for, from the catalog. */
export function ProdeAchievementsCatalog() {
  const { data } = useLoad<Catalog>("achievements/catalog");
  if (data && !Array.isArray(data.achievements)) return null;
  const prode = data?.achievements.filter(
    (a) => a.scope === "prode" && a.status !== "pending",
  );
  return (
    <section aria-labelledby="catalog-title">
      <h2 id="catalog-title">Logros</h2>
      {!prode ? (
        <p role="status">Cargando…</p>
      ) : (
        <ul className="ach-grid">
          {prode.map((a) => (
            <li key={a.id} className="ach-card" data-rarity={a.rarity}>
              <Link href={`/logros/${a.id}`}>
                <strong>{a.name}</strong>
              </Link>
              <span className="ach-desc">{a.condition ?? a.description}</span>
              <span className="ach-meta">
                <RarityTag rarity={a.rarity} />
                <StatLine stats={a.stats} />
              </span>
            </li>
          ))}
        </ul>
      )}
      <p>
        <Link href="/logros">Ver todos los logros de Smash Hub →</Link>
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- organizers

type AdminStatus = {
  auto: boolean;
  interval_seconds: number;
  catalog: { total: number; active: number; manual: number; pending: number };
  player_achievements: Record<string, number>;
  prode_achievements: Record<string, number>;
  subjects: {
    key: string;
    tag: string | null;
    startgg_player_id: string;
    consent_at: string | null;
    active: boolean;
    set_by: string;
  }[];
  runs: {
    id: string;
    trigger: string;
    actor: string;
    status: string;
    started_at: string;
    finished_at: string | null;
    counts: Record<string, number> | null;
    error: string | null;
  }[];
};
type Grants = {
  grants: {
    id: string;
    player_id: string;
    tag: string | null;
    achievement_id: string;
    name: string | null;
    status: string;
    reason: string | null;
    granted_by: string | null;
    revoked_reason: string | null;
  }[];
  manual: { id: string; name: string; available: boolean }[];
};

async function adminCall(
  admin: Admin,
  method: string,
  path: string,
  body?: unknown,
) {
  return fetch(`${api}/achievements/admin${path}`, {
    method,
    credentials: "include",
    headers: { ...adminHeaders(admin), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

const SUBJECTS: [string, string][] = [
  ["spike", "Régimen de Spike"],
  ["vbash", "Multiverso de vBash"],
];

/** /admin: engine status, recalculation, reference people and manual grants. */
export function AchievementsAdmin() {
  const admin = useAdmin();
  const me = useMe();
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [grants, setGrants] = useState<Grants | null>(null);
  const [message, setMessage] = useState("");
  const [tick, setTick] = useState(0);
  const [subject, setSubject] = useState({
    key: "spike",
    id: "",
    consent: false,
    active: false,
  });
  const [grant, setGrant] = useState({
    q: "",
    player: "",
    tag: "",
    id: "",
    reason: "",
  });
  const [found, setFound] = useState<{ id: string; tag: string }[]>([]);
  const running = status?.runs.some((r) => r.status === "running") ?? false;

  useEffect(() => {
    if (!admin) return;
    let active = true;
    Promise.all([
      adminCall(admin, "GET", "/status"),
      adminCall(admin, "GET", "/grants"),
    ])
      .then(async ([s, g]) => {
        if (!active) return;
        // Only well-formed answers are shown (an older API has no achievements).
        const status = s.ok ? ((await s.json()) as Partial<AdminStatus>) : null;
        if (status && Array.isArray(status.runs) && status.catalog)
          setStatus(status as AdminStatus);
        const grants = g.ok ? ((await g.json()) as Partial<Grants>) : null;
        if (
          grants &&
          Array.isArray(grants.grants) &&
          Array.isArray(grants.manual)
        )
          setGrants(grants as Grants);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [admin, tick]);

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setTick((t) => t + 1), 4000);
    return () => clearInterval(timer);
  }, [running]);

  async function send(
    method: string,
    path: string,
    body?: unknown,
    ok?: string,
  ) {
    if (!admin) return;
    setMessage("");
    const r = await adminCall(admin, method, path, body).catch(() => null);
    if (!r) return setMessage("No se pudo contactar a la API.");
    if (!r.ok) return setMessage(await errorText(r));
    if (ok) setMessage(ok);
    setTick((t) => t + 1);
  }

  async function search(q: string) {
    setGrant((g) => ({ ...g, q }));
    if (q.trim().length < 2) return setFound([]);
    const r = await apiFetch(
      `links/players?q=${encodeURIComponent(q.trim())}`,
    ).catch(() => null);
    if (r?.ok)
      setFound(((await r.json()) as { id: string; tag: string }[]).slice(0, 8));
  }

  if (!admin || !status) return null;
  const superadmin = me?.user?.role === "superadmin";
  return (
    <section className="seeding-admin ach-admin" aria-label="Logros">
      <h2>Logros</h2>
      <p>
        {status.catalog.total} en el catálogo: {status.catalog.active}{" "}
        automáticos, {status.catalog.manual} manuales y {status.catalog.pending}{" "}
        pendientes.{" "}
        {status.auto ? (
          <strong>La evaluación automática está encendida.</strong>
        ) : (
          <strong>
            La evaluación automática está apagada: solo se recalcula a mano.
          </strong>
        )}
      </p>
      <p>
        Logros de jugador activos: {status.player_achievements.active ?? 0}
        {status.player_achievements.revoked
          ? ` (revocados: ${status.player_achievements.revoked})`
          : ""}
        . Del Prode: {status.prode_achievements.active ?? 0}.
      </p>
      <p>
        <button
          className="primary-button"
          type="button"
          disabled={running}
          onClick={() =>
            send("POST", "/recalculate", undefined, "Recálculo iniciado.")
          }
        >
          {running ? "Recalculando…" : "Recalcular ahora"}
        </button>
      </p>
      {status.runs.length > 0 && (
        <ul className="sync-runs">
          {status.runs.slice(0, 5).map((r) => (
            <li key={r.id}>
              {day(r.started_at)} · {r.trigger} · {r.actor} ·{" "}
              <strong>{r.status}</strong>
              {r.counts &&
                ` · nuevos ${r.counts.added ?? 0}, revocados ${r.counts.revoked ?? 0}, restaurados ${r.counts.restored ?? 0}`}
              {r.error && ` · ${r.error}`}
            </li>
          ))}
        </ul>
      )}
      <h3>Personas de referencia</h3>
      <p className="seeding-lead">
        Las colecciones de Spike y vBash usan el ID de jugador de start.gg,
        nunca el nametag, y solo se activan con su consentimiento.
      </p>
      <ul>
        {SUBJECTS.map(([k, name]) => {
          const row = status.subjects.find((s) => s.key === k);
          return (
            <li key={k}>
              {name}:{" "}
              {row
                ? `${row.tag ?? "?"} (start.gg ${row.startgg_player_id}) · ${
                    row.consent_at ? "con consentimiento" : "sin consentimiento"
                  } · ${row.active ? "activa" : "inactiva"}`
                : "sin registrar"}
            </li>
          );
        })}
      </ul>
      {superadmin && (
        <form
          className="seeding-tools"
          onSubmit={(e) => {
            e.preventDefault();
            send(
              "PUT",
              `/subjects/${subject.key}`,
              {
                startgg_player_id: subject.id.trim(),
                consent: subject.consent,
                active: subject.active,
              },
              "Persona de referencia guardada.",
            );
          }}
        >
          <label>
            Colección{" "}
            <select
              value={subject.key}
              onChange={(e) => setSubject({ ...subject, key: e.target.value })}
            >
              {SUBJECTS.map(([k, name]) => (
                <option key={k} value={k}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            ID de jugador de start.gg{" "}
            <input
              inputMode="numeric"
              pattern="\d{1,20}"
              required
              value={subject.id}
              onChange={(e) => setSubject({ ...subject, id: e.target.value })}
            />
          </label>
          <label>
            <input
              type="checkbox"
              checked={subject.consent}
              onChange={(e) =>
                setSubject({ ...subject, consent: e.target.checked })
              }
            />{" "}
            Dio su consentimiento
          </label>
          <label>
            <input
              type="checkbox"
              checked={subject.active}
              onChange={(e) =>
                setSubject({ ...subject, active: e.target.checked })
              }
            />{" "}
            Activar la colección
          </label>
          <button className="primary-button" type="submit">
            Guardar
          </button>
        </form>
      )}
      <h3>Logros manuales</h3>
      <form
        className="seeding-tools"
        onSubmit={(e) => {
          e.preventDefault();
          send(
            "POST",
            "/grants",
            {
              player_id: grant.player,
              achievement_id: grant.id,
              reason: grant.reason,
            },
            "Logro otorgado.",
          );
        }}
      >
        <label>
          Jugador{" "}
          <input
            value={grant.q}
            onChange={(e) => search(e.target.value)}
            placeholder="Buscar por tag"
          />
        </label>
        {found.length > 0 && (
          <select
            aria-label="Elegir jugador"
            value={grant.player}
            onChange={(e) =>
              setGrant({
                ...grant,
                player: e.target.value,
                tag: found.find((f) => f.id === e.target.value)?.tag ?? "",
              })
            }
          >
            <option value="">Elegí…</option>
            {found.map((f) => (
              <option key={f.id} value={f.id}>
                {f.tag}
              </option>
            ))}
          </select>
        )}
        <label>
          Logro{" "}
          <select
            value={grant.id}
            required
            onChange={(e) => setGrant({ ...grant, id: e.target.value })}
          >
            <option value="">Elegí…</option>
            {grants?.manual.map((m) => (
              <option key={m.id} value={m.id} disabled={!m.available}>
                {m.name}
                {m.available ? "" : " (colección inactiva)"}
              </option>
            ))}
          </select>
        </label>
        <label>
          Motivo público{" "}
          <input
            required
            minLength={5}
            maxLength={500}
            value={grant.reason}
            onChange={(e) => setGrant({ ...grant, reason: e.target.value })}
          />
        </label>
        <button
          className="primary-button"
          type="submit"
          disabled={!grant.player}
        >
          Otorgar
        </button>
      </form>
      {grants && grants.grants.length > 0 && (
        <ul className="sync-runs">
          {grants.grants.map((g) => (
            <li key={g.id}>
              <Link href={`/players/${g.player_id}`}>{g.tag ?? "?"}</Link> ·{" "}
              {g.name} · {g.reason} · {g.granted_by}{" "}
              {g.status === "active" ? (
                <button
                  type="button"
                  className="link-button"
                  onClick={() => {
                    const reason = window.prompt("Motivo de la revocación");
                    if (reason)
                      send(
                        "POST",
                        `/grants/${g.id}/revoke`,
                        { reason },
                        "Logro revocado.",
                      );
                  }}
                >
                  Revocar
                </button>
              ) : (
                <em>revocado: {g.revoked_reason}</em>
              )}
            </li>
          ))}
        </ul>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
