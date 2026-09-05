# Despliegue de la ingesta desatendida

> Cómo se pasa de «la vigilancia funciona los días que enciendo el portátil» a «la vigilancia
> funciona». El porqué de cada pieza está en el [ADR 0032](adr/0032-la-ingesta-deja-de-depender-del-portatil.md);
> esto es el procedimiento.
>
> **El código ya está hecho y probado. Lo que queda son tres cuentas gratuitas que solo puede
> crear una persona**, porque hacen falta un correo y un usuario. Ninguna pide tarjeta.

| pieza | dónde | plan gratuito |
|---|---|---|
| cómputo | GitHub Actions (`.github/workflows/ingesta.yml`) | ilimitado en repositorios públicos |
| base de datos | [Neon](https://neon.tech) | 0,5 GB — hoy ocupamos 143 MB, ~2 años de margen |
| archivo (6.5) | [Backblaze B2](https://www.backblaze.com/cloud-storage) | 10 GB — hoy 1,6 GB, ~4 años |

Nada de esto toca el backend ni el frontend, que siguen levantándose con `docker compose up`
cuando haga falta mirar el panel. Lo que se mueve es **la ingesta diaria**.

---

## 1. La base de datos en Neon

1. Crear cuenta y un proyecto **PostgreSQL 16 o 17**, región europea (Frankfurt).
2. Copiar la cadena de conexión que da el panel. Vendrá así:

   ```
   postgresql://usuario:clave@ep-algo-123456.eu-central-1.aws.neon.tech/farocuir?sslmode=require
   ```

3. **Ojo con el driver, que es el error que cuesta media hora.** `psql` y `pg_restore` quieren esa
   cadena tal cual; `DATABASE_URL` de este proyecto quiere el prefijo del driver:

   ```
   postgresql+psycopg://usuario:clave@ep-algo-123456.eu-central-1.aws.neon.tech/farocuir?sslmode=require
   ```

3 bis. **Y usa la conexión DIRECTA, no la del pooler. Esto no es una precaución, pasó.**

   Neon ofrece por defecto la cadena con `-pooler` en el host. Es pgbouncer en **modo
   transacción**, o sea que **reutiliza conexiones de servidor entre clientes**, y `pg_restore`
   ejecuta al empezar un `set_config('search_path', '', false)` que es de **sesión**. El ajuste
   se queda pegado a esa conexión reutilizada, así que después de restaurar, cualquier cliente
   que caiga en ese backend ve el `search_path` vacío y **todas las consultas sin esquema
   fallan**:

   ```
   psycopg.errors.UndefinedTable: relation "fuente" does not exist
   ```

   Con las diez tablas ahí, en `public`, perfectamente restauradas. Un `ALTER DATABASE farocuir
   SET search_path TO "$user", public` **no basta**: se graba, pero solo se aplica a conexiones
   nuevas y el pooler te sigue dando la vieja.

   La directa es el mismo host **sin el `-pooler`**, y comprobado sobre este proyecto arregla las
   dos cosas a la vez (`search_path` correcto y las tablas visibles). Para un cron de veinte
   minutos al día el pooler no aporta nada y sí trae esto.

   **La cadena del secreto `DATABASE_URL` de GitHub también va sin `-pooler`.**

4. Volcar lo que hay y restaurarlo. **En la base vacía, sin pasar antes `alembic`**: el volcado
   trae el esquema y la tabla `alembic_version` con la revisión correcta.

   ```bash
   docker compose exec -T db sh -c 'pg_dump -U farocuir -d farocuir -Fc' > farocuir.dump
   pg_restore --no-owner --no-privileges -d "<CADENA SIN +psycopg>" farocuir.dump
   ```

5. Comprobar que llegó entero, con la consulta de la sección 10 de `CLAUDE.md`. **Tienen que
   seguir vivas las 14 CHECK**: son las que impiden, entre otras cosas, que una clasificación
   entre con un origen que no sea `derivado_diff` o `heuristica`.

   ```bash
   psql "<CADENA>" -c "SELECT count(*) FROM norma"
   psql "<CADENA>" -c "SELECT conrelid::regclass, conname FROM pg_constraint
                       WHERE contype='c' AND conrelid <> 0 ORDER BY 1,2"
   ```

6. `alembic upgrade head` contra Neon tiene que decir que no hay nada que hacer. Si propone
   migraciones, el volcado no llegó completo: parar y mirar, no aplicarlas encima.

## 2. El archivo en Backblaze B2

1. Crear cuenta. **No pide tarjeta** (Cloudflare R2 sí, y por eso no es la primera opción).
2. Crear un bucket **privado**. El archivo no se sirve al público desde ahí: quien quiera un
   documento lo pide a la API, que es donde vive el control de acceso.
3. Crear una **clave de aplicación acotada a ese bucket**, nunca la clave maestra de la cuenta.
   Da tres cosas: `keyID`, `applicationKey` y el endpoint S3 (`s3.eu-central-003.backblazeb2.com`
   o el que toque a tu región).
4. Rellenar en el `.env` local las cuatro variables `ALMACEN_S3_*` (ver `.env.example`).

## 3. Subir el archivo, verificándolo de paso

**Primero sin salir a la red.** Recorre los 84.185 ficheros y comprueba que cada uno sigue
casando con el sha256 que lleva por nombre — que es exactamente la propiedad que la sección 6.5
promete:

```bash
docker compose exec -T worker python -m scripts.migrar_almacen --solo-verificar
```

Si sale algún fichero que no casa, **parar y mirarlo**: no se sube, porque copiar a la nube un
archivo que ya no prueba lo que dice es peor que no copiarlo.

Y después la subida, que es reanudable —pregunta qué hay ya en el bucket y se salta esas claves—
e idempotente, porque la clave *es* el hash del contenido:

```bash
docker compose exec -T worker python -m scripts.migrar_almacen
```

1,6 GB por una línea doméstica es de una a varias horas. Si se corta, se relanza y sigue.

## 3 bis. El cambio: mover las credenciales a `.env` **y reconstruir la imagen**

Cuando la copia esté completa y comprobada, las cuatro `ALMACEN_S3_*` pasan a `.env`. Eso es el
cambio, y es instantáneo: a partir de ahí el archivo se lee del bucket y `ALMACEN_ROOT` deja de
usarse. **El disco local se queda intacto**, que es la vuelta atrás si hiciera falta.

Y acto seguido, esto, que costó un susto:

```bash
docker compose build backend worker && docker compose up -d --force-recreate backend worker
```

**`boto3` es una dependencia nueva y las imágenes no se reconstruyen solas.** El `docker compose
up` recrea el contenedor con la imagen que ya había, así que el código nuevo entra por el volumen
pero la dependencia que necesita, no. El síntoma es un `ModuleNotFoundError: No module named
'boto3'` en mitad de una ingesta, no al arrancar — y en la misma imagen vieja faltaba también
`pypdf`, o sea que la recuperación por PDF (ADR 0026) llevaba quién sabe cuánto sin poder correr
en local.

Comprobación de que el cambio funcionó, que es leer del bucket de verdad y no fiarse:

```bash
docker compose exec -T worker python -c "
from sqlalchemy import select
from app.config import get_settings
from app.database import SessionLocal
from app.models.norma import Norma
from app.services import almacen_remoto, cuerpo
print('remoto:', almacen_remoto.configurado())
with SessionLocal() as s:
    n = s.scalars(select(Norma).where(Norma.documento_texto_id.is_not(None)).limit(1)).one()
    print(n.identificador_oficial, len(cuerpo.leer_cuerpo(n, almacen_root=get_settings().almacen_root).texto))
"
```

## 4. Los secretos en GitHub

`Settings → Secrets and variables → Actions → New repository secret`, cinco:

| secreto | valor |
|---|---|
| `DATABASE_URL` | la cadena de Neon **con `+psycopg`** |
| `ALMACEN_S3_BUCKET` | el nombre del bucket |
| `ALMACEN_S3_ENDPOINT` | `https://s3.<region>.backblazeb2.com` |
| `ALMACEN_S3_ACCESS_KEY` | el `keyID` |
| `ALMACEN_S3_SECRET_KEY` | el `applicationKey` |

**Y ninguno más.** No van ni `SUSCRIPTOR_PEPPER` ni `PANEL_PASSWORD_HASH`: el worker no los usa,
y los logs de las Actions de un repositorio público los lee cualquiera. Un secreto que no está en
la nube no puede filtrarse desde la nube.

## 5. Estrenarlo

`Actions → Ingesta diaria → Run workflow`, dejando la fecha vacía. Tarda ~20 minutos. Qué mirar:

- Los cuatro pasos de fuente en verde (un día sin boletín también sale en verde y lo dice en el
  log: no es un fallo).
- Que el paso «Catálogo de reglas» diga cuántas evaluó. Ese es el que llena la cola del gate
  humano, y el que hace que la ausencia del LLM no cueste vigilancia.
- Que en el bucket hayan aparecido objetos nuevos.

A partir de ahí corre solo a las 06:30 UTC.

---

## Lo que sigue siendo trabajo de la máquina de casa

No es provisional: es donde tiene sentido que estén.

- **El extractor.** El workflow va con `--sin-extraccion` porque Ollama corre en local (ADR 0008)
  y en un runner no hay ninguno. La cola se drena con `python -m worker.run --extraer` cuando
  apetezca, y lo que se queda fuera no se pierde: la cola es una consulta.
- **Los reprocesados masivos.** `--reprefiltrar` sobre ~82.000 normas lee el cuerpo de cada una;
  contra el bucket serían 82.000 descargas, por encima del tope diario del plan gratuito y del
  límite de 6 h de un job. Subir `VERSION_VOCABULARIO` o `VERSION_WATCHLIST` se hace en local
  contra el archivo en disco.
- **El panel de revisión.** El gate humano es humano (regla de oro 4): se abre cuando hay alguien
  para revisar.

## El canario, porque un cron mudo es peor que ninguno

**GitHub desactiva un workflow programado tras 60 días sin actividad en el repositorio**, y solo
avisa por correo. Un correo no es un canario (6.9.6). El canario es el que ya existía: la web
publica `ultima_publicacion` por fuente, así que una fuente que lleva días sin nada **se ve en la
página de cobertura** sin que nadie tenga que acordarse de comprobarlo. Reactivarlo es lanzar el
`Run workflow` de arriba.


---

# Parte 2 · La web y la API en la nube (ADR 0033)

> La parte 1 saco la ingesta, la base y el archivo del portatil. Esto saca **lo que tiene
> publico**: el backend de FastAPI y la web.
>
> **Nada de esto se despliega sin que lo digas tu** (seccion 12). Aqui esta todo preparado.

| pieza | donde | plan | tarjeta |
|---|---|---|---|
| API | [Render](https://render.com), region **Frankfurt** | Free | **no** |
| Web | [Netlify](https://netlify.com) | Free | **no** |

## 0. Antes de nada: las tipografias

`frontend/index.html` carga las fuentes desde **Google Fonts**, o sea que el navegador de cada
visitante manda su IP a Google en cada carga. La seccion 6.4 dice que **no se registran IPs de
quien consulta la web**, y la EIPD se articula sobre eso.

**Esto se arregla antes de publicar**, alojando las tres familias nosotros. Mientras no se haga,
la CSP de `netlify.toml` tiene que nombrar a `fonts.googleapis.com` y `fonts.gstatic.com` — y ahi
esta, a la vista en el diff, que es donde tiene que estar una excepcion.

## 1. La API en Render

1. Crear cuenta (no pide tarjeta) y **no anadir metodo de pago**. Sin el, el modo de fallo es la
   suspension, no el cargo: es lo que protege la restriccion de 0 EUR.
2. **New -> Blueprint**, apuntando a este repositorio. Render lee `render.yaml` y crea el
   servicio con su region, su etapa de Docker y su comprobacion de salud ya puestas.
3. Rellenar a mano los **siete secretos** que el fichero declara con `sync: false`:

   | variable | de donde sale |
   |---|---|
   | `DATABASE_URL` | Neon, **sin `-pooler`** y **con `+psycopg`** (paso 3 bis de la parte 1) |
   | `ALMACEN_S3_BUCKET` / `_ENDPOINT` / `_ACCESS_KEY` / `_SECRET_KEY` | los mismos cuatro de B2 |
   | `SUSCRIPTOR_PEPPER` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `PANEL_PASSWORD_HASH` | `docker compose exec backend python -m scripts.generar_hash_panel` |

   Los dos ultimos **fallan cerrado** si faltan, y es lo correcto: sin pepper no se guarda ningun
   alta, y sin hash el panel no abre. El resto de la API sigue funcionando.
4. Anotar el host que da Render (`farocuir-api.onrender.com` o el que sea) y **ponerlo en
   `netlify.toml`**, en el `to` del proxy. Mientras no coincida, la web parecera rota sin decir
   por que.
5. Comprobar: `curl https://<host>/health` y `curl https://<host>/api/cobertura`.

## 2. La web en Netlify

1. Crear cuenta y **Add new site -> Import an existing project**, apuntando al repositorio.
   Netlify lee `netlify.toml`: no hay que teclear ni el comando de compilacion ni el directorio.
2. Desplegar y comprobar **tres cosas, en este orden**:
   - Que la pagina carga **con estilos**. Si se viera sin ellos, es la CSP: mirar la consola del
     navegador y arreglar la politica, **no aflojarla a `'unsafe-inline'` sin leer el error**.
   - Que `/api/cobertura` responde **desde el dominio de Netlify**. Eso prueba que el proxy
     funciona y que seguimos en el mismo origen.
   - Que el panel de revision abre y acepta la contrasena.
3. Pasar las cabeceras por un comprobador (securityheaders.com o `curl -I`): HSTS,
   `X-Content-Type-Options`, `Referrer-Policy` y la CSP.

## 3. Lo que hay que saber antes de ensenarselo a nadie

- **La API duerme a los 15 minutos sin trafico y tarda ~1 minuto en despertar.** La primera
  visita despues de un rato se queda esperando. No esta roto.
- **Las sesiones del panel mueren en cada suspension**: quien revise tendra que autenticarse casi
  cada vez.
- **La cadencia de intentos del panel tambien se reinicia al despertar.** Es el mismo «falla
  abierto» en version temporal, y **va al THREAT-MODEL** como riesgo residual.
- **La EIPD dice lo que se puede sostener, ni mas ni menos**: el sistema no registra IPs
  —uvicorn con `--no-access-log`— y lo que registre el proveedor no esta en nuestra mano. Netlify
  y Render las procesan en su borde y ninguno lo desactiva en un plan gratuito, asi que van
  nombrados como **encargados del tratamiento**.

  **Esto que se despliega es la muestra.** Si alguna vez una asociacion LGTBI+ lo usara de
  verdad, lo alojaria en su propia infraestructura y ese control seria de su IT — que es ademas
  la respuesta correcta para un sistema cuyos usuarios son dato de categoria especial. Nosotros
  nos encargamos de la muestra, aun en produccion.
