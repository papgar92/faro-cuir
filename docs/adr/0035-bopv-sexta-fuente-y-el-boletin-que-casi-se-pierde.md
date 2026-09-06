# ADR 0035 — El BOPV como sexta fuente, y el boletín extraordinario que casi se pierde

- **Fecha:** 2026-09-06
- **Estado:** aceptado
- **Relacionado con:** ADR 0034 (BOCM, y el sondeo que descartó esta fuente hace unas horas),
  0029 (BOCYL: la raya del raspado y las cabeceras de grupo), 0028, 0019, 0011.

## Contexto

En el ADR 0034, escrito esta misma mañana, el BOPV quedó **descartado** con este motivo:

> El BOPV es el que mejor XML tiene, mejor incluso que el BOCM, pero su sumario **no declara su
> propia fecha**: solo se puede pedir por número de edición y no hay forma de comprobar que el
> que llegó es el del día que se quería. Para el archivo de la 6.5 eso no es un inconveniente,
> es un descarte.

**Ese descarte estaba mal, y el motivo por el que estaba mal merece quedar escrito**: no se había
buscado lo suficiente. El índice fecha → edición existe, y estaba dentro de un `<iframe>` que
carga el calendario de la propia web del BOPV. Se encontró leyendo el HTML de una disposición
buscando otra cosa.

## Decisión

**El BOPV (Boletín Oficial del País Vasco) es la sexta fuente integrada**, y con ella se agota
el guardarraíl ampliado de la sección 8.

### Las tres URLs, verificadas descargando (2026-09-06)

1. **Calendario del mes:** `/bopv2/datos/{mm}{aaaa}.shtml`. **1,5 KB**, y trae dos arrays de
   JavaScript emparejados por posición:

   ```js
   var diasHabilitados = ['20260901','20260902','20260903','20260904'];
   var enlaces = [['s26_0166.shtml'],['s26_0167.shtml'],['s26_0168.shtml'],['s26_0169.shtml']];
   ```

   Comprobado hacia atrás hasta enero de 2024, así que **el backfill funciona**, que era la otra
   duda. Se lee con expresión regular y **no ejecutando el JavaScript**: ejecutar código de una
   fuente externa sería exactamente lo contrario de la regla de oro 1.

2. **Sumario:** `/bopv2/datos/{aaaa}/{mm}/s{aa}_{nnnn}.xml`, XML en UTF-8. La carpeta del mes es
   estricta: `s26_0169.xml` existe bajo `/2026/09/` y da 404 bajo `/2026/08/`.

3. **Cuerpo:** `/bopv2/datos/{aaaa}/{mm}/{aa}{orden:05d}a.xml`, XML en UTF-8. El sumario **no
   publica ni la URL ni el identificador de cada disposición**, solo su `BOPVSumarioOrden`; el
   nombre del fichero se deriva de ahí. Verificado con órdenes altos y bajos (1 → `2400001a`,
   18 → `2400018a`, 3788 → `2603788a`).

Esto convierte al BOPV en **la fuente con el mejor XML de las seis**: es la única, junto con el
BOCM, que sirve XML en las dos fases, y su cuerpo está más limpio que el de nadie.

### El coste: una petición más

Ingerir un día del BOPV son **dos peticiones antes del sumario** (calendario + sumario) en vez de
una. Es lo que hace archivable esta fuente: el calendario es quien empareja fecha y edición, y sin
él no habría manera de afirmar que el documento archivado es el del día que dice.

## El hallazgo que cambia una interfaz: un día puede traer DOS boletines

Sondeados **los 33 meses con datos** entre enero de 2024 y septiembre de 2026, cinco días traen
dos ediciones:

| Día | Ediciones |
|---|---|
| 2024-04-08 | `s24_0068`, `s24_0069` |
| 2025-10-24 | `s25_0203`, `s25_0204` |
| 2025-11-03 | `s25_0210`, `s25_0211` |
| 2025-12-01 | `s25_0231`, `s25_0232` |
| 2026-05-04 | `s26_0080`, `s26_0081` |

Aproximadamente **uno cada siete meses**. Y `enlaces` es una lista **de listas**: quien la lea
como si fuera una lista de cadenas se queda con la primera y **pierde la segunda edición entera,
en silencio**.

**Qué es la segunda edición, mirando la del 4 de mayo de 2026:** 485 bytes, **una sola
disposición**, sección `DISPOSICIONES GENERALES`, órgano `LEHENDAKARITZA` — un Decreto del
lehendakari. El contenido de ese en concreto es inocuo (luto oficial), pero **la forma es
exactamente la que importa**: una edición extraordinaria lleva una norma sola, del máximo rango,
en la sección de disposiciones generales. Es el canal por el que sale algo con prisa, y por tanto
justo lo que este proyecto existe para no perderse.

En los 33 meses, `diasHabilitados` y `enlaces` tienen **siempre la misma longitud**. Se comprueba
igual antes de emparejarlos: si dejaran de cuadrar, emparejar por posición asignaría a cada fecha
el boletín de otra, y eso es archivar bajo el día equivocado.

### Consecuencia: `ingerir_sumario_*` devuelve una tupla, todas

`services/ingesta.py` pasa a devolver `tuple[ResultadoIngesta, ...]` en las **seis** fuentes,
aunque cinco solo puedan devolver un elemento, y `worker/run.py` recorre las ediciones para las
etapas que van acotadas a un documento (fase 2, prefiltro, extracción, clasificación). Las que
barren toda la tabla —el versionado y el encolado de revisión— se quedan fuera del bucle, que es
donde tienen sentido.

**Uniforme y no un caso especial del BOPV, a propósito**: «un día trae uno o más boletines» es una
propiedad del dominio, no de una fuente. El BOJA publica extraordinarios también (su feed los
titula así), y el día que se integre no tendrá que cambiar esta interfaz para no perderlos.

## Las otras dos particularidades

1. **El sumario es plano.** `BOPVSumarioSeccion`, `BOPVSumarioSubseccion` y
   `BOPVSumarioOrganismo` son cabeceras de grupo sueltas entre los pares título/orden, no
   elementos que los contengan. Hay que arrastrar estado, como en el BOCYL. **Y la subsección se
   reinicia al cambiar de sección**: hay secciones que no la traen, y sin ese reinicio heredarían
   la de la anterior — la misma familia que el bug del título del ADR 0029, donde un valor de
   grupo se arrastra más allá de su grupo y acaba etiquetando una norma con lo que dice otra.

2. **El cuerpo no tiene contenedor.** El articulado (`BOPVDetalle`, `BOPVClave`, `BOPVFirma*`) son
   **hermanos** de los metadatos (`BOPVSeccion`, `BOPVOrganismo`, `BOPVTitulo`, `BOPVOrden`) bajo
   `<DOCUMENTO>`. `pipeline/texto.py` gana por eso una rama que **invierte** la derivación: en vez
   de señalar el articulado, excluye los cinco metadatos conocidos. La asimetría es la de 7.1 —
   una etiqueta nueva que no conozcamos entra en el texto (ruido, barato) en vez de quedarse fuera
   (articulado perdido, y perdido en silencio). `VERSION_TEXTO_PLANO` **no sube**: no cambia cómo
   se deriva nada ya archivado.

## Lo que NO trae

Ni el sumario ni el cuerpo dicen a qué norma afecta la disposición: no hay equivalente del
`<analisis>` del BOE. El eje referencial (7.3) depende aquí de las citas del texto
(`pipeline/citas.py`, ADR 0022), igual que en el DOGC, el BOA, el BOCYL y el BOCM. Con seis
fuentes ya se puede decir sin matices: **la estructura de referencias del BOE es la excepción, no
el estándar.**

Y el cuerpo **no declara su fecha de publicación**, así que no se puede contrastar como en el
BOCYL. Lo que sí declara es su `BOPVOrden`, y contra eso se comprueba: junto con la carpeta del
mes y el prefijo del año, que van en la URL, cubre el caso de que la fuente sirva otra cosa bajo
la misma dirección.

## Alternativas consideradas

- **BON (Navarra).** Se puede pedir por número de edición y **declara su propia fecha**. Su pega
  es que sus cuerpos son **HTML y nada más**, y eso choca con la raya del ADR 0029: *el texto que
  una alerta llegue a citar sale siempre del XML*. Con el BOPV resuelto, no hace falta decidir si
  esa raya se mueve, y esa decisión se deja sin tomar a propósito: moverla mientras se añade una
  fuente es cómo se pierde un guardarraíl. Navarra queda documentada en `docs/fuentes.md` como la
  primera candidata **si algún día se amplía el límite a siete**.
- **Ejecutar el JavaScript del calendario** con un intérprete. Ni se planteó en serio: es código
  de una fuente externa (regla de oro 1) y los dos arrays se leen con dos expresiones regulares.
- **Deducir la edición contando días hábiles** desde una edición conocida. Es adivinar con
  aritmética: los festivos autonómicos y los extraordinarios lo rompen, y el error sería archivar
  bajo el día equivocado sin que fallara nada.

## Consecuencias

- `fuente` gana una fila (`b3d5f80a1c47`), `worker/run.py` una entrada (`--fuente bopv`),
  `url_guard` una entrada de allowlist (`euskadi.eus`), `texto_integro` un validador de cuerpo y
  `pipeline/texto.py` una rama.
- **`services/ingesta.py` cambia de firma en las seis fuentes**, y `worker/run.py` recorre las
  ediciones. Es el cambio más invasivo de este ADR y el que lo justifica.
- **El recuento de CHECK no cambia** (hoy 15): la migración es un INSERT.
- La ingesta diaria de GitHub Actions (ADR 0032) pasa a seis fuentes.
- **El guardarraíl de la sección 8 queda agotado en 6.** La séptima necesita otra decisión del
  humano, no otra migración.
