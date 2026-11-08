# Revisión Técnica Profesional de Código (Code Review) — Etapa 7

**Proyecto:** Sistema de Gestión de Solicitudes Académicas  
**Materia:** Metodología de Sistemas II — UTN TUP  
**Revisor:** Iván Nievas Zorn (QA & Reviewer)  
**Autor del PR inicial:** Nicolás Copertino (Desarrollo & Refactoring)  
**Estado:** Cambios requeridos aplicados — APROBADO

---

## 1. Contexto y Objetivos de la Revisión

El propósito de esta revisión técnica entre pares fue evaluar la evolución del código desde la rama inicial (`estado-inicial`) hacia la arquitectura refactorizada (`estadorefactorizado`), garantizando:

1. El cumplimiento estricto de los **4 refactorings mínimos obligatorios** (Extract Method, Move Method, Introduce Parameter Object y desacoplamiento de reglas de negocio).
2. La aplicación práctica de los principios **SOLID** y reglas de **Clean Code**.
3. La preservación absoluta de la estabilidad funcional externa mediante los **20 tests de caracterización**.

---

## 2. Checklist Técnico Formal

| Categoría       | Criterio de Aceptación                                                                                        |                   Estado Inicial del PR                    |                         Estado Final Corregido                          |
| --------------- | ------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------: | :---------------------------------------------------------------------: |
| **SOLID — SRP** | Clases con una única razón para cambiar; responsabilidades de persistencia, negocio y presentación separadas. |  ❌ Parcial (`Gestor` concentraba persistencia y negocio)  |      ✅ Cumplido (Separación en Dominio, Repositorio y Servicios)       |
| **SOLID — OCP** | Incorporación de nuevos tipos de solicitud sin modificar sentencias condicionales dispersas.                  |         🟨 Parcial (Solo se modularizó prioridad)          |  ✅ Cumplido (`CalculadoraPrioridad` y tablas de políticas en dominio)  |
| **Clean Code**  | Eliminación de números mágicos (primitive obsession), tipado claro y modelos de dominio.                      | ❌ No cumplido (Estados como enteros y parámetros sueltos) |     ✅ Cumplido (Value Object `DatosAlumno` y entidad `Solicitud`)      |
| **Refactoring** | Aplicación documentada de _Introduce Parameter Object_ en la creación de solicitudes.                         |             ❌ Ausente (8 parámetros sueltos)              |     ✅ Cumplido (`DatosAlumno` con validación declarativa `next()`)     |
| **Refactoring** | Aplicación documentada de _Move Method_ de lógica hacia la entidad experta.                                   |    ❌ Ausente (Lógica dispersa en controlador y gestor)    | ✅ Cumplido (`Solicitud.cambiar_estado()` y `Solicitud.esta_vencida()`) |
| **Refactoring** | Aplicación de _Extract Method_ para simplificar rutinas extensas.                                             |             ✅ Cumplido (`calcular_ultimo_id`)             |               ✅ Cumplido (Métodos pequeños y cohesivos)                |
| **Pruebas**     | Suite de 20 tests de caracterización pasando sin fallas ni warnings deprecados.                               |               🟨 20 pasados con 12 warnings                |                ✅ 20 tests pasando en verde (0 warnings)                |

---

## 3. Observaciones y Feedback Técnico Registrado

### Observación 1: Persistencia del Smell "Long Parameter List / Data Clump" (CS-03)

- **Hallazgo:** El método `crear_solicitud` en `app/gestor.py` continuaba recibiendo 8 parámetros independientes.
- **Acción correctiva aplicada:** Se agrupó la información del estudiante en el Value Object `DatosAlumno` dentro de `app/domain.py`, implementando su validación declarativa mediante iteración funcional con `next()`.

### Observación 2: Falta de Move Method en el ciclo de vida y cálculo de vencimiento (CS-06)

- **Hallazgo:** La lógica para determinar si una solicitud estaba vencida se encontraba duplicada en `formatear()` y `generar_reporte()`, utilizando además llamadas deprecadas a `datetime.utcnow()`.
- **Acción correctiva aplicada:** Se aplicó _Move Method_ trasladando `esta_vencida()` y `cambiar_estado()` a la clase de entidad `Solicitud` en `app/domain.py`, eliminando la duplicación y resolviendo los 12 warnings de deprecación en la suite de pruebas.

---

## 4. Veredicto Final

Tras la aplicación integral de las correcciones sobre la estructura del dominio, los 4 refactorings obligatorios se encuentran formalmente completados y documentados. La suite de pruebas de caracterización arrojó **20 tests superados exitosamente con 0 advertencias**, verificando que la evolución de la calidad interna no generó regresiones en el comportamiento observable del sistema.

**Dictamen:** APROBADO PARA ENTREGA FINAL.
