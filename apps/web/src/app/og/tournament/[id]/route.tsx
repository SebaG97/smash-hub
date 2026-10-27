import { apiBase, shareImage } from "../../../../lib/og";

type Top = {
  placement: number;
  tag: string;
  seed: number | null;
  mains?: { character: string; costume?: number }[];
};

/** Top 12 of a tournament's main event. */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const api = apiBase(request);
  const get = (path: string) =>
    fetch(`${api}/${path}`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
  const [tournament, summary] = await Promise.all([
    get(`tournaments/${encodeURIComponent(id)}`),
    get(`insights/tournaments/${encodeURIComponent(id)}?limit=12`),
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
    title: tournament.name,
    subtitle: `${summary.entrants ?? "?"} jugadores${date ? `, ${date}` : ""}`,
    rows: (summary.top as Top[]).map((t) => ({
      place: t.placement,
      tag: t.tag,
      main: t.mains?.[0]?.character,
      costume: t.mains?.[0]?.costume,
      detail: t.seed ? `seed ${t.seed}` : undefined,
    })),
  });
}
