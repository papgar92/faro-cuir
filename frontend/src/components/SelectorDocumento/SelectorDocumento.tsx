import type { DocumentoApi } from "../../api/client";
import { formatearFecha } from "../../lib/formato";

/**
 * Elegir qué boletín se está mirando.
 *
 * ## Arregla un agujero, no un detalle de comodidad
 *
 * Antes esto era **un botón por documento**, sin recorte, en un `flex-wrap`. Con 100 documentos
 * eran 100 botones monoespaciados; y como el archivo tiene 798, **698 documentos archivados no
 * eran alcanzables desde ninguna pantalla**. Un sistema que afirma custodiar un archivo íntegro
 * no puede tener el 87 % de ese archivo fuera de su propia interfaz.
 *
 * El `<select>` nativo lo resuelve por dos sitios: cabe en una línea y trae gratis la búsqueda
 * por teclado del sistema operativo, que en una lista de fechas es exactamente lo que se quiere.
 * Y los controles de página alcanzan el resto.
 *
 * ## Por qué no se agrupa por fuente
 *
 * Sería lo natural —hay cuatro— pero `DocumentoResumen` no publica la fuente: el modelo tiene
 * `Documento.fuente_id` y el esquema no lo expone. La alternativa sería descifrar el prefijo del
 * identificador, y ese formato **lo pone la fuente, no nosotros** (`ingest/boe.py` lo dice), así
 * que agrupar por él sería construir sobre un formato ajeno que puede cambiar sin avisarnos.
 * Queda anotado: son ~3 líneas de backend y un cambio de API pública, o sea una decisión.
 */
export function SelectorDocumento({
  documentos,
  documentoId,
  pagina,
  hayPaginaSiguiente,
  onElegir,
  onPagina,
}: {
  documentos: DocumentoApi[];
  documentoId: number | null;
  pagina: number;
  hayPaginaSiguiente: boolean;
  onElegir: (id: number) => void;
  onPagina: (pagina: number) => void;
}) {
  const indice = documentos.findIndex((doc) => doc.id === documentoId);

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="min-w-[280px] flex-1">
        <label htmlFor="elegir-documento" className="block text-xs text-ink-3">
          Boletín archivado
        </label>
        <select
          id="elegir-documento"
          value={documentoId ?? ""}
          onChange={(evento) => onElegir(Number(evento.target.value))}
          className="mt-1.5 w-full rounded border border-line-2 bg-inset px-3 py-2 font-mono text-sm text-ink"
        >
          {documentos.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {doc.identificador_oficial} · {formatearFecha(doc.fecha_publicacion)}
            </option>
          ))}
        </select>
      </div>

      {/* Anterior y siguiente DENTRO de la página cargada: es el movimiento que se hace mil
          veces —ver el boletín de ayer— y no debería costar abrir un desplegable de 100. */}
      <div className="flex gap-1.5">
        <button
          type="button"
          disabled={indice <= 0}
          onClick={() => onElegir(documentos[indice - 1]!.id)}
          className="rounded border border-line-2 px-2.5 py-2 text-xs text-ink-2 hover:border-ink-3 disabled:opacity-40"
        >
          ‹ más reciente
        </button>
        <button
          type="button"
          disabled={indice < 0 || indice >= documentos.length - 1}
          onClick={() => onElegir(documentos[indice + 1]!.id)}
          className="rounded border border-line-2 px-2.5 py-2 text-xs text-ink-2 hover:border-ink-3 disabled:opacity-40"
        >
          más antiguo ›
        </button>
      </div>

      {(pagina > 0 || hayPaginaSiguiente) && (
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[11px] text-ink-3">pág. {pagina + 1}</span>
          <button
            type="button"
            disabled={pagina === 0}
            onClick={() => onPagina(pagina - 1)}
            className="rounded border border-line-2 px-2.5 py-2 text-xs text-ink-2 hover:border-ink-3 disabled:opacity-40"
          >
            «
          </button>
          <button
            type="button"
            disabled={!hayPaginaSiguiente}
            onClick={() => onPagina(pagina + 1)}
            className="rounded border border-line-2 px-2.5 py-2 text-xs text-ink-2 hover:border-ink-3 disabled:opacity-40"
          >
            »
          </button>
        </div>
      )}
    </div>
  );
}
