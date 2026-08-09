# ADR 0015 — Dónde vive el texto íntegro archivado

- **Fecha**: 2026-08-09
- **Estado**: aceptado
- **Contexto de tarea**: 0.c (fase 2 de la ingesta, ADR 0011)

## Contexto

El ADR 0011 decidió que la fase 2 descarga **el día entero**: 4,3 MB y ~10 s por sumario, 0
errores contra el BOE en 436 normas. El umbral de la fase 2 quedó fijado en cero. Lo que ese
ADR no decidió es **dónde se guarda lo descargado**, y hay que decidirlo antes de escribir la
primera línea porque la sección 6.5 no admite guardarlo de cualquier manera: de cada cuerpo
hacen falta `sha256` y `sello_tiempo`, que son los que sostienen la afirmación *"el día X esta
norma decía exactamente esto"*. Esa garantía de archivo es entregable evaluable (sección 1), y
cambiarla después obliga a re-descargar y a re-sellar todo lo ya archivado — con sellos que ya
no dirían la verdad, porque el sello es la fecha en que lo vimos, no la fecha en que lo
movimos de sitio.

Hoy la maquinaria de 6.5 existe **una sola vez**, en la tabla `documento`: `sha256`,
`sello_tiempo`, `ruta_almacen` derivada del hash (`security/hashing.py`), escritura atómica y
`UniqueConstraint(fuente_id, identificador_oficial)`.

## Decisión

**El texto íntegro de una norma se archiva como una fila más de `documento`**, con su propio
`identificador_oficial` (el de la norma: `BOE-A-2024-10767`), y `norma` gana una segunda clave
ajena, `documento_texto_id`, que apunta a ella.

Para que las dos clases de fila sigan siendo distinguibles, `documento` gana un discriminador
explícito:

```
tipo: sumario | texto_norma      (VARCHAR + CHECK, no ENUM nativo, como el resto)
```

- `norma.documento_id` sigue significando **de qué sumario salió** esta norma. No cambia.
- `norma.documento_texto_id` significa **dónde está archivado su cuerpo**. `NULL` mientras no
  se haya descargado, que es exactamente la cola de trabajo de la fase 2.
- Una fila `texto_norma` tiene su `normas` vacío: no es el sumario de nadie.

### Por qué esta y no otra

Lo que decidió, en orden:

1. **La definición de `documento` ya lo cubre.** La sección 5 dice «un documento crudo
   ingerido», no «un boletín». El texto íntegro de una norma es un documento crudo, con su
   identificador oficial, su URL, su contenido exacto y su fecha. No hay que forzar el modelo
   para que quepa: ya cabía.
2. **La garantía de 6.5 se implementa una vez o no es una garantía.** Una tabla nueva con sus
   propias columnas `sha256`/`sello_tiempo` es un segundo sitio donde alguien puede olvidarse
   del sello, escribir sin `os.replace`, o derivar la ruta de algo que no sea el hash. El
   proyecto ya razona así con `url_guard`, `xml_safe` y `llm/provider`: el valor de una puerta
   única está en que sea única. Un archivo con dos semánticas de archivo no es un archivo.
3. **La idempotencia sale gratis y ya está probada.** `UniqueConstraint(fuente_id,
   identificador_oficial)` es lo que hace que la segunda pasada no rehaga el trabajo, y es una
   restricción que ya existe, ya está migrada y ya tiene tests. Una tabla nueva obligaría a
   inventar la suya y a volver a demostrar que funciona.
4. **El coste de mantenimiento es una columna, no un subsistema.** La alternativa "tabla
   nueva" duplica cuatro columnas y toda su migración; esta añade una columna y una FK.

### Qué se pierde, dicho sin adornos

- **Sobrecarga semántica.** `documento` pasa a significar dos cosas y hay que leer `tipo` para
  saber cuál. Es el precio, y se paga con el discriminador explícito en vez de dejarlo
  implícito en "¿tiene normas colgando?", que es la clase de convención que se rompe sola.
- **Dos FK de `norma` a `documento`.** Obliga a `foreign_keys=` explícito en las relaciones
  ORM. Es verboso pero no ambiguo.
- **La API pública cambia de comportamiento si nadie hace nada.** `GET /api/documentos` lista
  `documento` sin filtro: sin tocarla, el día que se archiven los cuerpos empezaría a devolver
  436 filas nuevas por día mezcladas con los sumarios, **en silencio y sin error**. Se filtra
  por `tipo='sumario'` en la misma tarea. Este era el argumento decisivo para que el
  discriminador sea una columna y no una convención: una convención no se puede poner en un
  `WHERE`.

## Alternativas descartadas

**Tabla nueva `cuerpo_norma` (1:1 con `norma`).** Es la más limpia sobre el papel: sin
sobrecarga semántica y sin segunda FK. Se descarta por el punto 2 — replica la maquinaria de
6.5 en un segundo sitio. En un proyecto cuyo entregable evaluable es el rigor de los controles,
tener dos tablas que prometen la misma garantía de archivo con dos implementaciones es
exactamente el hallazgo que un auditor debe señalar. Si algún día un cuerpo necesitara campos
que un sumario no tiene (paginación, versión consolidada, idioma), esta alternativa vuelve a
estar sobre la mesa y la migración es mecánica.

**Columnas en `norma` (`texto_sha256`, `texto_sello`, `texto_ruta`).** La más barata de
escribir y la peor de las tres. Dos motivos: mezcla en una fila *lo que dijo el sumario* con
*lo que archivamos nosotros*, que son hechos de distinta procedencia y distinta fecha; y no
deja sitio para más de un cuerpo por norma, así que el día que el BOE republique un texto
corregido habría que **sobrescribir** el `sha256` y el sello anteriores. Eso destruye la
propiedad que justifica el archivo entero: el sello dejaría de decir cuándo vimos qué, y
"el día X decía esto" pasaría a ser indemostrable justo en el caso en que importa, que es
cuando el texto ha cambiado.

## Consecuencias

- Migración **escrita a mano** (el `autogenerate` lleva cinco intentos de borrar CHECKs
  ajenas): `documento.tipo` con su CHECK y `server_default='sumario'` para las filas que ya
  existen, y `norma.documento_texto_id` nullable con índice.
- La cola de la fase 2 se escribe `documento_texto_id IS NULL AND url_texto IS NOT NULL`. Es
  una consulta, no un estado nuevo: no hay que mantener sincronizada ninguna máquina de
  estados.
- **Descargar y evaluar quedan separados**, y esto no es cosmético: el prefiltro lee el cuerpo
  **del almacén**, no de la red. Así subir `VERSION_VOCABULARIO` y relanzar `--reprefiltrar`
  reevalúa 436 normas sin volver a pedirle nada al BOE. Si se hubieran acoplado, cada retoque
  del diccionario costaría otra descarga del día entero.
- `EstadoPipeline` de una fila `texto_norma` se queda en `ingerido`. El estado del pipeline lo
  lleva la `norma`, no su cuerpo; duplicarlo aquí crearía dos verdades sobre lo mismo.
