import { LinkAdmin } from "../../../components/admin-accounts";

export const metadata = { title: "Vinculaciones", robots: { index: false } };

export default function Page() {
  return (
    <div className="competition-page account-page">
      <h1>Vinculaciones de jugadores</h1>
      <LinkAdmin />
    </div>
  );
}
