/**
 * Metadatos visuales de clasificación (glifo + etiqueta + color). Nunca solo color:
 * CLAUDE.md exige que la clasificación se distinga también por icono/texto para
 * cumplir accesibilidad AA sin depender de la percepción del color.
 *
 * Dos vocabularios distintos, tal como venían en el diseño (frontend/_design-export):
 * - EstadoMapa: agregado por comunidad autónoma en la vista de mapa (4 estados).
 * - ClasificacionAlerta: clasificación de una alerta/detección individual (3 estados).
 * Ninguno de los dos es todavía el `deteccion.clasificacion` de CLAUDE.md sección 5
 * (avance|retroceso|neutro|indeterminado) — se reconciliará al cablear la API real.
 */

export type EstadoMapa = "avance" | "estable" | "retroceso" | "alerta";
export type ClasificacionAlerta = "avance" | "retroceso" | "neutro";
export type ColorClasificacion = "adv" | "reg" | "neu" | "alr";

export interface ClassificationMeta {
  label: string;
  glyph: string;
  color: ColorClasificacion;
}

export const ESTADO_MAPA_META: Record<EstadoMapa, ClassificationMeta> = {
  avance: { label: "Avance reciente", glyph: "▲", color: "adv" },
  estable: { label: "Estable", glyph: "●", color: "neu" },
  retroceso: { label: "Retroceso reciente", glyph: "▼", color: "reg" },
  alerta: { label: "Alerta activa", glyph: "⚠", color: "alr" },
};

export const CLASIFICACION_ALERTA_META: Record<ClasificacionAlerta, ClassificationMeta> = {
  avance: { label: "Avance", glyph: "▲", color: "adv" },
  retroceso: { label: "Retroceso", glyph: "▼", color: "reg" },
  neutro: { label: "Neutro", glyph: "●", color: "neu" },
};

/**
 * Clases Tailwind literales por color. Deben quedar completas en el código fuente
 * (no construidas con template strings tipo `text-${color}`): el escáner de
 * contenido de Tailwind v4 solo detecta nombres de clase que aparecen tal cual.
 */
export const COLOR_CLASSES: Record<
  ColorClasificacion,
  { text: string; bg: string; border: string }
> = {
  adv: { text: "text-adv", bg: "bg-adv-bg", border: "border-adv" },
  reg: { text: "text-reg", bg: "bg-reg-bg", border: "border-reg" },
  neu: { text: "text-neu", bg: "bg-neu-bg", border: "border-neu" },
  alr: { text: "text-alr", bg: "bg-alr-bg", border: "border-alr" },
};
