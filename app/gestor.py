import json
import os
import re
from datetime import datetime, timedelta, timezone
from app.prioridades import CalculadoraPrioridad
# archivo donde se guardan las solicitudes
ARCHIVO = os.environ.get("DATA_FILE") or os.path.join(os.path.dirname(__file__), "..", "data", "solicitudes.json")

solicitudes = []
ultimo_id = 0


def _iso(f):
    return f.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (f.microsecond // 1000)


class GestorSolicitudes:
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
        for i in range(len(solicitudes)):
            if solicitudes[i]["id"] == id:
                return solicitudes[i]
        return None

    # crea una solicitud nueva, valida todo y la guarda
    def crear_solicitud(self, nombre, apellido, legajo, email, carrera, tipo, descripcion, urgente):
        global ultimo_id

        # validaciones
        if not nombre or nombre.strip() == "":
            return {"error": "El nombre es obligatorio"}
        if not apellido or apellido.strip() == "":
            return {"error": "El apellido es obligatorio"}
        if not legajo or not re.match(r"^\d{5,6}$", str(legajo)):
            return {"error": "Legajo invalido"}
        if not email or "@" not in email or "." not in email:
            return {"error": "Email invalido"}
        if not carrera or carrera.strip() == "":
            return {"error": "La carrera es obligatoria"}
        if tipo != "CERTIFICADO" and tipo != "MESA_EXAMEN" and tipo != "EQUIVALENCIA" and tipo != "BAJA_MATERIA" and tipo != "RECLAMO_NOTA":
            return {"error": "Tipo de solicitud invalido"}
        if not descripcion or len(descripcion.strip()) < 10:
            return {"error": "La descripcion debe tener al menos 10 caracteres"}

        # no puede tener dos abiertas del mismo tipo
        for i in range(len(solicitudes)):
            s = solicitudes[i]
            if s["legajo"] == str(legajo) and s["tipo"] == tipo and (s["estado"] == 0 or s["estado"] == 1):
                return {"error": "Ya existe una solicitud abierta de ese tipo para el alumno"}

                # Calculamos la prioridad con una clase independiente
        calculadora = CalculadoraPrioridad()
        p = calculadora.calcular(tipo, urgente)
        
            
        
            
        
            
        
            
        
            
        
            

        # plazo en dias
        if tipo == "CERTIFICADO":
            dias = 3
        elif tipo == "MESA_EXAMEN":
            dias = 2
        elif tipo == "EQUIVALENCIA":
            dias = 15
        elif tipo == "BAJA_MATERIA":
            dias = 7
        elif tipo == "RECLAMO_NOTA":
            dias = 5
        if p == "ALTA" and dias > 5:
            dias = 5

        # responsable por defecto
        if tipo == "CERTIFICADO" or tipo == "MESA_EXAMEN" or tipo == "BAJA_MATERIA":
            r = "Bedelia"
        elif tipo == "EQUIVALENCIA":
            r = "Secretaria Academica"
        elif tipo == "RECLAMO_NOTA":
            r = "Coordinacion de Carrera"

        hoy = datetime.now(timezone.utc)
        venc = hoy + timedelta(seconds=dias * 24 * 60 * 60)

        ultimo_id += 1
        x = {
            "id": ultimo_id,
            "nombre": nombre.strip(),
            "apellido": apellido.strip(),
            "legajo": str(legajo),
            "email": email.lower(),
            "carrera": carrera.strip(),
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

        # aviso al alumno
        print("[MAIL] Para: " + x["email"] + " - Su solicitud #" + str(x["id"]) + " fue registrada")

        return x

    def estado_texto(self, e):
        if e == 0:
            return "PENDIENTE"
        if e == 1:
            return "EN_PROCESO"
        if e == 2:
            return "RESUELTA"
        if e == 3:
            return "RECHAZADA"
        return "DESCONOCIDO"

    # arma el diccionario que se devuelve en la API
    def formatear(self, s):
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
            "vencida": (s["estado"] == 0 or s["estado"] == 1) and datetime.fromisoformat(s["fechaVencimiento"]) < datetime.now(timezone.utc),
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
        for i in range(len(solicitudes)):
            s = solicitudes[i]
            d["porEstado"][self.estado_texto(s["estado"])] += 1
            d["porTipo"][s["tipo"]] += 1
            d["porPrioridad"][s["prioridad"]] += 1
            # esta vencida si sigue abierta y paso la fecha
            if s["estado"] < 2:
                v = datetime.strptime(s["fechaVencimiento"], "%Y-%m-%dT%H:%M:%S.%fZ")
                hoy = datetime.utcnow()
                if v < hoy:
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

    # version anterior, la dejo por las dudas
    def calcular_prioridad_vieja(self, tipo):
        if tipo == "MESA_EXAMEN":
            return 1
        if tipo == "RECLAMO_NOTA":
            return 1
        return 3

    # def buscar_por_legajo(self, legajo):
    #     return [s for s in solicitudes if s["legajo"] == legajo]
