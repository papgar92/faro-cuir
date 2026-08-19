# ADR 0020 — Una norma que el sistema no puede leer tiene su propio estado

- **Fecha**: 2026-08-18/19 (medición el 18, decisión e implementación el 19)
- **Estado**: aceptado
- **Contexto de tarea**: cierre del hueco de cobertura del DOGC (ESTADO.md, 2026-08-18).
- **Números libres**: el siguiente libre tras este es el **0021**.

## Contexto

Buscando candidatos del DOGC para el gold set apareció que algunos cuerpos archivados fallaban
al parsearse con `DtdForbidden`: el documento declara un DOCTYPE y `xml_safe` lo rechaza, que es
exactamente lo que 6.1 le manda hacer. La primera estimación, sobre una lectura parcial, fue de
12 normas.

**Medido de verdad el 2026-08-18, después de drenar la fase 2 (`--fase2`, que dejó la cola de
descarga a cero), son 172 de 264: el 65 % de la segunda fuente del proyecto.** Y hay un segundo
hallazgo que cambia el diagnóstico entero:

> Las 172 no son XML con un DOCTYPE de más. **Son la página de error del Portal Jurídic**, 12 KB
> de cromo de la Generalitat servidos con **HTTP 200** en la URL del XML castellano que el propio
> conjunto de datos abiertos anuncia para cada disposición. Ni una línea del articulado.

Comprobado además para una de ellas (`DOGC-24291044`, ORDEN ESP/214/2024): la versión catalana
del XML devuelve la misma página de error, el HTML es un contenedor de JavaScript sin articulado
—cero apariciones de «Artículo» o «Anexo» en 77 KB— y **el PDF sí existe y es nativo**
(883 KB, `%PDF-1.7`).

O sea que el dato archivado con su `sha256` y su sello de tiempo, bajo `tipo='texto_norma'`, es
una página de error. Y el pipeline no podía decirlo.

### Lo que pasaba después, que es el problema de verdad

`services/cuerpo.leer_cuerpo` devolvía `None` en dos casos que no son el mismo: «todavía no hay
cuerpo archivado» y «lo hay y no se puede leer». Con un solo valor para los dos, el prefiltro
degradaba a fase 1 —evaluar solo el título, que nunca descarta (7.1)— y la norma acababa en
`pendiente`, indistinguible de las que esperan su descarga.

Consecuencias, todas silenciosas:

- **El embudo mentía.** 172 normas contadas como «esperando su texto íntegro» cuando su texto
  llevaba días en el disco. Nadie las iba a volver a mirar, porque el estado decía que el trabajo
  pendiente era de otra etapa.
- **La cobertura del DOGC aparentaba ser la que no era.** La interfaz decía «Catalunya:
  autonómico, 1 de 1 vigilada» (ADR 0014) mientras dos de cada tres normas de esa fuente no las
  leía nadie.
- **Una de ellas estaba en la cola del extractor**, con un `sospecha` sacado de su título. Habría
  sumado un fallo por pasada, para siempre: el extractor lee el cuerpo del almacén.
- Es **el falso negativo invisible de la sección 1**, esta vez causado por un control de
  seguridad propio funcionando correctamente.

## Decisión

**Un quinto estado de prefiltro, `ilegible`** (7.2), y la distinción en el tipo que lo hace
posible.

1. **`leer_cuerpo` levanta `CuerpoIlegible`** cuando hay cuerpo archivado y no se puede leer o
   parsear, y reserva `None` para «todavía no hay cuerpo». El motivo real viaja en `__cause__` y
   ya se ha registrado. Se eligió una excepción y no una variante del valor devuelto porque
   **obliga a los cuatro llamantes a decidir**, que es lo contrario de lo que hacía el `None`
   compartido: prefiltro, extractor, catálogo de reglas y versionado.
2. **`prefiltro.evaluar` recibe `cuerpo_ilegible`** y devuelve `ILEGIBLE` **por delante de
   cualquier señal del título**, incluso de un título lleno de vocabulario del proyecto.
3. **`ILEGIBLE` no entra en la cola del extractor** ni en la del catálogo de reglas ni en la del
   versionado: las tres leen el cuerpo del almacén.
4. **Se conservan los términos del título** en la fila, aunque el estado no sea de cola. Son la
   única pista para priorizar la recuperación a mano.
5. **`prefiltro_version_texto` se queda a NULL, así que se reintenta en cada pasada.** Es
   deliberado y es lo único que recupera estas normas solas el día que su cuerpo se pueda leer.
6. **El embudo lo cuenta aparte**: en el log del worker, en `/api/documentos`, en
   `/api/cobertura` y en las dos pantallas que las enseñan.

**No se relaja `xml_safe`.** Un DOCTYPE en un documento de una fuente externa es justo lo que
este proyecto decidió no procesar (6.1), y en este caso concreto el control es además lo único
que impidió que 172 páginas de error se colaran en el pipeline como si fueran normas: el
prefiltro las habría descartado todas por falta de vocabulario y **nada habría fallado
visiblemente**. Es el mismo modo de fallo que el ADR 0019 documenta con el articulado dentro de
un atributo XML.

## Alternativas descartadas

**Dejarlas en `pendiente` y arreglar solo el log.** Es lo que había. Un log se lee una vez, el
día que se ejecuta; el estado se consulta siempre. La cifra hay que poder pedírsela a la base de
datos, no encontrarla en un fichero de texto de anteayer.

**Marcarlas `descartada`.** Es la opción que más ruido quita y la peor. `descartada` significa
«leído y no nos afecta»: un hecho sobre el contenido. Aquí no se ha leído nada. Sería convertir un
fallo nuestro en una afirmación sobre la norma, que es exactamente lo que este proyecto existe
para no hacer.

**No archivar lo que no parsea, y dejar la norma en la cola de la fase 2.** Suena más limpio y
tiene dos defectos. Uno práctico: 172 descargas por pasada contra una fuente pública, para
siempre, y una cola que nunca baja. Otro de fondo: **el archivo tiene que conservar lo que la
fuente sirvió** (6.5), y que el portal devolviera una página de error con HTTP 200 en la URL que
él mismo publica es un hecho que merece quedar registrado con su huella. La interpretación —esto
no es texto usable— es del pipeline, y por eso vive en el estado de la norma y no en el archivo.

**Reintentar en otro formato dentro de esta decisión.** Es la opción 1 que ESTADO.md dejó
abierta, y sigue abierta: para estas 172 el único formato con contenido es el PDF, y eso es una
etapa de extracción de texto de PDF (permitida por 6.1: texto sí, OCR no) con su propio trabajo y
su propio ADR. **Este ADR es la parte que no depende de aquella**: haya o no recuperación por
PDF, una norma que el sistema no puede analizar tiene que verse.

**Una columna con el motivo del fallo.** Se descarta por ahora: el motivo se reproduce en
cualquier momento sobre el documento archivado —de eso va 6.5— y ya está en el log. Una columna
más habría que mantenerla y no contesta ninguna pregunta que el archivo no conteste.

## Consecuencias

- **La cobertura del DOGC deja de aparentar lo que no es.** Sobre datos reales: 264 normas → 41
  sospecha, 51 descartada, **172 ilegible**, 0 pendiente. Antes esas mismas 172 se leían como
  «pendientes de descarga» con la descarga hecha.
- Migración `b8d2e40a71c5`, escrita a mano: sustituye la CHECK `estadoprefiltro`. Verificado tras
  aplicarla: **14 CHECK del proyecto, `origenclasificacion` intacta**.
- Sin UPDATE masivo en la migración, igual que la `d4f2a8c61b90` con `sospecha`: quién es
  ilegible lo decide el pipeline leyendo el almacén. Las 172 filas recibieron su estado en la
  primera pasada de `--reprefiltrar`.
- El `downgrade` devuelve `ilegible` a `pendiente`, y eso **pierde información**: vuelve a mezclar
  los dos huecos. Queda dicho en la migración.
- La cifra que hay que decir siempre junto a cualquier medición del DOGC: **el eje léxico solo se
  ha evaluado sobre el texto íntegro de 92 de sus 264 normas**. Cualquier recall calculado sobre
  esta fuente es un recall sobre ese 35 %.
- **`GET /api/cobertura` deja de poder afirmar una vigilancia que no existe.** Lo señaló la
  auditoría de seguridad de este mismo diff, y con razón: la regla que este ADR añade a 7.2
  —«cualquier cifra de cobertura va acompañada de cuántas de sus normas son ilegibles»— la
  incumplía justamente la única ruta que existe para declarar los huecos del proyecto (ADR 0014).
  El desglose por comunidad gana `normas` e `ilegibles`, siempre las dos: `ilegibles` a solas no
  dice si son 172 de 264 o de 20.000. En la interfaz, el panel de Catalunya sigue diciendo
  «Autonómico 1 de 1» —es verdad, la fuente está activa— y debajo dice que 172 de sus 264 normas
  no se han analizado. Las dos cosas son ciertas y hacen falta las dos.
- Lo que sigue sin hacer: el **color del mapa** se calcula con `vigiladas`, no con la parte
  legible. Una comunidad con fuente activa y todo su contenido ilegible se pintaría igual que una
  vigilada de verdad; hoy no ocurre porque el 35 % legible del DOGC sí se analiza.
