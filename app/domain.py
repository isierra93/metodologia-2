import re
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional


def _iso(f: datetime) -> str:
    return f.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (f.microsecond // 1000)


# Refactoring Obligatorio 1: Introduce Parameter Object (CS-03)
@dataclass(frozen=True)
class DatosAlumno:
    nombre: str
    apellido: str
    legajo: str
    email: str
    carrera: str

    def validar(self) -> Optional[str]:
        reglas = [
            (not self.nombre or not self.nombre.strip(), "El nombre es obligatorio"),
            (not self.apellido or not self.apellido.strip(), "El apellido es obligatorio"),
            (not self.legajo or not re.match(r"^\d{5,6}$", str(self.legajo)), "Legajo invalido"),
            (not self.email or "@" not in self.email or "." not in self.email, "Email invalido"),
            (not self.carrera or not self.carrera.strip(), "La carrera es obligatoria"),
        ]
        return next((msg for falla, msg in reglas if falla), None)


# Refactoring Obligatorio 2: Move Method / Entidad con comportamiento de ciclo de vida (CS-06)
class Solicitud:
    ESTADOS = {0: "PENDIENTE", 1: "EN_PROCESO", 2: "RESUELTA", 3: "RECHAZADA"}

    def __init__(self, datos_dict: dict):
        self.datos = datos_dict

    @property
    def id(self):
        return self.datos["id"]

    @property
    def estado(self):
        return self.datos["estado"]

    @property
    def fecha_vencimiento(self):
        return self.datos["fechaVencimiento"]

    def esta_vencida(self, ahora: Optional[datetime] = None) -> bool:
        """Move Method: cálculo encapsulado de vencimiento eliminando lógica dispersa."""
        if self.estado not in (0, 1):
            return False
        if ahora is None:
            ahora = datetime.now(timezone.utc)
        
        fv_str = self.fecha_vencimiento
        try:
            fv = datetime.fromisoformat(fv_str)
        except ValueError:
            fv = datetime.strptime(fv_str, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        
        if fv.tzinfo is None:
            fv = fv.replace(tzinfo=timezone.utc)
        return fv < ahora

    def cambiar_estado(self, nuevo_estado: int, motivo_rechazo: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """Move Method: máquina de estados y reglas de transición alojadas en la entidad."""
        if nuevo_estado not in (0, 1, 2, 3):
            return False, "Estado invalido"

        if nuevo_estado == 3 and (not motivo_rechazo or motivo_rechazo.strip() == ""):
            return False, "El motivo de rechazo es obligatorio"

        ahora = datetime.now(timezone.utc)
        self.datos["estado"] = nuevo_estado
        self.datos["historial"].append({"estado": nuevo_estado, "fecha": _iso(ahora)})

        if nuevo_estado == 3:
            self.datos["motivoRechazo"] = motivo_rechazo.strip()
        if nuevo_estado in (2, 3):
            self.datos["fechaCierre"] = _iso(ahora)

        return True, None