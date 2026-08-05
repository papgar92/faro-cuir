import type { RegionSummary } from "../../api/mocks";
import { ESTADO_MAPA_META, type ColorClasificacion } from "../../lib/classification";
import { CCAA_PATHS } from "./ccaa-paths";

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

function alertasLabel(n: number): string {
  if (n === 0) return "sin alertas activas";
  if (n === 1) return "1 alerta activa";
  return `${n} alertas activas`;
}

/**
 * Mapa de España por CCAA. Cada comunidad es un <path> con role="button" +
 * aria-label ya legible sin depender del color ("Andalucía: retroceso reciente,
 * 3 alertas activas"). A diferencia del mock original, aquí Enter/Espacio sobre
 * un path enfocado también selecciona la comunidad: en el mock el pick solo
 * llegaba por click/onMouseOver delegado en el <svg>, sin manejar teclado — un
 * botón de rol ARIA no convierte automáticamente el foco+Enter en un evento
 * click salvo que se cablee explícitamente.
 */
export function MapaCCAA({ regions, activeCode, onEnter, onLeave, onPick }: MapaCCAAProps) {
  const activePath = activeCode ? CCAA_PATHS.find((p) => p.code === activeCode) : undefined;

  return (
    <svg
      viewBox="115 0 775 700"
      role="group"
      aria-label="Mapa de España por comunidades autónomas"
      className="mt-1.5 block w-full"
    >
      {CCAA_PATHS.map((path) => {
        const region = regions[path.code];
        const meta = region ? ESTADO_MAPA_META[region.state] : undefined;
        const fill = meta ? FILL_VAR[meta.color] : "var(--color-neu-bg)";
        const label = region
          ? `${region.name}: ${meta!.label.toLowerCase()}, ${alertasLabel(region.alerts)}`
          : path.name;

        return (
          <path
            key={path.code}
            d={path.d}
            data-code={path.code}
            tabIndex={0}
            role="button"
            aria-label={label}
            fill={fill}
            stroke="var(--color-map-line)"
            strokeWidth={1.1}
            strokeLinejoin="round"
            className="cursor-pointer outline-none transition-[filter] duration-100 hover:brightness-95 focus-visible:brightness-90"
            onMouseEnter={() => onEnter(path.code)}
            onFocus={() => onEnter(path.code)}
            onMouseLeave={onLeave}
            onClick={() => onPick(path.code)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onPick(path.code);
              }
            }}
          />
        );
      })}
      {activePath && (
        <path
          d={activePath.d}
          fill="none"
          stroke="var(--color-ink)"
          strokeWidth={2.4}
          strokeLinejoin="round"
          pointerEvents="none"
        />
      )}
    </svg>
  );
}
