import { useRef } from "react";
import type { RegionSummary } from "../../api/mocks";
import { ESTADO_MAPA_META, type ColorClasificacion } from "../../lib/classification";
import { CCAA_PATHS, INSET_CANARIAS, type CcaaPath } from "./ccaa-paths";
import { useZoomMapa } from "./useZoomMapa";

interface MapaCCAAProps {
  regions: Record<string, RegionSummary>;
  activeCode: string | null;
  onEnter: (code: string) => void;
  onLeave: () => void;
  onPick: (code: string) => void;
}

const FILL_VAR: Record<ColorClasificacion, string> = {
  adv: "var(--color-adv-bg)",
  reg: "var(--color-reg-bg)",
  neu: "var(--color-neu-bg)",
  alr: "var(--color-alr-bg)",
};

/** Radio del objetivo de las ciudades autónomas, en píxeles de pantalla. */
const RADIO_MICRO = 9;

function alertasLabel(n: number): string {
  if (n === 0) return "sin alertas activas";
  if (n === 1) return "1 alerta activa";
  return `${n} alertas activas`;
}

const PENINSULARES = CCAA_PATHS.filter((p) => !p.inset);
const INSULARES = CCAA_PATHS.filter((p) => p.inset);

/**
 * Mapa de España por comunidad autónoma, ampliable.
 *
 * Geometría generada por `frontend/scripts/generar_mapa.py` desde el TopoJSON del
 * IGN: proyección cónica equivalente, Canarias en recuadro **a la misma escala**
 * y Ceuta y Melilla en su posición real. Los tres eran defectos reportados por el
 * humano en el backlog (CLAUDE.md sección 12) y ninguno se arregla aquí: se
 * arregla en el script, porque son defectos de proyección.
 *
 * Ceuta y Melilla miden 19 y 12 km²: a esta escala su polígono real es menos de un
 * píxel. Se dibuja el polígono real *y* un anillo de tamaño constante en pantalla
 * que es el objetivo de ratón y de teclado. Al ampliar, el anillo mantiene su
 * tamaño y la geometría real acaba desbordándolo — es decir, el zoom enseña la
 * forma verdadera en vez de un símbolo agrandado.
 *
 * Accesibilidad: cada entidad es `role="button"` con `aria-label` legible sin
 * depender del color, y Enter/Espacio la seleccionan. El zoom no se lleva el foco:
 * los objetivos siguen siendo los `<path>`, no un contenedor transformado.
 */
export function MapaCCAA({ regions, activeCode, onEnter, onLeave, onPick }: MapaCCAAProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const zoom = useZoomMapa();
  const activePath = activeCode ? CCAA_PATHS.find((p) => p.code === activeCode) : undefined;

  const etiqueta = (path: CcaaPath) => {
    const region = regions[path.code];
    if (!region) return `${path.name}: sin fuente vigilada todavía`;
    const meta = ESTADO_MAPA_META[region.state];
    return `${region.name}: ${meta.label.toLowerCase()}, ${alertasLabel(region.alerts)}`;
  };

  const relleno = (path: CcaaPath) => {
    const region = regions[path.code];
    // Sin fila no hay estado: se pinta como territorio sin vigilar, no como
    // "estable". Pintar de estable lo que nadie mira es afirmar un resultado.
    //
    // Y se distingue por TRAMA, no por un gris distinto: el gris de "estable" y
    // cualquier otro gris se confunden en pantalla y más aún en una impresión o
    // con visión de color reducida. "Sin datos" con rayado es además la
    // convención cartográfica de toda la vida.
    return region ? FILL_VAR[ESTADO_MAPA_META[region.state].color] : "url(#sin-vigilar)";
  };

  /**
   * Función plana y no un componente anidado a propósito: un componente definido
   * dentro del render es un tipo nuevo en cada pasada, así que React desmonta y
   * remonta el subárbol. Aquí eso **perdía el foco del teclado** en cada `onFocus`,
   * porque enfocar una comunidad cambia el estado del padre.
   */
  const entidad = (path: CcaaPath) => {
    const comun = {
      tabIndex: 0,
      role: "button",
      "aria-label": etiqueta(path),
      onMouseEnter: () => onEnter(path.code),
      onMouseLeave: onLeave,
      onFocus: () => onEnter(path.code),
      // Simétrico al ratón. Sin `onBlur`, salir del mapa con el tabulador dejaba
      // el panel lateral mostrando la última comunidad enfocada como si estuviera
      // fijada, y no había forma de soltarla sin pasar el ratón por encima.
      onBlur: onLeave,
      onClick: () => {
        if (zoom.consumirArrastre()) return;
        onPick(path.code);
      },
      onKeyDown: (event: React.KeyboardEvent) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onPick(path.code);
        }
      },
      className: "cursor-pointer outline-none transition-[filter] duration-100 hover:brightness-95 focus-visible:brightness-90",
    };

    if (path.micro) {
      // El grupo entero es el objetivo; el anillo le da el tamaño y el polígono
      // real va dentro, sin capturar eventos por su cuenta.
      return (
        <g key={path.code} {...comun}>
          <circle
            cx={path.cx}
            cy={path.cy}
            r={RADIO_MICRO / zoom.factor}
            fill={relleno(path)}
            stroke="var(--color-ink-3)"
            strokeWidth={1.2 / zoom.factor}
          />
          <path d={path.d} fill="var(--color-map-label)" pointerEvents="none" />
          <text
            x={path.cx + (RADIO_MICRO + 3) / zoom.factor}
            y={path.cy + 3.5 / zoom.factor}
            fontSize={11 / zoom.factor}
            fill="var(--color-map-label)"
            pointerEvents="none"
          >
            {path.name}
          </text>
        </g>
      );
    }

    return (
      <path
        key={path.code}
        {...comun}
        d={path.d}
        data-code={path.code}
        fill={relleno(path)}
        stroke="var(--color-map-line)"
        strokeWidth={1.1}
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    );
  };

  return (
    <div className="mt-1.5">
      <div className="mb-2 flex items-center gap-1.5">
        <button
          type="button"
          onClick={zoom.alejar}
          disabled={!zoom.puedeAlejar}
          aria-label="Alejar el mapa"
          className="h-7 w-7 rounded border border-line-2 bg-surface font-mono text-sm text-ink-2 hover:border-ink-3 hover:text-ink disabled:opacity-40 disabled:hover:border-line-2 disabled:hover:text-ink-2"
        >
          −
        </button>
        <button
          type="button"
          onClick={zoom.acercar}
          disabled={!zoom.puedeAcercar}
          aria-label="Acercar el mapa"
          className="h-7 w-7 rounded border border-line-2 bg-surface font-mono text-sm text-ink-2 hover:border-ink-3 hover:text-ink disabled:opacity-40 disabled:hover:border-line-2 disabled:hover:text-ink-2"
        >
          +
        </button>
        <button
          type="button"
          onClick={zoom.verTodo}
          disabled={!zoom.puedeAlejar}
          className="rounded border border-line-2 bg-surface px-2 py-1 text-xs text-ink-2 hover:border-ink-3 hover:text-ink disabled:opacity-40 disabled:hover:border-line-2 disabled:hover:text-ink-2"
        >
          Ver todo
        </button>
        <span aria-hidden="true" className="ml-1 font-mono text-xs text-ink-3">
          ×{zoom.factor.toFixed(1)}
        </span>
        <span className="sr-only" role="status">
          Ampliación {zoom.factor.toFixed(1)} aumentos
        </span>
        <span className="ml-auto text-xs text-ink-3">
          Arrastra para desplazar · teclas + − 0 y flechas
        </span>
      </div>

      <svg
        ref={svgRef}
        viewBox={`${zoom.vista.x} ${zoom.vista.y} ${zoom.vista.ancho} ${zoom.vista.alto}`}
        role="group"
        aria-label="Mapa de España por comunidades autónomas y ciudades autónomas"
        tabIndex={0}
        className={`block w-full touch-none rounded border border-line bg-inset ${
          zoom.arrastrando ? "cursor-grabbing" : "cursor-grab"
        }`}
        onDoubleClick={(event) => {
          const svg = svgRef.current;
          if (!svg) return;
          const punto = zoom.aLienzo(svg, event.clientX, event.clientY);
          zoom.ampliar(1.6, punto.x, punto.y);
        }}
        {...zoom.manejadores}
      >
        <defs>
          <pattern
            id="sin-vigilar"
            patternUnits="userSpaceOnUse"
            width={5}
            height={5}
            patternTransform="rotate(45)"
          >
            <rect width={5} height={5} fill="var(--color-surface-2)" />
            <line x1={0} y1={0} x2={0} y2={5} stroke="var(--color-line-2)" strokeWidth={1.4} />
          </pattern>
        </defs>

        {/* Recuadro de Canarias. Va debajo de las islas y con su rótulo dentro:
            un inset sin marco se lee como si las islas estuvieran ahí de verdad. */}
        <rect
          x={INSET_CANARIAS.x}
          y={INSET_CANARIAS.y}
          width={INSET_CANARIAS.ancho}
          height={INSET_CANARIAS.alto}
          fill="var(--color-surface)"
          stroke="var(--color-line-2)"
          strokeWidth={1}
          strokeDasharray="4 3"
          vectorEffect="non-scaling-stroke"
        />
        <text
          x={INSET_CANARIAS.x + 7}
          y={INSET_CANARIAS.y + 13 / zoom.factor}
          fontSize={10.5 / zoom.factor}
          fill="var(--color-ink-3)"
          className="font-mono"
          pointerEvents="none"
        >
          Canarias · misma escala
        </text>

        {PENINSULARES.map(entidad)}
        {INSULARES.map(entidad)}

        {activePath && !activePath.micro && (
          <path
            d={activePath.d}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth={2.4}
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        )}
        {activePath?.micro && (
          <circle
            cx={activePath.cx}
            cy={activePath.cy}
            r={(RADIO_MICRO + 2.5) / zoom.factor}
            fill="none"
            stroke="var(--color-ink)"
            strokeWidth={2.4}
            vectorEffect="non-scaling-stroke"
            pointerEvents="none"
          />
        )}
      </svg>
    </div>
  );
}
