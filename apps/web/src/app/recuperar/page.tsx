import { ForgotForm } from "../../components/account";

export const metadata = {
  title: "Recuperar contraseña",
  robots: { index: false },
};

export default function Page() {
  return (
    <div className="competition-page account-page">
      <h1>Recuperar contraseña</h1>
      <ForgotForm />
    </div>
  );
}
