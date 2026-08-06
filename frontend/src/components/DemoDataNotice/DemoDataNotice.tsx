interface DemoDataNoticeProps {
  /** Qué enseña esta pantalla, para escribir la frase en concreto y no un genérico. */
  que: string;
  /** De qué tablas del modelo depende para dejar de ser un ejemplo. */
  depende: string;
  onIrAlArchivo: () => void;
}

/**
 * Aviso de que la pantalla sirve datos inventados.
 *
 * Va arriba y ocupa ancho completo a propósito. La alternativa —una etiqueta discreta en una
 * esquina— es la que hace que en una demo nadie la lea y el que mira se lleve la impresión de
 * que el sistema tiene datos que no tiene. Aquí eso no es un detalle estético: el proyecto
 * publica el estado de derechos de personas concretas, y aparentar cobertura que no existe es
 * justo el error que no se puede cometer.
 *
 * Color + glifo + texto, nunca solo color (misma regla de accesibilidad que ClassificationBadge).
 */
export function DemoDataNotice({ que, depende, onIrAlArchivo }: DemoDataNoticeProps) {
  return (
    <aside
      aria-label="Aviso sobre el origen de los datos"
      className="mb-5 flex flex-wrap items-start gap-x-3 gap-y-2 rounded border border-alr border-l-4 border-l-alr bg-alr-soft px-4 py-3"
    >
      <span aria-hidden="true" className="text-sm font-semibold text-alr">
        ⚠
      </span>
      <p className="m-0 min-w-0 flex-1 text-sm text-ink-2">
        <strong className="font-semibold text-ink">Datos de ejemplo, no reales.</strong> {que} se
        construye a partir de {depende}, que hoy están vacías: el pipeline de clasificación
        todavía no existe (CLAUDE.md sección 7). Lo que ves aquí es una maqueta con contenido
        inventado para enseñar la interfaz. Los datos que Faro Cuir sí tiene están en el Archivo.
      </p>
      <button
        type="button"
        onClick={onIrAlArchivo}
        className="shrink-0 rounded border border-line-2 bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:border-ink-3"
      >
        Ver los datos reales
      </button>
    </aside>
  );
}
