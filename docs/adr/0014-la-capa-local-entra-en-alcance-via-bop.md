# ADR 0014 — La capa local entra en alcance, y entra por el BOP

- **Fecha:** 2026-08-08
- **Estado:** aceptada
- **Decide:** el humano (petición explícita del 2026-08-08). Redacta: Claude Code.

## Contexto

El alcance original (CLAUDE.md sección 1) era **17 CCAA + BOE**. Al revisar el mapa, el humano
preguntó si en provincias y municipios no se publica nada que pueda ir contra los derechos del
colectivo. La respuesta que se le dio primero fue **errónea** y conviene dejarla escrita para
que no vuelva: se afirmó que «las provincias no tienen competencia normativa, así que un mapa
provincial sería resolución cartográfica sin nada detrás».

Eso confunde *legislar* con *normar*. Los municipios no aprueban leyes, pero sí tienen
**potestad reglamentaria** (art. 4 de la Ley 7/1985, reguladora de las Bases del Régimen
Local): ordenanzas, reglamentos, bandos, acuerdos de pleno, convenios y —lo más relevante
aquí— **bases y convocatorias de subvenciones**.

### Por qué esta capa es la que más encaja con la tesis del proyecto

La sección 1 define el objetivo como detectar «el retroceso silencioso: no la reforma que sale
en prensa, sino la instrucción de rango bajo publicada un martes de agosto que desmonta un
derecho sin titulares». Medido contra esa definición, la capa local no es un añadido: es el
caso extremo. Retirar la línea de subvención a una asociación LGTBI+, dejar de convocar un
servicio de atención, o modificar las bases de una subvención para añadir un requisito que
excluye, son actos que:

- se publican en un boletín que casi nadie lee,
- no generan titular ni siquiera local,
- y tienen efecto inmediato sobre personas concretas.

Una ley autonómica que recorta derechos sale en la prensa. Una convocatoria de subvenciones
modificada no sale en ninguna parte.

### El hallazgo que hace esto tratable

**Verificado el 2026-08-08 contra fuentes oficiales, no deducido:**

1. **Ley 5/2002, de 4 de abril, reguladora de los Boletines Oficiales de las Provincias**
   (`BOE-A-2002-6467`). Obliga a que el BOP publique «las disposiciones de carácter general y
   las ordenanzas, así como los actos, edictos, acuerdos, notificaciones, anuncios y demás
   resoluciones de las Administraciones públicas» cuando así lo exija una norma.
2. **Una ordenanza municipal no entra en vigor si no se publica íntegra en el BOP** de su
   provincia. Sin publicación no hay validez.
3. El directorio oficial del Punto de Acceso General
   (`administracion.gob.es/pag_Home/espanaAdmon/boletinesYLegislacion/BO_Diputaciones.html`)
   lista **43 boletines provinciales**, con la advertencia explícita de que «no existe boletín
   de provincias que pertenecen a comunidades autónomas uniprovinciales ni de las ciudades
   autónomas de Ceuta y Melilla».

El punto 2 es el que decide este ADR. **No hay que vigilar 8.131 municipios: hay que vigilar
43 boletines.** El municipio no es una fuente, es un *emisor* que publica en la fuente
provincial. Eso convierte un problema aparentemente inabordable en uno del mismo orden que el
que ya se resolvió con el BOE.

### La aritmética, que cuadra y por eso se puede afirmar

50 provincias − 43 con BOP = **7 sin BOP**, y son exactamente las 7 CCAA uniprovinciales:
Asturias, Cantabria, Illes Balears, Madrid, Murcia, Navarra y La Rioja. En ellas el boletín
autonómico hace el papel del provincial, así que **no hay hueco de cobertura**: quedan
cubiertas por la capa autonómica que ya estaba en alcance. Ceuta y Melilla publican en sus
propios boletines de ciudad.

## Decisión

1. **La capa local entra en alcance, y se vigila a través del BOP**, no municipio a municipio.
2. El modelo de dominio gana una **dimensión territorial explícita** en `fuente`
   (`ambito_territorial`: `estatal` | `autonomico` | `provincial` | `local`) más `provincia`.
   No se reutiliza `tipo` para esto: `tipo` describe *qué clase de fuente* es y el ámbito
   describe *a qué nivel de administración alcanza*; son ejes independientes y mezclarlos
   obligaría a enumerar el producto cartesiano.
3. Las 43 fuentes provinciales se registran **con su URL verificada y `activa=false`**. Existe
   una diferencia que el sistema tiene que poder expresar y hoy no puede: *no sabemos que haya
   nada* no es lo mismo que *no estamos mirando*. Una fuente conocida y no vigilada es un hueco
   de cobertura declarado; una fuente ausente de la tabla es un hueco invisible.
4. **La interfaz agrupa por CCAA, no obliga a ampliar el mapa.** Al seleccionar una comunidad
   se muestra el desglose por nivel (autonómico / provincial / local). Fue la propuesta del
   humano y es mejor que la alternativa: un mapa provincial obligaría a hacer zoom para
   descubrir dónde ha pasado algo, que es justo lo contrario de lo que necesita quien vigila.
5. **Esto NO entra entero en V1.** Ver consecuencias.

## Alternativas consideradas

- **Vigilar los ayuntamientos directamente (sedes electrónicas, portales de transparencia).**
  Descartada. Son miles de sitios sin formato común, muchos sin publicación estructurada, y
  además **no es donde la norma adquiere validez**: sería vigilar el borrador en vez del
  boletín. El BOP es el punto de paso obligado, y vigilar un punto de paso obligado es
  siempre preferible a vigilar a todos los que pasan por él.
- **Mapa provincial con geometría nueva.** Descartada para V1 (ver decisión 4). Además exige
  geometría de fuente oficial que no está en el repo, y el zoom que ya existe cubre la
  necesidad de detalle sin prometer un dato que no tendríamos por provincia.
- **Dejarlo fuera de alcance por la sección 8 («nada de scope creep»).** Descartada por el
  humano, y con razón: la sección 8 protege contra features que no sirven a la tesis
  (monitorización de prensa, redes). Esta capa **es** la tesis. Lo que sí se conserva de la
  sección 8 es su guardarraíl real: el límite de fuentes por iteración.
- **Un único ingestor genérico para los 43 BOP.** Descartada por ahora, por no verificada:
  se ha comprobado que algunos exponen XML/datos abiertos (Barcelona, Huesca, Cáceres) y otros
  solo HTML o PDF, pero **no se ha auditado uno por uno**. Afirmar que existe un formato común
  sería exactamente la invención que prohíbe la regla de oro 8.

## Consecuencias

- **El alcance nominal pasa de 18 fuentes a 61** (BOE + 17 autonómicas + 43 provinciales), más
  BOCCE y BOME si el humano decide incluir las ciudades autónomas (decisión aún abierta).
- **El guardarraíl de la sección 8 sigue vigente y ahora importa más**: máximo 5 fuentes
  integradas en la primera iteración. 61 fuentes registradas no son 61 fuentes ingeridas, y
  confundir ambas cosas es la forma más rápida de no terminar ninguna.
- **V1 no cambia de fecha.** Lo que entra en V1 es la *estructura* (dimensión territorial,
  las 43 fuentes registradas e inactivas, el desglose por CCAA en la interfaz) y **un BOP
  integrado de punta a punta como prueba**, elegido entre los que exponen formato
  estructurado. Los 42 restantes son hoja de ruta declarada, igual que las 17 autonómicas.
- **El OCR sigue fuera de alcance** (sección 8). Es previsible que varios BOP publiquen PDF
  escaneado; esos se documentan como hoja de ruta y no se integran. Hay que resistir la
  tentación de hacer una excepción «solo para este», porque son 43 y la excepción se repite.
- **La EIPD no cambia**: se sigue tratando texto público de boletines oficiales, sin datos
  personales de suscriptores. El canal pull (6.4) sigue siendo la vía por defecto.
- **Riesgo nuevo de volumen, y hay que medirlo antes de prometer nada.** El ADR 0011 midió el
  BOE: 4,3 MB y ~10 s de red al día, y 133,9 s por extracción del LLM. Con 43 BOP más, la
  descarga sigue siendo barata pero **la cola del LLM no**. Es el mismo cuello de botella que
  ya obligó a que el prefiltro pasara de puerta de la red a puerta del modelo (7.1), solo que
  multiplicado. **Antes de activar el segundo BOP hay que repetir la medición del ADR 0011
  sobre el primero**, con el script `scripts/medir_fase2.py`, que ya existe justo para esto.
- El eje referencial del prefiltro (7.3) gana valor aquí: una ordenanza que recorta un derecho
  rara vez lo nombra, pero sí cita la norma que modifica.

## Verificación

- Directorio oficial de BOP consultado el 2026-08-08 (Punto de Acceso General). Los 43
  nombres y URL están volcados en `docs/fuentes.md`, no en este ADR, para que la auditoría
  viva en un solo sitio.
- Ley 5/2002 consultada en el BOE consolidado (`BOE-A-2002-6467`).
- **Lo que NO se ha verificado y por tanto no se afirma:** el formato, la licencia de
  reutilización y la necesidad de OCR de cada BOP concreto. Todo eso queda `TODO(verificar)`
  en `docs/fuentes.md`, con el mismo criterio que las 17 autonómicas.
