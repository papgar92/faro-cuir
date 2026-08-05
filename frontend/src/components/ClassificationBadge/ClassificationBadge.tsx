import { COLOR_CLASSES, type ClassificationMeta } from "../../lib/classification";

interface ClassificationBadgeProps {
  meta: ClassificationMeta;
  className?: string;
}

/**
 * Glifo + etiqueta + color. Nunca solo color (CLAUDE.md, accesibilidad AA):
 * el glifo es aria-hidden porque es decorativo, la etiqueta de texto es el
 * contenido accesible real.
 */
export function ClassificationBadge({ meta, className = "" }: ClassificationBadgeProps) {
  const colors = COLOR_CLASSES[meta.color];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-xs font-semibold ${colors.bg} ${colors.text} ${colors.border} ${className}`}
    >
      <span aria-hidden="true">{meta.glyph}</span>
      {meta.label}
    </span>
  );
}
