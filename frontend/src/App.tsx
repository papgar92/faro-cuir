import { FichaPage } from "./pages/FichaPage";

export default function App() {
  return <FichaPage onGoTimeline={() => console.log("goTimeline")} />;
}
