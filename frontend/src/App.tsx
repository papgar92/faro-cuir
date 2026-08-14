import { useEffect, useState } from "react";
import { Footer } from "./components/layout/Footer";
import { Header } from "./components/layout/Header";
import { PANTALLAS_CON_MOCK, type Screen, type SeleccionNorma } from "./lib/navigation";
import { AlertasPage } from "./pages/AlertasPage";
import { ArchivoPage } from "./pages/ArchivoPage";
import { FichaPage } from "./pages/FichaPage";
import { MapaPage } from "./pages/MapaPage";
import { RevisionPage } from "./pages/RevisionPage";

export default function App() {
  const [screen, setScreen] = useState<Screen>("mapa");
  const [dark, setDark] = useState(false);
  const [comunidadFiltro, setComunidadFiltro] = useState<string | undefined>(undefined);
  // Qué norma real está viendo la Ficha. Null mientras no se haya elegido ninguna: la Ficha
  // lee de la API y no tiene nada que pintar sin un id, así que en ese caso enseña un estado
  // vacío que lleva al Archivo en vez de inventarse una norma cualquiera.
  const [seleccion, setSeleccion] = useState<SeleccionNorma | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  const goArchivo = () => setScreen("archivo");
  const goTimeline = (comunidad?: string) => {
    setComunidadFiltro(comunidad);
    setScreen("alertas");
  };
  const verFicha = (nueva: SeleccionNorma) => {
    setSeleccion(nueva);
    setScreen("ficha");
  };

  return (
    <div className="min-h-screen bg-bg text-ink">
      <Header
        screen={screen}
        onNav={setScreen}
        dark={dark}
        onToggleTheme={() => setDark((v) => !v)}
        esDemo={PANTALLAS_CON_MOCK.has(screen)}
      />

      {screen === "mapa" && <MapaPage onGoArchivo={goArchivo} onGoTimeline={goTimeline} />}
      {screen === "alertas" && (
        <AlertasPage comunidadInicial={comunidadFiltro} onGoArchivo={goArchivo} />
      )}
      {screen === "archivo" && <ArchivoPage onVerFicha={verFicha} />}
      {screen === "ficha" && <FichaPage seleccion={seleccion} onIrAlArchivo={goArchivo} />}
      {screen === "revision" && <RevisionPage />}

      <Footer />
    </div>
  );
}
