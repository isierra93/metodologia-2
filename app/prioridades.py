class CalculadoraPrioridad:
    PRIORIDADES = {
        "CERTIFICADO": "BAJA",
        "MESA_EXAMEN": "ALTA",
        "EQUIVALENCIA": "MEDIA",
        "BAJA_MATERIA": "MEDIA",
        "RECLAMO_NOTA": "ALTA",
    }

    def calcular(self, tipo, urgente=False):
        if urgente is True or urgente == "true" or urgente == "URG":
            return "ALTA"

        return self.PRIORIDADES.get(tipo, "BAJA")