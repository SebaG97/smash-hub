import { RegisterForm } from "../../components/account";

export const metadata = { title: "Crear cuenta", robots: { index: false } };

type Props = { searchParams: Promise<{ next?: string }> };

export default async function Page({ searchParams }: Props) {
  const { next } = await searchParams;
  return (
    <div className="competition-page account-page">
      <h1>Crear cuenta</h1>
      <p className="seeding-lead">
        Gratis. No hace falta ser jugador: cualquiera puede jugar el Prode. Si
        competís, después podés pedir que vinculemos tu cuenta con tu ficha.
      </p>
      <RegisterForm next={next} />
    </div>
  );
}
