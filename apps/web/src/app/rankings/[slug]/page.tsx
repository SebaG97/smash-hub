import { SeedingBoard } from "../../../components/seeding-board";
export const metadata = { title: "Ranking" };
export default async function Page({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <SeedingBoard slug={slug} base="rankings" />;
}
