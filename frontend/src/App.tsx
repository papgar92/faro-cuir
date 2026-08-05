import { FEED, fichaDetail } from "./api/mocks";
import { AlertCard } from "./components/AlertCard/AlertCard";
import { DiffBlock } from "./components/DiffBlock/DiffBlock";

export default function App() {
  return (
    <div className="min-h-screen bg-bg p-8 text-ink">
      <h1 className="font-serif text-2xl font-bold">Centinela</h1>
      <p className="text-ink-2">Smoke test de componentes compartidos (FE-5).</p>

      <div className="mt-6 max-w-[900px]">
        {FEED.slice(0, 3).map((alerta) => (
          <AlertCard key={alerta.id} alerta={alerta} onVerFicha={(id) => console.log("ver ficha", id)} />
        ))}
      </div>

      <div className="max-w-[900px]">
        <DiffBlock diff={fichaDetail.diff} />
      </div>
    </div>
  );
}
