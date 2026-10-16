import { EventPage } from "../../../components/competition-browser";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EventPage id={id} />;
}
