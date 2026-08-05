import { useEffect, useState } from "react";
import { Footer } from "./components/layout/Footer";
import { Header } from "./components/layout/Header";
import type { Screen } from "./lib/navigation";
import { AlertasPage } from "./pages/AlertasPage";
import { FichaPage } from "./pages/FichaPage";
import { MapaPage } from "./pages/MapaPage";

export default function App() {
  const [screen, setScreen] = useState<Screen>("mapa");
  const [dark, setDark] = useState(false);
  const [comunidadFiltro, setComunidadFiltro] = useState<string | undefined>(undefined);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  const goFicha = () => setScreen("ficha");
  const goTimeline = (comunidad?: string) => {
    setComunidadFiltro(comunidad);
    setScreen("alertas");
  };

  return (
    <div className="min-h-screen bg-bg text-ink">
      <Header screen={screen} onNav={setScreen} dark={dark} onToggleTheme={() => setDark((v) => !v)} />

      {screen === "mapa" && <MapaPage onGoFicha={goFicha} onGoTimeline={goTimeline} />}
      {screen === "alertas" && <AlertasPage comunidadInicial={comunidadFiltro} onVerFicha={goFicha} />}
      {screen === "ficha" && <FichaPage onGoTimeline={() => goTimeline(undefined)} />}

      <Footer />
    </div>
  );
}
