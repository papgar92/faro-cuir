# ADR 0034 — El BOCM como quinta fuente, y con él entra el nivel local

- **Fecha:** 2026-09-06
- **Estado:** aceptado
- **Sustituye a:** nada. **Relacionado con:** ADR 0019 (DOGC), 0028 (BOA), 0029 (BOCYL),
  0027 (el límite medido del eje referencial), 0014 (por qué la capa local se vigila por el BOP).

## Contexto

El proyecto llevaba **cuatro fuentes integradas** de 61 registradas. La medición del 2026-09-05
(`scripts/medir_fuentes_pendientes.py`, `docs/ESTADO.md`) se hizo para decidir la quinta, y dejó
tres cosas:

1. El rendimiento entre fuentes varía **24 veces** (8,5 ‰ del BOE contra 203,1 ‰ del DOGC),
   aunque la comparación esté confundida porque del BOE se ingiere todo, subastas incluidas.
2. **El BOCYL lleva 969 normas y cero detecciones, y es estructural**: Castilla y León es una de
   las dos únicas comunidades sin ley autonómica LGTBI, así que allí el eje referencial no puede
   dispararse sobre una norma propia. No fue un error —amplía cobertura y el léxico sigue
   trabajando— pero es el criterio que no hay que repetir.
3. Quedaban cuatro candidatas empatadas a **2 normas vigiladas** y sin boletín integrado:
   Andalucía, C. Valenciana, Madrid y País Vasco.

El humano pidió el 2026-09-06 **dos comunidades más, «las que estén más digitalizadas»**, y
observó que cada boletín necesita su propia lectura. Lo segundo ya era la arquitectura
(`ingest/` con un módulo por fuente) y lo confirma esta ronda; lo primero obligaba a **sondear**,
no a leer documentación, que es la disciplina que el ADR 0019 dejó fijada.

## El sondeo: qué se probó y qué contestó cada una (2026-09-06)

Pidiendo un día concreto, no leyendo su portal. Los resultados corrigen la tabla del 2026-08-29
en dos entradas, y una de las correcciones es la que decide este ADR.

| Fuente | Sumario | Cuerpo | ¿Se direcciona por fecha? |
|---|---|---|---|
| **BOCM** (Madrid) | **XML**, `BOCM-AAAAMMDD.xml` | **XML** por identificador | **Sí, solo con la fecha** |
| BOPV (País Vasco) | XML (`s26_0169.xml`) | XML por identificador | **No** — hace falta el nº de edición, y su sumario no declara su propia fecha |
| BON (Navarra) | HTML | **HTML y nada más** | No — por nº de edición |
| BOJA (Andalucía) | HTML | — | No — por nº de edición |
| DOGV (C. Valenciana) | HTML **generado por JS** | — | Sí, pero el listado no está en el HTML servido |
| DOE (Extremadura) | 403 | — | — |
| DOG (Galicia) | 404 en las rutas probadas | — | — |

**Dos correcciones a la auditoría anterior**, y las dos importan:

- **«BOCM: el XML por disposición da 500» era falso a día de hoy.** El BOCM sirve XML por los dos
  lados y, además, es el único candidato cuyo sumario se pide **solo con la fecha**, sin resolver
  antes un número de edición. Es la fuente más barata desde el BOE.
- **El BOPV es el que mejor XML tiene**, mejor incluso que el BOCM, pero su sumario **no declara
  su propia fecha**: solo se puede pedir por número de edición y no hay forma de comprobar que el
  que llegó es el del día que se quería. Para el archivo de la 6.5 —cuya afirmación entera es «el
  día X esto decía exactamente esto»— eso no es un inconveniente, es un descarte.

## Decisión

**El BOCM (Boletín Oficial de la Comunidad de Madrid) es la quinta fuente integrada.**

Se decide por tres motivos, en este orden:

1. **Es la más digitalizada de las que quedaban**, medido y no opinado: sumario XML por fecha
   pura, cuerpo XML por identificador declarado en el propio sumario, y 404 los días sin boletín.
2. **Madrid es el caso alrededor del cual se construyó el proyecto.** La §7.8 nombra la reforma
   madrileña de 2023 como caso obligatorio del gold set, y sus dos normas (`BOE-A-2024-10767`,
   `BOE-A-2024-10768`) son casos de control del ADR 0031. Vigilar el boletín de la comunidad cuyo
   retroceso motivó el sistema no hay que explicarlo ante un tribunal.
3. **Trae el nivel local, que llevaba 0 de 43 fuentes.** Madrid es uniprovincial y **no tiene
   BOP** (`docs/fuentes.md`): sus ayuntamientos publican aquí sus ordenanzas. Del día medido
   (2026-09-04), **27 de las 73 disposiciones son municipales** — el 37 %. La sección 1 describe
   tres niveles de administración y hasta hoy el sistema solo veía dos.

### Coste, para que conste

Cero código nuevo en el pipeline. **El cuerpo del BOCM tiene la misma forma que el del BOE**
—`documento > metadatos, analisis, texto`—, así que `pipeline/texto.texto_plano` lo lee sin
tocar una línea y `VERSION_TEXTO_PLANO` **no sube**. Es la primera fuente que no obliga a
enseñarle al proyecto una forma nueva de decir «aquí está el articulado».

## Las dos trampas verificadas

Ninguna fuente las documenta, y las dos rompen en silencio. Van en el docstring de
`ingest/bocm.py` con sus números; aquí queda por qué son decisiones y no detalles.

### 1. El sumario repite la lista entera, en triángulo

El sumario del 2026-09-04 pesa **2,9 MB** y trae **2.701 elementos `<disposicion>` para 73
disposiciones reales**: la primera aparece 73 veces, la segunda 72, la tercera 71… El sumatorio
73·74/2 da 2.701 exactamente, así que no es una anomalía del día, es cómo se genera el fichero.

Las copias son **idénticas** —mismo identificador, mismo título, misma sección y mismo
organismo—, comprobado disposición a disposición, así que **deduplicar por identificador es
seguro**. Sin deduplicar, la fase 2 pediría 2.701 cuerpos en vez de 73 y el archivo tendría 37
copias de cada norma; y el tope de disposiciones por día, que existe para frenar exactamente ese
tipo de respuesta (6.2), habría saltado todos los días.

### 2. `<fecha_publicacion>` no es la fecha de publicación

Es la del día anterior, sistemáticamente. Verificado en tres días seguidos:

| Sumario pedido | `<identificador>` | `<fecha_publicacion>` |
|---|---|---|
| 2026-09-04 | `BOCM-20260904` | `2026/09/03` |
| 2026-09-03 | `BOCM-20260903` | `2026/09/02` |
| 2026-09-01 | `BOCM-20260901` | `2026/08/31` |

Es la fecha de cierre de la edición, no la de la portada. **Apoyarse en el campo de nombre obvio
habría desplazado la fuente entera un día**, y no habría fallado nada visiblemente: el sistema
habría archivado boletines correctos bajo la fecha equivocada, que es la corrupción concreta que
la 6.5 existe para impedir. Lo que sí cuadra con la fecha pedida es `<identificador>`, y es
contra eso contra lo que se comprueba. Hay un test que lo fija y que dice por qué, para que nadie
lo «arregle» después.

## Lo que esta fuente NO aporta

Su cuerpo trae un bloque `<analisis>`, pero **no es el `<analisis>` del BOE**: solo lleva
`seccion`, `apartado`, `organismo` y `tipo_disposicion`. No dice a qué norma afecta la
disposición. El eje referencial (7.3) depende aquí de las citas del texto (`pipeline/citas.py`,
ADR 0022), igual que en el DOGC, el BOA y el BOCYL. **La estructura de referencias sigue siendo
una particularidad del BOE, no un estándar**, y con cinco fuentes esa frase ya está medida.

Y el recordatorio del ADR 0027 antes de prometer nada: solo el 7 % de las disposiciones modifican
algo, y ampliar la vigilancia rinde del orden de **5 casos al año**. Esto ordena candidatas; no
promete cobertura.

## Alternativas consideradas

- **BOPV (País Vasco), que tiene mejor XML.** Descartada por lo dicho: su sumario no declara su
  fecha, así que no se puede comprobar que el boletín que llegó es el del día pedido. Queda
  documentada en `docs/fuentes.md` como la mejor candidata *si algún día publica un índice por
  fecha*, que es una cosa concreta que mirar y no un «pendiente».
- **BON (Navarra).** Su sumario se puede pedir por número de edición y **declara su propia
  fecha**, que es lo que le falta al BOPV. Su problema es otro: **sus cuerpos son HTML y nada
  más**, y eso choca con la raya que el ADR 0029 dejó escrita —*el texto que una alerta llegue a
  citar sale siempre del XML*—. Ver ADR 0035.
- **Esperar y no añadir ninguna.** Es lo que decía el guardarraíl de la sección 8 hasta hoy
  (máximo 5 en la primera iteración). Con esta se agota ese límite exactamente; la sexta necesita
  que el humano lo amplíe, y lo amplió.

## Consecuencias

- `fuente` gana una fila (`a7c1e94b2d38`), `worker/run.py` una entrada (`--fuente bocm`),
  `url_guard` una entrada de allowlist (`bocm.es`) y `texto_integro` un validador de cuerpo.
- **El recuento de CHECK no cambia** (hoy 15): la migración es un INSERT.
- La ingesta diaria de GitHub Actions (ADR 0032) pasa a cuatro… cinco fuentes.
- **La página de cobertura pasa a tener que decir la verdad de otra manera**: con el nivel local
  dentro de una sola comunidad, «cobertura por CCAA» deja de significar lo mismo en Madrid que en
  las demás. Está anotado en `ESTADO.md` como lo siguiente que toca.
- La licencia de reutilización del BOCM queda en `TODO(verificar)`: no se localizó declaración y
  **no se deduce** (regla de oro 8).
