/**
 * El catálogo de reglas, **en lenguaje que se pueda leer**.
 *
 * ## Por qué esto existe
 *
 * `CLAUDE.md` 7.6 dice, literalmente, que «una alerta publicada tiene que poder reconstruirla un
 * tercero leyendo la regla y el texto archivado, **sin ejecutar nuestro código**». Hasta hoy la
 * interfaz imprimía `regla R-MOD-001` y no había ningún sitio donde leer qué dice R-MOD-001: ese
 * tercero tenía el texto archivado y los offsets, pero no tenía la regla. La exigencia estaba
 * escrita y no se cumplía.
 *
 * ## Esto es una traducción, no la fuente
 *
 * La fuente es `backend/app/pipeline/reglas.py`. Aquí solo se enuncian en castellano, y por eso
 * hay dos salvaguardas:
 *
 * 1. **La versión se publica** (`VERSION_REGLAS`). Un enunciado sin versión no sirve para
 *    auditar: las reglas cambian, y una alerta de hace un mes se clasificó con el catálogo de
 *    hace un mes.
 * 2. **Hay un test que impide que esto se desincronice** (`backend/tests/test_catalogo_publicado.py`):
 *    comprueba que la versión de aquí es la de `reglas.py` y que no falta ni sobra ningún
 *    identificador. Un glosario que se queda atrás es peor que no tener glosario, porque explica
 *    mal con aire de autoridad.
 *
 * ## Lo que estos enunciados NO dicen
 *
 * Ninguna regla afirma un signo que no pueda sostener. Tres de las cinco emiten `indeterminado` a
 * propósito, y eso no es un fallo del catálogo: derogar es lo que hace tanto quien desmonta una
 * ley como quien la sustituye por otra mejor, y decidir cuál de las dos exige leer qué ocupa el
 * lugar de lo derogado. Eso lo hace una persona en el gate, no una expresión regular.
 */

/** La del catálogo con la que se clasificaron las alertas. Debe coincidir con `reglas.py`. */
export const VERSION_REGLAS_PUBLICADA = "2026.08.30.2";

export interface ReglaPublicada {
  id: string;
  /** Qué la dispara, en una frase. */
  enunciado: string;
  /** Qué evidencia exige guardar. Es lo que permite comprobarla contra el texto archivado. */
  evidencia: string;
  /** Qué signo emite, y por qué ese y no otro. */
  signo: string;
}

/**
 * En **orden de evaluación**, que es información y no presentación: el catálogo devuelve el
 * primer veredicto que encaja, así que una norma que suprime preceptos de una norma vigilada sale
 * como `R-SUP-001` aunque además la modifique. Sin el orden, dos reglas parecen alternativas
 * cuando en realidad una tapa a la otra.
 */
export const CATALOGO_REGLAS: ReglaPublicada[] = [
  {
    id: "R-SUP-001",
    enunciado:
      "El documento suprime preceptos, y la propia referencia declara que los suprimidos son de una norma vigilada. El verbo tiene que ir pegado a la norma: que el texto contenga una supresión y además toque la watchlist, por separado, no basta.",
    evidencia:
      "La cláusula de supresión con sus offsets sobre el texto archivado, y el identificador de la norma a la que se le suprime.",
    signo:
      "Retroceso **solo si la norma suprimida es protectora** —una ley LGTBI o trans—, porque suprimir un precepto de una norma de derechos no tiene lectura buena: no hace falta saber qué ocupa su lugar, porque no lo ocupa nada. Si lo suprimido es una norma-vehículo —la Ley del SNS, el Registro Civil, la LOE— **no afirma signo y cae a indeterminado**: ahí el derecho vive en dos o tres preceptos y el resto es materia ajena, así que suprimir uno cualquiera no es un retroceso LGTBI. Sigue yendo a la cola de revisión con su evidencia.",
  },
  {
    id: "R-DER-001",
    enunciado: "El documento deroga una norma vigilada.",
    evidencia: "La cláusula de derogación con sus offsets, y la norma derogada.",
    signo:
      "Sin signo, a propósito. Derogar es lo que hace tanto quien desmonta una ley como quien la sustituye por otra mejor — la Ley 4/2023 deroga y es un avance. Cuál de las dos cosas es exige leer qué ocupa el lugar de lo derogado, y eso lo decide una persona.",
  },
  {
    id: "R-MOD-001",
    enunciado:
      "El documento da nueva redacción a un precepto de una norma vigilada —en presente o en futuro: «queda» y «quedará redactado» cuentan igual— y el texto consolidado permite reconstruir qué decía antes y qué dice ahora.",
    evidencia:
      "Las cláusulas modificadoras con sus offsets, más los preceptos reescritos con su redacción anterior y la nueva, y la huella del consolidado del que salen.",
    signo:
      "Sin signo. Establece el hecho —antes decía esto, ahora dice esto otro— y deja el veredicto a quien lea las dos redacciones. Es la regla que más se dispara sobre normativa sanitaria.",
  },
  {
    id: "R-SUP-003",
    enunciado:
      "El documento suprime un órgano (consejo, observatorio, comisión) y en la MISMA cláusula aparece un término del vocabulario vigilado. Las dos condiciones en cláusulas distintas no disparan.",
    evidencia: "La cláusula con el verbo y el nombre del órgano, y el término que aparece con él.",
    signo:
      "Sin signo. Existe porque «se suprime el Consejo LGTBI de Aragón» no nombra ninguna norma vigilada —ese consejo lo creó un decreto que no está en la watchlist— y sin ella desaparecía quien vigila la ley sin que nadie lo mirase. Suprimir un órgano puede ser desmantelarlo o fundirlo con otro.",
  },
  {
    id: "R-SUP-002",
    enunciado:
      "El documento suprime preceptos, pero no se puede establecer que sean de ninguna norma vigilada ni de ningún órgano del ámbito.",
    evidencia: "La cláusula de supresión con sus offsets.",
    signo:
      "Sin signo, y es la de menos confianza del catálogo. Dispara con cualquier «se suprime el artículo 7» de cualquier materia. No llega al gate humano por sí sola —lo decidió el ADR 0017 con datos: iba 10 de 10 descartada— pero la detección se sigue creando y queda registrada.",
  },
];

/** Busca el enunciado de una regla por su identificador. `undefined` si el catálogo no la trae. */
export function reglaPublicada(id: string | null): ReglaPublicada | undefined {
  if (!id) return undefined;
  return CATALOGO_REGLAS.find((regla) => regla.id === id);
}
