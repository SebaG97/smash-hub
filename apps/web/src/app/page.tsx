import { BackendStatus } from "../components/backend-status";
import { HomeBoard } from "../components/home-board";
import { HomeSpotlight } from "../components/home-spotlight";
import { Logo } from "../components/logo";

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
      <HomeSpotlight />
      <HomeBoard />
      <div className="home-status">
        <BackendStatus />
      </div>
    </div>
  );
}
