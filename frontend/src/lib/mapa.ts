import type { AlertaApi, CoberturaApi, LeyVigenteApi } from "../api/client";
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
  /**
   * Motivo verificado por el que esta comunidad **no tiene ley autonómica LGTBI**, o `null`.
   *
   * Es la distinción que faltaba y que hacía mentir al mapa en el caso que menos se ve: Aragón
   * sin alertas significa «hay dos leyes vigiladas y nadie las ha tocado», y Castilla y León sin
   * alertas significa «no hay ninguna ley que tocar». Con el mismo relleno, la segunda se leía
   * como tranquilidad.
   *
   * **No es un juicio, es un hecho verificado** (`_sin_ley_autonomica` de la watchlist, con su
   * fecha de comprobación). El mapa dice que no hay marco; no dice si eso está bien o mal, que
   * es lo que prohíbe la regla de oro 2.
   */
  sinLeyAutonomica: string | null;
  /** Leyes autonómicas **en vigor** de esta comunidad. La línea base del mapa. */
  leyesVigentes: LeyVigenteApi[];
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

/**
 * El signo **que se le enseña a quien lee**: el que fijó una persona si lo fijó, y si no el que
 * derivó la regla.
 *
 * Es la misma precedencia que aplican `AlertCard` y el filtro de `GET /api/alertas`, y está aquí
 * porque el mapa la tenía mal: pintaba con `clasificacion` a secas. Con Catalunya —cuya regla se
 * abstuvo (`indeterminado`) y a la que una persona puso «avance»— el mapa la teñía de «sin
 * signo» mientras su tarjeta ponía «Avance». Dos superficies del mismo dato diciendo cosas
 * distintas. Encontrado el 2026-08-22, el mismo dia y por el mismo motivo que en el filtro.
 *
 * Si algún día cambia la precedencia, tiene que cambiar en los tres sitios.
 */
export function signoVisible(alerta: AlertaApi): AlertaApi["clasificacion"] {
  return alerta.clasificacion_humana ?? alerta.clasificacion;
}

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
      sinLeyAutonomica: null,
      leyesVigentes: [],
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
      sinLeyAutonomica: null,
      leyesVigentes: [],
    });
    region.vigilada = ccaa.vigiladas > 0;
    region.sinLeyAutonomica = ccaa.sin_ley_autonomica ?? null;
    region.leyesVigentes = ccaa.leyes_vigentes ?? [];
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
        sinLeyAutonomica: null,
        leyesVigentes: [],
      });

      region.alerts += 1;
      const estado = ESTADO_POR_CLASIFICACION[signoVisible(alerta)];
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

/**
 * Alertas de ámbito **estatal**: las que no se pueden pintar en el mapa.
 *
 * Una norma estatal afecta a las diecisiete comunidades, así que colorearlas todas diría que hay
 * diecisiete cambios cuando hay uno, y colorear una sola sería sencillamente falso. La geometría
 * no puede representar «todo el territorio» sin mentir en una de las dos direcciones, así que
 * salen **fuera del mapa**, con su propio bloque y contadas aparte.
 *
 * Que sea el caso mayoritario ahora mismo no lo hace menos importante: la Ley 4/2023 es estatal,
 * y es la norma que este proyecto usa para explicarse.
 */
export function alertasEstatales(alertas: AlertaApi[] | undefined): AlertaApi[] {
  return (alertas ?? []).filter((alerta) =>
    alerta.normas_vigiladas.some((vigilada) => vigilada.ambito === "estatal"),
  );
}

/** Las comunidades con alguna alerta, de más a menos. Para el ranking lateral. */
export function regionesConAlertas(regiones: Record<string, RegionMapa>): RegionMapa[] {
  return Object.values(regiones)
    .filter((region) => region.alerts > 0)
    .sort((a, b) => b.alerts - a.alerts || a.name.localeCompare(b.name, "es"));
}

/**
 * Cuántas alertas estatales hay **de cada signo**. Un recuento, nunca un estado agregado.
 *
 * La diferencia no es de matiz y es la razón de que esta función devuelva un objeto y no un
 * `EstadoMapa`. Resumir 4 avances y 1 retroceso en un solo valor obligaría a elegir uno, y la
 * regla de `GRAVEDAD` de aquí arriba elegiría `retroceso`: la pantalla afirmaría «España:
 * retroceso» teniendo el 80 % de sus alertas en avance. Eso es un veredicto que ninguna regla
 * emitió y que nadie aprobó — regla de oro 2 — y encima en el sitio más visible de la interfaz.
 *
 * Por eso la banda estatal pinta **una marca por alerta** y no una silueta de España coloreada:
 * a esta escala la unidad es legible, y es lo más honesto que se puede dibujar.
 */
export interface ResumenEstatal {
  total: number;
  /** Recuento por signo visible, en el orden en que se pinta. */
  porSigno: Array<{ signo: AlertaApi["clasificacion"]; alertas: AlertaApi[] }>;
}

const ORDEN_SIGNO: AlertaApi["clasificacion"][] = ["retroceso", "avance", "neutro", "indeterminado"];

export function resumenEstatal(alertas: AlertaApi[] | undefined): ResumenEstatal {
  const estatales = alertasEstatales(alertas);
  const porSigno = ORDEN_SIGNO.map((signo) => ({
    signo,
    alertas: estatales.filter((alerta) => signoVisible(alerta) === signo),
  })).filter((grupo) => grupo.alertas.length > 0);
  return { total: estatales.length, porSigno };
}

/**
 * Cuántos boletines oficiales de esta comunidad se conocen y **no** se están vigilando.
 *
 * Es lo que permite que la trama del mapa deje de ser una mancha uniforme: hoy las quince
 * comunidades sin vigilar se pintan igual, y no son iguales — Andalucía tiene 8 boletines
 * provinciales conocidos sin integrar y La Rioja 1. Esa diferencia está medida desde el ADR 0014
 * y no se veía.
 *
 * Ojo con lo que este número NO dice: no habla del territorio ni de sus derechos, habla **de
 * nosotros**. Es la única variable sobre la que este mapa tiene derecho a hacer un degradado.
 */
export function deudaCobertura(region: RegionMapa): number {
  return Math.max(0, region.fuentesConocidas - region.fuentesVigiladas);
}


/**
 * Las dos vistas del mapa, y por qué hacen falta las dos.
 *
 * `cambios` es lo que había: pinta **movimiento** —las alertas aprobadas—. Es lo que el sistema
 * afirma y solo después del gate humano. Su problema es que el ADR 0027 midió que el eje
 * referencial rinde ~5 casos al año, así que casi todo el mapa está en silencio casi siempre, y
 * un mapa en blanco se lee como «no pasa nada» cuando lo que dice es «no ha cambiado nada».
 *
 * `marco` pinta **estado**: qué ley protectora existe hoy en cada comunidad, de la watchlist,
 * auditada una a una contra boe.es. Es la línea base sobre la que `cambios` es el delta, y es el
 * «Rainbow Map por comunidad autónoma» del pitch (CLAUDE.md sección 1).
 *
 * **Ninguna de las dos puntúa.** `marco` enumera lo que hay, con su identificador del BOE
 * enlazable; decir qué comunidad está «mejor» sería el juicio propio que prohíbe la regla de
 * oro 2, y por eso su paleta es de un tono propio y no la de avance/retroceso.
 */
export type VistaMapa = "cambios" | "marco";

/** Qué marco tiene una comunidad. `null` = no lo sabemos (aún no ha llegado la cobertura). */
export type CategoriaMarco = "ambas" | "lgtbi" | "trans" | "ninguna" | null;

export function categoriaMarco(region: RegionMapa | undefined): CategoriaMarco {
  if (!region) return null;
  // El hecho verificado manda sobre la lista vacía: «no tiene ley» y «todavía no hemos cargado
  // sus leyes» son cosas distintas y solo la primera se puede afirmar.
  if (region.sinLeyAutonomica) return "ninguna";
  if (region.leyesVigentes.length === 0) return null;
  const trans = region.leyesVigentes.some((ley) => ley.tipo === "trans");
  const lgtbi = region.leyesVigentes.some((ley) => ley.tipo === "lgtbi");
  if (trans && lgtbi) return "ambas";
  return trans ? "trans" : "lgtbi";
}

/** Etiqueta de cada categoría: dice **qué existe**, nunca cuánto vale. */
export const MARCO_ETIQUETA: Record<Exclude<CategoriaMarco, null>, string> = {
  ambas: "Ley trans y ley LGTBI",
  trans: "Solo ley de identidad de género",
  lgtbi: "Solo ley LGTBI integral",
  ninguna: "Sin ley autonómica",
};
