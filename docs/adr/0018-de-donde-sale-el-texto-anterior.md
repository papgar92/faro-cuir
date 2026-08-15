# ADR 0018 — De dónde sale el texto anterior

- **Fecha**: 2026-08-15
- **Estado**: aceptado
- **Contexto de tarea**: poblar `version_norma`, que estaba vacía desde que se creó. Es lo único
  del pipeline que quedaba sin cerrar (CLAUDE.md 5 y 7.6).
- **Números libres**: 0013 sigue **reservado** (sección 9). El siguiente libre tras este es el
  0019.

## Contexto

El catálogo de reglas (7.6) tiene dos familias escritas —supresión y derogación— y no puede
tener una tercera. El motivo está escrito en la cabecera de `pipeline/reglas.py` y es el mismo
desde el ADR 0016:

> Una norma modificativa del BOE publica la redacción **nueva** («El artículo 4 queda redactado
> como sigue: …»), no la vieja, y `version_norma` está vacía: el diff de una *modificación*
> todavía no se puede construir.

Supresión y derogación son justo las dos familias que **no** necesitan texto anterior. Las demás
sí, y la modificación es la mayoritaria: de las 436 normas medidas en el ADR 0011, 67
referencias `MODIFICA` frente a 7 `DEROGA`.

Y no es un hueco cualquiera. El caso insignia del proyecto —`BOE-A-2024-10767`, la reforma
madrileña de 2023— hace las dos cosas: suprime artículos (que el sistema ya ve) y **reescribe
otros** (que no ve). Su artículo 4 pasa de

> «Artículo 4. Reconocimiento del **derecho a la identidad de género libremente manifestada**.»

a

> «Artículo 4. Reconocimiento del **respeto a la libertad y dignidad de las personas
> transexuales**.»

Ese cambio es exactamente el retroceso silencioso de la sección 1: el precepto sigue ahí, el
articulado sigue numerado igual, y lo que se ha ido es el reconocimiento de la identidad de
género manifestada. **Solo se ve comparando.** Sin texto anterior, el sistema archiva la
redacción nueva y no tiene con qué decir que antes decía otra cosa.

## Decisión

**El texto anterior sale de la legislación consolidada del BOE, se archiva aparte con su propia
huella, y el par (texto_anterior, texto_nuevo) se guarda en `version_norma` por bloque tocado.**

La API de datos abiertos sirve cada norma consolidada dividida en bloques, y **cada bloque
conserva sus redacciones sucesivas con la norma que introdujo cada una**. Estructura verificada
contra documentos reales el 2026-08-15, no deducida de documentación:

```
response > data > texto > bloque[@id="a7"][@tipo="precepto"][@titulo="Artículo 7"]
                            ├── version[@id_norma="BOE-A-2016-6728"][@fecha_vigencia="20160427"]
                            └── version[@id_norma="BOE-A-2024-10767"][@fecha_vigencia="20231230"]
```

De ahí sale el diff sin inventar nada: la versión cuyo `id_norma` es la norma que estamos
analizando es el texto nuevo, y la inmediatamente anterior del mismo bloque es el texto anterior.
Sobre el consolidado real de `BOE-A-2016-6728` (81 bloques), la reforma aparece en **34**.

Cuatro decisiones que van con esta y no son detalles de implementación:

1. **La URL se compone con el identificador de la watchlist, nunca con el del documento.** La
   6.10 dice que un identificador extraído de una fuente externa se compara con la watchlist
   pero **no se usa para construir una petición**. Aquí el `<analisis>` de la norma del día solo
   decide *a cuál* de las entradas de `config/watchlist.json` hay que mirar; la dirección se
   compone con el identificador de nuestro fichero versionado, y `url_consolidado` revalida el
   formato con `PATRON_IDENTIFICADOR` antes de interpolarlo. La petición pasa además por
   `url_guard` entero (ADR 0006). Son tres controles en serie sobre el mismo dato porque es el
   único punto del sistema donde algo escrito por otros decide a qué recurso se apunta.
2. **El consolidado es una elaboración del BOE, no lo que se publicó aquel día**, y por eso
   entra en el archivo con `tipo='consolidado'` y no como un `texto_norma` más. Mezclarlos haría
   que el archivo dejara de poder afirmar «el día X este documento decía exactamente esto», que
   es toda su utilidad (6.5). Cada fila de `version_norma` apunta al documento consolidado del
   que salió, con su `sha256`: un diff que nadie pueda rebatir con el fichero delante no sirve
   para el gate humano.
3. **`version_norma.norma_id` es la norma modificadora, y la modificada va como identificador de
   texto** (`norma_afectada`). Es la única opción honesta: la Ley 2/2016 de Madrid es de hace
   ocho años y **no tiene fila en `norma`**, porque nunca salió de un sumario que hayamos
   ingerido. Apuntarle con una clave ajena obligaría a inventarse una `norma` sin documento del
   que colgar, que es peor que guardar el identificador oficial, que es el dato que de verdad la
   nombra en cualquier fuente.
4. **Las notas del consolidador no entran en el diff.** El BOE anota los cambios dentro de
   `<blockquote><p class="nota_pie">` («Se suprime por el art. único.7 de la Ley 17/2023…»). Es
   metadato editorial, no articulado. Dejarlo dentro ensuciaría el diff con texto que nadie
   legisló y, peor, haría que **toda** redacción tocada pareciera distinta por la nota antes que
   por el cambio.

## Alternativas consideradas

- **Derivar el texto anterior de nuestro propio archivo.** Sería lo ideal —fuente primaria, ya
  sellada— y no se puede: solo hay tres días de BOE archivados y las normas modificadas son de
  2007, 2016, 2023. Queda como evolución natural el día que el archivo tenga años de fondo: la
  misma tabla vale, cambiando la procedencia.
- **Pedirle el texto anterior al LLM.** Descartada por los mismos cuatro motivos del ADR 0016, y
  aquí con uno más grave: el modelo no tiene el texto anterior delante, así que solo podría
  **inventarlo**. Sería la alucinación más difícil de detectar del sistema, porque tendría
  exactamente la forma correcta.
- **Raspar el HTML consolidado** (`/buscar/act.php`). Misma información, formato inestable y sin
  la atribución por norma que trae el XML. La API existe, es gratis y no necesita clave.
- **Marcar como agotada la norma cuyo cambio no está consolidado.** Descartada: la consolidación
  llega con retraso de días o semanas, así que agotarla significaría dejar de mirar justo lo que
  sí va a aparecer. Se reintenta, con el tope y la pausa de 6.2.

## Consecuencias

- **El catálogo de reglas puede crecer**, que era el objetivo. Con `version_norma` poblada, una
  familia de reglas sobre modificación ya tiene con qué compararse. **Este ADR no la escribe**:
  aquí se establece el hecho, el veredicto sigue siendo del catálogo, con `regla_aplicada` y
  spans (7.6).
- **El sistema depende de un segundo servicio del BOE** y de su ritmo de consolidación. Está
  acotado: un tope por ejecución (20), una pausa de un segundo, y candidatas que por definición
  son poquísimas —solo normas que modifican algo de la watchlist—.
- **Una norma cuya modificación nunca se consolide se reintenta cada pasada, para siempre.** Es
  una petición al día contra una fuente pública, y es el precio de no dejar de mirar. Queda
  escrito para que nadie lo descubra como si fuera un fallo.
- **El archivo crece con documentos que no son boletines.** Un consolidado son cientos de KB y
  puede llegar a megas. La fila de `documento` lleva el hash del contenido en el identificador,
  así que cada estado consolidado que hayamos visto es una fila distinta e inmutable y volver a
  descargar el mismo estado reutiliza la fila. Es la única fila del archivo cuyo identificador
  no es literalmente el que da la fuente, y está dicho en el código.
- **Falta medir el volumen real**, igual que se midió la fase 2 antes de fijar su umbral (ADR
  0011). Hoy se sabe el tamaño de cuatro consolidados, no la distribución. Mientras tanto, el
  tope pequeño hace que equivocarse salga barato.
- La EIPD no cambia: el consolidado es contenido público de la misma fuente que ya se archiva, y
  el tratamiento descrito en `docs/eipd.md` para el archivo íntegro lo cubre sin excepciones
  nuevas.
