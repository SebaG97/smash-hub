import { CountryAdmin } from "../../../components/flag-picker";

export const metadata = { title: "Nacionalidades", robots: { index: false } };

export default function Page() {
  return (
    <div className="competition-page">
      <h1>Nacionalidades de los jugadores</h1>
      <CountryAdmin />
    </div>
  );
}
