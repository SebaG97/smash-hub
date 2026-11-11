import { UserAdmin } from "../../../components/admin-accounts";

export const metadata = { title: "Usuarios y roles", robots: { index: false } };

export default function Page() {
  return (
    <div className="competition-page account-page">
      <h1>Usuarios y roles</h1>
      <UserAdmin />
    </div>
  );
}
