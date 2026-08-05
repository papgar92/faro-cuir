import { MapaPage } from "./pages/MapaPage";

export default function App() {
  return (
    <MapaPage
      onGoFicha={() => console.log("goFicha")}
      onGoTimeline={(com) => console.log("goTimeline", com)}
    />
  );
}
