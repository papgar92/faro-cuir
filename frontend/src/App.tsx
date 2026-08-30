import { useEffect, useState } from "react";
import { Footer } from "./components/layout/Footer";
import { Header } from "./components/layout/Header";
import {
  PANTALLAS_CON_MOCK,
  escribirUrl,
  leerUrl,
  type Screen,
  type SeleccionNorma,
} from "./lib/navigation";
import { AlertasPage } from "./pages/AlertasPage";
import { ArchivoPage } from "./pages/ArchivoPage";
import { FichaPage } from "./pages/FichaPage";
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
  // Qué norma real está viendo la Ficha. Null mientras no se haya elegido ninguna: la Ficha
  // lee de la API y no tiene nada que pintar sin un id, así que en ese caso enseña un estado
  // vacío que lleva al Archivo en vez de inventarse una norma cualquiera.
  const [seleccion, setSeleccion] = useState<SeleccionNorma | null>(null);

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
  }, [dark]);

  // La URL sigue a la pantalla. `ccaa` lo escribe el Mapa por su cuenta, porque es quien sabe
  // qué comunidad hay seleccionada; aquí solo se conserva lo que ya hubiera para no borrarlo al
  // cambiar de pantalla y volver.
  useEffect(() => {
    escribirUrl({ screen, ccaa: leerUrl(window.location.search).ccaa });
  }, [screen]);

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
      {screen === "archivo" && <ArchivoPage onVerFicha={verFicha} />}
      {screen === "ficha" && <FichaPage seleccion={seleccion} onIrAlArchivo={goArchivo} />}
      {screen === "revision" && <RevisionPage />}

      <Footer />
    </div>
  );
}
