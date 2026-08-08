import type { CoberturaCcaaApi, CoberturaNivelApi } from "../../api/client";

const ETIQUETA_AMBITO: Record<string, string> = {
  estatal: "Estatal (BOE)",
  autonomico: "Autonómico",
  provincial: "Provincial (BOP)",
  local: "Local",
};

const AYUDA_AMBITO: Record<string, string> = {
  autonomico: "Leyes, decretos, órdenes e instrucciones de la comunidad.",
  provincial: "Ordenanzas municipales, bases y convocatorias de subvenciones, acuerdos de pleno.",
  local: "Boletines propios de entidades locales.",
};

function Barra({ nivel }: { nivel: CoberturaNivelApi }) {
  const porcentaje = nivel.conocidas === 0 ? 0 : (nivel.vigiladas / nivel.conocidas) * 100;
  const ayuda = AYUDA_AMBITO[nivel.ambito];

  return (
    <li className="border-b border-line py-2.5 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-ink">{ETIQUETA_AMBITO[nivel.ambito] ?? nivel.ambito}</span>
        {/* El par vigiladas/conocidas nunca se separa. "8" a secas se lee como ocho
            vigiladas; "0 de 8" no se puede leer mal. */}
        <span className="font-mono text-sm text-ink-2">
          <span className={nivel.vigiladas === 0 ? "text-ink-3" : "font-medium text-ink"}>
            {nivel.vigiladas}
          </span>
          <span className="text-ink-3"> de {nivel.conocidas}</span>
        </span>
      </div>
      <div
        className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-surface-2"
        role="img"
        aria-label={`${nivel.vigiladas} de ${nivel.conocidas} fuentes vigiladas`}
      >
        <div className="h-full rounded-full bg-adv" style={{ width: `${porcentaje}%` }} />
      </div>
      {ayuda && <p className="mt-1.5 text-xs leading-snug text-ink-3">{ayuda}</p>}
    </li>
  );
}

/**
 * Cobertura de fuentes de una comunidad, desglosada por nivel de administración (ADR 0014).
 *
 * Va **dentro del panel de la comunidad, no en el mapa**. Fue la propuesta del humano y es
 * la correcta: la alternativa era un mapa provincial que obliga a ampliar para descubrir
 * dónde ha pasado algo, que es justo lo contrario de lo que necesita quien vigila. Aquí la
 * información llega agrupada al seleccionar la comunidad, sin buscarla.
 *
 * **Este componente enseña un hueco, no un logro.** Hoy dice, para todas las comunidades,
 * que 0 de sus N boletines provinciales se están leyendo. Está bien que lo diga: el proyecto
 * denuncia decisiones administrativas que se toman en silencio, así que no puede tener su
 * propia cobertura en silencio. Cuando el ADR 0014 se implemente entero, estos números suben
 * solos sin tocar esta pantalla.
 */
export function CoberturaCcaa({ cobertura }: { cobertura: CoberturaCcaaApi | undefined }) {
  if (!cobertura) {
    return (
      <div className="mt-4 rounded border border-dashed border-line-2 bg-inset p-3">
        <p className="m-0 text-xs leading-relaxed text-ink-2">
          Sin fuentes registradas para esta comunidad. Las que existen y aún no se vigilan
          están en <code className="font-mono text-ink">docs/fuentes.md</code>.
        </p>
      </div>
    );
  }

  return (
    <section className="mt-5" aria-label="Cobertura de fuentes oficiales">
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
          Boletines oficiales vigilados
        </h3>
        <span className="font-mono text-xs text-ink-3">
          {cobertura.vigiladas} de {cobertura.conocidas}
        </span>
      </div>

      <ul className="mt-2 list-none border-t border-line p-0">
        {cobertura.niveles.map((nivel) => (
          <Barra key={nivel.ambito} nivel={nivel} />
        ))}
      </ul>

      {cobertura.vigiladas === 0 && (
        <p className="mt-2.5 rounded border border-line bg-inset p-2.5 text-xs leading-relaxed text-ink-2">
          Ninguna de estas fuentes se está leyendo todavía. Que no aparezcan cambios{" "}
          <strong className="font-semibold text-ink">no significa que no los haya</strong>:
          significa que nadie está mirando ahí.
        </p>
      )}
    </section>
  );
}
