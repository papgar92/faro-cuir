import type { Screen } from "../../lib/navigation";

interface HeaderProps {
  screen: Screen;
  onNav: (screen: Screen) => void;
  dark: boolean;
  onToggleTheme: () => void;
  showDemoBadge?: boolean;
}

const NAV_ITEMS: Array<{ screen: Screen; label: string }> = [
  { screen: "mapa", label: "Mapa" },
  { screen: "alertas", label: "Alertas" },
  { screen: "ficha", label: "Ficha de norma" },
];

/** Franja con los colores de la bandera trans: no es decorativa, marca el enfoque del proyecto. */
function PrideStripe({ className = "" }: { className?: string }) {
  return (
    <div className={`flex ${className}`} aria-hidden="true">
      <div className="h-1 flex-1 bg-[#5ec8e8]" />
      <div className="h-1 flex-1 bg-[#e9a5be]" />
      <div className="h-1 flex-1 bg-[#f2efe9]" />
      <div className="h-1 flex-1 bg-[#e9a5be]" />
      <div className="h-1 flex-1 bg-[#5ec8e8]" />
    </div>
  );
}

export function Header({ screen, onNav, dark, onToggleTheme, showDemoBadge = true }: HeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface">
      <PrideStripe />
      <div className="mx-auto flex max-w-[1360px] items-center gap-7 px-7 py-3.5">
        <div className="flex flex-col gap-0.5">
          <div className="font-serif text-xl font-bold leading-none tracking-[0.14em] text-ink">
            FARO CUIR
          </div>
          <div className="text-[11.5px] tracking-wide text-ink-3">
            Observatorio de derechos LGTBI+ · 17 CCAA + BOE
          </div>
        </div>

        <nav className="ml-2 flex gap-0.5" aria-label="Navegación principal">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.screen}
              type="button"
              onClick={() => onNav(item.screen)}
              aria-current={screen === item.screen ? "page" : undefined}
              className={`rounded border border-transparent px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-2 ${
                screen === item.screen ? "bg-surface-2" : ""
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2.5">
          {showDemoBadge && (
            <span className="rounded border border-dashed border-line-2 px-1.5 py-1 font-mono text-[10.5px] uppercase tracking-wide text-ink-3">
              Datos de demostración
            </span>
          )}
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label="Cambiar modo claro u oscuro"
            className="rounded border border-line-2 bg-surface px-2.5 py-1.5 text-xs text-ink-2 hover:border-ink-3 hover:text-ink"
          >
            {dark ? "Modo claro" : "Modo oscuro"}
          </button>
        </div>
      </div>

      <div className="border-t border-line bg-inset">
        <div className="mx-auto flex max-w-[1360px] flex-wrap items-center gap-6 px-7 py-2 font-mono text-xs text-ink-2">
          <span className="font-medium text-ink">Pulso · datos de demostración</span>
          <span>
            <span className="font-medium text-ink">1.284</span> documentos analizados hoy
          </span>
          <span>
            <span className="font-medium text-ink">6</span> alertas nuevas
          </span>
          <span>
            <span className="font-medium text-ink">18</span> boletines en cola
          </span>
          <span className="ml-auto text-ink-3">última pasada 07:40 CEST</span>
        </div>
      </div>
    </header>
  );
}
