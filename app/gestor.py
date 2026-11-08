import json
import os
from datetime import datetime, timedelta, timezone
from app.prioridades import CalculadoraPrioridad
from app.domain import DatosAlumno, Solicitud, _iso

ARCHIVO = os.environ.get("DATA_FILE") or os.path.join(os.path.dirname(__file__), "..", "data", "solicitudes.json")

solicitudes = []
ultimo_id = 0


class GestorSolicitudes:
    TIPOS_VALIDOS = ("CERTIFICADO", "MESA_EXAMEN", "EQUIVALENCIA", "BAJA_MATERIA", "RECLAMO_NOTA")

    def __init__(self):
        self.cargar()

    def calcular_ultimo_id(self, lista_solicitudes):
        ultimo = 0
        for solicitud in lista_solicitudes:
            if solicitud["id"] > ultimo:
                ultimo = solicitud["id"]
        return ultimo

    def cargar(self):
        global solicitudes, ultimo_id
        try:
            with open(ARCHIVO, "r", encoding="utf-8") as f:
                d = f.read()
            solicitudes = json.loads(d)
            ultimo_id = self.calcular_ultimo_id(solicitudes)
        except Exception:
            solicitudes = []

    def guardar(self):
        try:
            with open(ARCHIVO, "w", encoding="utf-8") as f:
                f.write(json.dumps(solicitudes, indent=2, ensure_ascii=False))
        except:
            pass

    def get_todas(self):
        return solicitudes

    def buscar_por_id(self, id):
        for solicitud in solicitudes:
            if solicitud["id"] == id:
                return solicitud
        return None

    # Soporta Parameter Object DatosAlumno o argumentos posicionales
    def crear_solicitud(self, nombre, apellido=None, legajo=None, email=None, carrera=None, tipo=None, descripcion=None, urgente=False):
        global ultimo_id

        if isinstance(nombre, DatosAlumno):
            alumno = nombre
        else:
            alumno = DatosAlumno(
                nombre=nombre.strip() if nombre else "",
                apellido=apellido.strip() if apellido else "",
                legajo=str(legajo) if legajo else "",
                email=email.lower().strip() if email else "",
                carrera=carrera.strip() if carrera else ""
            )

        error_alumno = alumno.validar()
        if error_alumno:
            return {"error": error_alumno}

        if tipo not in self.TIPOS_VALIDOS:
            return {"error": "Tipo de solicitud invalido"}
        if not descripcion or len(descripcion.strip()) < 10:
            return {"error": "La descripcion debe tener al menos 10 caracteres"}

        for s in solicitudes:
            if s["legajo"] == str(alumno.legajo) and s["tipo"] == tipo and (s["estado"] == 0 or s["estado"] == 1):
                return {"error": "Ya existe una solicitud abierta de ese tipo para el alumno"}

        calculadora = CalculadoraPrioridad()
        p = calculadora.calcular(tipo, urgente)

        plazos = {
            "CERTIFICADO": 3,
            "MESA_EXAMEN": 2,
            "EQUIVALENCIA": 15,
            "BAJA_MATERIA": 7,
            "RECLAMO_NOTA": 5
        }
        dias = plazos.get(tipo, 5)
        if p == "ALTA" and dias > 5:
            dias = 5

        responsables = {
            "CERTIFICADO": "Bedelia",
            "MESA_EXAMEN": "Bedelia",
            "BAJA_MATERIA": "Bedelia",
            "EQUIVALENCIA": "Secretaria Academica",
            "RECLAMO_NOTA": "Coordinacion de Carrera"
        }
        r = responsables.get(tipo, "Bedelia")

        hoy = datetime.now(timezone.utc)
        venc = hoy + timedelta(seconds=dias * 24 * 60 * 60)

        ultimo_id += 1
        x = {
            "id": ultimo_id,
            "nombre": alumno.nombre,
            "apellido": alumno.apellido,
            "legajo": alumno.legajo,
            "email": alumno.email,
            "carrera": alumno.carrera,
            "tipo": tipo,
            "descripcion": descripcion.strip(),
            "prioridad": p,
            "estado": 0,
            "responsable": r,
            "emailResponsable": None,
            "fechaCreacion": _iso(hoy),
            "fechaVencimiento": _iso(venc),
            "historial": [{"estado": 0, "fecha": _iso(hoy)}],
        }
        solicitudes.append(x)
        self.guardar()

        print("[MAIL] Para: " + x["email"] + " - Su solicitud #" + str(x["id"]) + " fue registrada")
        return x

    def estado_texto(self, e):
        return Solicitud.ESTADOS.get(e, "DESCONOCIDO")

    def formatear(self, s):
        sol_entidad = Solicitud(s)
        o = {
            "id": s["id"],
            "alumno": {
                "nombre": s["nombre"],
                "apellido": s["apellido"],
                "legajo": s["legajo"],
                "email": s["email"],
                "carrera": s["carrera"],
            },
            "tipo": s["tipo"],
            "descripcion": s["descripcion"],
            "prioridad": s["prioridad"],
            "estado": self.estado_texto(s["estado"]),
            "responsable": s["responsable"],
            "emailResponsable": s.get("emailResponsable") or None,
            "fechaCreacion": s["fechaCreacion"],
            "fechaVencimiento": s["fechaVencimiento"],
            "vencida": sol_entidad.esta_vencida(),
            "historial": [{"estado": self.estado_texto(h["estado"]), "fecha": h["fecha"]} for h in s["historial"]],
        }
        if s.get("motivoRechazo"):
            o["motivoRechazo"] = s["motivoRechazo"]
        if s.get("fechaCierre"):
            o["fechaCierre"] = s["fechaCierre"]
        return o

    def generar_reporte(self):
        d = {
            "total": len(solicitudes),
            "porEstado": {"PENDIENTE": 0, "EN_PROCESO": 0, "RESUELTA": 0, "RECHAZADA": 0},
            "porTipo": {"CERTIFICADO": 0, "MESA_EXAMEN": 0, "EQUIVALENCIA": 0, "BAJA_MATERIA": 0, "RECLAMO_NOTA": 0},
            "porPrioridad": {"ALTA": 0, "MEDIA": 0, "BAJA": 0},
            "vencidas": 0,
            "generado": _iso(datetime.now(timezone.utc)),
        }
        ahora = datetime.now(timezone.utc)
        for s in solicitudes:
            d["porEstado"][self.estado_texto(s["estado"])] += 1
            d["porTipo"][s["tipo"]] += 1
            d["porPrioridad"][s["prioridad"]] += 1
            sol_entidad = Solicitud(s)
            if sol_entidad.esta_vencida(ahora):
                d["vencidas"] += 1
        return d

    def reporte_texto(self, d):
        t = ""
        t += "=== REPORTE DE SOLICITUDES ===\n"
        t += "Generado: " + d["generado"] + "\n"
        t += "Total de solicitudes: " + str(d["total"]) + "\n"
        t += "\n-- Por estado --\n"
        for k in d["porEstado"]:
            t += k + ": " + str(d["porEstado"][k]) + "\n"
        t += "\n-- Por tipo --\n"
        for k in d["porTipo"]:
            t += k + ": " + str(d["porTipo"][k]) + "\n"
        t += "\n-- Por prioridad --\n"
        for k in d["porPrioridad"]:
            t += k + ": " + str(d["porPrioridad"][k]) + "\n"
        t += "\nVencidas: " + str(d["vencidas"]) + "\n"
        return t