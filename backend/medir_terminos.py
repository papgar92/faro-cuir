"""Mide terminos candidatos sobre el corpus YA ARCHIVADO. Ni una peticion de red.

Pregunta que responde: si añadimos estos terminos, cuantas normas ENTRARIAN que hoy no entran,
y cuanto ruido traerian. Se mide sobre una muestra aleatoria de DESCARTADAS, que es donde vive
la respuesta: lo que ya entra no cambia.
"""
import random, sys
from pathlib import Path
from sqlalchemy import select
from app.database import SessionLocal
from app.config import get_settings
from app.models.norma import EstadoPrefiltro, Norma
from app.pipeline.prefiltro import _normalizar, _contiene, _VOCABULARIO as VOCABULARIO, Categoria
from app.services.cuerpo import leer_cuerpo, CuerpoIlegible

CANDIDATOS = {
    "gays": "M-4/4.1 plural que usan los titulos de las propias leyes vigiladas",
    "gay": "4.1 singular; OJO al falso positivo 'ley de Gay-Lussac'",
    "sexo registral": "M-4 criterio de acceso por registro",
    "sexo al nacer": "M-4",
    "sexo asignado al nacer": "M-4",
    "sexo de nacimiento": "M-4",
    "mencion registral relativa al sexo": "M-4 forma literal de la Ley 3/2007",
    "mismo sexo": "4.1 formula del Codigo Civil y la Ley 13/2005",
    "doble maternidad": "4.1 filiacion de familias lesbianas",
    "cisgenero": "4.1",
    "mujeres trans": "4.1",
    "hombres trans": "4.1",
}
DIRECTOS = {t for t, c in VOCABULARIO.items() if c is Categoria.DIRECTO}

n_muestra = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
s = get_settings(); root = Path(s.almacen_root); ses = SessionLocal()
ids = [r[0] for r in ses.execute(
    select(Norma.id).where(Norma.prefiltro_estado == EstadoPrefiltro.DESCARTADA,
                           Norma.documento_texto_id.is_not(None))).all()]
random.seed(42); muestra = random.sample(ids, min(n_muestra, len(ids)))
print(f"universo descartadas: {len(ids):,} | muestra: {len(muestra):,}")

hits = {t: 0 for t in CANDIDATOS}
rescatarian = {t: 0 for t in CANDIDATOS}
leidas = 0
for nid in muestra:
    norma = ses.get(Norma, nid)
    try:
        cuerpo = leer_cuerpo(norma, almacen_root=root)
    except CuerpoIlegible:
        continue
    if cuerpo is None:
        continue
    leidas += 1
    texto = _normalizar(cuerpo.texto)
    ya_tiene_directo = any(_contiene(texto, t) for t in DIRECTOS)
    for cand in CANDIDATOS:
        if _contiene(texto, _normalizar(cand)):
            hits[cand] += 1
            if not ya_tiene_directo:
                rescatarian[cand] += 1

print(f"leidas de verdad: {leidas:,}\n")
print(f"{'termino':38} {'apariciones':>11} {'RESCATARIA':>11}  nota")
for t, nota in CANDIDATOS.items():
    print(f"{t:38} {hits[t]:>11} {rescatarian[t]:>11}  {nota}")
