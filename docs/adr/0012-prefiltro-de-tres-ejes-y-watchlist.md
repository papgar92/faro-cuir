# ADR 0012 — Prefiltro de varios ejes, watchlist y el cuarto estado

- **Fecha:** 2026-08-08
- **Estado:** aceptada
- **Sustituye parcialmente a:** ADR 0007 (prefiltro léxico con sesgo a recall), que sigue
  vigente en su razonamiento — este ADR le añade ejes, no le cambia el criterio.

## Contexto

El ADR 0011 midió el coste real de la ingesta y movió el prefiltro de sitio. Antes decidía
**qué se descargaba**; ahora se descarga el día entero (4,3 MB y ~10 s de red) y el prefiltro
decide **qué entra en el LLM y en qué orden**, porque una extracción cuesta 133,9 s en esta
máquina — mandarle el día entero serían ~16 h de CPU.

Ese cambio de puesto trajo dos problemas que este ADR resuelve.

### Problema 1: el vocabulario estaba calibrado para títulos

Sobre un título, la *presencia* de un término discrimina. Sobre 200.000 caracteres, no: una
convocatoria de oposición cita la Ley 4/2023 en su temario y dispara igual que la propia ley.
De las 23 normas que el cuerpo dispara y el título no, buena parte son exactamente eso.

### Problema 2: el diccionario tiene un agujero estructural, y es el importante

**Una instrucción que elimina un derecho no dice "identidad de género". Dice "se modifica el
epígrafe 4.3 del anexo II".** Ningún vocabulario, por extenso que sea, detecta eso — y es
precisamente la forma que tiene el retroceso silencioso que define la sección 1.

Hay una fuente de datos para cubrirlo, y ya se conocía: el bloque `<analisis>` del XML de texto
íntegro del BOE trae las normas a las que la disposición hace referencia **y el verbo**
(`MODIFICA`, `DEROGA`, `AÑADE`). Medido sobre 436 normas reales: el 100 % traen `<analisis>`,
solo 43 (9,9 %) traen referencias anteriores y **13 modifican o derogan algo**. De esas 13, el
eje léxico sobre el título detecta **1**.

## Decisión

### 1. Dos ejes, combinados con OR y jamás con AND

- **Eje léxico** (existía): ~90 términos, sin cambios en su lógica.
- **Eje referencial** (nuevo): la disposición **modifica o deroga** una norma de
  `config/watchlist.json`. Pasa el filtro por definición, diga lo que diga su texto.
- **Eje semántico**: hueco reservado, fuera de alcance (sección 8).

Con AND, dos filtros de alto recall se convierten en uno de bajo recall. Nunca AND.

### 2. Cuarto estado, `sospecha`, y el umbral que no puede hacer daño

El conteo de términos directos separa `RELEVANTE` de `SOSPECHA` y **nunca decide un descarte**.
Ambos estados entran en la cola del extractor; lo único que cambia es el orden.

Esto es lo más importante de este ADR. El umbral (`UMBRAL_DIRECTOS_RELEVANTE = 8`) **está sin
validar y no se puede validar hasta el gold set**. En vez de retrasar el trabajo hasta tenerlo,
se ha construido el sistema para que **equivocarse con ese número cueste latencia y no recall**.
Un umbral mal puesto retrasa normas en la cola; jamás las pierde.

El 8 no sale de una calibración. Los cuatro documentos medidos en el ADR 0011 (43 / 11 / 9 / 3
términos) contaban **todos** los términos, directos y de contexto, mientras que aquí se cuentan
solo los directos: no son comparables. Es un valor de arranque, y está escrito como tal en el
código para que nadie lo cite como si estuviera comprobado.

### 3. Sobre el título solo no se descarta nunca

Una norma sin señal evaluada solo con el sumario queda `PENDIENTE`, no `DESCARTADA`
(CLAUDE.md 7.1). El título es lo que un redactor controla; decidir sobre él es decidir sobre lo
que el redactor quiso que pareciera.

### 4. La watchlist falla ruidosamente

Si no se encuentra, no se puede leer, está vacía o trae un identificador con formato inválido,
**el proceso no arranca**. Una watchlist vacía no rompe nada: el eje deja de disparar y el
sistema sigue funcionando, aparentemente bien, habiendo perdido la única defensa contra la
instrucción que no se nombra. Ese es el fallo que hay que hacer imposible.

### 5. El identificador se valida y nunca construye nada

`PATRON_IDENTIFICADOR` está anclado por los dos extremos, y el valor **no se usa jamás para
construir una URL, una ruta ni una consulta** (regla de oro 10). Hoy no se usa para nada de
eso; el control está en el validador precisamente para que siga siendo cierto mañana.

## Alternativas consideradas

- **Bajar el umbral y descartar por debajo.** Descartada: convierte un parámetro sin validar en
  una fuente de falsos negativos. La asimetría del proyecto (mejor 50 falsos positivos que 1
  falso negativo) obliga a lo contrario.
- **Usar `posteriores` del bloque `<analisis>`.** Descartada: son las normas que modificaron a
  esta *después*, y el día que se ingiere el documento no existen. Disparar por ellas sería
  disparar por el futuro.
- **Aceptar cualquier verbo como modificativo.** Descartada. `CITA` es exactamente el falso
  positivo que produce el eje léxico; si citar bastara, este eje metería en la cola el 10 % del
  boletín diario y no filtraría nada.
- **Watchlist en base de datos.** Descartada: un fichero versionado se revisa en un diff, se
  audita en el repo y no necesita una pantalla de administración. Además `VERSION_WATCHLIST`
  encaja con el mecanismo que ya existía para el vocabulario.
- **PyYAML para leer la watchlist.** Descartada por la sección 3 ("sin dependencias nuevas para
  la watchlist"). El fichero se escribe en **JSON, que es un subconjunto válido de YAML**, y se
  lee con la biblioteca estándar. Escribir un parser propio de YAML habría sido peor que
  cualquiera de las dos opciones. **Punto abierto para el humano:** si prefiere YAML de verdad
  con comentarios, basta con autorizar la dependencia.

## Consecuencias

- **La cola del extractor cambia de definición** y era un fallo silencioso esperando a ocurrir:
  `services/extraccion.py` filtraba por `== RELEVANTE`, lo que habría dejado fuera todo lo
  marcado como sospecha sin que apareciera en ningún recuento. Ahora filtra por los dos estados
  y ordena `RELEVANTE` primero.
- **"Hay que reevaluar" deja de preguntarse por el estado.** Con `PENDIENTE` convertido en
  estado de espera, la condición vieja (`estado == PENDIENTE`) habría reevaluado esas normas en
  cada pasada. No habría reventado nada — habría roto la idempotencia del worker en silencio.
  Ahora se pregunta por `prefiltro_evaluado_en` y por las dos versiones.
- **Dos versiones independientes**: subir el vocabulario o subir la watchlist obliga a reevaluar,
  por separado. Compartir columna habría obligado a reevaluarlo todo por cualquier cambio.
- **`config/` se monta en los contenedores en solo lectura.** Vive a la altura del repo, no
  dentro de `backend/`, así que sin montaje el contenedor no la veía. Solo lectura porque un
  fichero de configuración que el proceso puede reescribir deja de ser configuración versionada.
- **La watchlist tiene 13 normas verificadas una a una contra el BOE**: 4 estatales y 9
  autonómicas de 7 comunidades. La primera versión tenía solo las 4 estatales porque se dio por
  hecho —mal— que las autonómicas usaban identificadores de su propio boletín.

  **Corrección, verificada el 2026-08-08: las leyes autonómicas se publican también en el BOE y
  reciben su propio identificador `BOE-A`.** No hace falta aprender el esquema de identificación
  de cada boletín autonómico para vigilar sus leyes. Eso desbloquea la parte más valiosa de la
  watchlist con el trabajo que ya estaba hecho.

  Dos trampas que aparecieron al verificar y que están anotadas en el fichero: hay **desfase de
  año** (la Ley 8/2017 de Andalucía es `BOE-A-2018-1549`, la 18/2018 de Aragón es
  `BOE-A-2019-2712`) y hay **números de ley repetidos entre comunidades** (Murcia y Baleares
  tienen las dos una "Ley 8/2016", aprobadas con tres días de diferencia). Cruzar por número de
  ley en vez de por identificador habría fallado en ambos casos.

- **Limitación del eje, y hay que tenerla presente porque es justo donde duele.** El eje lee el
  `<analisis>` del BOE, así que detecta una norma estatal que modifique cualquiera de estas, y
  una ley autonómica que modifique otra (porque se republica). **No detecta un decreto, orden o
  instrucción autonómica que modifique la ley de su comunidad**, porque eso no llega al BOE y su
  boletín todavía no se ingiere. Ese es exactamente el retroceso de rango bajo que define la
  sección 1: es el argumento más fuerte para priorizar la ingesta de boletines autonómicos, y
  por eso está escrito en el fichero de la watchlist y no solo en la hoja de ruta.
- **El recall de ninguno de los dos ejes está medido.** Sigue en pie el aviso de S1: no publicar
  cifras de recall hasta el gold set.

## Verificación

- 22 tests nuevos, incluido el caso que justifica el eje entero: una norma cuyo texto **no
  contiene ni un término del vocabulario** y que pasa por modificar la Ley 4/2023.
- El fichero real `config/watchlist.json` se carga y valida en un test, para que un error de
  sintaxis al añadir una norma no se descubra en la siguiente pasada del worker.
- Migración aplicada y comprobada con `psql`: 12 CHECK, `estadoprefiltro` con los cuatro
  valores y `origenclasificacion` (ADR 0004) intacta.
- **Verificado contra el caso real que motiva el proyecto entero:** la reforma madrileña de 2023
  (`BOE-A-2024-10767`, Ley 17/2023, que suprime los artículos 7, 24, 45 y 48 y los títulos X y
  XIV de la Ley 2/2016 de Madrid). Ejecutado contra la watchlist real:

  - solo con el título → `relevante`, eje léxico, términos `expresion de genero` y
    `no discriminacion`;
  - con el `<analisis>` → `relevante`, **los dos ejes**, cruzando `BOE-A-2016-6728`.

  Un detalle que salió al ejecutarlo y que ilustra por qué hacía falta el eje referencial:
  **`identidad de genero` NO cruza en ese título**, porque dice "Identidad **y Expresión** de
  Género" y la conjunción rompe la secuencia. El léxico se salvó por otro término; podría no
  haberse salvado.

  Está incorporado al gold set como caso (`casos/boe-a-2024-10767.json`), que además era un caso
  que CLAUDE.md 7.8 pedía expresamente y faltaba.

- **Sigue sin verificarse:** el eje no se ha ejecutado contra el `<analisis>` de un documento
  **descargado en vivo**, porque el worker aún no descarga texto íntegro (tarea 0.c). Las
  referencias del caso de Madrid se construyeron a mano a partir de lo que publica el BOE, que
  no es lo mismo que haberlas parseado del XML real.
