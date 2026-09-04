# Cómo se ejecuta el trabajo con Claude Code — Faro Cuir

> **Esto era la sección 13 de `CLAUDE.md`.** Se sacó a un fichero propio el 2026-08-30 por el
> mismo motivo medido que la sección 11 el 2026-08-09: `CLAUDE.md` **entra entero en el contexto
> de cada subagente**, y su cabecera pide mantenerlo por debajo de ~55 KB. Estaba en 60.
>
> **Y esta sección es la que menos falta le hace a un subagente**: habla de cuota, de sesiones
> limpias, del backlog y del driver — cosas de la sesión principal. `revisor-seguridad` audita un
> diff y `auditor-reglas` mira esquemas; ninguno lanza un `run_agent.sh` ni decide si una tarea
> cabe en la ventana de cinco horas. Pagaban ~1.600 tokens cada uno por instrucciones que no
> pueden ejecutar.
>
> **Se intentó antes recortar narrativa de las secciones 6 y 7 y no dio.** Son reglas, no
> historial: los cortes limpios sumaron ~800 bytes y las correcciones que hacían falta el mismo
> día (el ADR 0030 en 7.6, el presupuesto de contexto ya medido en 6.9.7) añadieron más. Sacar
> un bloque entero que nadie del otro lado necesita es lo que de verdad baja el coste.
>
> **La numeración se conserva a propósito**, igual que con la 11: el repositorio cita «la sección
> 13» desde `run_agent.sh`, los ficheros de `.claude/agents/` y varios ADR, y renumerar rompería
> esas referencias a cambio de nada. Sigue siendo la sección 13; vive en otro fichero.

---

## 13. Cómo se ejecuta el trabajo con Claude Code

Sección operativa. No cambia el diseño del producto; cambia cómo se gasta el recurso escaso,
que aquí no es el dinero (todo es coste 0 €) sino la **cuota de la suscripción y el tiempo
humano de revisión**.

### 13.1 Límites de uso, en corto

Dos límites solapados: ventana móvil de 5 horas y **tope semanal**, con la cuota compartida con
el chat web. El semanal es el límite real: una sesión larga con mucho contexto arrastrado se lo
come rápido. Consecuencias, y son reglas:

- **Una tarea = una sesión limpia**, con `/clear` al cambiar. El estado vive en `ESTADO.md`, no en
  la conversación. Cambiar de modelo a mitad de conversación larga pierde la caché de prompt: si
  hay que cambiar, al empezar.
- Trabajo rutinario contra un criterio de aceptación claro: modelo rápido. Diseño, ADRs y
  seguridad: el modelo bueno.
- `/usage` antes de arrancar algo grande. Las estimaciones de contexto de `ESTADO.md` sirven para
  decidir si una tarea cabe en la sesión que empieza.

### 13.2 Backlog de tareas (`tasks/backlog/`)

Un fichero por tarea, `NN-nombre-corto.md`, ordenados por dependencia. Cada tarea debe ser
**autosuficiente**: se le pasa a una sesión nueva que solo tiene este CLAUDE.md como contexto.
Contenido mínimo:

- Objetivo en una frase.
- Ficheros exactos que se van a tocar.
- Criterio de aceptación **verificable con `pytest`** (más la verificación real que
  corresponda: `psql`, `curl`, navegador — en este repo eso ha encontrado fallos que ningún
  test veía).
- Restricciones de este archivo que la tarea no puede violar (citar sección).
- Coste estimado de contexto.

Al terminar una tarea: actualizar la sección 11, mover el fichero a `tasks/done/`.

### 13.3 Driver de sesiones (`run_agent.sh`)

Ejecuta tareas del backlog en modo headless, una sesión limpia por tarea. **Automatiza el
tecleo, no el criterio**: cada tarea va a su rama y **el merge lo autoriza el humano**.

#### Cómo se entra en `main` (regla cambiada el 2026-09-04, a petición del humano)

Antes decía «ninguna rama entra en `main` sin que la mire el humano», o sea que había que leerse
el diff. Ahora **el trabajo de comprobar es del agente y la autorización sigue siendo del
humano**. La razón del cambio, dicha por él: leerse dieciocho commits para autorizar algo que las
comprobaciones ya cubren es tiempo que no tiene, y el plazo es el 10 de septiembre.

**Lo que el agente tiene que haber hecho antes de pedir permiso, y no vale a medias:**

1. **Comprobar el RESULTADO DEL MERGE, no la rama.** Una rama puede estar verde y romper `main`
   igualmente: dos cambios compatibles a ojo pueden ser incompatibles juntos, y eso no lo ve el
   CI de la rama. Se hace el merge en local contra `main` actualizado y se comprueba **eso**.
2. **En un clon limpio, no en el directorio de trabajo.** Un `git clone` aparte y un entorno
   nuevo. Si no, se está comprobando la máquina de quien trabaja —con su `.venv` de hace tres
   semanas y sus ficheros sin commitear— y no lo que va a entrar. Ha pasado: la imagen de Docker
   local llevaba tiempo sin `pypdf` y nadie lo sabía.
3. **La puerta entera del CI**: `ruff check`, `ruff format --check`, `mypy app`, `alembic upgrade
   head` sobre una base vacía y `pytest` **completo**. Más el CI verde en el PR.
4. **Decir qué NO se ha podido comprobar.** Lo que necesita Ollama, lo que solo se ve contra
   producción, lo que depende de una decisión. Un informe que solo dice «todo verde» esconde
   justamente lo que hay que mirar.
5. **Nombrar los cambios que afirman algo**: catálogo de reglas, watchlist, prefiltro, esquema de
   extracción, controles de seguridad. No es un veto —no bloquean el merge— pero **se enumeran en
   la petición**, porque son los que ningún test puede validar: un test comprueba que la regla
   hace lo que dice, no que la regla deba decir eso. Ahí el humano decide si quiere mirar.

**Y después se pide autorización y se espera.** El agente **nunca** mergea por iniciativa propia,
ni aunque salga todo verde: lo que se ha relajado es qué se le pide al humano —autorizar en vez
de auditar—, no que haya humano. Un «sí» explícito, para ese merge concreto.

Lo que **no** cambia, y conviene no confundirlo con esto: el gate humano del producto (regla de
oro 4, ninguna alerta se emite sin una persona), las acciones externas de la sección 12, y que
**las migraciones las revisa una persona siempre** (13.3, abajo).

El script vive en **[`run_agent.sh`](../run_agent.sh)**, en la raíz del repositorio. **Lo que no
se va de aquí son sus reglas**, porque son de criterio y no de implementación:

- **Nunca `--dangerously-skip-permissions`.** La allowlist de herramientas es la que lleva el
  script: escribir código y correr las comprobaciones del CI, nada más.
- **Nunca `alembic upgrade` desatendido.** El aviso del autogenerate (sección 11) ha aparecido
  cuatro veces y una de ellas habría desarmado un control del proyecto. Las migraciones las
  revisa una persona, siempre.
- **Parada al primer rojo.** Un agente que sigue sobre tests rotos genera deuda más rápido de
  lo que se revisa.
- Ninguna acción de la sección 12 "Difusión" entra jamás en el backlog automático.
- `tasks/log/` en `.gitignore`.

### 13.4 Subagentes (`.claude/agents/`)

Ficheros Markdown con frontmatter, ámbito de proyecto. Contexto propio: la lectura pesada no
contamina la sesión principal. **Se cargan al arrancar**: si se crea uno con la sesión
abierta, hay que reiniciarla.

- **`revisor-seguridad`** — audita un diff buscando: fugas de datos de suscriptores, IPs o
  identificadores en logs, superficies de inyección nuevas, HTTP fuera de `url_guard`, XML
  fuera de `xml_safe`, llamadas al LLM fuera de `llm/`, y cualquier camino que salte el gate
  humano. `Read, Grep, Glob` más **`Bash` acotado a lectura del historial** (`git diff`, `log`,
  `show`, `status`): sin eso auditaba el árbol y no el diff, y un import **nuevo** —el hallazgo
  que su propio fichero llama el más importante— es indistinguible de uno de siempre.
- **`auditor-reglas`** — comprueba que el clasificador siga siendo determinista y auditable:
  que ninguna regla dependa de la salida valorativa del modelo, que cada veredicto emita
  `regla_aplicada` y spans, y que el esquema de extracción no haya ganado campos de juicio.
  `Read, Grep, Glob` más **`Bash` solo de verificación**: `git diff` sobre `alembic/` y el
  `SELECT ... FROM pg_constraint` de la sección 10. Leer la cadena de migraciones prueba que
  ninguna borra la CHECK; no prueba que la CHECK esté en la base de datos.
- **`evaluador`** — corre el gold set y reporta recall **desglosado por eje** (7.3),
  enumerando los falsos negativos uno a uno. Un número agregado no sirve: lo que importa es
  qué se escapó y por qué eje debería haber entrado.
- **`jurista-lgtbi`** — analiza normas de los tres niveles desde el derecho antidiscriminatorio.
  Produce **reglas candidatas para el clasificador (7.6)** e informes de apoyo al etiquetado y al
  gate humano. Aporta el conocimiento de dominio que no está escrito en ningún sitio: los
  instrumentos por nivel (con las **bases de subvención** como vector local), los vectores de
  retroceso ordenados por lo silenciosos que son, y **lo que parece cambio y no lo es** — de
  donde saldrían los falsos positivos del clasificador.

  **Sí señala «posible retroceso, a verificar»; no emite veredictos.** La diferencia no es de
  grado, es de naturaleza: una hipótesis va dirigida a una persona y **muere cuando esa persona
  decide**; un veredicto se persiste, se publica y hay que poder defenderlo ante un tercero sin
  ejecutar nuestro código. Que eso no llegue a `deteccion` ni a la API lo hace cumplir la CHECK
  `origenclasificacion`.

  **El riesgo que se diseñó en contra es el anclaje.** Si quien revisa lee «posible retroceso»
  antes que el artículo, ya no lo juzga: lo confirma, y el gate humano (regla 4) se vacía. Por eso
  el orden del informe es fijo —**texto citado → pregunta → hipótesis → qué la refutaría**— y el
  último punto es obligatorio siempre. Y tiene prohibido etiquetar el gold set: si lo etiquetara
  él, el sistema se mediría contra sí mismo.

Ninguno de los cuatro escribe código. Su salida es un informe para la sesión principal o para el
humano.

**Ojo con dos cosas que costaron una tanda entera de cuota:**

1. **Los subagentes se cargan al arrancar y son de ámbito de proyecto.** Si la sesión se abre
   fuera del repositorio, `subagent_type: auditor-reglas` devuelve *not found* y los cuatro son
   inalcanzables. Abrir la sesión **en la raíz del repositorio**, siempre.
2. **Gastan cuota muy rápido.** Los cuatro en paralelo agotaron el límite de sesión a mitad de
   trabajo y hubo que retomarlos. Regla: lanzarlos **de uno en uno**, con un presupuesto de
   llamadas dicho en el encargo, y no arrancar ninguno por encima del 60 % de consumo. Se
   retoman por su identificador conservando el contexto, así que un corte no obliga a repetir
   desde cero — pero lo barato es no provocarlo.