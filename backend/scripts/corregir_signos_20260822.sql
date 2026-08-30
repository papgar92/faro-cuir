-- Corrección puntual de dos signos humanos publicados al revés. 2026-08-22.
--
-- QUÉ PASÓ. La noche del 2026-08-21, entre las 21:06 y las 21:17, una persona resolvió los nueve
-- ítems de la cola de revisión. En dos de ellos el signo que quedó guardado es el contrario del
-- que sostenía su informe de apoyo y, sobre todo, el contrario de lo que dice el texto archivado:
--
--   * cola 21 — Orden SSI/2065/2014 (BOE-A-2014-11444). Es la orden que ató la reproducción
--     asistida del SNS a un diagnóstico de esterilidad y a «12 meses de coito vaginal», dejando
--     fuera a mujeres sin pareja, lesbianas y personas trans con capacidad de gestar. Quedó
--     publicada como `avance`. Es un retroceso, y lo reconoce por escrito el propio Ministerio en
--     el preámbulo de la Orden SND/1215/2021.
--
--   * cola 23 — Orden SCB/480/2019 (BOE-A-2019-6277). Crea el cribado poblacional de cáncer de
--     cérvix e incluye la micropigmentación de areola y pezón en la reconstrucción mamaria. Quedó
--     publicada como `retroceso`. Las dos prestaciones son nuevas: es un avance, con un borde de
--     género que merece señalarse pero que no invierte el signo.
--
-- CAUSA PROBABLE. Los cuatro títulos aprobados esa noche son casi idénticos («Orden …, por la que
-- se modifican los anexos … del Real Decreto 1030/2006…») y en el panel los radios «Avance» y
-- «Retroceso» van pegados. Nueve ítems en once minutos. Queda como tarea de producto: el gate
-- tiene que hacer el signo difícil de errar, no solo posible de fijar.
--
-- QUÉ TOCA ESTE SCRIPT, Y QUÉ NO.
--   * Toca SOLO `cola_revision.clasificacion_humana`, que es el campo que fijó la persona.
--   * NO reabre la cola: `estado` sigue en `aprobada` y `resuelta_en` no se toca. El ADR 0017 dice
--     que un ítem resuelto no se reabre, y esto no lo reabre.
--   * NO re-emite nada: no se crea ni se borra ninguna fila de `alerta`.
--   * NO toca `deteccion.clasificacion`, que es lo que derivó la regla auditable del archivo y no
--     es de nadie más (ADR 0004). Las dos siguen en `indeterminado`, que es lo correcto: R-MOD-001
--     establece el hecho, no el signo.
--
-- POR QUÉ ESTE FICHERO EXISTE. Corregir en silencio un dato ya publicado es exactamente la
-- desindexación sin registro que este proyecto documenta para denunciarla (6.5). Si se cambia, se
-- deja escrito qué, cuándo y por qué. Autorizado por el humano el 2026-08-22.
--
-- Idempotente: las condiciones del WHERE incluyen el valor viejo, así que reejecutarlo no hace
-- nada y no puede volver a invertir un signo ya corregido.

BEGIN;

UPDATE cola_revision
   SET clasificacion_humana = 'retroceso'
 WHERE id = 21
   AND clasificacion_humana = 'avance';

UPDATE cola_revision
   SET clasificacion_humana = 'avance'
 WHERE id = 23
   AND clasificacion_humana = 'retroceso';

COMMIT;
