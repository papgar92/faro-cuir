# ADR 0016 — Cómo se representa una supresión sin texto

- **Fecha**: 2026-08-09
- **Estado**: aceptado
- **Contexto de tarea**: desbloqueo del clasificador por diff (CLAUDE.md 7.6) sobre el caso que
  7.8 señala como el más importante del gold set.
- **Números libres**: 0010 y 0013 siguen **reservados** (sección 9). El siguiente libre tras
  este es el 0017.

## Contexto

El subagente `jurista-lgtbi`, en su primera ejecución real (2026-08-09), no encontró un
problema jurídico sino uno de código, y bloqueante:

> `_articulos_con_algun_texto` (`schemas/extraccion.py:87-96`) descarta la extracción **entera**
> si un artículo llega sin `texto_anterior` ni `texto_nuevo`.

Y las supresiones no traen texto por ninguno de los dos lados. El documento no reproduce lo que
elimina: lo nombra y lo borra. Verificado sobre el cuerpo ya archivado de `BOE-A-2024-10767`
(Ley 17/2023 de la Comunidad de Madrid, la reforma que 7.8 pide expresamente), 44.526
caracteres de texto derivado, **diez supresiones y ni una sola línea del texto suprimido**:

```
Los apartados 1 y 8 del artículo 1 quedan suprimidos.
Los apartados 1, 2 y 3 del artículo 3 quedan suprimidos.
Se suprime el artículo 7.
Queda suprimido el apartado 2 del artículo 9.
Queda suprimido el apartado 2 del artículo 11 sobre descentralización y desconcentración …
El artículo 24 queda suprimido.
El Título X queda suprimido.
El artículo 45 queda suprimido.
El artículo 48 queda suprimido.
Se suprime el Título XIV y se sustituye el Título XIII, que tendrá la siguiente rúbrica …
```

Consecuencia hoy, con el código tal cual está: el modelo lee «El artículo 24 queda suprimido»,
emite el artículo con los dos textos a `null` —que es lo correcto y lo que el prompt le pide—,
el validador rechaza la respuesta **completa**, y con ella se pierden también las trece
modificaciones del mismo documento que sí traen redacción nueva. No queda fila en `deteccion`,
así que **la norma nunca llega a la cola de revisión** y ninguna regla que dependa de
`articulos[]` puede dispararse jamás sobre ella. Además, como la ausencia de fila es
justamente lo que define la cola del extractor, cada barrido que la incluya vuelve a gastar los
133,9 s de LLM medidos en el ADR 0011, indefinidamente y sin producir nada.

Dicho en corto: **el mejor caso del corpus es hoy el único que el pipeline no puede procesar**,
y falla en el modo más caro posible — en silencio, salvo una línea de aviso, y repitiéndose.

Dos datos más del mismo documento, que condicionan la decisión:

1. **La fuente oficial ya declara la supresión, en dos sitios.** El bloque `<analisis>` del XML
   del BOE trae `MODIFICA` sobre `BOE-A-2016-6728` con el texto *«el título, el preámbulo y
   determinados preceptos; y SUPRIME los arts. 7, 24 y 45, 48 y los títulos X y XIV de la Ley
   2/2016»*. El verbo no hay que deducirlo: viene escrito por quien publica.
2. **Ninguna de las dos fuentes es completa por sí sola.** El `<analisis>` resume: declara
   cuatro artículos y dos títulos, y **omite las supresiones de apartados** (arts. 1, 3, 9 y 11)
   que el cuerpo sí recoge. El cuerpo, a su vez, las tiene todas pero en diez redacciones
   sintácticas distintas.

Y un tercer hecho que conviene dejar escrito aquí porque cambia el orden del trabajo que viene:
**`texto_anterior` es casi siempre `null` y no por culpa del extractor.** Una norma modificativa
del BOE publica la redacción *nueva* («El artículo 4 queda redactado como sigue: …»), no la
vieja. El diff del que habla 7.6 no está dentro del documento: hay que construirlo contra la
versión anterior de la norma afectada, y `version_norma` está vacía. La supresión es, en
cambio, el único cambio que **no** necesita el texto anterior para poder clasificarse — lo que
la convierte, paradójicamente, en la primera familia de reglas escribible con lo que hoy está
archivado.

## Decisión

**Una supresión no se representa en el esquema de extracción. Se detecta y se clasifica sobre
el texto archivado, con reglas versionadas que emiten `regla_aplicada` y spans de evidencia.**
No se añade ningún campo `accion` a `ArticuloExtraido`.

Tres piezas, y las tres son necesarias:

1. **El catálogo de reglas de 7.6 lee el texto archivado**, no la salida del modelo. Una regla
   de supresión localiza el lema `suprim*` en las proximidades de una referencia a precepto y
   emite el rango de caracteres sobre el texto archivado como evidencia. El cuerpo es la fuente
   primaria —es el que tiene los spans y el que está completo— y el `<analisis>` es
   **corroboración estructurada** del verbo, no sustituto.
2. **La discrepancia entre cuerpo y `<analisis>` es señal, no ruido.** Una supresión que el
   resumen oficial no menciona (las cinco de apartados en este documento) es exactamente el
   perfil del retroceso silencioso de la sección 1. La regla que compare ambos no está en este
   ADR, pero el diseño tiene que dejarla posible: por eso el cuerpo manda y el resumen se
   guarda, en vez de fiarlo todo al resumen, que sería mucho más cómodo de parsear.
3. **`_articulos_con_algun_texto` deja de descartar la extracción entera.** Un artículo citado
   sin texto pasa a ser válido y se conserva como **puntero**: el hecho de que el documento
   nombra ese precepto. Con dos condiciones que son parte de la decisión, no matices de
   implementación:
   - **El puntero no acciona nada** (regla de oro 10). Por sí solo no produce clasificación
     ninguna. Si la regla no encuentra la supresión en el texto archivado, no hay veredicto,
     por mucho que el modelo haya listado el artículo. Un puntero alucinado es inerte.
   - **Cuántos punteros trae cada extracción se registra**, como se registra el embudo del
     prefiltro. Lo que no se cuenta no se afina.

La premisa que el validador daba por buena —«un artículo sin texto no aporta nada al diff»— era
cierta cuando el diff se esperaba dentro del documento. Ha dejado de serlo: un artículo sin
texto es *precisamente* la forma que tiene una supresión de presentarse.

## Alternativas consideradas

### A — Campo `accion: alta | modificacion | supresion` en `ArticuloExtraido`

Es la opción más directa y es descriptiva, no valorativa: el documento dice literalmente
«queda suprimido», así que el modelo no estaría opinando. Aun así se descarta, por cuatro
motivos ordenados de más a menos grave:

1. **7.6 quedaría desactivado en su punto central.** «Ninguna regla puede consultar al modelo ni
   depender de un campo que venga de su juicio.» `accion` no es un juicio de valor, pero sí es
   una **lectura** del modelo: la alerta más grave del corpus dependería de una palabra escrita
   por un modelo de 3B parámetros sobre un texto redactado por el sujeto vigilado.
2. **Rompe la auditabilidad ante terceros**, que es lo que 7.6 pide de verdad: una alerta
   publicada tiene que poder reconstruirla alguien de fuera leyendo la regla y el texto
   archivado, **sin ejecutar nuestro código**. `accion == "supresion"` no es reconstruible por
   nadie: exigiría el mismo modelo, el mismo digest, la misma semilla y la misma máquina — y a
   día de hoy ni siquiera se registran el digest ni la semilla (deuda conocida, ver `ESTADO.md`).
   «Queda suprimido», en cambio, lo comprueba cualquiera con el XML y el `sha256` delante.
3. **Regala una superficie de inyección barata y silenciosa** (6.7). Con A, basta con que una
   frase del documento consiga que el modelo escriba `modificacion` donde ponía `supresion` para
   apagar la detección: la salida sigue validando contra el esquema, no hay error, no hay
   registro y nadie lo mira. Con la decisión adoptada, apagar la regla exige cambiar el texto
   publicado en el BOE — que es justamente lo que el archivo con sello de 6.5 sirve para
   demostrar que no ha pasado.
4. **Es caro y el dato es gratis.** A obliga a tocar el esquema, subir `VERSION_PROMPT` a v2 y
   **reextraer** lo ya extraído a 133,9 s por norma, para obtener un dato que la fuente ya
   publica dos veces. Las reglas sobre texto archivado se pueden ejecutar hoy mismo sobre los
   652 cuerpos que ya hay en disco, sin una sola llamada al modelo.

Se deja constancia de lo que A tiene a favor, porque es real y puede hacer que se reabra este
ADR: el lenguaje jurídico admite muchas más formas de suprimir que las diez de este documento
(«se deja sin contenido», «pierde vigencia», una tabla que reaparece con una fila menos), y un
modelo generaliza sobre esa variedad mejor que un catálogo de patrones. Si el gold set demuestra
que las reglas se dejan supresiones que el modelo sí ve, la salida **no** es promover `accion` a
disparador: es usarlo, si acaso, como *candidato* que una regla tiene que confirmar contra el
texto archivado antes de clasificar nada.

### A′ — Relajar solo el validador y que «artículo sin texto» signifique supresión

Barato y tentador, y es la peor de todas: convierte la ausencia de un campo en un veredicto
implícito. Un modelo que se quede sin contexto y devuelva un artículo a medias produciría una
supresión inventada, indistinguible de una real, sin que ninguna regla ni ningún revisor pueda
notar la diferencia. Tiene todos los inconvenientes de A y además no está escrito en ningún
sitio.

### C — No tocar nada y aceptar que estos documentos no se procesan

Es la alternativa que hay que descartar explícitamente porque es la que está en vigor por
omisión. Significa que el sistema no ve la reforma madrileña de 2023: el caso que el proyecto
usa para explicar por qué existe. Un vigilante que falla justo en el caso que motivó su
construcción no es un vigilante incompleto, es uno que da confianza infundada (6.9.6).

## Consecuencias

- **El clasificador de 7.6 no depende del extractor para las supresiones.** Estructuralmente ya
  era posible: `deteccion.extraccion_json` es nullable, así que una detección derivada de reglas
  sobre el archivo puede existir con `extraccion_json` a `null`, `origen='derivado_diff'`,
  `regla_aplicada` y sus spans. Es la forma canónica para este caso.
- **Los spans de evidencia son offsets sobre el texto archivado**, o sea el mismo material que
  pide 7.5. Esta decisión adelanta parte de ese trabajo en vez de duplicarlo, y refuerza la
  precondición que el ADR 0015 ya dejó cumplida: el pipeline lee del archivo, así que citar
  contra el archivo es citar contra lo que de verdad se procesó.
- **El catálogo de reglas se versiona** como el vocabulario y la watchlist (`VERSION_REGLAS`),
  y subirlo obliga a reevaluar lo anterior. Sin eso, dos alertas de fechas distintas no serían
  comparables.
- **La fragilidad de los patrones es real y hay que medirla, no afirmarla.** Diez supresiones en
  un solo documento y cinco órdenes sintácticos distintos; el sondeo con el que se escribió este
  ADR se dejó una (la que mezcla supresión y sustitución en la misma frase: «Se suprime el
  Título XIV y se sustituye el Título XIII…»). Eso es un dato sobre el método, no una anécdota:
  **ninguna cifra de cobertura de estas reglas se publica antes del gold set**, igual que con el
  eje léxico.
- **El contrato del extractor se ablanda en un punto y hay que decirlo claro**: una respuesta con
  artículos sin texto ya no se rechaza. Los demás controles siguen intactos —`extra="forbid"`,
  ausencia de campos de valoración, topes de tamaño y de número de artículos, `ambito` de
  vocabulario cerrado—, y la defensa que sustituye a la rechazada no es menor sino mayor: antes
  el artículo sin texto se descartaba con todo lo demás; ahora se conserva y **se corrobora
  contra el archivo antes de que pueda producir nada**.
- **El prompt no cambia y `VERSION_PROMPT` sigue en `extraccion.v1`.** La regla 5 («copia los
  textos LITERALMENTE») ya produce el comportamiento correcto: ante una supresión no hay texto
  que copiar y el modelo devuelve `null`. Lo que estaba mal era el validador que lo castigaba.
- **Lo que este ADR no resuelve, y conviene no confundirlo**: el diff de las *modificaciones*
  sigue sin ser construible, porque el documento no publica la redacción anterior y
  `version_norma` está vacía. Es el siguiente muro del clasificador y no lo tira ninguna de las
  dos opciones que este ADR compara.

## Verificación

Al implementar (commit aparte, después de este ADR), como mínimo:

1. Un test que valide una extracción con un artículo sin ninguno de los dos textos, y que
   compruebe que el resto de artículos del mismo documento sobrevive.
2. Ejecución de las reglas contra el cuerpo **real y ya archivado** de `BOE-A-2024-10767`
   (`data/5e/42/5e42…4317.xml`, `sha256` en la fila `texto_norma` de `documento`), comprobando
   que se localizan las diez supresiones con sus spans y que cada span, recortado del texto
   archivado, contiene literalmente la frase que la regla dice haber encontrado.
3. Comprobación de que un artículo-puntero que **no** aparece corroborado en el texto archivado
   no produce ninguna clasificación.
4. Los casos correspondientes en el gold set, con `clasificacion_esperada` ya rellenable para
   esta familia (hasta ahora estaba en `null` a propósito porque no existía clasificador).
