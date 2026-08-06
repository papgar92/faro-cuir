import type { DocumentoApi } from "../../api/client";
import { formatearSelloTiempo } from "../../lib/formato";

interface IntegrityPanelProps {
  documento: DocumentoApi;
}

/**
 * Cadena de verificación del documento del que sale la norma: hash y sello de tiempo reales,
 * tal y como los devuelve la API (CLAUDE.md 6.5).
 *
 * Este panel dice **solo lo que el sistema puede sostener hoy**, que es menos de lo que decía
 * el mock. En concreto:
 *
 * - No pone "✓ Íntegro". Esa palabra afirma que se ha vuelto a descargar el documento y el
 *   hash sigue coincidiendo, y eso no lo hace nadie todavía. Lo que sí es cierto es que está
 *   archivado con su huella, y eso es lo que se dice.
 * - No hay autoridad de sellado. El mock anunciaba "freetsa.org (RFC 3161)"; el sello de hoy
 *   lo pone nuestro propio ingestor, así que es afirmación nuestra y no prueba frente a
 *   terceros. El RFC 3161 está planteado como evolución en el ADR 0005 y aquí se declara
 *   como pendiente, no como hecho.
 *
 * Regla de oro 8: si no está verificado, se marca; no se rellena con algo plausible.
 */
export function IntegrityPanel({ documento }: IntegrityPanelProps) {
  const copiarHash = () => {
    void navigator.clipboard?.writeText(documento.sha256).catch(() => {
      // Portapapeles no disponible (contexto no seguro o sin permiso); no bloquea la UI.
    });
  };

  return (
    <section className="rounded border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line bg-inset px-4 py-3">
        <h2 className="text-[13.5px] font-semibold text-ink">Cadena de verificación</h2>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs font-semibold text-neu">
          <span aria-hidden="true">⛁</span>Archivado
        </span>
      </div>
      <div className="flex flex-col gap-3.5 p-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
            Hash del documento (SHA-256)
          </div>
          <code className="mt-1.5 block break-all rounded border border-line bg-inset px-2.5 py-2 font-mono text-[11.5px] leading-relaxed text-ink">
            {documento.sha256}
          </code>
        </div>

        <dl className="m-0 flex flex-col gap-2.5 text-xs">
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Sello de tiempo</dt>
            <dd className="m-0 font-mono">{formatearSelloTiempo(documento.sello_tiempo)}</dd>
          </div>
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Documento</dt>
            <dd className="m-0 font-mono">{documento.identificador_oficial}</dd>
          </div>
          <div className="flex justify-between gap-2.5">
            <dt className="shrink-0 text-ink-3">Origen de la captura</dt>
            <dd className="m-0 min-w-0 truncate text-right font-mono">
              <a href={documento.url_original} target="_blank" rel="noopener noreferrer">
                {new URL(documento.url_original).host}
              </a>
            </dd>
          </div>
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Sellado por un tercero</dt>
            <dd className="m-0 text-right font-mono text-ink-3">Pendiente (ADR 0005)</dd>
          </div>
        </dl>

        <p className="m-0 text-xs leading-relaxed text-ink-2">
          El hash corresponde al contenido descargado de la fuente oficial, byte a byte. Sirve
          para comprobar que lo que archivamos es lo que se publicó. El sello de tiempo lo pone
          por ahora nuestro propio ingestor: acredita cuándo lo capturamos, no es todavía una
          prueba verificable por terceros.
        </p>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={copiarHash}
            className="flex-1 rounded border border-line-2 px-2.5 py-2 text-xs text-ink hover:border-ink-3"
          >
            Copiar hash
          </button>
          <button
            type="button"
            disabled
            title="Disponible cuando el sellado RFC 3161 esté implementado (ADR 0005)"
            className="flex-1 cursor-not-allowed rounded border border-line-2 px-2.5 py-2 text-xs text-ink-3"
          >
            Descargar sello
          </button>
        </div>
      </div>
    </section>
  );
}
