import { useEffect, useState } from "react";
import { Footer } from "./components/layout/Footer";
import { Header } from "./components/layout/Header";
import { PANTALLAS_CON_MOCK, escribirUrl, leerUrl, type Screen } from "./lib/navigation";
import { AlertasPage } from "./pages/AlertasPage";
import { ArchivoPage } from "./pages/ArchivoPage";
import { HallazgosPage } from "./pages/HallazgosPage";
import { MapaPage } from "./pages/MapaPage";
import { RevisionPage } from "./pages/RevisionPage";

export default function App() {
  // El estado inicial sale de la URL, no de una constante: si alguien llega con un enlace
  // compartido tiene que aterrizar donde le dijeron, no en el mapa.
  const [screen, setScreen] = useState<Screen>(() => leerUrl(window.location.search).screen);
  // La comunidad que venía en el enlace. Se pasa al Mapa como selección inicial y **se lee una
  // sola vez**: a partir de ahí manda la interacción, no la URL.
  const [ccaaInicial] = useState<string | undefined>(() => leerUrl(window.location.search).ccaa);
  const [dark, setDark] = useState(false);
  const [comunidadFiltro, setComunidadFiltro] = useState<string | undefined>(undefined);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  // La URL sigue a la pantalla. `ccaa` lo escribe el Mapa por su cuenta y `doc`/`norma` el
  // Archivo, porque son quienes saben qué hay seleccionado; aquí solo se conserva lo que ya
  // hubiera, para que cambiar de pantalla y volver no borre la norma que estabas mirando.
  useEffect(() => {
    const actual = leerUrl(window.location.search);
    escribirUrl({ screen, ccaa: actual.ccaa, doc: actual.doc, norma: actual.norma });
  }, [screen]);

  const goArchivo = () => setScreen("archivo");
  const goTimeline = (comunidad?: string) => {
    setComunidadFiltro(comunidad);
    setScreen("alertas");
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

      {screen === "mapa" && (
        <MapaPage
          onGoArchivo={goArchivo}
          onGoTimeline={goTimeline}
          ccaaInicial={ccaaInicial}
        />
      )}
      {screen === "alertas" && (
        <AlertasPage comunidadInicial={comunidadFiltro} onGoArchivo={goArchivo} />
      )}
      {screen === "hallazgos" && <HallazgosPage />}
      {screen === "archivo" && <ArchivoPage />}
      {screen === "revision" && <RevisionPage />}

      <Footer />
    </div>
  );
}
