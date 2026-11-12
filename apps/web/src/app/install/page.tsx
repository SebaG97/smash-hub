import type { Metadata } from "next";
import { InstallGuide } from "../../components/pwa";

export const metadata: Metadata = {
  title: "Instalar Smash Hub",
  description:
    "Instalá Smash Hub en tu celular o computadora desde el navegador, sin descargar un APK.",
  alternates: { canonical: "/install" },
};

export default function InstallPage() {
  return <InstallGuide />;
}
