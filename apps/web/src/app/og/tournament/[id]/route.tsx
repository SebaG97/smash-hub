import { apiBase, shareImage, type Art } from "../../../../lib/og";
import { readUploads } from "../../../../lib/og-uploads";

type Top = {
  placement: number;
  tag: string;
  seed: number | null;
  mains?: { character: string; costume?: number }[];
};

type Params = { params: Promise<{ id: string }> };

/** Top 12 of a tournament's main event. */
export async function GET(request: Request, { params }: Params) {
  return tournamentImage(request, (await params).id);
}

/** Same image with pictures uploaded by an organizer (form fields image-<row>). */
export async function POST(request: Request, { params }: Params) {
  const uploads = await readUploads(request);
  if (uploads instanceof Response) return uploads;
  return tournamentImage(request, (await params).id, uploads);
}

async function tournamentImage(
  request: Request,
  id: string,
  uploads?: Map<number, Art>,
) {
  const api = apiBase(request);
  // One event of the tournament (Mission 20); its main one when not given.
  const event = new URL(request.url).searchParams.get("event");
  const only = event && /^[0-9a-f-]{36}$/i.test(event) ? `&event=${event}` : "";
  const get = (path: string) =>
    fetch(`${api}/${path}`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  const [tournament, summary] = await Promise.all([
    get(`tournaments/${encodeURIComponent(id)}`),
    get(`insights/tournaments/${encodeURIComponent(id)}?limit=12${only}`),
  ]);
  if (!tournament || !summary)
    return new Response("Torneo sin resultados", { status: 404 });
  const date = tournament.starts_at
    ? new Date(tournament.starts_at).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";
  return shareImage(request, {
    title:
      summary.main === false && summary.event
        ? `${tournament.name} · ${summary.event}`
        : tournament.name,
    subtitle: `${summary.entrants ?? "?"} jugadores${date ? `, ${date}` : ""}`,
    rows: (summary.top as Top[]).map((t) => ({
      place: t.placement,
      tag: t.tag,
      main: t.mains?.[0]?.character,
      costume: t.mains?.[0]?.costume,
      detail: t.seed ? `seed ${t.seed}` : undefined,
    })),
    uploads,
  });
}
