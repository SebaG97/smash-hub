import { notFound } from "next/navigation";
import { ProdeProfile } from "../../../../components/prode";

export const metadata = { title: "Perfil del Prode" };

type Props = { params: Promise<{ id: string }> };

export default async function Page({ params }: Props) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  return <ProdeProfile id={id} />;
}
