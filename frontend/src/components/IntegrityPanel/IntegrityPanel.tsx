import type { FichaDetail } from "../../api/mocks";

interface IntegrityPanelProps {
  integridad: FichaDetail["integridad"];
}

/** Cadena de verificación (hash + sello de tiempo) de la ficha de norma. */
export function IntegrityPanel({ integridad }: IntegrityPanelProps) {
  const copiarHash = () => {
    void navigator.clipboard?.writeText(integridad.hashSha256).catch(() => {
      // Portapapeles no disponible (contexto no seguro o sin permiso); no bloquea la UI.
    });
  };

  return (
    <section className="rounded border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line bg-inset px-4 py-3">
        <h2 className="text-[13.5px] font-semibold text-ink">Cadena de verificación</h2>
        <span className="ml-auto inline-flex items-center gap-1.5 text-xs font-semibold text-adv">
          <span aria-hidden="true">✓</span>Íntegro
        </span>
      </div>
      <div className="flex flex-col gap-3.5 p-4">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-ink-3">
            Hash del documento (SHA-256)
          </div>
          <code className="mt-1.5 block break-all rounded border border-line bg-inset px-2.5 py-2 font-mono text-[11.5px] leading-relaxed text-ink">
            {integridad.hashSha256}
          </code>
        </div>

        <dl className="m-0 flex flex-col gap-2.5 text-xs">
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Sello de tiempo</dt>
            <dd className="m-0 font-mono">{integridad.selloTiempo}</dd>
          </div>
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Autoridad TSA</dt>
            <dd className="m-0 font-mono">{integridad.autoridadTsa}</dd>
          </div>
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Captura</dt>
            <dd className="m-0 font-mono">{integridad.captura}</dd>
          </div>
          <div className="flex justify-between gap-2.5">
            <dt className="text-ink-3">Última comprobación</dt>
            <dd className="m-0 font-mono">{integridad.ultimaComprobacion}</dd>
          </div>
        </dl>

        <p className="m-0 text-xs leading-relaxed text-ink-2">
          El hash corresponde al PDF original descargado de la fuente. Si el documento oficial
          cambia, el hash deja de coincidir y la ficha lo señala.
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
            title="Disponible cuando el sellado de tiempo esté implementado (CLAUDE.md 6.5)"
            className="flex-1 cursor-not-allowed rounded border border-line-2 px-2.5 py-2 text-xs text-ink-3"
          >
            Descargar sello
          </button>
        </div>
      </div>
    </section>
  );
}
