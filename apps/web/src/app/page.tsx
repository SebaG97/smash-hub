import { HomeBoard } from "../components/home-board";
import { HomeSpotlight } from "../components/home-spotlight";
import { LiveMatches, LiveNotice } from "../components/live";
import { Logo } from "../components/logo";
import { HomeInstallCard } from "../components/pwa";

export default function Home() {
  return (
    <div className="home">
      <section className="home-intro">
        <Logo size={150} />
        <div>
          <h1>Smash Club Paraguay</h1>
          <p>
            Ranking, torneos y mains de la escena de Smash Ultimate en Paraguay.
            Los resultados salen de start.gg después de cada torneo.
          </p>
        </div>
      </section>
      <LiveNotice />
      <LiveMatches />
      <HomeInstallCard />
      <HomeSpotlight />
      <HomeBoard />
    </div>
  );
}
