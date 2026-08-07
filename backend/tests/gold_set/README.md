# Gold set

Casos históricos etiquetados a mano para medir el pipeline con datos reales (CLAUDE.md
sección 7). El objetivo final son 150-200 casos; hoy hay 3, de arranque, para dejar montado
el mecanismo — el etiquetado en volumen lo hace el humano, por tandas.

## Cómo añadir un caso

Un fichero JSON por caso en `casos/`, con este formato (ver `esquema.py` para el detalle):

```json
{
  "identificador_oficial": "BOE-A-2023-5366",
  "fuente": "boe",
  "fecha_publicacion": "2023-03-01",
  "titulo": "Título literal tal y como lo publica la fuente",
  "organo_emisor": "Quién lo emite, si se conoce",
  "es_relevante": true,
  "clasificacion_esperada": null,
  "notas": "Por qué este caso importa: positivo conocido, negativo difícil, caso citado en el TFM..."
}
```

- `es_relevante`: si el prefiltro léxico (etapa 1) debería marcarlo como relevante. Es lo
  único que se puede evaluar hoy — el clasificador por diff (etapa 3) todavía no existe.
- `clasificacion_esperada`: `avance` | `retroceso` | `neutro` | `indeterminado`, o `null`.
  Se deja en `null` hasta que exista el clasificador; no adivinar qué diría (regla de oro 8).
- `notas`: obligatorio. Sin él, nadie sabe dentro de seis meses por qué se eligió ese caso.

Casos que interesan especialmente, según el propio plan del proyecto: la reforma madrileña de
2023, reformas rechazadas, y negativos difíciles (títulos de temática cercana pero fuera de
alcance — sanidad reproductiva no LGTBI+, igualdad de género no trans, etc.), no solo
negativos triviales.

## Qué prueba hoy `test_gold_set_prefiltro.py`

Solo el prefiltro léxico (etapa 1), contra el título — no requiere red ni base de datos.
Cuando exista el clasificador por diff, un test aparte comprobará `clasificacion_esperada`
contra los casos que ya lo tengan relleno.
