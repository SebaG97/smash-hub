"use client";

import Link from "next/link";
import { Resource } from "./competition-browser";
import type { CalendarItem } from "./insights";
import { TournamentLogo } from "./tournament-art";

/* /previas (Mission SH-UI-01): every upcoming tournament with its previa. Same data as
   the home calendar (insights/calendar); the previa itself stays on /previa/[slug]. */

function when(iso: string | null) {
  if (!iso) return "Fecha a confirmar";
  const day = new Date(iso).toLocaleDateString("es-PY", {
    timeZone: "America/Asuncion",
    weekday: "short",
    day: "numeric",
    month: "short",
  });
  return day.charAt(0).toUpperCase() + day.slice(1);
}

function PreviewCard({ t }: { t: CalendarItem }) {
  const place = [t.venue, t.city].filter(Boolean).join(", ");
  return (
    <li className="previews-card">
      <TournamentLogo images={t.images} size={44} />
      <div>
        <h2>
          {t.slug ? (
            <Link href={`/previa/${t.slug}`}>{t.name}</Link>
          ) : (
            <a href={t.url} target="_blank" rel="noreferrer">
              {t.name}
            </a>
          )}
        </h2>
        <p>
          <time dateTime={t.starts_at ?? undefined}>{when(t.starts_at)}</time>
          {place && ` · ${place}`}
          {t.attendees ? ` · ${t.attendees} inscritos` : ""}
        </p>
      </div>
      {t.slug && (
        <Link
          className="secondary-button"
          href={`/previa/${t.slug}`}
          aria-label={`Ver la previa de ${t.name}`}
        >
          Ver previa →
        </Link>
      )}
    </li>
  );
}

export function PreviewsList() {
  return (
    <div className="competition-page previews-page">
      <h1>Previas</h1>
      <p className="seeding-lead">
        Los próximos torneos de Smash Ultimate en Paraguay anunciados en
        start.gg. Cada previa muestra inscritos, favoritos, el Prode y el
        reglamento cuando el torneo lo tiene.
      </p>
      {/* start.gg can be slow on a cold cache. */}
      <Resource<{ items: CalendarItem[]; unavailable?: boolean }>
        path="insights/calendar"
        timeout={20000}
      >
        {(d) =>
          d.items.length ? (
            <ul className="previews-list">
              {d.items.map((t) => (
                <PreviewCard key={t.url} t={t} />
              ))}
            </ul>
          ) : d.unavailable ? (
            <p role="alert">
              start.gg no respondió. Probá de nuevo en unos minutos.
            </p>
          ) : (
            <p>
              No hay torneos anunciados por ahora. Mirá los{" "}
              <Link href="/tournaments">torneos anteriores</Link>.
            </p>
          )
        }
      </Resource>
    </div>
  );
}
