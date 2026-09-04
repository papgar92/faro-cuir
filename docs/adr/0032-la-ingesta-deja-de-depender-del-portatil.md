# ADR 0032 — La ingesta deja de depender de que el portátil esté encendido

- **Fecha:** 2026-09-04
- **Estado:** aceptado
- **Afecta a:** `.github/workflows/ingesta.yml`, `services/archivo.py`, `services/almacen_remoto.py`,
  `config.py`, el despliegue entero
- **Continúa:** ADR 0005 (el archivo íntegro), ADR 0006 (la excepción de Ollama a `url_guard`),
  ADR 0008 (LLM local, coste 0 €), ADR 0011 (se descarga el día entero)

## Contexto

Un sistema que vigila boletines **a diario** y solo ingiere cuando alguien enciende un portátil y
levanta Docker no vigila a diario: vigila los días que alguien se acuerda. Está medido en el
propio repositorio — los backfill de fondo no sobreviven a un `docker compose up` y ha habido que
relanzarlos a mano más de una vez, con la nota en `CLAUDE.md` sección 10 para probarlo.

El humano preguntó por Supabase, que es a donde habían migrado unos compañeros. La respuesta corta
es que **Supabase pausa un proyecto gratuito a los 7 días sin actividad** y hay que reactivarlo a
mano desde el panel: para una aplicación que alguien abre a diario da igual, para un cron
desatendido es exactamente el fallo que 6.9.6 prohíbe. Lo mismo con los otros candidatos obvios:
Fly.io ya no tiene plan gratuito (solo una prueba), Render no incluye cron jobs en el gratuito,
Railway da 5 $ que caducan, y Oracle Always Free exige tarjeta.

## Decisión

Tres piezas, ninguna con coste ni tarjeta:

| pieza | dónde | por qué esa |
|---|---|---|
| **cómputo** | GitHub Actions, `schedule:` diario | runners de Linux **gratis e ilimitados en repositorios públicos**, y este lo es. 6 h por job contra los ~20 min que tarda el día entero |
| **base de datos** | Neon | Postgres gestionado, 0,5 GB, **se despierta solo al conectar** en vez de pausarse a la semana |
| **archivo (6.5)** | bucket compatible con S3 (Backblaze B2) | 10 GB gratis. El disco de un runner se destruye al acabar el job |

### Lo que este despliegue NO hace, y es lo primero que hay que saber

**No llama al LLM.** Todos los pasos de ingesta del workflow llevan `--sin-extraccion`. No es una
degradación silenciosa: Ollama corre en local por el ADR 0008 y en un runner no hay ninguno.

**No cuesta vigilancia**, y eso no es una esperanza sino la consecuencia de una decisión anterior:
desde el ADR 0016 **el gate humano se alimenta del catálogo de reglas leyendo el texto archivado,
no de la extracción**, y 6.9.7 ya dejó medido que el modelo pequeño solo llega a ver el 2,6 % de
un documento medio. La cola del extractor se drena en local con `--extraer` cuando apetezca, y lo
que se queda fuera no se pierde nunca porque la cola es una consulta.

### El archivo cambia de sitio sin cambiar de forma

`services/archivo.py` ya era **la puerta única** del almacén, así que esto fue un `if` y no un
refactor: los treinta y ocho módulos que archivan o leen no se enteran. Y la clave del objeto es
**la misma ruta relativa** que en disco, la que deriva del sha256, así que **migrar no reescribe ni
una fila de `documento`** — se copia el árbol tal cual (`rclone copy ./data remoto:bucket`) y se
rellenan cuatro variables de entorno. Hay un test que fija esa igualdad.

Tres decisiones dentro de esta:

1. **Sustituye al disco, no lo replica.** Con bucket configurado no se escribe nada en local.
   Escribir en las dos partes dejaría en el runner una copia que parece un respaldo y se destruye
   con el job. Y si falta una credencial **se para y se dice** en vez de caer al disco.
2. **«No está» y «no se puede llegar» siguen siendo hechos distintos.** Un objeto ausente lanza
   `FileNotFoundError` —que es `OSError`, así que `cuerpo.py` marca la norma `ilegible` como
   siempre (7.2), reintentable en cada pasada—. Cualquier otro fallo lanza `AlmacenRemotoCaido`,
   que **no** es `OSError` y para la pasada: un 500 del almacén no puede marcar de golpe cientos
   de normas como ilegibles y contarlo como cobertura perdida.
3. **`boto3`, y no SigV4 a mano sobre `httpx`.** Escribir sesenta líneas de HMAC propias en el
   camino de escritura del archivo que sostiene el proyecto es peor idea que una dependencia más.
   Y el dialecto S3 antes que la API nativa de B2 porque deja cambiar de proveedor sin tocar
   código.

### Es la segunda excepción declarada a la allowlist de `url_guard` (6.2)

La primera es Ollama (ADR 0006), y el criterio que las hace legítimas es el mismo: **el destino
sale de la configuración del despliegue, no de un documento.** `url_guard` existe para las URLs
que vienen de un sumario, que son las que controla un tercero; aquí el host es un literal de
entorno y la clave del objeto es un sha256 nuestro.

Y por eso se valida al arrancar, igual que la URL de Ollama: **HTTPS obligatorio** —por ahí van el
archivo íntegro y la credencial que lo firma—, sin credenciales en la URL y sin ruta.

## Consecuencias

- **La vigilancia deja de depender del portátil.** Que era el problema.
- **Menos secretos en la nube que en local**, a propósito: el workflow no lleva
  `SUSCRIPTOR_PEPPER` ni `PANEL_PASSWORD_HASH` porque el worker no los usa. Los logs de las
  Actions de un repositorio público los lee cualquiera; que no haya nada que leer es mejor que
  confiar en que GitHub enmascare bien. Y no hay nada personal que registrar, porque 6.4 ya
  prohibía registrarlo.
- **Los reprocesados masivos siguen siendo trabajo de la máquina de casa.** `--reprefiltrar` sobre
  ~82.000 normas lee el cuerpo de cada una: contra el bucket serían 82.000 descargas, por encima
  del tope diario del plan gratuito y del límite de 6 h de un job. El `--reclasificar` diario sí
  cabe de sobra, porque solo mira lo que cambió de versión.
- **GitHub desactiva un `schedule:` tras 60 días sin actividad en el repositorio**, avisando solo
  por correo. Un correo no es un canario (6.9.6), así que el canario es el que ya existe: la web
  publica `ultima_publicacion` por fuente (`schemas/cobertura.py`) y una fuente muda se ve en la
  página de cobertura sin que nadie tenga que acordarse. Reactivar es un `workflow_dispatch`.
- **Dos plazos, medidos y no estimados.** La base ocupa 143 MB con 83.011 normas —**1.805 bytes
  por norma**— y crece ~170 MB/año al ritmo real: unos **dos años** dentro de los 0,5 GB de Neon.
  El archivo son 1,6 GB en 84.185 ficheros y crece ~2 GB/año: unos **cuatro años** en los 10 GB de
  B2. Cuando se acaben, la salida es pagar o podar, y conviene saberlo desde hoy.
- **El backend y el frontend siguen donde estaban.** Esto mueve la ingesta, que es lo que tenía
  que correr desatendido. Publicar la web es una decisión aparte y de la sección 12.

## Alternativas descartadas

- **Supabase.** Pausa el proyecto a los 7 días sin actividad. Para un cron desatendido eso es el
  fallo mudo de 6.9.6, y encima uno que se arregla a mano.
- **Una VM 24/7 gratuita** (Oracle Always Free, Fly.io, Koyeb). Resuelve un problema que no
  tenemos —servir tráfico— y todas exigen tarjeta, prueba temporal o cuota recortada. Un cron que
  corre 20 minutos al día no necesita una máquina encendida las otras 23.
- **Cloudflare R2 antes que B2.** Mejor producto y sin egress, pero **exige tarjeta para
  activarse**, y la sección 0 bis manda elegir lo que exija menos cosas que conseguir. El código
  no distingue: cambiar de uno a otro son dos variables de entorno.
- **Dejarlo en local con una tarea programada de Windows.** Es lo que yo recomendé primero, por
  plazo: cero coste, cero cuentas y media hora de trabajo. El humano decidió ir directo a la
  solución buena, que además es la que se puede enseñar en la memoria.
- **Correr también el extractor en el runner.** Un `ollama pull` de gigabytes y 133,9 s por norma
  en CPU compartida, para alimentar algo que no gobierna el gate humano. No.
