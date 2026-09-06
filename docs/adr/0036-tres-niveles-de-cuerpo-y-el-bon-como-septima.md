# ADR 0036 — Tres niveles de cuerpo, y el BON como séptima fuente

- **Fecha:** 2026-09-06
- **Estado:** aceptado
- **Relacionado con:** ADR 0020 (el estado `ilegible`), 0026 (el PDF como cuerpo), 0029 (la raya
  del raspado del BOCYL), 0015 (cada cuerpo es una fila de `documento`), 0035 (las dos ediciones
  de un día).

## Contexto

El humano lo pidió así el 2026-09-06:

> «Necesitamos a Navarra sí o sí, podemos hacer una regla aparte para estas CCAA que no tienen en
> XML, tenemos que adaptar las normas por comunidad, o englobar comunidades por el tipo de cuerpo
> (HTML, XML, etc) y tener normas según esto.»

El ADR 0035 había dejado a Navarra fuera con este motivo: sus cuerpos son **HTML y nada más**, y
el ADR 0029 tenía escrita esta raya:

> El HTML aporta identificadores y metadatos. El texto que una alerta llegue a citar sale
> siempre del XML.

## Decisión

**Se adopta la segunda opción del humano —agrupar por tipo de cuerpo— con una corrección: el
nivel es del DOCUMENTO, no de la comunidad.**

Agrupar por CCAA se rompe con la fuente que llevamos más tiempo ingiriendo: **el DOGC publica
unas normas en XML y otras solo en PDF** (ADR 0026), así que Cataluña estaría en dos grupos a la
vez. Y se rompería otra vez el día que cualquier otra fuente cambie de formato para un tipo de
disposición, que es una cosa que las fuentes hacen sin avisar.

Por eso el nivel lo decide `services/cuerpo.py` **mirando los bytes archivados**, que es lo que
ya hacía para el PDF: «el formato se decide por el contenido, no por la extensión ni por la
fuente». Esto no es una arquitectura nueva; es hacer explícito y completo lo que ya existía.

### Los tres niveles

| Nivel | Formato | Derivación | Fuentes hoy |
|---|---|---|---|
| **A** | XML estructurado | `pipeline/texto.texto_plano` | BOE, DOGC, BOA, BOCYL, BOCM, BOPV |
| **B** | PDF | capa de texto (`security/pdf_safe`, ADR 0026) | DOGC (las que solo salen en PDF) |
| **C** | **HTML de portal** | `pipeline/texto_html` | **BON** |

### La raya del ADR 0029 no se rompe: se dice mejor

Lo que aquella frase protegía **nunca fue el XML**. El proyecto ya admitía PDF desde el ADR 0026,
así que la regla real siempre fue: *la evidencia sale de un recorte declarado y reproducible, no
de raspar lo que haya en una página*. Aquí se hace explícita y se le añade el tercer nivel.

Lo que sí cambia es la carga de la prueba, y por eso el nivel C **tiene tres obligaciones que los
otros dos no necesitan**:

1. **Contenedor declarado y lista cerrada.** `pipeline/texto_html.CONTENEDORES` enumera dónde
   vive el articulado en cada fuente de este nivel. De un HTML que no traiga uno de esos
   contenedores **no se extrae nada**: no hay recorte genérico, no hay «coge el div más grande».
   Añadir una fuente de nivel C es añadir una entrada ahí, verificada contra un documento real, y
   decirlo en su ADR.
2. **Canario de tamaño.** Un contenedor que casa pero devuelve menos de `MINIMO_CARACTERES` se
   trata como fallo. Una plantilla vacía o una página de mantenimiento darían un texto corto que
   el prefiltro leería como «aquí no hay nada relevante»: el falso negativo invisible de 7.1.
3. **Degradación ruidosa** (6.9.6). Los dos fallos anteriores acaban en `CuerpoIlegible`, o sea
   en el estado `ilegible` de 7.2: fuera de las colas automáticas, **reintentado en cada pasada**
   y **contado aparte en el embudo**. Un rediseño del portal se convierte en un montón visible de
   `ilegible`, no en vigilancia que dejó de funcionar sin que nadie se entere.

### Lo que NO se relaja, y es lo que había que proteger

**`xml_safe` sigue rechazando el HTML** (6.1). En el caso que motivó el estado `ilegible` (ADR
0020), ese control es lo único que impidió que **172 páginas de error del DOGC** entraran como si
fueran normas. Ahora existe una rama que sabe leer HTML, así que esa protección tiene que venir
de otro sitio, y viene de la obligación 1: **una página de error no trae ninguno de los
contenedores declarados**, así que sigue dando vacío y sigue siendo `ilegible`.

Hay un test que lo fija **con la página de error real** (`test_texto_html.py::
test_una_pagina_de_error_sigue_siendo_ilegible`), y es el que hay que mirar antes de tocar nada
de este nivel.

### El nivel viaja en la evidencia

`Cuerpo` gana un campo `derivacion` (`xml` | `pdf` | `html`) que se registra en
`evidencia_json` junto a `version_texto_plano`. Con tres niveles, la versión sola ya no termina
la frase: decía «sobre qué derivación se midieron los offsets» cuando solo había una.

**Lo que NO cambia son las columnas de reprocesado.** `prefiltro_version_texto` y
`reglas_version_texto` siguen llevando `VERSION_TEXTO_PLANO`, una sola para toda la capa. Una
versión por documento haría que las normas de los niveles B y C parecieran caducadas en **cada
pasada** —`!= VERSION_TEXTO_PLANO` sería siempre cierto— y se reprocesarían para siempre: el
bucle infinito contra el que ya avisa `services/prefiltro.py`. Es el error fácil de este cambio.

## El BON como séptima fuente

Con el nivel C definido, Navarra entra. Lo verificado el 2026-09-06:

- **Sumario:** `/es/boletin/-/sumario/{aaaa}/{numero}`, y **declara su propia cabecera**:
  `BOLETÍN Nº 6 - 9 de enero de 2024`. Eso es lo que la hace archivable: sin poder comprobar que
  el boletín que llegó es el del día pedido, la 6.5 no puede afirmar lo que afirma.
- **Cuerpo:** `/es/anuncio/-/texto/{aaaa}/{numero}/{orden}`, HTML. **El orden empieza en 0.**
- **Su búsqueda por fecha miente.** `?anio=&mes=&dia=` existe y **ignora la fecha**: pedirle el
  10 de enero de 2024 devuelve el último boletín publicado, byte por byte igual que cualquier
  otro día. Es la trampa del RSS del BOCYL otra vez, y se descubre igual: pidiendo dos días
  distintos y comparando.
- **Fecha → número por bisección**, leyendo la cabecera que declara cada candidato. El número es
  monótono en la fecha dentro del año (comprobado: 1 → 2 ene, 6 → 9 ene, 120 → 11 jun, 253 → 16
  dic de 2024). **La fecha nunca se supone: la declara el documento.**
- **Un número que no existe responde 200 con página vacía**, no 404. Séptima forma distinta de
  decir «aquí no hay boletín» que se encuentra este proyecto, y ninguna fuente la documenta.
- **Un día puede traer dos boletines**, como el BOPV: el **253 y el 254 son los dos del 16 de
  diciembre de 2024**, y el 254 trae una sola disposición. La diferencia a favor del BON es que
  lo dice: su cabecera añade ` - EXTRAORDINARIO`. La interfaz de tupla del ADR 0035 lo cubre sin
  tocar nada, que es exactamente para lo que se hizo uniforme.
- **El atributo `title` del enlace lleva comillas sin escapar**, así que el título se lee del
  **texto del enlace**. Leerlo del atributo lo truncaría en la primera comilla interior.

### Su coste, dicho antes de lanzarlo

Resolver una fecha cuesta **hasta `MAX_SONDEOS` (16) peticiones** de ~100 KB cada una. Para la
pasada diaria casi siempre es una —el índice `/es/boletines` lista los cuatro últimos con su
fecha—, pero **un backfill del BON es caro**, y conviene saberlo antes de lanzarlo en vez de
descubrirlo a mitad.

Agotar el tope es un **error**, no un final silencioso. La primera versión de este código paraba
el barrido de vecinos al llegar al tope y seguía: eso truncaba la lista de ediciones sin decir
nada, o sea perdía un extraordinario por el mismo sitio por el que este ADR entra. Lo cazó su
propio test.

## Alternativas consideradas

- **Reglas por comunidad**, la primera opción del humano. Descartada por lo dicho: el DOGC ya es
  dos comunidades a efectos de formato. Y además haría que añadir una fuente obligara a tocar el
  pipeline, en vez de solo declarar dónde está su articulado.
- **Dejar a Navarra fuera**, que es lo que decía el ADR 0035. El humano lo revocó explícitamente
  («sí o sí»), y con las tres obligaciones del nivel C la objeción original —que la evidencia
  saliera de raspar— deja de aplicar.
- **Un parser HTML de verdad** (`beautifulsoup4`, `lxml.html`). Descartada por la sección 3: sin
  dependencias nuevas. `html.parser` de la biblioteca estándar basta para recortar un subárbol, y
  una dependencia menos es una superficie menos que auditar (ADR 0008).

## Consecuencias

- Nuevo módulo `pipeline/texto_html.py` y nueva rama en `services/cuerpo.py`.
- `Cuerpo.derivacion` viaja a `evidencia_json` desde `clasificacion` y `extraccion`.
- `fuente` gana una fila (`c9e2a71f5b04`) con **`formato='html'`**, que por primera vez dice
  literalmente de dónde sale el texto analizado. La página de cobertura publica esa columna, así
  que quien mire la web puede saber que la evidencia de Navarra se recorta de una página y no de
  un documento estructurado. Esconderlo tras un `api` cómodo sería lo contrario de la 6.9.6.
- **El recuento de CHECK no cambia** (hoy 15): la migración es un INSERT.
- **El guardarraíl de la sección 8 sube de 6 a 7**, por decisión del humano, y con el criterio
  que ya ganó en el ADR 0034 más uno nuevo: **una fuente de nivel C entra solo si su articulado
  no existe en ningún formato documental**. Si hay XML o PDF, se usa ese.
- La ingesta diaria de GitHub Actions pasa a siete fuentes.
