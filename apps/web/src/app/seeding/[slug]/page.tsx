import type { Metadata } from "next";
import { SeedingBoard } from "../../../components/seeding-board";
import type { PublicSeedingView } from "../../../lib/api";
import { apiJson, preview } from "../../../lib/previews";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  // Without the key the API only answers for published views.
  const view = await apiJson<PublicSeedingView>(
    `seeding/${encodeURIComponent(slug)}`,
  );
  if (!view?.public) return { title: "Seeding" };
  const top = view.seeds
    .slice(0, 3)
    .map((s) => `${s.seed}. ${s.gamer_tag}`)
    .join(", ");
  return preview({
    title: view.name,
    description: `${top}. ${view.seeds.length} jugadores.`,
    path: `/seeding/${slug}`,
    image: `/og/seeding/${slug}`,
    square: true,
  });
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  return <SeedingBoard slug={slug} />;
}
