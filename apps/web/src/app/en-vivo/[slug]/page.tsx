import type { Metadata } from "next";
import { LivePage } from "../../../components/live";

type Props = { params: Promise<{ slug: string }> };

export const metadata: Metadata = {
  title: "En vivo",
  description: "Bracket y posiciones del torneo mientras se juega.",
};

export default async function Page({ params }: Props) {
  const { slug } = await params;
  return <LivePage slug={slug} />;
}
