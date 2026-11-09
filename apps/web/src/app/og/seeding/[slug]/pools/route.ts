import type { SeedingView } from "../../../../../lib/api";
import type { Pools } from "../../../../../components/pool-board";
import { adminJson } from "../../../../../lib/og-admin";
import { poolsImage } from "../../../../../lib/og-seeding-list";

type Params = { params: Promise<{ slug: string }> };

/** Organizers: every start.gg pool with its players in order (1920×1080). */
export async function POST(request: Request, { params }: Params) {
  const slug = encodeURIComponent((await params).slug);
  const [view, pools] = await Promise.all([
    adminJson<SeedingView>(request, `seeding/${slug}`),
    adminJson<Pools>(request, `seeding/${slug}/pools`),
  ]);
  if (view instanceof Response) return view;
  if (pools instanceof Response) return pools;
  const players = pools.pools.reduce((n, p) => n + p.players.length, 0);
  return poolsImage({
    title: view.name,
    subtitle: `${pools.phase} · ${players} jugadores en ${pools.pools.length} pools`,
    pools: pools.pools.map((p) => ({
      name: p.name,
      rows: p.players.map((x) => ({
        seed: x.seed,
        pool_seed: x.pool_seed,
        tag: x.tag,
        prefix: x.prefix,
        main: x.mains?.[0]?.character,
        circuit: x.circuit,
      })),
    })),
  });
}
