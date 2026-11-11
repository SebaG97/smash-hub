import { SignInForm } from "../../components/account";

export const metadata = { title: "Ingresar", robots: { index: false } };

type Props = { searchParams: Promise<{ next?: string }> };

export default async function Page({ searchParams }: Props) {
  const { next } = await searchParams;
  return (
    <div className="competition-page account-page">
      <h1>Ingresar</h1>
      <p className="seeding-lead">
        Con tu cuenta de Smash Hub jugás el Prode y, si organizás, usás las
        herramientas de administración.
      </p>
      <SignInForm next={next} />
    </div>
  );
}
