import { useRef } from "react";
import type { RegionMapa } from "../../lib/mapa";
import { ESTADO_MAPA_META, type ColorClasificacion } from "../../lib/classification";
import { CCAA_PATHS, INSET_CANARIAS, MAPA_VIEWBOX, type CcaaPath } from "./ccaa-paths";

interface MapaCCAAProps {
  regions: Record<string, RegionMapa>;
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
 * píxel. Se dibuja el polígono real *y* un anillo que es el objetivo de ratón y de
 * teclado, porque un objetivo de menos de un píxel no se puede pulsar.
 *
 * Accesibilidad: cada entidad es `role="button"` con `aria-label` legible sin
 * depender del color, y Enter/Espacio la seleccionan.
 */
export function MapaCCAA({ regions, activeCode, onEnter, onLeave, onPick }: MapaCCAAProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const activePath = activeCode ? CCAA_PATHS.find((p) => p.code === activeCode) : undefined;

  const etiqueta = (path: CcaaPath) => {
    const region = regions[path.code];
    if (!region || (!region.vigilada && region.alerts === 0)) {
      return `${path.name}: sin fuente vigilada todavía`;
    }
    if (region.state === null) {
      // La distinción que este mapa no puede perder: aquí SÍ se mira, y no ha salido nada
      // aprobado. Decir "estable" sería convertir el silencio en tranquilidad.
      return (
        `${region.name}: vigilada (${region.fuentesVigiladas} de ${region.fuentesConocidas} ` +
        `fuentes), sin alertas aprobadas todavía`
      );
    }
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
    if (region?.state) return FILL_VAR[ESTADO_MAPA_META[region.state].color];
    // Vigilada y sin conclusión: trama **clara**. Sin fuente: trama densa. Son dos silencios
    // distintos —"todavía no ha salido nada" y "aquí no estamos mirando"— y confundirlos sería
    // tan malo como pintarlos de gris "estable".
    return region?.vigilada ? "url(#sin-alertas)" : "url(#sin-vigilar)";
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
            r={RADIO_MICRO}
            fill={relleno(path)}
            stroke="var(--color-ink-3)"
            strokeWidth={1.2}
          />
          <path d={path.d} fill="var(--color-map-label)" pointerEvents="none" />
          <text
            x={path.cx + (RADIO_MICRO + 3)}
            y={path.cy + 3.5}
            fontSize={11}
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
      {/* **Sin controles de zoom desde el 2026-08-17, por decisión del humano.** Estaban para
          bajar de comunidad a provincia y a localidad, y ese camino ya no es el del proyecto: al
          pulsar una comunidad se enseñará también su normativa provincial y local (ADR 0014), que
          se vigila por BOP y no por geometría. Un zoom que no lleva a ningún dato nuevo es un
          control que promete una capacidad inexistente, y de esos ya se quitaron los filtros de
          alertas por el mismo motivo. La geometría real de Ceuta y Melilla se sigue dibujando
          debajo de su anillo: para verla ya no hace falta ampliar, pero tampoco se ha borrado. */}
      <svg
        ref={svgRef}
        viewBox={`0 0 ${MAPA_VIEWBOX.ancho} ${MAPA_VIEWBOX.alto}`}
        role="group"
        aria-label="Mapa de España por comunidades autónomas y ciudades autónomas"
        className="block w-full rounded border border-line bg-inset"
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
          {/* Vigilada sin alertas: misma trama, más separada y más tenue. Se lee como "aquí hay
              alguien mirando y todavía no hay nada que contar", no como un color de estado. */}
          <pattern
            id="sin-alertas"
            patternUnits="userSpaceOnUse"
            width={9}
            height={9}
            patternTransform="rotate(45)"
          >
            <rect width={9} height={9} fill="var(--color-surface)" />
            <line x1={0} y1={0} x2={0} y2={9} stroke="var(--color-line-2)" strokeWidth={1} />
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
          y={INSET_CANARIAS.y + 13}
          fontSize={10.5}
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
            r={(RADIO_MICRO + 2.5)}
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
