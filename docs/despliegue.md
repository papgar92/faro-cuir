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
