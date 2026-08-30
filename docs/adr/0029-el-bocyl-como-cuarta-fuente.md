# ADR 0029 — El BOCYL como cuarta fuente, y dónde se traza la raya del raspado

- **Fecha:** 2026-08-29
- **Estado:** aceptado
- **Continúa a:** ADR 0019 (DOGC) y ADR 0028 (BOA).

## Contexto

Tras el ADR 0028 el mapa pintaba 3 de 19 territorios y quedaban **dos huecos** dentro del límite
de cinco fuentes de la sección 8. El humano pidió seguir rellenando el mapa.

El sondeo del ADR 0028 dejó una lista de candidatas con su estado. Se volvió a sondear, otra vez
descargando y no leyendo documentación, y apareció algo que en aquella tanda se había marcado mal:
**el BOCYL se había descartado porque su RSS por fecha devolvía 500**. Eso era cierto y era
irrelevante: el RSS no es su interfaz de datos.

## Cómo se eligió

| Fuente | Qué se pudo obtener | Veredicto |
|---|---|---|
| **BOCYL** (Castilla y León) | Sumario HTML por fecha exacta + **XML por disposición, direccionable por identificador** | **Integrable ya** |
| BOPV (Euskadi) | Sumario HTML direccionado por **número de boletín**; verificado que el 7/2024 es el 10 de enero, pero no se localizó el índice fecha → número. Cuerpo en HTML | Pendiente |
| BOIB (Illes Balears) | Front XHTML; el único acceso al texto localizado es PDF | Pendiente |
| BOC (Canarias), DOE (Extremadura), BON (Navarra) | Índices HTML, sin interfaz de datos localizada | Pendiente |
| BOCM (Madrid) | Las rutas probadas dan 404; sigue el diagnóstico del ADR 0019 | Integrable con esfuerzo |
| DOG (Galicia), BOPA (Asturias) | 404 en las rutas probadas | Pendiente |
| **BORM (Murcia)** | **Captcha de Radware ante la petición del texto** | **Descartada, y no por formato** |

**El BORM merece su propia línea porque su motivo no es técnico.** Su portal responde a la
petición del texto con una página de captcha. Sortearla sería eludir una detección de bots
deliberada del titular de la fuente; no se hace, y no se intenta. Queda documentado como lo que
es —una fuente que no quiere ser leída por programa— y no como un formato difícil.

### Por qué el BOCYL gana

Su XML por disposición es **el más estructurado de las cuatro fuentes integradas**:
`seccion`, `subseccion`, `apartado`, `organismo`, `rango`, `numeroOficial`, `fechaDisposicion`
y `fechaPublicacion`, con el articulado en `contenido > texto`. Y sobre todo:

> **El cuerpo se direcciona por su identificador**
> (`boletines/2024/01/10/xml/BOCYL-D-10012024-1.xml`), no por su posición dentro del día.

Eso elimina de raíz la fragilidad que gobierna el módulo del BOA (ADR 0028), donde hay que pedir
«el registro número n del día d» y verificar el `<docn>` porque la fuente podría reordenar el día.
Aquí la URL nombra el documento.

## Decisión

**Se integra el Boletín Oficial de Castilla y León como cuarta fuente y tercera autonómica.**

### 1. Se raspa el sumario, y la raya se traza aquí

Es la **primera fuente cuyo sumario hay que leer de HTML**. No hay sumario XML: probado
`BOCYL-S-ddmmaaaa.xml` (500) y el RSS por fecha (que **ignora el parámetro** y devuelve siempre el
último boletín — comprobado pidiendo el 10/01/2024 y recibiendo el 28/08/2026).

La regla que hace esto aceptable, y que no se negocia:

> **El HTML aporta identificadores y metadatos. El texto que una alerta llegue a citar sale
> siempre del XML.** La cadena de evidencia (6.5, 7.5) no pasa por el raspado en ningún punto.

En concreto: del HTML salen el identificador, el título, la sección y el organismo. **De ahí no
sale ni un carácter de articulado.** El cuerpo que archiva la fase 2, el que ancla los offsets del
ADR 0013 y el que leen las reglas del ADR 0016 es siempre el XML de la disposición.

Se hace con expresiones regulares acotadas y sin dependencias nuevas (sección 3). Es más frágil
que parsear XML y hay que decirlo: si el BOCYL cambia su plantilla, esta fuente deja de ingerir.
Lo que **no** puede hacer es ingerir mal en silencio, y de eso se ocupan las dos comprobaciones
siguientes.

### 2. Los identificadores se filtran por la fecha pedida

**Todas las páginas del BOCYL llevan un enlace fijo a una disposición de noviembre de 2022**,
incluidas las de días sin boletín. Sin filtrar por la fecha que va dentro del identificador, cada
día del archivo ingeriría esa norma **bajo la fecha equivocada**, y no fallaría nada visiblemente:
el archivo afirmaría que se publicó un día en el que no se publicó. Tiene su test.

### 3. El título se consume; la sección y el organismo se arrastran

No es una asimetría descuidada. `<h3>` (sección) y `<h5>` (organismo) son **cabeceras de grupo** y
valen para todas las disposiciones que vienen debajo; `<p>` (título) es de una sola.

**Esto lo encontró su test, no el diseño.** La primera versión llevaba el título como estado
corrido igual que los otros dos, así que una disposición sin `<p>` propio **heredaba el título de
la anterior** y se habría archivado con el título de otra norma. Es peor que descartarla, porque
no rompe nada visible. Ahora el título se vacía al consumirse y una disposición sin título propio
se descarta con aviso.

### 4. Aunque la URL nombre el documento, se comprueba la fecha del cuerpo

El BOCYL no puede devolver la disposición de al lado. Lo que sí puede devolver bajo la misma URL
es **otra cosa**: una página de error, o un documento resellado con otra fecha. El archivo afirma
«el día X esto decía exactamente esto», así que se contrasta la `<fechaPublicacion>` del XML con
la fecha que va dentro del identificador. No cuesta ni una petición.

Por eso el BOCYL entra en el registro de validadores de `services/texto_integro.py`, pero **por un
motivo distinto al del BOA**, y el comentario de ese registro lo distingue: el BOA porque no se
puede direccionar por identificador; el BOCYL porque su cuerpo declara una fecha que se puede
contrastar. El BOE y el DOGC no necesitan validador: su URL nombra la disposición y su cuerpo no
declara una fecha con la que contrastarla.

### 5. Un día sin boletín no da 404 — otra vez, y de otra forma

El BOE contesta 404, el DOGC una lista vacía, el BOA su portada, y el BOCYL **una página corta que
tras el filtro por fecha deja cero disposiciones**. Cuatro fuentes, cuatro maneras, ninguna
documentada.

**Es la pregunta que hay que hacerle explícitamente a toda fuente nueva**, porque equivocarse
cuesta caro: en el BOA costó que cada fin de semana abortara un bloque entero de backfill (ADR
0028 y el `fix` del 2026-08-29).

### 6. Las dos codificaciones no coinciden

El **sumario es UTF-8** (lo declara su `Content-Type`, comprobado) y el **cuerpo es ISO-8859-15**
(lo declara su prólogo XML). Cruzarlas no falla: llena el texto de basura, que es peor. El XML lo
resuelve `xml_safe` solo; el HTML se decodifica explícitamente como UTF-8 con `errors="replace"`,
porque un byte suelto mal codificado no debe costar el día entero y lo que sale de ahí son
metadatos, no evidencia citable.

### 7. La licencia queda en `TODO(verificar)`

A diferencia del DOGC y del BOA, cuyos catálogos de datos abiertos declaran CC BY 4.0, **no se
localizó una declaración de reutilización del BOCYL**. Se anota como pendiente y no se deduce
(regla de oro 8). Inventarla sería peor que no tenerla.

## Alternativas consideradas

- **Enumerar `BOCYL-D-ddmmaaaa-N.xml` desde 1 hasta el primer 404**, evitando el HTML por
  completo. Descartada: los identificadores del día verificado son contiguos (1..27), pero **nada
  garantiza que lo sean siempre**, y parar en el primer hueco dejaría un agujero de cobertura
  invisible — el fallo exacto que este proyecto existe para no cometer.
- **Tomar el título del XML en la fase 2** en vez de raspar el HTML. Habría evitado el raspado del
  título, pero `norma.titulo` se escribe al crear la fila en la fase 1 y una norma sin título
  hasta la fase 2 no se puede ni priorizar ni enseñar. El coste no compensaba.
- **Euskadi (BOPV) primero**, por tamaño y por tener boletín propio consolidado. Aplazada: su
  sumario se direcciona por número de boletín y falta resolver el índice fecha → número; su cuerpo
  es HTML, así que habría que raspar **también la evidencia**, y ahí sí se cruzaría la raya de la
  decisión 1.

## Consecuencias

- **El mapa pinta 4 de 19 territorios.** Con Castilla y León, además, el que más superficie ocupa.
- **Cuatro fuentes integradas: queda una** dentro del límite de la sección 8.
- **El proyecto raspa HTML por primera vez, con una regla escrita de hasta dónde.** Cualquier
  fuente futura que exija raspar el **texto** —no los metadatos— choca con la decisión 1 y necesita
  su propio ADR para justificarlo.
- **`texto_plano` gana una tercera rama** (`disposicion > contenido > texto`). Apunta a `<texto>` y
  no a `<contenido>` porque `<titulo>` es su hermano y se colaría en el articulado, produciendo el
  mismo falso positivo del prefiltro léxico que el `<analisis>` del BOE en el caso de respaldo.
  **`VERSION_TEXTO_PLANO` no sube**, por lo mismo que en el ADR 0028: gobierna las colas de
  reproceso y esta rama no toca la derivación de nada ya archivado.
- **El eje referencial sigue dependiendo de las citas del texto** (ADR 0022). Tres de las cuatro
  fuentes no publican a quién afecta una norma. **La estructura de referencias del BOE no es un
  estándar**, y a estas alturas es más exacto decir que es la excepción.
