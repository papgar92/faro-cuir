import type { TextoArchivadoApi } from "../../api/client";

/**
 * La prueba de que el texto de una norma está archivado y es verificable (CLAUDE.md 6.5).
 *
 * **Por qué esto se enseña y no se queda en la base de datos.** El proyecto afirma "el día X
 * esta norma decía exactamente esto". Esa afirmación es el producto entero, y no vale nada si
 * quien la lee tiene que fiarse: con el sha256 y la fecha delante, cualquiera puede descargar
 * el texto de la fuente oficial, calcular el hash y contrastarlo. Publicar la garantía sin
 * publicar la huella sería pedir confianza, que es justo lo contrario de lo que hace esta
 * herramienta con la administración.
 *
 * El hash va **truncado en pantalla y completo en el `title` y en el portapapeles**: 64
 * caracteres hexadecimales en una lista de 250 normas es ruido ilegible, pero recortarlo sin
 * dar forma de obtener el original convertiría la prueba en decoración.
 */

/** Fecha en local, sin hora: el sello tiene precisión de microsegundos y aquí sobra. */
function fecha(iso: string): string {
  return new Date(iso).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface HuellaArchivoProps {
  archivo: TextoArchivadoApi | null;
  /** En la ficha hay sitio para el hash entero; en la lista no. */
  completo?: boolean;
}

export function HuellaArchivo({ archivo, completo = false }: HuellaArchivoProps) {
  if (!archivo) {
    // Ausencia con motivo, no un hueco. "Todavía no" y "no hay" son estados distintos y
    // pintarlos igual es el error que este proyecto denuncia en otros sitios.
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[10.5px] text-ink-3">
        <span aria-hidden="true">○</span>
        Texto íntegro pendiente de descarga
      </span>
    );
  }

  const corto = `${archivo.sha256.slice(0, 8)}…${archivo.sha256.slice(-6)}`;

  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[10.5px] text-ink-3">
      <span
        className="inline-flex items-center gap-1 rounded border border-line-2 bg-inset px-1.5 py-0.5 text-ink-2"
        title={`Texto íntegro archivado el ${fecha(archivo.sello_tiempo)}. sha256 completo: ${archivo.sha256}`}
      >
        {/* Glifo de la misma familia geométrica que `PrefiltroBadge` (◉ ○ ◌ ◐), y no un
            candado o un escudo: esos están en bloques Unicode que muchas fuentes de sistema
            no cubren y saldrían como caja vacía justo en la insignia que promete rigor. */}
        <span aria-hidden="true">▣</span>
        Texto archivado
      </span>
      <code className="text-ink-3" title={archivo.sha256}>
        sha256 {completo ? archivo.sha256 : corto}
      </code>
      <span>· {fecha(archivo.sello_tiempo)}</span>
      {completo && (
        <a
          href={archivo.url_original}
          target="_blank"
          rel="noreferrer noopener"
          className="underline decoration-line-2 underline-offset-2 hover:text-ink"
        >
          verificar en la fuente
        </a>
      )}
    </span>
  );
}
