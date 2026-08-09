import type { ReactNode } from "react";
import type { DocumentoDetalleApi, NormaApi } from "../api/client";
import { obtenerDocumento } from "../api/client";
import { describirError, useRecurso } from "../api/useRecurso";
import { IntegrityPanel } from "../components/IntegrityPanel/IntegrityPanel";
import { HuellaArchivo } from "../components/HuellaArchivo/HuellaArchivo";
import { PrefiltroBadge } from "../components/PrefiltroBadge/PrefiltroBadge";
import { formatearFecha } from "../lib/formato";
import type { SeleccionNorma } from "../lib/navigation";

interface FichaPageProps {
  seleccion: SeleccionNorma | null;
  onIrAlArchivo: () => void;
}

interface MetaRowProps {
  label: string;
  value: ReactNode;
  mono?: boolean;
  last?: boolean;
}

function MetaRow({ label, value, mono = false, last = false }: MetaRowProps) {
  return (
    <div
      className={`grid grid-cols-[200px_minmax(0,1fr)] gap-4 py-2.5 ${last ? "" : "border-b border-line"}`}
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

/** Cuerpo de la ficha una vez resueltos documento y norma. */
function Ficha({
  documento,
  norma,
  onIrAlArchivo,
}: {
  documento: DocumentoDetalleApi;
  norma: NormaApi;
  onIrAlArchivo: () => void;
}) {
  return (
    <>
      <nav
        aria-label="Ruta de navegación"
        className="flex flex-wrap items-center gap-2 font-mono text-xs text-ink-3"
      >
        <button type="button" onClick={onIrAlArchivo} className="font-mono text-xs text-link hover:text-ink">
          Archivo
        </button>
        <span>/</span>
        <span>{documento.identificador_oficial}</span>
        <span>/</span>
        <span>{norma.identificador_oficial}</span>
      </nav>

      <div className="mt-3.5 grid grid-cols-1 items-start gap-7 lg:grid-cols-[minmax(0,1fr)_372px]">
        <div className="min-w-0">
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
            <span className="inline-flex items-center gap-1.5 rounded border border-line-2 bg-surface-2 px-2.5 py-1 text-xs font-medium text-ink-2">
              Estado {documento.estado_pipeline}
            </span>
          </div>

          <h1 className="mt-3 max-w-[52ch] font-serif text-[29px] font-bold leading-tight tracking-tight text-ink">
            {norma.titulo}
          </h1>

          <Panel titulo="Todavía no hay comparación de texto">
            El antes y el después de cada artículo vive en <code className="font-mono text-xs">version_norma</code>,
            que se rellena cuando el extractor descarga el texto íntegro y el clasificador
            deriva el diff (CLAUDE.md sección 7). De esta norma se ha ingerido y archivado su
            entrada en el sumario; el texto completo aún no se ha procesado. Mientras tanto, el
            enlace a la fuente oficial de abajo lleva al texto tal cual lo publica el BOE.
          </Panel>

          <div className="mt-3.5 rounded border border-line border-l-4 border-l-line-2 bg-surface p-4">
            <p className="m-0 text-sm text-ink-2">
              <strong className="font-semibold text-ink">Faro Cuir no interpreta la norma.</strong>{" "}
              Mostramos el texto tal como aparece publicado y el enlace a la fuente oficial. La
              clasificación indica el sentido del cambio respecto al texto anterior, no una
              valoración política.
            </p>
          </div>

          <section className="mt-6 rounded border border-line bg-surface">
            <h2 className="border-b border-line bg-inset px-4 py-3 text-sm font-semibold text-ink">
              Metadatos de la norma
            </h2>
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
                  <PrefiltroBadge
                    estado={norma.prefiltro_estado}
                    terminos={norma.prefiltro_terminos}
                    ejes={norma.prefiltro_ejes}
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
                        Texto íntegro en el BOE ↗
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
        </div>

        <aside className="sticky top-[150px] flex flex-col gap-3.5">
          <IntegrityPanel documento={documento} />
          <section className="rounded border border-dashed border-line-2 bg-inset p-4">
            <h2 className="m-0 text-[13.5px] font-semibold text-ink">Historial de la norma</h2>
            <p className="m-0 mt-1.5 text-xs leading-relaxed text-ink-2">
              El encadenado de versiones de un mismo artículo se construye a partir de{" "}
              <code className="font-mono">version_norma</code>, que es inmutable por diseño. Con
              una sola pasada de ingesta todavía no hay histórico que recorrer.
            </p>
          </section>
        </aside>
      </div>
    </>
  );
}

/**
 * Ficha de una norma, con datos reales de `GET /api/documentos/{id}`.
 *
 * La API expone las normas anidadas en su documento, así que aquí se pide el documento y se
 * busca la norma dentro. No se añade `GET /api/normas/{id}` al backend solo para esto: el
 * documento se necesita igualmente (la fecha de publicación, el hash y el sello son suyos, no
 * de la norma), de modo que sería una segunda petición para no ahorrar ninguna.
 *
 * Buena parte de lo que enseñaba el mock aquí no existe todavía y por eso no se pinta:
 * clasificación, diff e historial dependen de `deteccion` y `version_norma`, vacías hasta que
 * exista el pipeline. En su lugar se explica qué falta y por qué.
 */
export function FichaPage({ seleccion, onIrAlArchivo }: FichaPageProps) {
  const estado = useRecurso<DocumentoDetalleApi | null>(
    (signal) =>
      seleccion === null ? Promise.resolve(null) : obtenerDocumento(seleccion.documentoId, signal),
    [seleccion?.documentoId],
  );

  const documento = estado.fase === "listo" ? estado.datos : null;
  const norma = documento?.normas.find((item) => item.id === seleccion?.normaId) ?? null;

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-6">
      {seleccion === null && (
        <div className="mx-auto max-w-[70ch] rounded border border-dashed border-line-2 bg-surface p-8 text-center">
          <h1 className="m-0 font-serif text-xl font-bold text-ink">Ninguna norma seleccionada</h1>
          <p className="mt-2 text-sm text-ink-2">
            Esta pantalla muestra una norma concreta con datos reales de la API. Elige una en el
            archivo de documentos ingeridos.
          </p>
          <button
            type="button"
            onClick={onIrAlArchivo}
            className="mt-4 rounded bg-ink px-3.5 py-2 text-sm text-surface"
          >
            Ir al Archivo
          </button>
        </div>
      )}

      {seleccion !== null && estado.fase === "cargando" && (
        <p className="text-sm text-ink-2">Cargando la norma…</p>
      )}

      {seleccion !== null && estado.fase === "error" && (
        <div className="rounded border border-dashed border-line-2 bg-surface p-8 text-center">
          <p className="m-0 font-semibold text-ink">No se ha podido cargar la norma</p>
          <p className="mt-1.5 text-sm text-ink-2">{describirError(estado.error)}</p>
        </div>
      )}

      {/* El documento existe pero no contiene esa norma: id obsoleto tras reingerir, o mal
          formado. Es distinto de un error de red y merece su propio mensaje. */}
      {seleccion !== null && documento !== null && norma === null && (
        <div className="rounded border border-dashed border-line-2 bg-surface p-8 text-center">
          <p className="m-0 font-semibold text-ink">Esa norma ya no está en el documento</p>
          <p className="mt-1.5 text-sm text-ink-2">
            El documento {documento.identificador_oficial} se ha cargado, pero no contiene
            ninguna norma con el identificador interno {seleccion.normaId}.
          </p>
          <button
            type="button"
            onClick={onIrAlArchivo}
            className="mt-4 rounded bg-ink px-3.5 py-2 text-sm text-surface"
          >
            Volver al Archivo
          </button>
        </div>
      )}

      {documento !== null && norma !== null && (
        <Ficha documento={documento} norma={norma} onIrAlArchivo={onIrAlArchivo} />
      )}
    </main>
  );
}
