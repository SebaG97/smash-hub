"use client";

import Link from "next/link";
import { useState } from "react";
import type { Entrant, Event, Page } from "../lib/api";
import { BracketView, type Bracket } from "./bracket";
import { Collection, Resource } from "./competition-browser";
import { EventSets } from "./event-sets";
import { TournamentSummaryBlock } from "./insights";
import { MainEventFlag } from "./mains";

/** Tournament page: one tab per event, and inside it summary, sets, bracket, players. */

const VIEWS = [
  ["resumen", "Resumen"],
  ["sets", "Sets"],
  ["bracket", "Bracket"],
  ["participantes", "Participantes"],
] as const;
type View = (typeof VIEWS)[number][0];

/** Main bracket first, then the biggest events. */
export function orderEvents(events: Event[]) {
  return [...events].sort(
    (a, b) =>
      Number(b.main === true) - Number(a.main === true) ||
      Number(a.team_size !== 1) - Number(b.team_size !== 1) ||
      b.entrant_count - a.entrant_count ||
      a.name.localeCompare(b.name),
  );
}

function kind(e: Event) {
  if (e.team_size !== 1) return `Equipos de ${e.team_size}`;
  if (e.main === true) return "Principal";
  if (e.main === false) return "Secundario";
  return "Individual";
}

/** ?evento=<id>&vista=sets, so a tab can be shared and survives a reload. */
function readUrl() {
  if (typeof window === "undefined") return { event: null, view: null };
  const params = new URLSearchParams(window.location.search);
  return { event: params.get("evento"), view: params.get("vista") };
}

function writeUrl(event: string, view: View) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  url.searchParams.set("evento", event);
  url.searchParams.set("vista", view);
  window.history.replaceState(null, "", url);
}

export function TournamentEvents({
  id,
  reliable = true,
}: {
  id: string;
  /** Seeds organizers trust: upsets are only marked when they do. */
  reliable?: boolean;
}) {
  return (
    <Resource<Page<Event>> path={`tournaments/${id}/events?page_size=100`}>
      {(page) =>
        page.items.length ? (
          <EventTabs
            id={id}
            events={orderEvents(page.items)}
            reliable={reliable}
          />
        ) : (
          <p className="seeding-lead">Este torneo no tiene eventos cargados.</p>
        )
      }
    </Resource>
  );
}

export function EventTabs({
  id,
  events,
  reliable,
}: {
  id: string;
  events: Event[];
  reliable: boolean;
}) {
  // Mounted in the browser only, once the events loaded: the URL is there to read.
  const [event, setEvent] = useState(() => {
    const wanted = readUrl().event;
    return events.some((e) => e.id === wanted) ? wanted! : events[0].id;
  });
  const [view, setView] = useState<View>(() => {
    const wanted = readUrl().view;
    return VIEWS.some(([key]) => key === wanted) ? (wanted as View) : "resumen";
  });
  const current = events.find((e) => e.id === event) ?? events[0];
  const go = (next: string, nextView: View) => {
    setEvent(next);
    setView(nextView);
    writeUrl(next, nextView);
  };
  return (
    <section className="tournament-events" aria-label="Eventos del torneo">
      {events.length > 1 && (
        <div className="event-tabs" role="tablist" aria-label="Eventos">
          {events.map((e) => (
            <button
              key={e.id}
              type="button"
              role="tab"
              aria-selected={e.id === current.id}
              onClick={() => go(e.id, view)}
            >
              {e.name}
              <small>
                {kind(e)} · {e.entrant_count}{" "}
                {e.team_size === 1 ? "jugadores" : "equipos"}
              </small>
            </button>
          ))}
        </div>
      )}
      <header className="event-head">
        <h2>{current.name}</h2>
        <p className="seeding-lead">
          {current.game} · {kind(current)} · {current.entrant_count}{" "}
          {current.team_size === 1 ? "jugadores" : "equipos"} ·{" "}
          <Link href={`/events/${current.id}`}>Página del evento</Link>
        </p>
        <MainEventFlag key={current.id} event={current} />
      </header>
      <div className="tabs" role="tablist" aria-label="Secciones del evento">
        {VIEWS.map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`tab-${key}`}
            aria-selected={view === key}
            aria-controls={`panel-${key}`}
            onClick={() => go(current.id, key)}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
        {view === "resumen" &&
          (current.team_size === 1 ? (
            <SinglesSummary
              id={id}
              event={current}
              onSets={() => go(current.id, "sets")}
            />
          ) : (
            <Standings event={current} />
          ))}
        {view === "sets" && (
          <EventSets
            key={current.id}
            eventId={current.id}
            reliable={reliable}
          />
        )}
        {view === "bracket" && (
          <BracketOrNotice key={current.id} eventId={current.id} />
        )}
        {view === "participantes" && (
          <Entrants key={current.id} event={current} />
        )}
      </div>
    </section>
  );
}

function SinglesSummary({
  id,
  event,
  onSets,
}: {
  id: string;
  event: Event;
  onSets: () => void;
}) {
  return (
    <>
      <TournamentSummaryBlock
        key={event.id}
        id={id}
        event={event.id}
        embedded
      />
      <p>
        <button type="button" className="link-button" onClick={onSets}>
          Ver todos los sets, ronda por ronda →
        </button>
      </p>
    </>
  );
}

/** Teams (and events without a singles summary): final placements. */
function Standings({ event }: { event: Event }) {
  return (
    <Resource<Page<Entrant>> path={`events/${event.id}/entrants?page_size=100`}>
      {(page) => {
        const placed = page.items
          .filter((e) => e.placement)
          .sort((a, b) => a.placement! - b.placement!)
          .slice(0, 8);
        return placed.length ? (
          <ol className="standings">
            {placed.map((e) => (
              <li key={e.id}>
                <span className="place">{e.placement}</span>
                <span>
                  {e.name}
                  {e.members.length > 1 && (
                    <small>
                      {" "}
                      {e.members.map((m, i) => (
                        <span key={m.player_id}>
                          {i > 0 && " / "}
                          <Link href={`/players/${m.player_id}`}>{m.tag}</Link>
                        </span>
                      ))}
                    </small>
                  )}
                </span>
                <small>seed {e.seed ?? "–"}</small>
              </li>
            ))}
          </ol>
        ) : (
          <p className="seeding-lead">Todavía no hay posiciones finales.</p>
        );
      }}
    </Resource>
  );
}

function BracketOrNotice({ eventId }: { eventId: string }) {
  return (
    <Resource<Bracket>
      path={`events/${eventId}/bracket`}
      notFound={
        <p className="seeding-lead">Este evento no tiene bracket cargado.</p>
      }
    >
      {(b) => <BracketView bracket={b} />}
    </Resource>
  );
}

function Entrants({ event }: { event: Event }) {
  return (
    <Collection<Entrant>
      title={event.team_size === 1 ? "Jugadores" : "Equipos"}
      path={`events/${event.id}/entrants`}
      search
      render={(entrant) => (
        <>
          <h3>
            {entrant.members.length === 1 ? (
              <Link href={`/players/${entrant.members[0].player_id}`}>
                {entrant.name}
              </Link>
            ) : (
              entrant.name
            )}
          </h3>
          <p>
            {entrant.placement
              ? `Terminó ${entrant.placement}.º`
              : "Sin posición final"}
            {entrant.seed ? ` · seed ${entrant.seed}` : ""}
          </p>
          {entrant.members.length > 1 && (
            <ul>
              {entrant.members.map((m) => (
                <li key={m.player_id}>
                  <Link href={`/players/${m.player_id}`}>{m.tag}</Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    />
  );
}
