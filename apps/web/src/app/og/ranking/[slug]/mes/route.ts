import { apiBase } from "../../../../../lib/og";
import {
  highlights,
  monthlyRankingImage,
  type Monthly,
  type MonthlyRow,
} from "../../../../../lib/og-monthly";

type Params = { params: Promise<{ slug: string }> };

function day(value: string) {
  return new Date(value).toLocaleDateString("es-PY", {
    timeZone: "America/Asuncion",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** The whole ranking at the end of a month (?month=YYYY-MM), for social media. */
export async function GET(request: Request, { params }: Params) {
  const { slug } = await params;
  const month = new URL(request.url).searchParams.get("month");
  const query = month && /^\d{4}-\d{2}$/.test(month) ? `?month=${month}` : "";
  const d: Monthly | null = await fetch(
    `${apiBase(request)}/seeding/${encodeURIComponent(slug)}/monthly${query}`,
  )
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null);
  if (!d) return new Response("Ranking sin datos", { status: 404 });
  const rows: MonthlyRow[] = d.rows.map((r) => ({
    place: r.place,
    change: r.change,
    new: r.new,
    tag: r.gamer_tag,
    prefix: r.prefix,
    main: r.mains?.[0]?.character,
    wins: r.wins,
    losses: r.losses,
  }));
  return monthlyRankingImage({
    title: d.name,
    label: `Al cierre de ${d.label}`,
    requirements: `Torneos presenciales del ${day(d.window_start)} al ${day(
      d.window_end,
    )} (${d.events}) · mínimo ${d.min_sets} sets · método ${d.method_label}`,
    highlights: highlights(d, rows),
    rows,
  });
}
