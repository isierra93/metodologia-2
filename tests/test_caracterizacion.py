# Tests de caracterizacion: fijan el comportamiento EXTERNO de la API (v1).
# Tienen que seguir pasando sin cambios despues de cada refactoring.
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DIA_SEGUNDOS = 24 * 60 * 60
FIXTURE = Path(__file__).parent / "fixtures" / "solicitudes.json"

SOLICITUD_VALIDA = {
    "nombre": "Julian",
    "apellido": "Castro",
    "legajo": "112233",
    "email": "Julian.Castro@alumnos.example.edu",
    "carrera": "Ingenieria en Sistemas",
    "tipo": "CERTIFICADO",
    "descripcion": "Certificado de alumno regular para la obra social",
}


@pytest.fixture(scope="module")
def archivo_datos(tmp_path_factory):
    # cada corrida usa una copia limpia de los datos de prueba
    destino = tmp_path_factory.mktemp("datos") / "solicitudes.json"
    shutil.copy(FIXTURE, destino)
    return destino


@pytest.fixture(scope="module")
def cliente(archivo_datos):
    os.environ["DATA_FILE"] = str(archivo_datos)
    from app.main import app

    return TestClient(app)


def ids(lista):
    return sorted(s["id"] for s in lista)


def plazo_en_dias(solicitud):
    creacion = datetime.fromisoformat(solicitud["fechaCreacion"])
    vencimiento = datetime.fromisoformat(solicitud["fechaVencimiento"])
    return (vencimiento - creacion).total_seconds() / DIA_SEGUNDOS


# --- Reportes (antes de modificar datos) ---


def test_reporte_resumen_json(cliente):
    respuesta = cliente.get("/reportes/resumen")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["total"] == 9
    assert cuerpo["porEstado"] == {"PENDIENTE": 4, "EN_PROCESO": 2, "RESUELTA": 2, "RECHAZADA": 1}
    assert cuerpo["porTipo"] == {"CERTIFICADO": 2, "MESA_EXAMEN": 2, "EQUIVALENCIA": 2, "BAJA_MATERIA": 1, "RECLAMO_NOTA": 2}
    assert cuerpo["porPrioridad"] == {"ALTA": 4, "MEDIA": 3, "BAJA": 2}
    assert cuerpo["vencidas"] == 6
    datetime.fromisoformat(cuerpo["generado"])


def test_reporte_resumen_texto(cliente):
    respuesta = cliente.get("/reportes/resumen?formato=texto")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/plain")
    texto = respuesta.text
    assert "=== REPORTE DE SOLICITUDES ===" in texto
    assert "Total de solicitudes: 9" in texto
    assert "PENDIENTE: 4" in texto
    assert "RECLAMO_NOTA: 2" in texto
    assert "Vencidas: 6" in texto


# --- Consultas ---


def test_listar_todas_con_formato_de_salida(cliente):
    respuesta = cliente.get("/solicitudes")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert ids(cuerpo) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    primera = next(s for s in cuerpo if s["id"] == 1)
    assert primera["alumno"] == {
        "nombre": "Lucia",
        "apellido": "Fernandez",
        "legajo": "104523",
        "email": "lucia.fernandez@alumnos.example.edu",
        "carrera": "Ingenieria en Sistemas",
    }
    assert primera["estado"] == "PENDIENTE"
    assert primera["vencida"] is True
    assert primera["historial"] == [{"estado": "PENDIENTE", "fecha": "2026-03-02T13:00:00.000Z"}]


def test_filtros(cliente):
    assert ids(cliente.get("/solicitudes?estado=PENDIENTE").json()) == [1, 5, 8, 9]
    assert ids(cliente.get("/solicitudes?estado=RECHAZADA").json()) == [4]
    assert ids(cliente.get("/solicitudes?tipo=MESA_EXAMEN").json()) == [2, 9]
    assert ids(cliente.get("/solicitudes?prioridad=BAJA").json()) == [1, 6]
    assert ids(cliente.get("/solicitudes?estado=PENDIENTE&tipo=EQUIVALENCIA").json()) == [8]


def test_filtros_invalidos_devuelven_400(cliente):
    por_estado = cliente.get("/solicitudes?estado=CERRADA")
    assert por_estado.status_code == 400
    assert por_estado.json() == {"error": "Estado invalido"}

    por_tipo = cliente.get("/solicitudes?tipo=OTRO")
    assert por_tipo.status_code == 400
    assert por_tipo.json() == {"error": "Tipo de solicitud invalido"}

    por_prioridad = cliente.get("/solicitudes?prioridad=URGENTE")
    assert por_prioridad.status_code == 400
    assert por_prioridad.json() == {"error": "Prioridad invalida"}


def test_consultar_por_id(cliente):
    resuelta = cliente.get("/solicitudes/3")
    assert resuelta.status_code == 200
    assert resuelta.json()["estado"] == "RESUELTA"
    assert resuelta.json()["vencida"] is False
    assert resuelta.json()["fechaCierre"] == "2026-02-27T16:20:00.000Z"

    rechazada = cliente.get("/solicitudes/4")
    assert rechazada.json()["motivoRechazo"] == "Presentado fuera de termino"

    inexistente = cliente.get("/solicitudes/999")
    assert inexistente.status_code == 404
    assert inexistente.json() == {"error": "Solicitud no encontrada"}


# --- Alta ---


def test_alta_valida(cliente, archivo_datos):
    respuesta = cliente.post("/solicitudes", json=SOLICITUD_VALIDA)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["id"] == 10
    assert cuerpo["alumno"]["email"] == "julian.castro@alumnos.example.edu"
    assert cuerpo["prioridad"] == "BAJA"
    assert cuerpo["responsable"] == "Bedelia"
    assert cuerpo["estado"] == "PENDIENTE"
    assert cuerpo["vencida"] is False
    assert cuerpo["emailResponsable"] is None
    assert plazo_en_dias(cuerpo) == 3
    assert len(cuerpo["historial"]) == 1

    # queda persistida en el archivo
    guardadas = json.loads(archivo_datos.read_text(encoding="utf-8"))
    assert any(s["id"] == 10 for s in guardadas)


def test_plazos_prioridades_y_responsables_por_tipo(cliente):
    casos = [
        ("MESA_EXAMEN", "ALTA", 2, "Bedelia"),
        ("EQUIVALENCIA", "MEDIA", 15, "Secretaria Academica"),
        ("BAJA_MATERIA", "MEDIA", 7, "Bedelia"),
        ("RECLAMO_NOTA", "ALTA", 5, "Coordinacion de Carrera"),
    ]
    legajo = 120000
    for tipo, prioridad, dias, responsable in casos:
        legajo += 1
        respuesta = cliente.post("/solicitudes", json={**SOLICITUD_VALIDA, "legajo": str(legajo), "tipo": tipo})
        assert respuesta.status_code == 201, tipo
        cuerpo = respuesta.json()
        assert cuerpo["prioridad"] == prioridad, tipo
        assert cuerpo["responsable"] == responsable, tipo
        assert plazo_en_dias(cuerpo) == dias, tipo

    # urgente: pasa a ALTA y el plazo se acota a 5 dias
    for urgente in [True, "true", "URG"]:
        legajo += 1
        cuerpo = cliente.post(
            "/solicitudes", json={**SOLICITUD_VALIDA, "legajo": str(legajo), "tipo": "EQUIVALENCIA", "urgente": urgente}
        ).json()
        assert cuerpo["prioridad"] == "ALTA"
        assert plazo_en_dias(cuerpo) == 5


@pytest.mark.parametrize(
    "cambio, mensaje",
    [
        ({"nombre": ""}, "El nombre es obligatorio"),
        ({"apellido": "  "}, "El apellido es obligatorio"),
        ({"legajo": "abc"}, "Legajo invalido"),
        ({"legajo": "12"}, "Legajo invalido"),
        ({"email": "sin-arroba.com"}, "Email invalido"),
        ({"carrera": ""}, "La carrera es obligatoria"),
        ({"tipo": "OTRO"}, "Tipo de solicitud invalido"),
        ({"descripcion": "corta"}, "La descripcion debe tener al menos 10 caracteres"),
    ],
)
def test_alta_invalida_devuelve_400(cliente, cambio, mensaje):
    respuesta = cliente.post("/solicitudes", json={**SOLICITUD_VALIDA, "legajo": "130000", **cambio})
    assert respuesta.status_code == 400
    assert respuesta.json() == {"error": mensaje}


def test_no_se_permiten_dos_abiertas_del_mismo_tipo(cliente):
    duplicada = cliente.post("/solicitudes", json={**SOLICITUD_VALIDA, "legajo": "104523", "tipo": "CERTIFICADO"})
    assert duplicada.status_code == 409
    assert duplicada.json() == {"error": "Ya existe una solicitud abierta de ese tipo para el alumno"}

    # si la anterior esta cerrada, si se permite (id 6 RESUELTA)
    permitida = cliente.post("/solicitudes", json={**SOLICITUD_VALIDA, "legajo": "99120", "tipo": "CERTIFICADO"})
    assert permitida.status_code == 201


# --- Cambios de estado ---


def test_transiciones_de_estado(cliente):
    en_proceso = cliente.put("/solicitudes/5/estado", json={"estado": "EN_PROCESO"})
    assert en_proceso.status_code == 200
    assert en_proceso.json()["estado"] == "EN_PROCESO"
    assert [h["estado"] for h in en_proceso.json()["historial"]] == ["PENDIENTE", "EN_PROCESO"]

    resuelta = cliente.put("/solicitudes/5/estado", json={"estado": "RESUELTA"})
    assert resuelta.status_code == 200
    assert resuelta.json()["estado"] == "RESUELTA"
    assert resuelta.json()["fechaCierre"]
    assert resuelta.json()["vencida"] is False

    vuelta = cliente.put("/solicitudes/5/estado", json={"estado": "PENDIENTE"})
    assert vuelta.status_code == 422
    assert vuelta.json() == {"error": "Transicion de estado no permitida"}

    salto = cliente.put("/solicitudes/1/estado", json={"estado": "RESUELTA"})
    assert salto.status_code == 422

    invalido = cliente.put("/solicitudes/1/estado", json={"estado": "ARCHIVADA"})
    assert invalido.status_code == 400
    assert invalido.json() == {"error": "Estado invalido"}

    inexistente = cliente.put("/solicitudes/999/estado", json={"estado": "EN_PROCESO"})
    assert inexistente.status_code == 404


def test_rechazar_exige_motivo(cliente):
    sin_motivo = cliente.put("/solicitudes/8/estado", json={"estado": "RECHAZADA"})
    assert sin_motivo.status_code == 400
    assert sin_motivo.json() == {"error": "Para rechazar hay que indicar un motivo"}

    con_motivo = cliente.put("/solicitudes/8/estado", json={"estado": "RECHAZADA", "motivo": "Documentacion incompleta"})
    assert con_motivo.status_code == 200
    assert con_motivo.json()["estado"] == "RECHAZADA"
    assert con_motivo.json()["motivoRechazo"] == "Documentacion incompleta"
    assert con_motivo.json()["fechaCierre"]


# --- Asignacion ---


def test_asignar_responsable(cliente):
    asignada = cliente.put("/solicitudes/9/asignar", json={"responsable": "Laura Perez", "emailResponsable": "Laura.Perez@example.edu"})
    assert asignada.status_code == 200
    assert asignada.json()["responsable"] == "Laura Perez"
    assert asignada.json()["emailResponsable"] == "laura.perez@example.edu"
    assert asignada.json()["estado"] == "EN_PROCESO"

    # si ya estaba en proceso no agrega historial
    reasignada = cliente.put("/solicitudes/9/asignar", json={"responsable": "Diego Luna", "emailResponsable": "diego.luna@example.edu"})
    assert reasignada.status_code == 200
    assert len(reasignada.json()["historial"]) == 2

    sin_responsable = cliente.put("/solicitudes/9/asignar", json={"emailResponsable": "x@example.edu"})
    assert sin_responsable.status_code == 400
    assert sin_responsable.json() == {"error": "El responsable es obligatorio"}

    email_invalido = cliente.put("/solicitudes/9/asignar", json={"responsable": "Diego", "emailResponsable": "diego"})
    assert email_invalido.status_code == 400
    assert email_invalido.json() == {"error": "Email invalido"}

    cerrada = cliente.put("/solicitudes/3/asignar", json={"responsable": "Diego", "emailResponsable": "diego@example.edu"})
    assert cerrada.status_code == 422
    assert cerrada.json() == {"error": "No se puede asignar una solicitud cerrada"}

    inexistente = cliente.put("/solicitudes/999/asignar", json={"responsable": "Diego", "emailResponsable": "diego@example.edu"})
    assert inexistente.status_code == 404
