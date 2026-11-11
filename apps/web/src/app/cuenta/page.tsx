import { AccountPage } from "../../components/account";

export const metadata = { title: "Mi cuenta", robots: { index: false } };

export default function Page() {
  return (
    <div className="competition-page account-page">
      <h1>Mi cuenta</h1>
      <AccountPage />
    </div>
  );
}
