# ADR 0019 — El DOGC como segunda fuente, y lo que costó integrarlo

- **Fecha**: 2026-08-16
- **Estado**: aceptado
- **Contexto de tarea**: el humano pidió «muchísimas más normas, también provinciales y locales».
  La primera parte de la respuesta es volumen del BOE; esta es la segunda.
- **Números libres**: el siguiente es el 0020.

## Contexto

El proyecto vigilaba **una** fuente. La pregunta que lo cambió fue del humano y era la correcta:
*¿el BOE publica las resoluciones de las comunidades?*

**No.** Medido sobre 1.193 normas ya ingeridas: de órganos autonómicos llegan **31 ítems**, y
mirándolos uno a uno son anuncios de información pública, correcciones de errores y alguna
resolución de servicios judiciales. El BOE **sí** republica las *leyes* autonómicas —ahí está la
Ley 17/2023 madrileña, el caso insignia del proyecto— y por eso la watchlist de 21 leyes (ADR
0012) funcionó sin tocar ningún boletín autonómico. Pero **ni un decreto, ni una orden, ni una
instrucción de consejería**. Y de lo municipal, solo convocatorias de plazas y licitaciones:
ninguna ordenanza.

Eso deja al sistema ciego exactamente donde la sección 1 dice que mira: «la instrucción de rango
bajo publicada un martes de agosto». Nadie deroga una ley trans por decreto; se vacía su
desarrollo con una orden que solo sale en el boletín de su comunidad.

## Decisión

**Se integra el DOGC (Diari Oficial de la Generalitat de Catalunya) como segunda fuente y primera
autonómica.**

Se eligió tras verificar cinco candidatas descargando sus endpoints, no leyendo su documentación:

| Fuente | Qué se pudo obtener | Veredicto |
|---|---|---|
| **DOGC** | Sumario JSON filtrable por fecha + texto íntegro en XML Akoma Ntoso | **Integrable ya** |
| BOPB (Barcelona) | RSS del día + histórico por fecha + PDF por anuncio | Integrable, siguiente |
| BOJA (Andalucía) | API REST prometedora (`bodyNoHtml`) que devolvió 422; el HTML alternativo **declara que suprime contenido** | Descartada por ahora: choca con 7.1 |
| BOCM (Madrid) | RSS de 20 sumarios + HTML; el XML por disposición devuelve 500 | Integrable con esfuerzo |
| BOP de Cáceres | CSV de **metadatos sin texto ni enlace** | No sirve |

El DOGC es el único que cumple los cuatro requisitos sin concesiones: sumario por fecha exacta,
**texto íntegro estructurado** (no un PDF ni un HTML recortado), URL estable sin clave y
actualización diaria. Cubre **31.094 disposiciones desde 1977**, de las cuales **20.889 órdenes y
9.061 decretos**: justo el rango bajo que motivaba todo esto.

## Tres decisiones que van con esta, y ninguna es cómoda

### 1. Se ingiere la versión castellana, no la oficial catalana

El vocabulario del prefiltro (7.3) es castellano. Sobre el texto catalán no dispararía casi nada
y **el eje léxico quedaría apagado sin que nada fallara**, que es el modo de fallo que este
proyecto no se permite. La versión oficial del DOGC es la catalana; la castellana es su
traducción oficial, publicada por la misma fuente y con su propia URL ELI.

Queda dicho aquí porque una alerta se sostiene sobre una cita literal, y esa cita saldrá de la
traducción. La alternativa honesta a medio plazo es un vocabulario catalán —no traducir nosotros,
que sería inventar el texto—, y entonces se ingerirían las dos versiones.

### 2. El sumario vive fuera del dominio del diario

No está en `gencat.cat` sino en el portal de datos abiertos de la Generalitat, servido por un
proveedor externo. Es la fuente oficial de datos abiertos del gobierno catalán, así que entra en
la allowlist de `url_guard` (ADR 0006) — pero entra **escrito**, porque «allowlist de dominios
oficiales» deja de ser autodescriptivo en cuanto uno de ellos no lo parece.

### 3. Se acepta un perfil TLS heredado **solo para un host**

`portaldogc.gencat.cat`, que es donde acaba la redirección del texto íntegro, **solo negocia TLS
1.2 con `AES256-SHA`**. OpenSSL 3 lo rechaza por su nivel de seguridad por defecto. Esto costó
una hora de depuración y merece quedar escrito, porque el síntoma engañaba: **`curl` funcionaba y
Python no**, porque `curl` en Windows usa el TLS del sistema. Se probaron handshakes uno a uno
hasta aislar el cifrado exacto.

Qué se relaja y qué no:

- **Se relaja** el nivel de cifrado para ese host: se acepta un algoritmo sin secreto hacia
  adelante y con MAC antiguo.
- **No se relaja** la verificación del certificado. Sigue haciendo falta un certificado válido
  para el nombre, así que esto **no es `verify=False` con otro nombre**.
- **No se relaja para nadie más.** La política es una lista de hosts en `url_guard`, no un ajuste
  global: hacerlo global habría debilitado también la descarga del BOE, que negocia TLS 1.3.
- La integridad no depende solo del canal: lo descargado se sella con su `sha256` (6.5).

Y el contenido es normativa pública: no hay confidencialidad que proteger, sí integridad, y esa
se sostiene con certificado más huella.

## El hallazgo técnico que casi pasa desapercibido

El DOGC publica **Akoma Ntoso** (estándar OASIS de documentos legales) con una peculiaridad que
no está en el estándar: **el articulado entero no va en nodos de texto, va dentro de un atributo
XML** (`<content period="&lt;div&gt;&lt;p&gt;…">`), con el HTML escapado dentro.

Consecuencia: `itertext()` sobre ese árbol devuelve **cadena vacía**. Un derivador escrito
leyendo el estándar habría archivado cientos de normas con texto vacío, el prefiltro las habría
descartado todas por no encontrar ningún término, y **no habría fallado nada visiblemente**. Se
detectó porque se comprobó el texto derivado sobre un documento real (22.086 caracteres tras
arreglarlo) en vez de dar por bueno el parseo. Tiene su propio test con XML real.

## Alternativas consideradas

- **Esperar a integrar los 17 boletines autonómicos a la vez.** Contra la sección 8, que limita a
  cinco fuentes la primera iteración: con una integrada de verdad se demuestra la capacidad y se
  aprende lo que cada fuente tiene de particular —que, visto lo visto, es mucho.
- **Empezar por Madrid (BOCM)**, que es donde ocurrió la reforma del caso insignia. Descartada
  hoy por formato: su XML por disposición devuelve 500 y el resto es HTML y PDF. Es la siguiente
  candidata en cuanto se resuelva cómo obtener el número de boletín de una fecha pasada.
- **Raspar el HTML del BOJA.** La propia página advierte de que «se han suprimido ciertas tablas
  y algunos textos de la versión oficial por dificultades de edición». Eso choca de frente con
  7.1: el descarte solo ocurre tras leer el documento **completo**.

## Consecuencias

- **El sistema deja de ser monofuente**, y con él el modelo de dominio: `fuente` tiene su primera
  fila `boletin_autonomico` activa. Las 43 provinciales siguen registradas y **no vigiladas**
  (`activa` en falso), que es la distinción que el ADR 0014 pedía mantener visible.
- **El ingestor nuevo devuelve el mismo `Sumario`/`ItemSumario` que el del BOE.** El archivo, el
  prefiltro y el clasificador no saben de qué boletín viene una norma, y así debe seguir: cinco
  formas distintas de decir «una disposición publicada» serían cinco caminos que mantener.
- **Lo que esta fuente no trae, y hay que repetirlo**: son disposiciones generales (leyes,
  decretos legislativos, decretos ley, decretos y órdenes). **Las resoluciones e instrucciones no
  están**, y son un vector de retroceso real. Cubrirlas exige el sumario completo del diario, que
  no se ha verificado que sea obtenible por programa.
- **El prefiltro se estrena con un vocabulario que nunca ha visto texto catalán traducido.** Los
  primeros días de DOGC ingeridos son también los primeros datos para saber si el eje léxico se
  comporta igual sobre una traducción. Ninguna cifra de esto se publica hasta que el gold set
  tenga casos del DOGC.
- El coste de añadir la tercera fuente baja: lo genérico ya está separado de lo específico. Lo
  que no baja es el coste de **verificar** una fuente nueva, que es donde se ha ido el tiempo
  aquí y donde se irá siempre.
