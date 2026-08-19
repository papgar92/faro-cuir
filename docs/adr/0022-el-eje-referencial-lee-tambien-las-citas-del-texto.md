# ADR 0022 — El eje referencial lee también las citas del texto

- **Fecha**: 2026-08-19
- **Estado**: aceptado
- **Contexto de tarea**: hallazgo de la primera tanda del gold set del DOGC (ADR 0021 y la entrada
  de ESTADO del 2026-08-19).
- **Números libres**: el siguiente libre tras este es el **0023**.

## Contexto

El eje 2 del prefiltro (7.3) es el que cubre el agujero estructural del diccionario: una
instrucción que elimina un derecho no dice «identidad de género», dice «se modifica el epígrafe
4.3 del anexo II». Se construyó leyendo el bloque `<analisis>` del BOE, que publica la norma
afectada y el verbo (`MODIFICA`, `DEROGA`) ya estructurados.

Con una sola fuente eso bastaba. **Con la segunda, el eje sencillamente no existe**:

| | BOE | DOGC |
|---|---|---|
| cuerpos legibles | 2.968 | 92 |
| con referencias que el eje puede leer | **211 (7,1 %)** | **0** |

El DOGC sí trae un bloque `<references>` en su Akoma Ntoso, pero **no dice a quién afecta la
norma**: sus `activeRef` apuntan al *propio documento* con `showAs="Modificado"`/`"Derogado"`
—son anotaciones de ciclo de vida— y los `passiveRef` son normas *posteriores*, que el día de la
publicación no existen. Comprobado el 2026-08-19 en cuatro documentos distintos, uno de ellos
titulado literalmente «de modificación del Decreto 358/2004»: **la norma afectada no aparece en
ningún metadato, solo en el texto.**

El caso que lo puso delante está en el gold set (`dogc-24261095`): un decreto que deroga
artículos del Decreto 134/2022, el de estructura del Departamento de Igualdad y Feminismos —donde
viven las competencias LGTBI en Catalunya—, invisible para el eje que existe para verlo.

## Decisión

**Las citas dentro del texto son una segunda fuente de evidencia para el mismo eje.**
`pipeline/citas.py` produce `ReferenciaAnterior`, exactamente el mismo tipo que el
`<analisis>`, y `services/cuerpo.leer_cuerpo` concatena las dos listas. Ni el prefiltro ni el
versionado ni el catálogo de reglas se enteran: siguen preguntando lo mismo a la misma
estructura, que es lo que permite que este cambio no toque la decisión de ninguna etapa.

Cuatro reglas, y las cuatro salen de una medición, no de una intuición:

1. **Solo la forma larga: número *y* fecha.** «Ley 11/2014, de 10 de octubre», nunca «Ley
   11/2014».
2. **El verbo se busca hacia atrás**, en una ventana de 200 caracteres. El texto dispositivo pone
   el verbo antes: «Se suprime el apartado 2 del artículo 8 de la Ley 2/2016, de 29 de marzo».
   Mirar en las dos direcciones se comería el verbo de la frase siguiente, que habla de otra
   norma.
3. **Sin verbo, `CITA`.** Que no está en `VERBOS_MODIFICATIVOS` y por tanto **no dispara el
   eje**. Mencionar una ley en el preámbulo no es tocarla: es el mismo criterio con el que el BOE
   distingue `MODIFICA` de una cita cualquiera, y el falso positivo que el eje léxico produce a
   destajo.
4. **La watchlist se pasa como parámetro, no se carga dentro.** Cargarla en `leer_cuerpo` metería
   estado global en una función de lectura y —así se descubrió— dejaría fuera de juego a los
   tests que la sustituyen. El extractor, que no usa referencias, no la pasa.

### La trampa medida, que es lo que decide el diseño

Buscar la forma corta **no vale**, y no es una precaución teórica. Sobre los 264 cuerpos del DOGC
produjo 4 coincidencias con verbo modificativo al lado y **las 4 eran falsas**:

- «Ley 2/2021» cazó la *Ley 2/2021 de medidas fiscales de Catalunya*; la vigilada es la Ley 2/2021
  **de Canarias**. La numeración se repite en cada comunidad y en el Estado.
- «Ley 4/2023» cazó «**Decreto ley** 4/2023, de 19 de diciembre»: la forma corta es subcadena de
  la larga de otra norma. De ahí el `(?<!decreto )` del patrón, que sin la medición nadie habría
  escrito.
- «Ley 2/2014» cazó la *Ley 2/2014 de medidas fiscales de Catalunya*; la vigilada es la de
  **Galicia**.

Con la forma larga las cuatro desaparecen, que es la respuesta correcta: ninguna toca nada de la
watchlist. Cada una tiene su test en `tests/test_citas.py`.

## Qué no hace, y qué riesgo queda

- **No construye ninguna URL con lo que encuentra** (6.10). Lo que devuelve es el identificador
  **de la watchlist**, que es un fichero versionado del repositorio; la cadena que aparecía en el
  documento sirve para localizar y se tira. La URL del consolidado la sigue componiendo
  `versionado` a partir del identificador nuestro, validado.
- **No decide nada.** Devuelve indicios; quien decide sigue siendo `prefiltro.evaluar`.
- **No arregla las 172 normas ilegibles del DOGC** (ADR 0020): sin texto no hay citas.
- **Una entrada de la watchlist cuyo título no empiece por su forma de cita queda fuera del eje
  en silencio.** Hoy las 21 la tienen; hay un test contra la watchlist real que se pone rojo si
  alguien añade una que no. Es la parte de este diseño que más fácil se rompe sin darse cuenta.
- **Riesgo residual, dicho claro**: una norma que modifique otra sin citarla en forma larga —«se
  modifica la ley catalana de igualdad»— sigue siendo invisible para este eje. El léxico la
  cubriría solo si nombra al colectivo.

## Consecuencias

- **Valida sobre el caso más importante del corpus.** Lo enseñó un test que se puso rojo al
  conectarlo: en `BOE-A-2024-10767` (la reforma madrileña de 2023), el eje encuentra
  `BOE-A-2016-6728` con verbo `SUPRIME` **leyendo el texto**, sin tocar el `<analisis>`. Es
  decir, sobre el caso que el proyecto usa para explicarse, las dos fuentes de evidencia
  coinciden por separado.
- `VERSION_WATCHLIST` sube a `2026.08.19` aunque la lista de normas no cambie: lo que ha cambiado
  es de dónde saca su evidencia el eje, y sin subirla lo ya evaluado no se reevaluaría.
- El test `test_una_norma_que_solo_cita_la_watchlist_no_sale_a_la_red` (versionado) sigue verde
  con la watchlist de prueba, cuyo título no lleva fecha. Conviene saber por qué: **neutralizar
  el `<analisis>` ya no basta para neutralizar una referencia**, porque hay dos fuentes.
- Queda una asimetría que no se resuelve aquí: `versionado` descarga el **consolidado del BOE**
  para construir el diff. Con una referencia sacada del texto de un boletín autonómico eso sigue
  funcionando —la ley autonómica vigilada tiene identificador del BOE, que es como está en la
  watchlist— pero el consolidado del BOE puede tardar más en recoger una modificación autonómica.
  `sin_consolidar` ya cubre ese caso y lo dice en el log.
