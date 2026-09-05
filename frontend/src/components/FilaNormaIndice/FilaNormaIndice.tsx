import type { NormaApi } from "../../api/client";
import { HuellaArchivo } from "../HuellaArchivo/HuellaArchivo";
import { PrefiltroBadge } from "../PrefiltroBadge/PrefiltroBadge";

/**
 * Una norma en el índice del Archivo.
 *
 * ## El botón lleva dentro lo justo, y eso es un arreglo de accesibilidad
 *
 * La fila anterior metía **todo** dentro de un solo `<button>`: identificador, título completo
 * —los del BOE pasan de 400 caracteres—, órgano, la insignia del prefiltro con sus hasta 20
 * chips de términos y la huella con el hash. El nombre accesible de ese botón era la
 * concatenación de todo eso, así que un lector de pantalla anunciaba un párrafo por fila, y
 * había sesenta.
 *
 * Aquí el botón lleva **identificador + título** y nada más; la insignia y la huella son
 * hermanas suyas, fuera del control. Es el mismo patrón que ya usaba el enlace al boletín, que
 * era hermano y no anidado porque un `<a>` dentro de un `<button>` no es HTML válido.
 *
 * ## La huella sigue en el índice, y no es negociable
 *
 * Que el archivo sea verificable es una propiedad de **todo** lo ingerido, incluidas las
 * descartadas. Enseñarla solo en las interesantes daría a entender lo contrario, y es
 * justamente lo que la sección 6.5 no admite.
 */
export function FilaNormaIndice({
  norma,
  seleccionada,
  onAbrir,
}: {
  norma: NormaApi;
  seleccionada: boolean;
  onAbrir: () => void;
}) {
  return (
    <li
      className={`border-b border-line px-4 py-2.5 last:border-b-0 ${
        seleccionada ? "bg-inset" : "hover:bg-inset"
      }`}
    >
      <button
        type="button"
        onClick={onAbrir}
        // `aria-current="true"` y no un color: quien navega sin ver la pantalla necesita que
        // "esta es la que estás leyendo" esté en el árbol de accesibilidad, no en el fondo.
        aria-current={seleccionada ? "true" : undefined}
        className={`block w-full text-left ${seleccionada ? "border-l-2 border-l-ink pl-2 -ml-2" : ""}`}
      >
        <span className="block font-mono text-[11px] text-ink-3">
          {norma.identificador_oficial}
        </span>
        {/* line-clamp mantiene el índice escaneable: un título del BOE llena la columna
            entera. El completo está en la ficha de la derecha, a un clic. */}
        <span className="mt-0.5 line-clamp-2 block text-[13px] leading-snug text-ink">
          {norma.titulo}
        </span>
        <span className="mt-0.5 block truncate text-[11px] text-ink-3">
          {norma.organo_emisor ?? "Órgano emisor no informado"}
        </span>
      </button>
      <div className="mt-1.5">
        <PrefiltroBadge
          estado={norma.prefiltro_estado}
          terminos={norma.prefiltro_terminos}
          ejes={norma.prefiltro_ejes}
        />
      </div>
      <div className="mt-1">
        <HuellaArchivo archivo={norma.texto_archivado} />
      </div>
    </li>
  );
}
