-- Se fija el signo humano de dos alertas que se aprobaron sin fijarlo. 2026-08-22.
--
-- NO ES UNA CORRECCION DE UN ERROR, y la diferencia con el script hermano
-- (`corregir_signos_20260822.sql`) importa: alli habia dos signos puestos al reves y hubo que
-- darles la vuelta; aqui no habia ninguno. `clasificacion_humana` es opcional a proposito y
-- estas dos se aprobaron dejandola vacia, asi que la web las enseñaba como «sin signo».
--
--   * cola 1 — Ley 4/2023 (BOE-A-2023-5366), la ley trans y LGTBI. Regla `R-DER-001`,
--     `indeterminado`. **Es literalmente el caso que justifica que este campo exista**: esta
--     escrito en el docstring de `services/revision.aprobar` desde que se implemento el gate.
--     La regla se abstiene a proposito porque derogar es lo que hace tanto quien desmonta una
--     ley como quien la sustituye por otra mejor, y solo leyendo el texto se sabe cual de las
--     dos. Aqui es lo segundo.
--
--   * cola 15 — Ley 19/2020 de igualdad de trato y no discriminacion (BOE-A-2021-1663). Regla
--     `R-MOD-001`, que establece el hecho de la modificacion y nunca afirma signo (ADR 0018).
--
-- En los dos casos el signo lo pone una persona que ha leido el texto, que es exactamente para
-- lo que existe la columna: la regla dice lo que puede sostener sola y no mas (regla de oro 2),
-- y quien revisa completa lo que la regla no puede.
--
-- QUE TOCA, Y QUE NO. Identico al script hermano:
--   * Solo `cola_revision.clasificacion_humana`.
--   * NO reabre la cola: `estado` sigue `aprobada` y `resuelta_en` no se toca (ADR 0017).
--   * NO re-emite nada: ninguna fila de `alerta` se crea ni se borra.
--   * NO toca `deteccion.clasificacion`, que es de la regla y de nadie mas (ADR 0004). Las dos
--     siguen en `indeterminado`, y eso es correcto: el catalogo no sostiene ningun signo aqui.
--
-- Va escrito y no suelto por lo mismo de siempre: esto cambia lo que la web publica, y cambiar
-- un dato publicado sin dejar rastro es la desindexacion sin registro que el proyecto denuncia.
-- Pedido por el humano el 2026-08-22.
--
-- Idempotente: el WHERE exige que siga sin signo, asi que reejecutarlo no pisa una decision
-- posterior de nadie.

BEGIN;

UPDATE cola_revision
   SET clasificacion_humana = 'avance'
 WHERE id = 1
   AND clasificacion_humana IS NULL;

UPDATE cola_revision
   SET clasificacion_humana = 'avance'
 WHERE id = 15
   AND clasificacion_humana IS NULL;

COMMIT;
