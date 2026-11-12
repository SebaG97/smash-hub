import { notFound } from "next/navigation";
import { AchievementDetailPage } from "../../../components/achievements";

export const metadata = { title: "Logro" };

type Props = { params: Promise<{ id: string }> };

export default async function Page({ params }: Props) {
  const { id } = await params;
  if (!/^[a-z0-9_]{1,40}$/.test(id)) notFound();
  return <AchievementDetailPage id={id} />;
}
