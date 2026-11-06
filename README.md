# Gestión de Solicitudes Académicas — TPI Metodología de Sistemas II

API REST para registrar solicitudes de estudiantes (certificados, mesas de examen, equivalencias, bajas de materia y reclamos de nota), clasificarlas por tipo, prioridad y estado, asignar responsables, consultarlas y generar un reporte.

> **Versión inicial (tag `estado-inicial`):** el sistema funciona correctamente desde la mirada del usuario, pero tiene problemas reales de diseño e implementación. El diagnóstico de calidad y deuda técnica está en [`docs/deuda-tecnica.md`](docs/deuda-tecnica.md).

- **Repositorio:** https://github.com/isierra93/metodologia-2
- Todos los datos del sistema son **sintéticos**.

---

## 1. Descripción del sistema base

### Dominio
Gestión de trámites académicos de una facultad. Los estudiantes inician solicitudes que tienen que ser atendidas por un área (Bedelía, Secretaría Académica o Coordinación de Carrera) dentro de un plazo que depende del tipo de trámite.

### Actores
| Actor | Rol en el sistema |
|---|---|
| **Estudiante** | Registra solicitudes con sus datos (nombre, apellido, legajo, email, carrera) y recibe un aviso cuando se registra o cambia de estado. |
| **Responsable / Área** | Persona o área asignada para atender la solicitud. Cambia su estado (en proceso, resuelta o rechazada con motivo). |
| **Personal administrativo** | Consulta y filtra solicitudes, asigna responsables y obtiene el reporte de resumen. |

> No hay autenticación: los actores se distinguen por la operación que realizan sobre la API.

### Entidades / estructuras principales
| Entidad | Representación en la versión inicial |
|---|---|
| **Solicitud** | Diccionario con tipo, descripción, prioridad, estado, fechas de creación, vencimiento y cierre, y motivo de rechazo |
| **Estudiante** | Campos `nombre`, `apellido`, `legajo`, `email`, `carrera` guardados de forma plana dentro de la solicitud |
| **Responsable / Área** | Campos `responsable` y `emailResponsable` |
| **Estado** | Entero `0-3` (`PENDIENTE`, `EN_PROCESO`, `RESUELTA`, `RECHAZADA`) |
| **Historial** | Lista de cambios de estado con su fecha |

### Alcance
**Incluye:** alta de solicitudes con validación, cálculo automático de prioridad, plazo y responsable, control de duplicados, ciclo de vida de estados, asignación de responsable, consultas con filtros y reporte de resumen (JSON o texto). Los datos se guardan en un archivo JSON.

**No incluye:** autenticación ni roles, interfaz gráfica (se usa la API o la documentación interactiva `/docs`), envío real de emails (se simula con un mensaje por consola) ni base de datos.

### Funcionalidades (casos de uso)
| # | Caso de uso | Método | Ruta |
|---|---|---|---|
| 1 | Registrar solicitud | POST | `/solicitudes` |
| 2 | Buscar / filtrar solicitudes | GET | `/solicitudes?estado=&tipo=&prioridad=` |
| 3 | Consultar una solicitud | GET | `/solicitudes/{id}` |
| 4 | Cambiar estado | PUT | `/solicitudes/{id}/estado` — body `{ "estado": "...", "motivo": "..." }` |
| 5 | Asignar responsable | PUT | `/solicitudes/{id}/asignar` — body `{ "responsable": "...", "emailResponsable": "..." }` |
| 6 | Reporte de resumen | GET | `/reportes/resumen?formato=texto` (sin `formato` devuelve JSON) |

**Tipos:** `CERTIFICADO`, `MESA_EXAMEN`, `EQUIVALENCIA`, `BAJA_MATERIA`, `RECLAMO_NOTA`
**Estados:** `PENDIENTE → EN_PROCESO → RESUELTA`, y `PENDIENTE | EN_PROCESO → RECHAZADA` (requiere motivo)

#### Reglas de negocio
| Tipo | Prioridad | Plazo | Responsable por defecto |
|---|---|---|---|
| CERTIFICADO | BAJA | 3 días | Bedelia |
| MESA_EXAMEN | ALTA | 2 días | Bedelia |
| EQUIVALENCIA | MEDIA | 15 días | Secretaria Academica |
| BAJA_MATERIA | MEDIA | 7 días | Bedelia |
| RECLAMO_NOTA | ALTA | 5 días | Coordinacion de Carrera |

- `urgente: true` lleva la prioridad a ALTA y acota el plazo a 5 días como máximo.
- Un estudiante no puede tener dos solicitudes abiertas del mismo tipo (409).
- Asignar responsable a una solicitud PENDIENTE la pasa a EN_PROCESO; no se puede asignar una cerrada (422).
- Una solicitud está **vencida** si sigue abierta y pasó su fecha de vencimiento.

#### Códigos de respuesta
| Código | Cuándo |
|---|---|
| 200 / 201 | Consulta o modificación correcta / alta correcta |
| 400 | Dato inválido (con mensaje específico en `{"error": "..."}`) |
| 404 | La solicitud no existe |
| 409 | Ya existe una solicitud abierta del mismo tipo para el estudiante |
| 422 | Transición de estado no permitida o solicitud cerrada |

### Tecnología utilizada
- **Python 3.12+** (probado con 3.14)
- **FastAPI** 0.162 + **Uvicorn** 0.54
- **Persistencia:** archivo JSON (`data/solicitudes.json`)
- **Pruebas:** pytest 9.2 + `TestClient` de FastAPI (httpx)

---

## 2. Instalación y uso

```bash
py -m venv .venv
.venv\Scripts\activate              # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

uvicorn app.main:app --reload       # http://localhost:8000  (documentación interactiva en /docs)
pytest                              # tests de caracterización
```

Variable de entorno opcional: `DATA_FILE` (ruta del archivo de datos; por defecto `data/solicitudes.json`).

> El servidor **modifica** `data/solicitudes.json` al operar. Los tests trabajan sobre una copia temporal de `tests/fixtures/solicitudes.json`, por lo que no alteran esos datos.

### Ejemplo
```bash
curl -X POST http://localhost:8000/solicitudes -H "Content-Type: application/json" -d "{\"nombre\":\"Julian\",\"apellido\":\"Castro\",\"legajo\":\"112233\",\"email\":\"julian@alumnos.example.edu\",\"carrera\":\"Ingenieria en Sistemas\",\"tipo\":\"CERTIFICADO\",\"descripcion\":\"Certificado de alumno regular\"}"
curl "http://localhost:8000/solicitudes?estado=PENDIENTE"
curl -X PUT http://localhost:8000/solicitudes/1/estado -H "Content-Type: application/json" -d "{\"estado\":\"EN_PROCESO\"}"
curl "http://localhost:8000/reportes/resumen?formato=texto"
```

---

## 3. Evidencia de funcionamiento

El comportamiento externo de la versión inicial está fijado con **20 tests de caracterización** (`tests/test_caracterizacion.py`) que recorren los 6 casos de uso, las reglas de negocio y los errores esperados. Estos tests tienen que seguir pasando **sin cambios** después de cada refactoring.

```
$ pytest
....................                                                     [100%]
20 passed, 12 warnings in 0.45s
```

Los 12 warnings son `DeprecationWarning` de `datetime.utcnow()`, registrados como deuda técnica (CS-13).

---

## 4. Diagnóstico

[`docs/deuda-tecnica.md`](docs/deuda-tecnica.md) contiene:
- **Calidad externa vs. calidad interna:** qué funciona desde la mirada del usuario, defectos latentes detectados y cómo la estructura interna afecta la mantenibilidad, la legibilidad y la evolución.
- **Deuda técnica y code smells:** 13 problemas identificados, con evidencia, ubicación, impacto, riesgo y prioridad de corrección.

---

## Hitos del repositorio
| Tag | Contenido |
|---|---|
| `estado-inicial` | Sistema base sin refactorizar, con tests de caracterización |
| `etapa-diagnostico` | Documentación de la descripción del sistema y el diagnóstico de calidad y deuda técnica |

## Estructura
```
app/main.py       endpoints FastAPI
app/gestor.py     lógica de solicitudes y persistencia
data/             datos sintéticos de trabajo
tests/            tests de caracterización + fixtures
docs/             diagnóstico de calidad y deuda técnica
```
