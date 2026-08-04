# Centinela

Sistema de vigilancia normativa que monitoriza a diario los boletines oficiales y parlamentos
autonómicos españoles (17 CCAA + BOE) para detectar cambios legislativos que afecten a los
derechos del colectivo LGTBI+, con foco especial en las personas trans.

> El Rainbow Map de ILGA-Europe, pero por comunidad autónoma y en tiempo real.

Detecta el retroceso silencioso: no la reforma que sale en prensa, sino la instrucción de
rango bajo publicada un martes de agosto que desmonta un derecho sin titulares.

Práctica final de un máster de Ciberseguridad e IA. El diseño, las reglas de negocio y los
guardarraíles del proyecto viven en [`CLAUDE.md`](./CLAUDE.md) — léelo antes de tocar código.

**Estado:** en desarrollo activo (S0). Ver sección 11 de `CLAUDE.md` para el estado detallado.

## Documentación

- [`docs/adr/`](./docs/adr/) — decisiones de arquitectura.
- [`docs/fuentes.md`](./docs/fuentes.md) — auditoría de las 18 fuentes normativas.
- [`docs/eipd.md`](./docs/eipd.md) — evaluación de impacto en protección de datos.
- [`SECURITY.md`](./SECURITY.md) — política de seguridad.
- [`THREAT-MODEL.md`](./THREAT-MODEL.md) — modelo de amenaza (STRIDE).

## Arranque rápido

```bash
docker compose up --build
```

Ver [`CLAUDE.md`](./CLAUDE.md) sección 10 para el resto de comandos.
