import type { Metadata } from "next";
import { TeamPage } from "../../../components/teams";

type Props = { params: Promise<{ key: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { key } = await params;
  return { title: `Equipo ${decodeURIComponent(key).toUpperCase()}` };
}

export default async function Page({ params }: Props) {
  const { key } = await params;
  return <TeamPage teamKey={decodeURIComponent(key)} />;
}
