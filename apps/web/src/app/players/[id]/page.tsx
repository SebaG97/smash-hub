import type { Metadata } from "next";
import { PlayerPage } from "../../../components/competition-browser";
import type { PlayerDetail } from "../../../lib/api";
import { apiJson, placeText, preview } from "../../../lib/previews";

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const p = await apiJson<PlayerDetail>(`players/${encodeURIComponent(id)}`);
  if (!p) return { title: "Jugador" };
  const parts = [
    p.ranking && `${placeText(p.ranking.place)} en ${p.ranking.name}`,
    p.mains?.length &&
      `juega ${p.mains
        .slice(0, 2)
        .map((m) => m.character)
        .join(" y ")}`,
    p.best_results?.[0] &&
      `mejor resultado: ${placeText(p.best_results[0].placement)} en ${p.best_results[0].tournament_name}`,
  ].filter(Boolean);
  return preview({
    title: p.tag,
    description: parts.length
      ? `${parts.join(", ")}.`
      : "Jugador de la escena de Smash Ultimate en Paraguay.",
    path: `/players/${id}`,
    image: `/og/player/${id}`,
  });
}

export default async function Page({ params }: Props) {
  const { id } = await params;
  return <PlayerPage id={id} />;
}
