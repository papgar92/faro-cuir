import type { AlertaApi } from "../../api/client";
import { COLOR_CLASSES, type ClassificationMeta } from "../../lib/classification";
import { formatearFecha, formatearSelloTiempo } from "../../lib/formato";
import { nombreTerritorio } from "../../lib/territorio";
import { ClassificationBadge } from "../ClassificationBadge/ClassificationBadge";

/**
 * Una alerta **real**: una detección que pasó el gate humano (regla de oro 4).
 *
 * La tarjeta enseña la evidencia, no solo el veredicto. Es la misma razón por la que la
 * huella de archivo se publica en vez de guardarse (6.5): el proyecto afirma «esta norma
 * suprime esto», y esa afirmación no vale nada si quien la lee tiene que fiarse. Aquí va el
 * fragmento recortado del texto archivado, con sus offsets, la regla que lo clasificó y el
 * enlace a la fuente oficial para contrastarlo.
 *
 * Deliberadamente **no** hay ningún texto de opinión ni adjetivos: el titular es el título
 * oficial de la norma y el cuerpo son citas literales (regla de oro 2).
 */

/**
 * Los cuatro valores de `deteccion.clasificacion`, que no son los tres del mock de diseño.
 * `indeterminado` se pinta en el color de aviso y **no** en el de retroceso: es el umbral de
 * recall alto de 7.6 —el catálogo ha visto algo y no sabe de qué signo— y teñirlo de rojo
 * sería emitir el veredicto del que la regla se abstuvo.
 */
const META: Record<AlertaApi["clasificacion"], ClassificationMeta> = {
  avance: { label: "Avance", glyph: "▲", color: "adv" },
  retroceso: { label: "Retroceso", glyph: "▼", color: "reg" },
  neutro: { label: "Neutro", glyph: "●", color: "neu" },
  indeterminado: { label: "Sin signo", glyph: "?", color: "alr" },
};

interface AlertCardProps {
  alerta: AlertaApi;
}

export function AlertCard({ alerta }: AlertCardProps) {
  const meta = META[alerta.clasificacion];
  const colors = COLOR_CLASSES[meta.color];
  const territorios = alerta.normas_vigiladas.map((n) => nombreTerritorio(n.ambito));

  return (
    <article
      className={`mb-3 max-w-[900px] rounded border border-line ${colors.borderLeft} border-l-4 bg-surface p-4`}
    >
      <div className="flex flex-wrap items-center gap-2.5">
        <ClassificationBadge meta={meta} />
        {territorios.length > 0 && (
          <span className="text-sm font-semibold text-ink">{territorios.join(" · ")}</span>
        )}
        <span className="ml-auto font-mono text-xs text-ink-3">
          {formatearFecha(alerta.fecha_publicacion)}
        </span>
      </div>

      <h3 className="mt-2.5 text-base font-semibold leading-snug text-ink">
        {alerta.norma.titulo}
      </h3>

      {alerta.spans.length > 0 && (
        <div className="mt-3 rounded border border-line-2 bg-inset p-3">
          <p className="font-mono text-[13px] leading-relaxed text-ink">
            «{alerta.spans[0].fragmento}»
          </p>
          <p className="mt-1.5 font-mono text-[10.5px] text-ink-3">
            texto archivado, caracteres {alerta.spans[0].inicio.toLocaleString("es-ES")}–
            {alerta.spans[0].fin.toLocaleString("es-ES")}
            {alerta.spans.length > 1 &&
              ` · y ${alerta.spans.length - 1} fragmento${alerta.spans.length > 2 ? "s" : ""} más`}
          </p>
        </div>
      )}

      {alerta.normas_vigiladas.length > 0 && (
        <p className="mt-2.5 text-xs leading-relaxed text-ink-2">
          Toca{" "}
          {alerta.normas_vigiladas.map((n, i) => (
            <span key={n.identificador}>
              {i > 0 && ", "}
              <span className="font-medium text-ink">{n.titulo || n.identificador}</span>
            </span>
          ))}
          .
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[11px] text-ink-3">
        <span>{alerta.norma.identificador_oficial}</span>
        <span>
          regla {alerta.regla_aplicada ?? "—"}
          {alerta.version_reglas && ` · catálogo ${alerta.version_reglas}`}
        </span>
        {alerta.texto_archivado && (
          <span title={alerta.texto_archivado.sha256}>
            sha256 {alerta.texto_archivado.sha256.slice(0, 12)}… ·{" "}
            {formatearSelloTiempo(alerta.texto_archivado.sello_tiempo)}
          </span>
        )}
        {alerta.norma.url_texto && (
          <a
            href={alerta.norma.url_texto}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto font-sans text-sm text-link hover:text-ink"
          >
            Comprobar en la fuente oficial →
          </a>
        )}
      </div>
    </article>
  );
}
