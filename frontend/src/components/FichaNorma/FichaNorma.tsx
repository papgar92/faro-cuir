import type { ReactNode } from "react";
import type { DocumentoDetalleApi, NormaApi } from "../../api/client";
import { formatearFecha } from "../../lib/formato";
import { HuellaArchivo } from "../HuellaArchivo/HuellaArchivo";
import { IntegrityPanel } from "../IntegrityPanel/IntegrityPanel";
import { PrefiltroBadge } from "../PrefiltroBadge/PrefiltroBadge";

/**
 * La ficha de una norma: metadatos, prefiltro y cadena de verificación.
 *
 * **Era la pantalla `FichaPage` y desde el 2026-09-05 es el panel derecho del Archivo.** El
 * motivo no fue estético: la pantalla volvía a pedir el mismo documento de 160 KB que el Archivo
 * acababa de descargar y tenía en memoria, así que abrir una norma costaba una recarga entera.
 * Y «Ficha de norma» en el menú, pulsada en frío, solo servía para ofrecer un botón que llevaba
 * al Archivo — una entrada de menú cuyo destino era otra entrada de menú.
 *
 * Al mudarse desaparecieron dos cosas que aquí ya no dicen nada: la miga de pan
 * `Archivo / documento / norma` —dibujaba una jerarquía que la navegación por pestañas negaba, y
 * ahora es literalmente la pantalla en la que estás— y los tres estados de error de carga, que
 * no pueden darse cuando quien te pinta ya tiene el documento resuelto.
 *
 * Lo que NO cambió, porque es lo que la sección 6.5 promete: la huella y el sello siguen
 * enseñándose enteros, y el panel de integridad sigue en su columna.
 */

interface MetaRowProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
  last?: boolean;
}

function MetaRow({ label, value, mono = false, last = false }: MetaRowProps) {
  return (
    <div
      className={`grid grid-cols-[minmax(0,150px)_minmax(0,1fr)] gap-4 py-2.5 ${last ? "" : "border-b border-line"}`}
    >
      <dt className="text-xs text-ink-3">{label}</dt>
      <dd className={`m-0 text-sm text-ink ${mono ? "font-mono" : ""}`}>{value}</dd>
    </div>
  );
}

/**
 * Valor que el extractor todavía no ha determinado.
 *
 * No es lo mismo que un hueco y no debe pintarse igual: el backend guarda NULL a propósito
 * porque deducir el rango o el ámbito del título a ojo sería inventarlos (regla de oro 8).
 * Decirlo en la interfaz es información útil — indica en qué etapa del pipeline está la norma.
 */
function Pendiente({ que }: { que: string }) {
  return (
    <span className="text-ink-3">
      Pendiente de análisis
      <span className="sr-only"> — el extractor todavía no ha determinado {que}</span>
    </span>
  );
}

function Panel({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="mt-3.5 rounded border border-dashed border-line-2 bg-inset p-4">
      <h2 className="m-0 text-sm font-semibold text-ink">{titulo}</h2>
      <div className="mt-1.5 text-sm text-ink-2">{children}</div>
    </section>
  );
}

export function FichaNorma({
  documento,
  norma,
}: {
  documento: DocumentoDetalleApi;
  norma: NormaApi;
}) {
  return (
    <article aria-labelledby="ficha-titulo">
      <div className="flex flex-wrap items-center gap-2.5">
        {/* Aquí iba la insignia de clasificación del mock. No se pinta: la clasificación
            vive en `deteccion`, que está vacía hasta que exista el pipeline. Enseñar una
            sería exactamente el veredicto sin gate humano que prohíben las reglas 2 y 4. */}
        <span className="inline-flex items-center gap-1.5 rounded border border-line-2 bg-surface-2 px-2.5 py-1 font-mono text-xs font-medium text-ink-2">
          {norma.identificador_oficial}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded border border-line-2 bg-surface-2 px-2.5 py-1 text-xs font-medium text-ink-2">
          {norma.ambito ? `Ámbito ${norma.ambito}` : "Ámbito sin determinar"}
        </span>
      </div>

      <h2
        id="ficha-titulo"
        className="mt-3 max-w-[52ch] font-serif text-[26px] font-bold leading-tight tracking-tight text-ink"
      >
        {norma.titulo}
      </h2>

      <Panel titulo="Todavía no hay comparación de texto">
        El antes y el después de cada artículo vive en{" "}
        <code className="font-mono text-xs">version_norma</code>, que se rellena cuando el
        extractor descarga el texto íntegro y el clasificador deriva el diff (CLAUDE.md sección
        7). De esta norma se ha ingerido y archivado su entrada en el sumario; el texto completo
        aún no se ha procesado. Mientras tanto, el enlace a la fuente oficial de abajo lleva al
        texto tal cual lo publica el boletín.
      </Panel>

      <div className="mt-3.5 rounded border border-line border-l-4 border-l-line-2 bg-surface p-4">
        <p className="m-0 text-sm text-ink-2">
          <strong className="font-semibold text-ink">Faro Cuir no interpreta la norma.</strong>{" "}
          Mostramos el texto tal como aparece publicado y el enlace a la fuente oficial. La
          clasificación indica el sentido del cambio respecto al texto anterior, no una
          valoración política.
        </p>
      </div>

      <section className="mt-5 rounded border border-line bg-surface">
        <h3 className="border-b border-line bg-inset px-4 py-3 text-sm font-semibold text-ink">
          Metadatos de la norma
        </h3>
        <dl className="m-0 px-4 pb-3.5 pt-1">
          <MetaRow label="Título oficial" value={norma.titulo} />
          <MetaRow
            label="Órgano emisor"
            value={norma.organo_emisor ?? <Pendiente que="el órgano emisor" />}
          />
          <MetaRow label="Rango" value={norma.rango ?? <Pendiente que="el rango" />} />
          <MetaRow
            // Ya no es solo léxico: desde el ADR 0012 hay un eje referencial, y desde la
            // tarea 0.c dispara sobre datos reales. La etiqueta mentía.
            label="Prefiltro"
            value={
              // `todosLosTerminos`: en el índice de la izquierda los términos se recortan por
              // volumen, y este es el sitio donde la decisión tiene que poder auditarse entera.
              <PrefiltroBadge
                estado={norma.prefiltro_estado}
                terminos={norma.prefiltro_terminos}
                ejes={norma.prefiltro_ejes}
                todosLosTerminos
              />
            }
          />
          <MetaRow
            label="Archivo verificable"
            value={<HuellaArchivo archivo={norma.texto_archivado} completo />}
          />
          <MetaRow label="Ámbito" value={norma.ambito ?? <Pendiente que="el ámbito" />} />
          <MetaRow
            label="Publicación"
            value={`${formatearFecha(documento.fecha_publicacion)} · ${documento.identificador_oficial}`}
            mono
          />
          <MetaRow
            label="Fuente oficial"
            last
            value={
              // El ancla muerta `#fuente` del mock se sustituye por la URL real que da el
              // sumario. Si la norma no la trae, se dice; no se finge un enlace.
              norma.url_texto ? (
                <>
                  <a href={norma.url_texto} target="_blank" rel="noopener noreferrer">
                    Texto íntegro en el boletín ↗
                  </a>{" "}
                  <span className="text-xs text-ink-3">· se abre en la fuente oficial</span>
                </>
              ) : (
                <span className="text-ink-3">
                  El sumario no publica enlace al texto íntegro de esta norma.
                </span>
              )
            }
          />
        </dl>
      </section>

      <div className="mt-5">
        <IntegrityPanel documento={documento} />
      </div>
    </article>
  );
}
