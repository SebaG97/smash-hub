import { ProdePage } from "../../components/prode";

export const metadata = {
  title: "Prode",
  description:
    "Pronósticos de los torneos de Smash de Paraguay, con logros como premio.",
};

type Props = { searchParams: Promise<{ ingreso?: string }> };

export default async function Page({ searchParams }: Props) {
  // Sign-in problems come back from the API as ?ingreso=<reason>.
  const { ingreso } = await searchParams;
  return <ProdePage problem={ingreso ?? null} />;
}
