import { apiBase, shareImage, type Art } from "../../../../lib/og";
import { readUploads } from "../../../../lib/og-uploads";

type Top = {
  placement: number;
  tag: string;
  seed: number | null;
  mains?: { character: string; costume?: number }[];
};

type Params = { params: Promise<{ slug: string }> };

/** Top of a tournament still being read live from start.gg (Mission 27). */
export async function GET(request: Request, { params }: Params) {
  return liveImage(request, (await params).slug);
}

/** Same image with pictures uploaded by an organizer (form fields image-<row>). */
export async function POST(request: Request, { params }: Params) {
  const uploads = await readUploads(request);
  if (uploads instanceof Response) return uploads;
  return liveImage(request, (await params).slug, uploads);
}

async function liveImage(
  request: Request,
  slug: string,
  uploads?: Map<number, Art>,
) {
  const event = new URL(request.url).searchParams.get("event");
  const only = event && /^\d{1,12}$/.test(event) ? `?event=${event}` : "";
  const live = await fetch(
    `${apiBase(request)}/live/${encodeURIComponent(slug)}${only}`,
  )
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (!live?.top?.length)
    return new Response("Torneo sin posiciones", { status: 404 });
  const date = live.tournament.starts_at
    ? new Date(live.tournament.starts_at).toLocaleDateString("es-PY", {
        timeZone: "America/Asuncion",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : "";
  const players = `${live.event.entrants ?? "?"} jugadores`;
  return shareImage(request, {
    title: live.tournament.name,
    subtitle: `${players}${date ? `, ${date}` : ""}${live.final ? "" : " · parcial"}`,
    rows: (live.top as Top[]).slice(0, 12).map((t) => ({
      place: t.placement,
      tag: t.tag,
      main: t.mains?.[0]?.character,
      costume: t.mains?.[0]?.costume,
      detail: t.seed ? `seed ${t.seed}` : undefined,
    })),
    uploads,
  });
}
