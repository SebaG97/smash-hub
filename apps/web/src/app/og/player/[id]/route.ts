import type { PlayerDetail, Statistics } from "../../../../lib/api";
import type { PlayerInsights } from "../../../../components/insights";
import { playerCard } from "../../../../lib/og";
import { apiBase } from "../../../../lib/origin";

/** Player card for link previews and sharing. */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const id = encodeURIComponent((await params).id);
  const api = apiBase(request);
  const get = <T>(path: string) =>
    fetch(`${api}/${path}`)
      .then((r) => (r.ok ? (r.json() as Promise<T>) : null))
      .catch(() => null);
  const player = await get<PlayerDetail>(`players/${id}`);
  if (!player) return new Response("Jugador no encontrado", { status: 404 });
  const singles = player.scopes?.find((s) => s.mode === "singles");
  const [stats, insights] = await Promise.all([
    singles
      ? get<Statistics>(
          `players/${id}/statistics?game_id=${singles.game_id}&mode=singles`,
        )
      : null,
    get<PlayerInsights>(`insights/players/${id}`),
  ]);
  const best = player.best_results?.[0];
  return playerCard({
    tag: player.tag,
    main: player.mains?.[0]?.character,
    costume: player.mains?.[0]?.costume,
    ranking: player.ranking,
    wins: stats?.wins,
    losses: stats?.losses,
    badges: insights?.badges.map((b) => b.name) ?? [],
    best: best && {
      placement: best.placement,
      tournament: best.tournament_name,
      entrants: best.entrants,
    },
  });
}
