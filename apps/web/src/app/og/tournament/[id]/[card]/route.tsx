import { apiBase } from "../../../../../lib/og";
import { tournamentCard } from "../../../../../lib/og-tournament";
import {
  cardOf,
  isFormat,
  MISSING,
  type Social,
} from "../../../../../lib/tournament-social";

type Params = { params: Promise<{ id: string; card: string }> };

const UUID = /^[0-9a-f-]{36}$/i;

/**
 * One social media image of a tournament (SH-SOCIAL-01): ?format=portrait|square|story|wide,
 * ?event= for another singles bracket and ?under=1 to add who finished below their seed.
 */
export async function GET(request: Request, { params }: Params) {
  const { id, card } = await params;
  const chosen = cardOf(card);
  if (!chosen || !UUID.test(id))
    return new Response("Imagen desconocida", { status: 404 });
  const query = new URL(request.url).searchParams;
  const format = query.get("format");
  const event = query.get("event");
  const only = event && UUID.test(event) ? `?event=${event}` : "";
  const data: Social | null = await fetch(
    `${apiBase(request)}/insights/tournaments/${id}/social${only}`,
  )
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (!data) return new Response("Torneo sin resultados", { status: 404 });
  if (!chosen.has(data))
    return new Response(MISSING[chosen.key], {
      status: 404,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  return tournamentCard(
    data,
    chosen.key,
    chosen.title,
    isFormat(format) ? format : "portrait",
    { under: query.get("under") === "1" },
  );
}
