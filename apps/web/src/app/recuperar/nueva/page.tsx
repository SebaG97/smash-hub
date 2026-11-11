import { ResetForm } from "../../../components/account";

export const metadata = {
  title: "Contraseña nueva",
  robots: { index: false },
  // The link carries a one-time token: never send it anywhere as a referrer.
  referrer: "no-referrer" as const,
};

export default function Page() {
  return (
    <div className="competition-page account-page">
      <h1>Contraseña nueva</h1>
      <ResetForm />
    </div>
  );
}
