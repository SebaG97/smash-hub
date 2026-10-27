import { Players } from "../../components/competition-browser";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams;
  return <Players initialQuery={(q ?? "").slice(0, 120)} />;
}
