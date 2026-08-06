import { useMemo, useState, type ReactNode } from "react";
import type { DocumentoDetalleApi, NormaApi } from "../api/client";
import { listarDocumentos, obtenerDocumento } from "../api/client";
import { describirError, useRecurso } from "../api/useRecurso";
import { acortarHash, formatearFecha, formatearSelloTiempo } from "../lib/formato";

/**
 * Un sumario del BOE trae ~250 normas y la API las devuelve todas en la respuesta del
 * documento. Pintarlas todas de golpe no rompe nada, pero convierte la pantalla en un muro
 * ilegible: el tope obliga a usar el buscador, que es la forma real de encontrar algo aquí.
 */
const NORMAS_VISIBLES = 60;

/** Quita acentos y baja a minúsculas para que "fisicas" encuentre "Físicas". */
function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();
}

function Aviso({ children }: { children: ReactNode }) {
  return (
    <div className="rounded border border-dashed border-line-2 bg-surface p-6 text-center text-sm text-ink-2">
      {children}
    </div>
  );
}

function FilaNorma({ norma }: { norma: NormaApi }) {
  return (
    <li className="grid grid-cols-1 gap-1 border-b border-line px-4 py-3 last:border-b-0 sm:grid-cols-[190px_minmax(0,1fr)_auto] sm:gap-4">
      <span className="font-mono text-xs text-ink-3">{norma.identificador_oficial}</span>
      <div className="min-w-0">
        {/* line-clamp mantiene la lista escaneable: los títulos del BOE pasan de 400
            caracteres y uno solo llenaría la pantalla. */}
        <p className="m-0 line-clamp-2 text-sm text-ink">{norma.titulo}</p>
        <p className="m-0 mt-1 text-xs text-ink-3">
          {norma.organo_emisor ?? "Órgano emisor no informado"}
        </p>
      </div>
      {norma.url_texto ? (
        <a
          href={norma.url_texto}
          target="_blank"
          // noopener corta el acceso de la pestaña abierta a `window.opener`, y noreferrer
          // evita anunciar a la fuente desde dónde se la consulta.
          rel="noopener noreferrer"
          className="self-start whitespace-nowrap text-xs"
        >
          Texto íntegro ↗
        </a>
      ) : (
        // Sin URL no se pinta un enlace muerto: parecer funcional sin serlo es peor que
        // decir que no hay (backlog de CLAUDE.md sección 12).
        <span className="self-start whitespace-nowrap text-xs text-ink-3">Sin enlace</span>
      )}
    </li>
  );
}

function CabeceraDocumento({ documento }: { documento: DocumentoDetalleApi }) {
  return (
    <div className="border-b border-line bg-inset px-4 py-3.5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-mono text-sm font-semibold text-ink">
          {documento.identificador_oficial}
        </h2>
        <span className="text-xs text-ink-2">{formatearFecha(documento.fecha_publicacion)}</span>
        <span className="text-xs text-ink-3">
          {documento.normas.length}{" "}
          {documento.normas.length === 1 ? "norma" : "normas"}
        </span>
        <span className="ml-auto font-mono text-[11px] text-ink-3">
          estado: {documento.estado_pipeline}
        </span>
      </div>
      <dl className="mt-2.5 grid grid-cols-1 gap-x-6 gap-y-1 text-[11.5px] sm:grid-cols-2">
        <div className="flex gap-2">
          <dt className="text-ink-3">sha256</dt>
          <dd className="m-0 truncate font-mono text-ink-2" title={documento.sha256}>
            {acortarHash(documento.sha256)}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="text-ink-3">sello</dt>
          <dd className="m-0 font-mono text-ink-2">
            {formatearSelloTiempo(documento.sello_tiempo)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * Archivo: la única pantalla que hoy enseña **datos reales de la API**.
 *
 * Existe porque la Ficha necesita el id de una norma real y las otras dos pantallas no pueden
 * dárselo: sus alertas son inventadas. Además el archivo de lo ingerido no es material de
 * relleno — con su hash y su sello es el entregable de la sección 6.5, así que merece
 * pantalla propia y no esconderse en un desplegable.
 */
export function ArchivoPage() {
  const [documentoElegido, setDocumentoElegido] = useState<number | null>(null);
  const [busqueda, setBusqueda] = useState("");

  const lista = useRecurso((signal) => listarDocumentos({ limite: 100 }, signal), []);

  // Sin elección explícita se abre el más reciente: la API ya los devuelve ordenados por
  // fecha descendente, y con un solo documento ingerido obligar a un clic previo sería ruido.
  const documentoId =
    documentoElegido ?? (lista.fase === "listo" ? (lista.datos[0]?.id ?? null) : null);

  const detalle = useRecurso<DocumentoDetalleApi | null>(
    (signal) => (documentoId === null ? Promise.resolve(null) : obtenerDocumento(documentoId, signal)),
    [documentoId],
  );

  const documento = detalle.fase === "listo" ? detalle.datos : null;

  const coincidencias = useMemo(() => {
    if (!documento) return [];
    const aguja = normalizar(busqueda.trim());
    if (!aguja) return documento.normas;
    return documento.normas.filter(
      (norma) =>
        normalizar(norma.titulo).includes(aguja) ||
        normalizar(norma.identificador_oficial).includes(aguja) ||
        normalizar(norma.organo_emisor ?? "").includes(aguja),
    );
  }, [documento, busqueda]);

  return (
    <main className="mx-auto max-w-[1360px] px-7 pb-2 pt-7">
      <div className="max-w-[900px]">
        <div className="flex flex-wrap items-center gap-2.5">
          <h1 className="font-serif text-2xl font-bold tracking-tight text-ink">
            Archivo de documentos ingeridos
          </h1>
          <span className="rounded border border-adv bg-adv-bg px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wide text-adv">
            Datos reales
          </span>
        </div>
        <p className="mt-2 max-w-[70ch] text-sm text-ink-2">
          Todo lo que Faro Cuir ha descargado y archivado, tal cual salió de la fuente oficial.
          De cada documento se guarda su huella SHA-256 y el momento de la captura, para que
          cualquiera pueda comprobar que lo archivado es lo que se publicó. Abre una norma para
          ver su ficha.
        </p>
      </div>

      <div className="mt-5 max-w-[900px]">
        {lista.fase === "cargando" && <Aviso>Cargando el archivo…</Aviso>}

        {lista.fase === "error" && (
          <Aviso>
            <p className="m-0 font-semibold text-ink">No se ha podido cargar el archivo</p>
            <p className="mt-1.5">{describirError(lista.error)}</p>
          </Aviso>
        )}

        {lista.fase === "listo" && lista.datos.length === 0 && (
          <Aviso>
            <p className="m-0 font-semibold text-ink">Todavía no hay nada ingerido</p>
            <p className="mt-1.5">
              Lanza el worker de ingesta para poblar el archivo:{" "}
              <code className="font-mono text-xs">
                python -m worker.run --fuente boe --fecha 2024-12-19
              </code>
            </p>
          </Aviso>
        )}

        {lista.fase === "listo" && lista.datos.length > 1 && (
          <nav aria-label="Documentos ingeridos" className="mb-4 flex flex-wrap gap-2">
            {lista.datos.map((doc) => (
              <button
                key={doc.id}
                type="button"
                onClick={() => setDocumentoElegido(doc.id)}
                aria-current={doc.id === documentoId ? "true" : undefined}
                className={`rounded border px-3 py-1.5 font-mono text-xs ${
                  doc.id === documentoId
                    ? "border-ink-3 bg-surface-2 text-ink"
                    : "border-line-2 text-ink-2 hover:border-ink-3"
                }`}
              >
                {doc.identificador_oficial}
              </button>
            ))}
          </nav>
        )}

        {detalle.fase === "error" && (
          <Aviso>
            <p className="m-0 font-semibold text-ink">No se ha podido cargar el documento</p>
            <p className="mt-1.5">{describirError(detalle.error)}</p>
          </Aviso>
        )}

        {documento && (
          <section className="rounded border border-line bg-surface">
            <CabeceraDocumento documento={documento} />

            <div className="border-b border-line px-4 py-3">
              <label htmlFor="buscar-norma" className="block text-xs text-ink-3">
                Buscar por título, identificador u órgano emisor
              </label>
              <input
                id="buscar-norma"
                type="search"
                value={busqueda}
                onChange={(evento) => setBusqueda(evento.target.value)}
                placeholder={`Buscar entre ${documento.normas.length} normas…`}
                className="mt-1.5 w-full rounded border border-line-2 bg-inset px-3 py-2 text-sm text-ink placeholder:text-ink-3"
              />
              <p aria-live="polite" className="mt-2 m-0 font-mono text-xs text-ink-3">
                {coincidencias.length}{" "}
                {coincidencias.length === 1 ? "norma coincide" : "normas coinciden"}
                {coincidencias.length > NORMAS_VISIBLES &&
                  ` · se muestran las ${NORMAS_VISIBLES} primeras`}
              </p>
            </div>

            {coincidencias.length === 0 ? (
              <p className="m-0 px-4 py-8 text-center text-sm text-ink-2">
                Ninguna norma de este documento coincide con la búsqueda.
              </p>
            ) : (
              <ul className="m-0 list-none p-0">
                {coincidencias.slice(0, NORMAS_VISIBLES).map((norma) => (
                  <FilaNorma key={norma.id} norma={norma} />
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
