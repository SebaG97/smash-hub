import type { Metadata } from "next";
import {
  TournamentPreviewPage,
  type TournamentPreview,
} from "../../../components/tournament-preview";
import { apiJson, preview } from "../../../lib/previews";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const d = await apiJson<TournamentPreview>(
    `insights/upcoming/${encodeURIComponent(slug)}`,
  );
  if (!d) return { title: "Previa" };
  const favorites = d.favorites.map((p) => p.tag).join(", ");
  return preview({
    title: `Previa: ${d.tournament.name}`,
    description: `${d.event?.entrants ?? 0} inscritos.${favorites ? ` Favoritos: ${favorites}.` : ""}`,
    path: `/previa/${slug}`,
    // The start.gg banner when the tournament has one (1600×800), else the club logo.
    ...(d.tournament.images?.banner
      ? {
          image: d.tournament.images.banner,
          size: { width: 1600, height: 800 },
        }
      : { image: "/smashclublogo.jpg", square: true }),
  });
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  return <TournamentPreviewPage slug={slug} />;
}
