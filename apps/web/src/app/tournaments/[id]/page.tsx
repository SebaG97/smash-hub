import type { Metadata } from "next";
import { TournamentPage } from "../../../components/competition-browser";
import { apiJson, preview } from "../../../lib/previews";

type Props = { params: Promise<{ id: string }> };
type Summary = { entrants: number | null; top: { tag: string | null }[] };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const key = encodeURIComponent(id);
  const [t, summary] = await Promise.all([
    apiJson<{ name: string }>(`tournaments/${key}`),
    apiJson<Summary>(`insights/tournaments/${key}?limit=3`),
  ]);
  if (!t) return { title: "Torneo" };
  const podium = summary?.top.map((p) => p.tag).filter(Boolean) ?? [];
  return preview({
    title: t.name,
    description: podium.length
      ? `Ganó ${podium[0]}${podium.length > 1 ? `; podio: ${podium.join(", ")}` : ""}. ${summary?.entrants ?? "?"} jugadores.`
      : "Resultados del torneo en Smash Club Paraguay.",
    path: `/tournaments/${id}`,
    image: summary ? `/og/tournament/${id}` : "/smashclublogo.jpg",
    square: true,
  });
}

export default async function Page({ params }: Props) {
  const { id } = await params;
  return <TournamentPage id={id} />;
}
