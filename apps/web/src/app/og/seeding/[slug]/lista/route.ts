import type { SeedingView } from "../../../../../lib/api";
import { adminJson } from "../../../../../lib/og-admin";
import { seedListImage } from "../../../../../lib/og-seeding-list";

type Params = { params: Promise<{ slug: string }> };

/** Organizers: the top seeds as a list (?top=32), published or not. */
export async function POST(request: Request, { params }: Params) {
  const slug = encodeURIComponent((await params).slug);
  const view = await adminJson<SeedingView>(request, `seeding/${slug}`);
  if (view instanceof Response) return view;
  const asked = Number(new URL(request.url).searchParams.get("top") || 32);
  const top = Math.min(Math.max(Number.isFinite(asked) ? asked : 32, 4), 64);
  const rows = view.seeds.slice(0, top);
  if (!rows.length) return new Response("Sin seeds", { status: 404 });
  return seedListImage({
    title: view.name,
    subtitle:
      view.seeds.length > rows.length
        ? `Seeding · top ${rows.length} de ${view.seeds.length} jugadores`
        : `Seeding · ${rows.length} jugadores`,
    rows: rows.map((s) => ({
      seed: s.seed,
      tag: s.gamer_tag,
      prefix: s.prefix,
      main: s.mains?.[0]?.character,
      circuit: s.country ?? s.main_circuit,
    })),
  });
}
