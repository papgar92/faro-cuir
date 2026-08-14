# ADR 0017 — Autenticación del panel de revisión (una credencial, sin tabla de usuarios)

- **Fecha**: 2026-08-14
- **Estado**: aceptado
- **Contexto de tarea**: gate humano (regla de oro 4 y ADR 0003), que hasta hoy existía en el
  esquema (`cola_revision`, `alerta`) y no en el código: había 5 detecciones con veredicto y
  ninguna forma de aprobarlas.
- **Números libres**: 0010 (canal pull) y 0013 (offsets) siguen **reservados** y sin escribir.
  El siguiente libre tras este es el **0018**.

## Contexto

El ADR 0003 declaró el gate humano obligatorio y sin flag que lo salte. El pipeline ya llega
hasta un veredicto derivado de reglas con su evidencia (ADR 0016), así que lo que faltaba era la
única etapa cuya decisión no la toma el código. Y toda la API del proyecto era, hasta hoy, de
solo lectura y sin autenticación —lo dice la cabecera de `api/documentos.py`— porque los
boletines oficiales son públicos y la transparencia es el producto.

Aprobar una alerta no es eso. Es la acción con consecuencias del sistema entero: lo que entra en
`alerta` es lo que el proyecto afirma en su nombre. Necesita autenticación, y esa autenticación
es el primer secreto de acceso que tiene el proyecto.

La pregunta no era «¿ponemos login?» sino **qué mínimo de aparato de identidad hace falta**, con
tres restricciones que no se pueden negociar por separado:

1. **Coste 0 € y lo mínimo que conseguir** (sección 0 bis): ni servicio de identidad, ni cuenta,
   ni dependencia nueva que auditar.
2. **Minimización (6.4)**: este proyecto no crea datos personales que no necesite, y quién
   revisa alertas sobre derechos trans es un dato que revela afinidad al colectivo exactamente
   igual que estar suscrito. `cola_revision` ya se diseñó sin columna de autor por ese motivo.
3. **Falla cerrado**: sin configuración, el panel no abre. Nunca «pues que entre cualquiera».

## Decisión

**Una credencial de revisión compartida, guardada como hash scrypt en el entorno, con sesión
opaca en cookie `HttpOnly` gestionada en memoria por el propio backend.** Sin tabla de usuarios,
sin dependencia nueva y sin identidad de la persona en ninguna fila.

Las piezas, todas en `security/panel.py` (puerta única, igual que `url_guard` con el HTTP
saliente) y `api/revision.py`:

- **`PANEL_PASSWORD_HASH`**, formato `scrypt$n$r$p$sal$clave`, con los parámetros dentro del
  propio hash para poder subirlos mañana sin invalidar lo ya generado. `hashlib.scrypt` es
  biblioteca estándar: nada que instalar. Se genera con
  `python -m scripts.generar_hash_panel`, que pide la contraseña por `getpass` para que no pase
  por el historial del intérprete de órdenes ni por un fichero.
- **Token de sesión aleatorio** (`secrets`), devuelto **solo** en una cookie `HttpOnly` +
  `Secure` + `SameSite=Strict` + `Path=/api/revision`. Nunca en el cuerpo de la respuesta.
- **Sesiones en memoria, indexadas por `sha256` del token**, con caducidad y tope. El servidor
  no necesita poder leer los tokens vivos, solo reconocer uno cuando lo ve.
- **Segundo control anti-CSRF**: las escrituras exigen la cabecera `X-Faro-Panel`. Es
  redundante con `SameSite=Strict` a propósito — ver «Consecuencias».
- **Cadencia de intentos global y sin IP** para la fuerza bruta.

## Alternativas consideradas

**Tabla `usuario` con altas, roles y recuperación de contraseña.** Es lo que se hace por
costumbre, y aquí habría sido crear el fichero que la 6.4 se dedica a no crear. Con una sola
persona revisando, la tabla no aporta nada que la variable de entorno no dé, y sí aporta correos
electrónicos, hashes de contraseña y un flujo de recuperación que mantener. Cuando haya varias
personas revisando habrá que rehacer esto, y **entonces será una decisión con su propio ADR**,
no el efecto colateral de un `CREATE TABLE` escrito hoy «por si acaso». Está escrito en la
cabecera del módulo para que se lea al tocarlo.

**HTTP Basic.** Cero código, pero manda la credencial en cada petición, la deja en el gestor de
contraseñas del navegador sin cierre de sesión posible, y no hay forma de invalidar nada.

**JWT sin estado.** Se descarta por lo mismo que se descarta guardar el token en
`localStorage`: **no se puede revocar**. Un cierre de sesión que solo borra la cookie del
navegador es teatro — quien tuviera el token seguiría entrando. Y un JWT obliga a gestionar un
secreto de firma para no ahorrarse ninguna consulta, porque aquí no hay varios servicios que
verificar entre sí. Hay un test cuyo único trabajo es comprobar que cerrar sesión invalida el
token **en el servidor**.

**Sesiones en una tabla.** Sobreviven al reinicio, y a cambio crean una segunda ubicación
persistente con material de autenticación. Para un panel que usa una persona, reiniciar el
backend y volver a entrar es un precio bajo. Si algún día molesta, se cambia; el almacén de
sesiones es una clase con tres métodos.

**Un OAuth cualquiera (Google, GitHub).** Cuenta de terceros, dependencia externa y —lo
importante— le cuenta a un proveedor quién revisa alertas de derechos trans y cuándo. Contra la
6.4 en el peor sitio posible.

**Limitar los intentos por IP.** Es lo estándar y aquí está prohibido: la 6.4 dice literalmente
que no se registran IPs, y el limitador general (`rate_limit.py`) ya se escribió sin
persistirlas. El cubo de fichas es **global**, sin clave por cliente.

**Y un cubo global mal ordenado anula el gate: el hallazgo de la auditoría.** La primera versión
gastaba una ficha *antes* de comprobar la contraseña y devolvía 429 con el cubo vacío. El
subagente `revisor-seguridad`, sobre el diff ya escrito, señaló la consecuencia: cualquiera, sin
credenciales y desde una sola dirección sin salirse del limitador general de 60 pet./min,
mantiene el cubo a cero indefinidamente, **y entonces la contraseña correcta tampoco entra**. El
control de fuerza bruta se convertía en la vía para cerrar el único camino hacia `alerta`, o sea
para desactivar desde fuera la etapa que la regla de oro 4 declara obligatoria.

El arreglo no reduce la probabilidad, elimina el caso: **la contraseña se comprueba siempre, y si
es correcta se entra siempre; solo un intento fallido gasta ficha**. Quien la sabe no puede
quedarse fuera por estado del servidor; quien no la sabe se queda sin intentos. El precio es que
scrypt corre en cada intento (~50 ms y 16 MB), así que la verificación se **serializa con un
cerrojo**: sin él, cien intentos simultáneos son 1,6 GB y el control de acceso vuelve a ser el
vector, esta vez de agotamiento. Hay un test cuyo único trabajo es fallar si alguien vuelve a
poner la cadencia por delante de la comprobación.

## Consecuencias

**Buenas**

- El gate humano existe de verdad: `alerta` solo se escribe desde `services/revision.aprobar`, y
  no hay ningún otro camino hasta esa tabla. El test que lo fija comprueba que un intento sin
  sesión devuelve 401 **y además no deja fila**, que es la mitad que se olvida.
- **La frase «la API pública no tiene escrituras» sigue siendo cierta y comprobable.** El test
  que la sostiene (`test_la_api_publica_no_expone_ninguna_escritura`) se puso rojo al montar el
  panel, que es exactamente para lo que estaba; se corrigió nombrando `/api/revision` como la
  **única** excepción, no relajando la comprobación.
- Un ítem resuelto **no se reabre** (409). Reabrirlo permitiría emitir dos veces la misma alerta
  o retirar una emitida sin dejar constancia, y el rastro de auditoría es parte del producto
  (6.5): descartar no borra la detección ni su evidencia.
- Sin dependencia nueva, sin cuenta que pedir, sin coste.

**Malas, y asumidas**

- **Una credencial compartida no distingue personas.** Es coherente con no guardar el autor,
  pero significa que el registro de auditoría dice «se aprobó», no «lo aprobó Fulana». Para un
  proyecto con una persona revisora es el intercambio correcto; con dos ya no lo será, y ese es
  el disparador para revisitar este ADR.
- **Cada intento de login cuesta scrypt**, incluso los que van a acabar en 429, porque la
  comprobación va por delante de la cadencia (ver arriba). Serializado, eso son ~20 intentos por
  segundo como techo; el limitador general acota además por IP. Es CPU gastada a propósito.
- **Reiniciar el backend cierra todas las sesiones.**
- **Este servicio es de proceso único.** `_sesiones` y `_cadencia` viven en memoria del proceso, y
  el compose arranca uvicorn sin `--workers`. Con varios procesos, las sesiones no se verían
  entre ellos —falla cerrado, 401 intermitentes— pero **la cadencia se multiplicaría por el
  número de workers, y eso falla abierto**. Escalar exige mover los dos almacenes a un sitio
  compartido; está escrito en `api/revision.py`, junto a las variables, que es donde se va a
  leer.
- **La cookie es `Secure` sin interruptor para apagarla.** En producción obliga a HTTPS, que es
  lo que se quiere; en local funciona porque los navegadores tratan `localhost` como origen
  seguro. El precio real apareció al verificar: `curl` sobre `http://` **no devuelve** una cookie
  `Secure`, así que la comprobación por línea de órdenes hay que hacerla pasando la cabecera
  `Cookie` a mano. Que el verificador tuviera que hacer eso es, de por sí, la prueba de que el
  atributo está puesto.

**Sobre la redundancia del control anti-CSRF.** `SameSite=Strict` ya impide que un formulario de
otro sitio mande la cookie, así que la cabecera `X-Faro-Panel` sobra *si* el navegador la
respeta y *si* nadie activa CORS. Se pone igualmente porque las dos condiciones son cosas que
alguien puede cambiar sin darse cuenta de que estaba sosteniendo un control de seguridad, y
porque una cabecera propia no se puede enviar entre orígenes sin un *preflight*. Dos controles
que fallan por motivos distintos valen más que uno bueno; es el mismo criterio que el «cinturón
y tirantes» de `storage_path` en `security/hashing.py`.

## Lo que cambió después de la auditoría (misma sesión)

`revisor-seguridad` corrió sobre el diff ya escrito y encontró seis cosas. Se arreglaron las seis
antes de dar la tarea por cerrada:

1. **La cadencia podía cerrar el panel** (arriba, y es la importante).
2. **Un intento fallido no dejaba ningún rastro.** El único control de acceso del proyecto era
   también el único sin observabilidad. Ahora se registra un **contador agregado** de fallos en
   la ventana y la apertura y cierre de sesión — sin IP, sin identidad, sin la contraseña. La 6.4
   prohíbe inventariar direcciones, no contar.
3. **Carrera al resolver.** `_resolver` leía el estado y escribía sin bloquear la fila, así que
   dos `POST` simultáneos pasaban los dos por «está pendiente». No salían dos alertas —lo impide
   la unicidad de `alerta.deteccion_id`— pero una comprobación que solo funciona porque la base
   de datos la rescata no es una comprobación. Ahora `with_for_update` al resolver, y el error de
   integridad se traduce al 409 que ya significaba «llegas tarde».
4. **La cookie de borrado no repetía `Secure`.**
5. **Las respuestas del panel salían sin `Cache-Control: no-store`.** La API pública sirve
   boletines y puede cachearse; la cola de revisión lleva evidencia y notas.
6. **Un `assert` en el camino de escritura**, que con `python -O` desaparece y habría reventado
   *después* de emitir la alerta.

## Verificación

Contra la base de datos real y por HTTP, no solo con tests (46 nuevos, 398 en verde):

- Sin sesión: `GET /api/revision/cola` → 401, y aprobar → 401 **con 0 filas en `alerta`**.
- Contraseña incorrecta → 401. Cuarta en un minuto con el cubo a 3 → 429.
- Cookie emitida: `HttpOnly; Max-Age=3600; Path=/api/revision; SameSite=strict; Secure`.
- Cola real: **5 ítems**, ordenados por severidad declarada. Las **13 detecciones** de la base
  incluyen 8 centinelas del extractor (ADR 0009) y **ninguno entra en la cola**: sin regla no hay
  veredicto que aprobar.
- Aprobar sin `X-Faro-Panel` → **403 y 0 alertas**. Con la cabecera → 200, y en la base:
  `cola_revision.estado='aprobada'`, `resuelta_en` con fecha, `deteccion.revisada=true` y **1
  fila en `alerta`**. Segundo intento sobre el mismo ítem → **409**.
- `DELETE /api/revision/sesion` → 204, y el mismo token → 401.
- `worker.run --reclasificar` dos veces: 5 encoladas y luego **0**. Idempotente.

La primera alerta aprobada del proyecto es `BOE-A-2024-10767`, la reforma madrileña de 2023, con
sus doce spans de evidencia sobre el texto archivado. Es el caso que el proyecto usa para
explicar por qué existe, y ahora ha recorrido el pipeline entero: ingesta → archivo con huella →
prefiltro por dos ejes → catálogo de reglas → **una persona mirándolo** → alerta.
