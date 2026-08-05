import { AlertasPage } from "./pages/AlertasPage";

export default function App() {
  return <AlertasPage onVerFicha={(id) => console.log("verFicha", id)} />;
}
