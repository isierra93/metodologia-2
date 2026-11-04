from datetime import datetime, timezone

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

from app.gestor import GestorSolicitudes, _iso

app = FastAPI(title="Gestion de Solicitudes Academicas")

gestor = GestorSolicitudes()


@app.post("/solicitudes")
def crear(b: dict = Body(default={})):
    x = gestor.crear_solicitud(b.get("nombre"), b.get("apellido"), b.get("legajo"), b.get("email"), b.get("carrera"), b.get("tipo"), b.get("descripcion"), b.get("urgente"))
    if "error" in x:
        if "Ya existe" in x["error"]:
            return JSONResponse(status_code=409, content=x)
        return JSONResponse(status_code=400, content=x)
    return JSONResponse(status_code=201, content=gestor.formatear(x))


@app.get("/solicitudes")
def listar(estado: str = None, tipo: str = None, prioridad: str = None):
    data2 = gestor.get_todas()

    if estado:
        e = -1
        if estado == "PENDIENTE":
            e = 0
        elif estado == "EN_PROCESO":
            e = 1
        elif estado == "RESUELTA":
            e = 2
        elif estado == "RECHAZADA":
            e = 3
        if e == -1:
            return JSONResponse(status_code=400, content={"error": "Estado invalido"})
        data2 = [s for s in data2 if s["estado"] == e]

    if tipo:
        tipos = ["CERTIFICADO", "MESA_EXAMEN", "EQUIVALENCIA", "BAJA_MATERIA", "RECLAMO_NOTA"]
        if tipo not in tipos:
            return JSONResponse(status_code=400, content={"error": "Tipo de solicitud invalido"})
        data2 = [s for s in data2 if s["tipo"] == tipo]

    if prioridad:
        if prioridad != "ALTA" and prioridad != "MEDIA" and prioridad != "BAJA":
            return JSONResponse(status_code=400, content={"error": "Prioridad invalida"})
        data2 = [s for s in data2 if s["prioridad"] == prioridad]

    tmp = []
    for i in range(len(data2)):
        tmp.append(gestor.formatear(data2[i]))
    return tmp


@app.get("/solicitudes/{id}")
def detalle(id: int):
    s = gestor.buscar_por_id(id)
    if not s:
        return JSONResponse(status_code=404, content={"error": "Solicitud no encontrada"})
    return gestor.formatear(s)


# cambia el estado de una solicitud
# no tocar, anda
@app.put("/solicitudes/{id}/estado")
def cambiar_estado(id: int, b: dict = Body(default={})):
    s = gestor.buscar_por_id(id)
    if not s:
        return JSONResponse(status_code=404, content={"error": "Solicitud no encontrada"})

    nuevo = -1
    if b.get("estado") == "PENDIENTE":
        nuevo = 0
    elif b.get("estado") == "EN_PROCESO":
        nuevo = 1
    elif b.get("estado") == "RESUELTA":
        nuevo = 2
    elif b.get("estado") == "RECHAZADA":
        nuevo = 3
    if nuevo == -1:
        return JSONResponse(status_code=400, content={"error": "Estado invalido"})

    flag = False
    if s["estado"] == 0 and (nuevo == 1 or nuevo == 3):
        flag = True
    if s["estado"] == 1 and (nuevo == 2 or nuevo == 3):
        flag = True
    if not flag:
        return JSONResponse(status_code=422, content={"error": "Transicion de estado no permitida"})

    if nuevo == 3:
        if not b.get("motivo") or len(b["motivo"].strip()) < 5:
            return JSONResponse(status_code=400, content={"error": "Para rechazar hay que indicar un motivo"})
        s["motivoRechazo"] = b["motivo"].strip()

    s["estado"] = nuevo
    ahora = _iso(datetime.now(timezone.utc))
    s["historial"].append({"estado": nuevo, "fecha": ahora})
    if nuevo == 2 or nuevo == 3:
        s["fechaCierre"] = ahora
    gestor.guardar()

    print("[MAIL] Para: " + s["email"] + " - Su solicitud #" + str(s["id"]) + " cambio a " + gestor.estado_texto(nuevo))

    return gestor.formatear(s)


@app.put("/solicitudes/{id}/asignar")
def asignar(id: int, b: dict = Body(default={})):
    s = gestor.buscar_por_id(id)
    if not s:
        return JSONResponse(status_code=404, content={"error": "Solicitud no encontrada"})

    r = b.get("responsable")
    em = b.get("emailResponsable")
    if not r or r.strip() == "":
        return JSONResponse(status_code=400, content={"error": "El responsable es obligatorio"})
    if not em or "@" not in em or "." not in em:
        return JSONResponse(status_code=400, content={"error": "Email invalido"})
    if s["estado"] == 2 or s["estado"] == 3:
        return JSONResponse(status_code=422, content={"error": "No se puede asignar una solicitud cerrada"})

    s["responsable"] = r.strip()
    s["emailResponsable"] = em.lower()
    if s["estado"] == 0:
        s["estado"] = 1
        s["historial"].append({"estado": 1, "fecha": _iso(datetime.now(timezone.utc))})
    gestor.guardar()

    return gestor.formatear(s)


@app.get("/reportes/resumen")
def resumen(formato: str = None):
    d = gestor.generar_reporte()
    if formato == "texto":
        return PlainTextResponse(gestor.reporte_texto(d))
    return d
