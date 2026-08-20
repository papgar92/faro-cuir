import { listarDocumentos, obtenerCobertura } from "../../api/client";
import { useRecurso } from "../../api/useRecurso";
import { formatearFecha } from "../../lib/formato";
import type { Screen } from "../../lib/navigation";

interface HeaderProps {
  screen: Screen;
  onNav: (screen: Screen) => void;
  dark: boolean;
  onToggleTheme: () => void;
  /** Si la pantalla activa sirve datos inventados. Lo decide App, no el Header. */
  esDemo: boolean;
}

const NAV_ITEMS: Array<{ screen: Screen; label: string }> = [
  { screen: "mapa", label: "Mapa" },
  { screen: "alertas", label: "Alertas" },
  { screen: "archivo", label: "Archivo" },
  { screen: "ficha", label: "Ficha de norma" },
  // El panel del gate humano (ADR 0017). Está en la navegación pública a propósito: que exista
  // un paso humano obligatorio antes de publicar es parte de lo que el proyecto afirma, y
  // esconder la puerta no la protege — la protege el 401 del backend. Quien no tenga la
  // contraseña ve la pantalla de acceso y la explicación de para qué sirve.
  { screen: "revision", label: "Revisión" },
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

/**
 * Franja de pulso con cifras inventadas. Se mantiene solo en las pantallas que ya son una
 * maqueta; en las que leen de la API se sustituye por `PulsoReal`.
 */
function PulsoDemo() {
  return (
    <>
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
    </>
  );
}

/**
 * Pulso con lo que de verdad hay ingerido.
 *
 * Es una petición extra, pero la alternativa era dejar "1.284 documentos analizados hoy" —una
 * cifra inventada— presidiendo la pantalla que sí muestra datos reales. Una franja fija que
 * miente sobre el volumen del sistema es peor que una petición de más.
 */
function PulsoReal() {
  // Dos peticiones y no una, y la de la lista pide **un** documento en vez de cien. El total
  // sale de `/api/cobertura`, que es donde viven los agregados: pedir cien y contarlos hacía que
  // esta franja dijera «100 documentos archivados» con 162 en el almacén, que es exactamente lo
  // que este componente existe para no hacer. De paso baja el payload de cien documentos con su
  // huella a uno.
  const totales = useRecurso((signal) => obtenerCobertura(signal), []);
  const estado = useRecurso((signal) => listarDocumentos({ limite: 1 }, signal), []);

  if (estado.fase === "cargando") return <span className="text-ink-3">Consultando la API…</span>;
  if (estado.fase === "error") return <span className="text-ink-3">API no disponible</span>;

  const documentos = estado.datos;
  const ultimo = documentos[0];
  const archivados = totales.fase === "listo" ? totales.datos.documentos : documentos.length;

  return (
    <>
      <span className="font-medium text-ink">Pulso · datos reales</span>
      <span>
        <span className="font-medium text-ink">{archivados}</span>{" "}
        {archivados === 1 ? "documento archivado" : "documentos archivados"}
      </span>
      {ultimo && (
        <span>
          último: <span className="font-medium text-ink">{ultimo.identificador_oficial}</span> ·{" "}
          {formatearFecha(ultimo.fecha_publicacion)}
        </span>
      )}
      <span className="ml-auto text-ink-3">
        {/*
          Decía "pipeline de clasificación: pendiente", y desde el ADR 0016 era falso: el
          catálogo de reglas produce veredictos con su evidencia. Se corrige por lo mismo que
          existe `DemoDataNotice` — una franja fija que afirma algo que ya no es cierto es
          exactamente lo que este proyecto denuncia. Lo que sigue siendo verdad, y es lo que
          importa decir, es que nada se publica sin que una persona lo apruebe (regla de oro 4).
        */}
        nada se publica sin revisión humana
      </span>
    </>
  );
}

export function Header({ screen, onNav, dark, onToggleTheme, esDemo }: HeaderProps) {
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
          {esDemo ? (
            <span className="rounded border border-alr bg-alr-soft px-1.5 py-1 font-mono text-[10.5px] uppercase tracking-wide text-alr">
              Datos de ejemplo
            </span>
          ) : (
            <span className="rounded border border-adv bg-adv-soft px-1.5 py-1 font-mono text-[10.5px] uppercase tracking-wide text-adv">
              Datos reales
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
          {esDemo ? <PulsoDemo /> : <PulsoReal />}
        </div>
      </div>
    </header>
  );
}
