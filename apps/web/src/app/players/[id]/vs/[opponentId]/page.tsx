import { HeadToHeadPage } from "../../../../../components/player-statistics";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ id: string; opponentId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id, opponentId } = await params;
  const query = await searchParams;
  const value = (key: string) =>
    typeof query[key] === "string" ? (query[key] as string) : undefined;
  return (
    <HeadToHeadPage
      id={id}
      opponentId={opponentId}
      initialGame={value("game_id")}
      initialMode={value("mode")}
      initialFrom={value("date_from")}
      initialTo={value("date_to")}
    />
  );
}
