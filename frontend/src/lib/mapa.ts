import type { AlertaApi, CoberturaApi } from "../api/client";
import { CCAA_PATHS } from "../components/MapaCCAA/ccaa-paths";
import type { EstadoMapa } from "./classification";
import { nombreTerritorio } from "./territorio";

/**
 * El mapa, construido con datos reales. Sustituye a `REGIONS` de `mocks.ts` (2026-08-17).
 *
 * ## Las tres categorías, y por qué son tres y no dos
 *
 * La versión de maqueta pintaba cada comunidad de un color y ya. Con datos reales eso miente en
 * el caso que más importa, que es el mayoritario: **una comunidad sin alertas no es una comunidad
 * estable**. Puede ser que nadie haya aprobado nada todavía, o que ahí no estemos mirando. Así
 * que hay tres estados visuales y el más importante es el que no es un color:
 *
 * 1. **Con alertas aprobadas** → el color de su clasificación. Es lo único que el sistema
 *    afirma, y solo lo afirma después del gate humano (regla de oro 4).
 * 2. **Vigilada, sin alertas aprobadas** → trama clara. Hay una fuente integrada y el pipeline
 *    la mira; todavía no ha salido nada aprobado. **No es «estable»**: es «no hay conclusión».
 * 3. **Sin fuente vigilada** → trama densa. Ahí no estamos mirando, y decirlo es la mitad del
 *    valor de este mapa. Hoy son 15 de 17 comunidades.
 *
 * Confundir 2 con 3 sería tan malo como pintarlas de gris «estable»: convertiría el silencio en
 * tranquilidad. Por eso la distinción está en el relleno, en la etiqueta accesible y en el panel.
 *
 * ## De dónde sale cada dato
 *
 * - Las **alertas** de `GET /api/alertas`, que solo devuelve lo aprobado por una persona. El
 *   territorio no sale de la fuente sino de `normas_vigiladas[].ambito`, o sea de la watchlist:
 *   una ley autonómica se publica en el BOE, así que por fuente sería «estatal» y la comunidad
 *   quedaría en blanco justo en el caso que este proyecto existe para enseñar.
 * - La **cobertura** de `GET /api/cobertura`, que publica siempre conocidas y vigiladas juntas.
 */

/** Estado visual de una comunidad. `null` = no hay conclusión, y eso se pinta con trama. */
export type EstadoRegion = EstadoMapa | null;

export interface RegionMapa {
  code: string;
  name: string;
  /** `null` cuando no hay ninguna alerta aprobada: no se inventa un estado. */
  state: EstadoRegion;
  alerts: number;
  /** ¿Hay al menos una fuente integrada y activa en esta comunidad? */
  vigilada: boolean;
  fuentesVigiladas: number;
  fuentesConocidas: number;
  /** Titular y fecha de la alerta más reciente, si la hay. */
  title?: string;
  date?: string;
  rango?: string;
}

/**
 * Clasificación de la alerta → estado del mapa.
 *
 * `indeterminado` va a `alerta` («sin signo») y **no** a `estable`: el catálogo de reglas se
 * abstuvo de decir hacia dónde, y pintar eso de color neutro sería emitir el veredicto del que
 * la regla se abstuvo (7.6).
 */
const ESTADO_POR_CLASIFICACION: Record<AlertaApi["clasificacion"], EstadoMapa> = {
  avance: "avance",
  retroceso: "retroceso",
  neutro: "estable",
  indeterminado: "alerta",
};

/** Orden de gravedad: si una comunidad tiene varias alertas, manda la peor. */
const GRAVEDAD: EstadoMapa[] = ["estable", "avance", "alerta", "retroceso"];

export function construirRegiones(
  alertas: AlertaApi[] | undefined,
  cobertura: CoberturaApi | undefined,
): Record<string, RegionMapa> {
  const regiones: Record<string, RegionMapa> = {};

  // **El universo son las comunidades del mapa, no las que aparecen en la cobertura.** La
  // cobertura solo lista territorios con alguna fuente registrada, así que las comunidades
  // uniprovinciales —que no tienen BOP propio— faltaban y los recuentos salían cortos: «9 sin
  // fuente integrada» cuando son 16. Un denominador incompleto en una pantalla que mide huecos
  // de cobertura es justo el error que no se puede cometer aquí.
  for (const path of CCAA_PATHS) {
    regiones[path.code] = {
      code: path.code,
      name: path.name,
      state: null,
      alerts: 0,
      vigilada: false,
      fuentesVigiladas: 0,
      fuentesConocidas: 0,
    };
  }

  // La cobertura define QUÉ se está mirando, que es independiente de si ha salido algo.
  for (const ccaa of cobertura?.por_ccaa ?? []) {
    const region = (regiones[ccaa.ccaa_codigo] ??= {
      code: ccaa.ccaa_codigo,
      name: ccaa.ccaa,
      state: null,
      alerts: 0,
      vigilada: false,
      fuentesVigiladas: 0,
      fuentesConocidas: 0,
    });
    region.vigilada = ccaa.vigiladas > 0;
    region.fuentesVigiladas = ccaa.vigiladas;
    region.fuentesConocidas = ccaa.conocidas;
  }

  // Después las alertas, que solo pueden añadir estado a lo que ya existe o crear la entrada si
  // la cobertura todavía no ha llegado (las dos peticiones son independientes).
  for (const alerta of alertas ?? []) {
    for (const vigilada of alerta.normas_vigiladas) {
      // `estatal` no es una comunidad: una norma estatal afecta a todas y pintarla en una sola
      // sería falso. Se deja fuera del mapa a propósito; su sitio es la pantalla de Alertas.
      if (!vigilada.ambito || vigilada.ambito === "estatal") continue;

      const region = (regiones[vigilada.ambito] ??= {
        code: vigilada.ambito,
        // Solo se llega aquí si la watchlist trae un código que el mapa no dibuja; el nombre
        // legible sale del propio código para no enseñar «MD» en una lista.
        name: nombreTerritorio(vigilada.ambito),
        state: null,
        alerts: 0,
        vigilada: false,
        fuentesVigiladas: 0,
        fuentesConocidas: 0,
      });

      region.alerts += 1;
      const estado = ESTADO_POR_CLASIFICACION[alerta.clasificacion];
      if (region.state === null || GRAVEDAD.indexOf(estado) > GRAVEDAD.indexOf(region.state)) {
        region.state = estado;
      }
      // La lista llega ordenada de más reciente a más antigua, así que el titular de la primera
      // que toque esta comunidad es el más nuevo.
      if (!region.title) {
        region.title = alerta.norma.titulo;
        region.date = alerta.fecha_publicacion;
        region.rango = alerta.regla_aplicada ?? undefined;
      }
    }
  }

  return regiones;
}

/** Las comunidades con alguna alerta, de más a menos. Para el ranking lateral. */
export function regionesConAlertas(regiones: Record<string, RegionMapa>): RegionMapa[] {
  return Object.values(regiones)
    .filter((region) => region.alerts > 0)
    .sort((a, b) => b.alerts - a.alerts || a.name.localeCompare(b.name, "es"));
}
