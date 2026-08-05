# 0006 — Puerta única de salida HTTP y conexión clavada a la IP validada

> Numeración: los ADR 0002–0005 están reservados en `CLAUDE.md` sección 9 para decisiones ya
> previstas (el LLM extrae no juzga, gate humano obligatorio, no persistir el veredicto del
> LLM, archivo con sellado de tiempo). Este ADR documenta una decisión que surgió al
> implementar la sección 6.2, así que toma el siguiente número libre en vez de ocupar uno
> reservado.

## Contexto

El worker de ingesta descarga sumarios de boletines oficiales y después sigue los enlaces a
documentos que vienen **dentro de esos sumarios**. Esas URLs son dato no confiable: las
escribe la fuente, no nosotros. Cualquiera que controle o comprometa una fuente puede colar
una URL arbitraria y hacer que el worker la pida por él.

Eso es un SSRF de manual. El worker corre dentro de la red del despliegue, así que puede
alcanzar cosas que un atacante desde fuera no puede: la base de datos, la propia API en
`localhost`, y — en cualquier despliegue en cloud — el endpoint de metadatos de
`169.254.169.254`, que en muchas configuraciones entrega credenciales de la instancia.

`CLAUDE.md` sección 6.2 ya fijaba el requisito (allowlist, rechazo de IPs internas, control
de redirecciones, timeouts, límite de bytes). Al implementarlo aparecieron dos preguntas que
el requisito no resolvía y que condicionan el resto de la ingesta.

## Decisión

### 1. `security/url_guard.py` es la única salida HTTP del proyecto

Ningún módulo de `ingest/` importa `httpx` directamente. Todo tráfico saliente pasa por
`url_guard.fetch()`.

La alternativa natural —"que cada módulo de ingesta use httpx y llame al validador antes"—
convierte la seguridad en algo que hay que **acordarse** de hacer. Con 18 fuentes por
integrar, cada una escrita en un momento distinto, la probabilidad de que alguna se salte el
paso no es baja: es del 100% a medio plazo. Al no existir otra vía de salida, saltarse el
control deja de ser un olvido posible y pasa a requerir un cambio deliberado y visible en
revisión de código.

### 2. La petición se clava a la IP ya validada

Validar el nombre de host y dejar que el cliente HTTP lo resuelva otra vez por su cuenta deja
un TOCTOU clásico (*time-of-check to time-of-use*):

1. Validamos: `boe.es` → resuelve a una IP pública. Correcto, adelante.
2. httpx abre la conexión y **vuelve a resolver** `boe.es` por su cuenta.
3. Un DNS hostil, con TTL de 0, contesta `127.0.0.1` en esa segunda resolución.
4. La petición sale hacia dentro de la red con la validación ya superada.

Esto es **DNS rebinding**, y hace que la comprobación de IP del punto anterior sea
decorativa. La solución adoptada: construir la petición contra `https://<ip-validada>/...`,
llevando el nombre original en la cabecera `Host` (para que el servidor sirva el vhost
correcto) y en la extensión `sni_hostname` de httpx.

Verificado en el código de `httpcore` (`_sync/connection.py`): `sni_hostname` se pasa a
`start_tls` como `server_hostname`, que es el parámetro que usa `ssl` tanto para el SNI del
handshake como para **verificar el certificado**. Es decir: conectamos contra la IP que ya
validamos, pero seguimos exigiendo un certificado válido a nombre de `boe.es`. No se relaja
TLS a cambio de esto.

De ahí se sigue el rechazo de `http://`: sin certificado no habría nada que desmintiera al
DNS, y clavarse a una IP sería clavarse justamente a lo que dijo un DNS potencialmente
hostil.

### 3. Los rangos internos se rechazan por `is_global`, no por lista

Se comprueba "¿es una dirección enrutable en Internet pública?" en vez de "¿está en mi lista
de rangos prohibidos?". Una lista escrita a mano siempre se deja algo fuera: CGNAT
(`100.64.0.0/10`), benchmarking (`198.18.0.0/15`), `0.0.0.0/8`, unique-local IPv6
(`fc00::/7`)... Invertir la pregunta hace que lo desconocido se rechace por defecto.

Complemento necesario: un IPv6 mapeado (`::ffff:127.0.0.1`) se desenvuelve a su IPv4 antes de
juzgarlo, porque según la versión de Python el predicado sobre el envoltorio no siempre mira
la dirección de dentro, y esa discrepancia es exactamente por donde se cuela un bypass.

## Alternativas consideradas

- **Confiar en `follow_redirects=True` de httpx y validar solo la URL inicial.** Descartado:
  un `302` hacia `http://127.0.0.1` anula toda la validación previa. Las redirecciones se
  siguen a mano, revalidando cada salto desde cero (allowlist + resolución + IP pública),
  con un máximo de 3.
- **Aplicar el límite de tamaño mirando `Content-Length`.** Descartado: esa cabecera la
  escribe el servidor, o sea el atacante, y puede mentir o no existir. El tope se aplica
  sobre los bytes según van llegando, leyendo en streaming. Comprobar la cabecera sería un
  atajo cómodo e igual de inútil.
- **Un proxy de salida (squid/tinyproxy) con la allowlist configurada, en vez de controlarlo
  en código.** Es una defensa en profundidad legítima y probablemente lo correcto en
  producción real, pero desplaza el control a infraestructura que el tribunal no ejecuta y
  que no queda cubierta por tests. Se documenta como refuerzo recomendado en despliegue, no
  como sustituto del control en código.
- **Allowlist en base de datos (derivada de `fuente.url_base`) desde ya.** Aplazado: hoy solo
  hay una fuente verificada (BOE). Se deja una constante en el módulo con la nota de que debe
  pasar a derivarse de la tabla `fuente` cuando haya varias fuentes reales, para no montar la
  maquinaria antes de necesitarla.

## Consecuencias

- Añadir una fuente nueva exige **también** añadir su dominio a la allowlist. Es fricción
  deliberada: una fuente nueva es una decisión de confianza, no un detalle de configuración.
- El pinning por IP rompería si alguna fuente futura exigiera pasar por un proxy HTTP
  corporativo o usara un CDN con validación por SNI no estándar. Si aparece ese caso, se
  revisita aquí, no se parchea en el módulo de ingesta.
- La suite de tests del guardia no toca la red: el resolver DNS se inyecta y el transporte es
  un `MockTransport`. Es determinista y corre en CI sin salida a Internet — condición para
  que estos controles se verifiquen en cada push y no solo el día que se escribieron.
- `url_guard` sólo expone `GET`. Cuando haga falta otro verbo (hoy no), se añade ahí y hereda
  todos los controles; no se abre una vía paralela.
