# ADR 0026 — El PDF como segunda vía del cuerpo archivado

- **Fecha**: 2026-08-22
- **Estado**: aceptado
- **Contexto de tarea**: recuperar las normas del DOGC que el pipeline no podía leer (ADR 0020).
- **Números libres**: el siguiente libre tras este es el **0027**.

## Contexto

El ADR 0020 creó el estado `ilegible` para decir en voz alta lo que antes se confundía con
«pendiente»: hay normas cuyo cuerpo está descargado, archivado y sellado, y que **el pipeline no
puede leer**. Al escribirlo eran 172 del DOGC, el 65 % de esa fuente. Al 2026-08-22, con la ingesta
al día, eran **235**.

La causa está medida: el DOGC publica muchas normas **solo en PDF**. Su endpoint `/dof/spa/xml`
devuelve para esas la página de error del portal, así que se archivaba un HTML de error con nombre
`.xml` y `xml_safe` lo rechazaba —correctamente— por declarar un DOCTYPE.

**Lo que faltaba no era OCR, y esto se comprobó antes de decidir nada.** Un PDF del DOGC trae 59
referencias de fuente, 18 bloques de texto y **cero imágenes**; su capa de texto da 8.295
caracteres limpios de un fichero de 795 KB, empezando por `DISPOSICIONES GENERALES / DEPARTAMENTO
DE LA PRESIDENCIA / ORDEN PRE/292/2023…`. El texto estaba ahí. Nadie había mirado.

## Decisión 1 — `security/pdf_safe.py` es la puerta única, como `xml_safe`

Ningún módulo importa `pypdf` directamente y hay un test que lo comprueba, igual que con
`defusedxml`. Un PDF de una fuente externa es entrada hostil (regla de oro 1) y el sitio para
decidir qué se le permite es uno solo.

**Extrae la capa de texto y nada más.** Un PDF no es un documento, es un programa con un formato de
archivo alrededor: puede llevar JavaScript, `/OpenAction`, formularios que envían datos y
referencias a ficheros remotos. Nada de eso se ejecuta ni se resuelve.

**Tres topes, porque son tres ataques distintos** y uno solo no cubre los otros dos:

| tope | ataque que para |
|---|---|
| `MAX_PDF_BYTES` (20 MB) | lo que no se lee no puede hacer daño |
| `MAX_PAGINAS` (400) | bomba de páginas: 300 KB que declaran cien mil páginas |
| `MAX_CARACTERES` (4 M) | bomba de expansión: pocas páginas, salida enorme |

Al pasarse cualquiera, **excepción y ni un carácter devuelto**. Medio documento archivado como si
fuera entero es peor que ninguno: el prefiltro lo evaluaría y diría «aquí no hay nada» sobre un
texto que nadie ha visto completo.

`RecursionError` se captura explícitamente: un PDF con referencias circulares en su árbol de
objetos la provoca, y sin capturarla se lleva por delante al worker entero.

## Decisión 2 — `SinCapaDeTexto` es un tipo propio, y es la cifra que decide si el OCR hará falta

`MalformedPdf` es «esto no se puede leer». `SinCapaDeTexto` es «esto se lee perfectamente y no
tiene letras», o sea un escaneo. Confundirlos haría **imposible saber si el OCR merece la pena**, y
esa es exactamente la decisión que la sección 8 quiere que se tome con datos.

El humano levantó la prohibición de OCR el 2026-08-22, y la regla quedó escrita así: sigue siendo
el último recurso y no el primero, y **antes de escribir una línea de OCR hay que demostrar con un
documento real que su PDF no tiene capa de texto**. `ResumenRecuperacion.sin_texto` es ese número,
y se publica en el log aunque valga cero. Al escribir este ADR vale **cero**.

## Decisión 3 — El formato se decide por el contenido, nunca por el nombre

`cuerpo.leer_cuerpo` mira los cinco primeros bytes (`%PDF-`) y enruta. **No mira la extensión ni la
fuente**: un PDF archivado con nombre `.xml` sigue siendo un PDF, y fiarse del nombre de un fichero
que viene de fuera es el mismo error que 6.3 prohíbe para las rutas.

Consecuencia que no es un descuido: un cuerpo en PDF **no aporta referencias del metadato**. No
trae el bloque `<analisis>` del BOE, así que el eje referencial solo puede alimentarse de las citas
del propio texto — que es justo lo que el ADR 0022 existía para cubrir en las fuentes sin
metadatos.

## Decisión 4 — Se archiva un documento nuevo; el anterior no se toca

La recuperación **no sustituye** el cuerpo archivado. Crea un `Documento` nuevo con su propia
huella, su propio sello y el sufijo `#pdf` en el identificador, y reapunta `documento_texto_id`.

El archivo es inmutable (6.5) y eso no admite excepciones por conveniencia. Además, lo que se
descargó aquel día —aunque fuera una página de error— **es un hecho sobre la fuente y merece
conservarse**: es la prueba de que el endpoint oficial devolvía eso.

Va en una **pasada aparte** (`worker.run --recuperar-pdf`) y no dentro de la descarga, por tres
motivos y el tercero decide: `texto_integro.descargar` no parsea, así que no puede saber que algo
es ilegible; hay 235 ya archivadas y un arreglo en la ingesta solo serviría para el futuro; y el
problema es sobre todo el pasado.

## Consecuencias

- Dependencia nueva: **`pypdf`**, elegida entre `pdfminer.six` y `PyMuPDF` porque es **Python puro**
  (no mete binarios del sistema en la imagen ni en la auditoría) y **MIT**, mientras PyMuPDF es
  AGPL y arrastraría una decisión de licencia que este proyecto no necesita tomar.
- `_url_pdf` solo conoce el patrón del DOGC y devuelve `None` para todo lo demás **a propósito**:
  construir URLs suponiendo es la forma de pedirle a una fuente rutas que no existen. Cada fuente
  nueva declara su patrón aquí a conciencia.
- La recuperación es idempotente sin banderas: al recuperar una norma deja de ser `ilegible`, así
  que la siguiente pasada no la ve. Lo que falla se queda como está y vuelve a salir.
- **Lo que esto no arregla**: las normas cuyo PDF sí sea un escaneo. Hoy son cero; si algún día no
  lo son, el número estará en el log y el OCR tendrá con qué justificarse.
