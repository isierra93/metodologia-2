# Diagnóstico de calidad — versión inicial

Este documento cubre las **Etapas 2 y 3** del TPI sobre la versión base del sistema:

- **Etapa 2 — Calidad externa vs. calidad interna**: qué funciona bien desde la mirada del usuario y qué problemas hay en la estructura interna.
- **Etapa 3 — Deuda técnica y code smells**: inventario de los problemas, cada uno con evidencia, ubicación, impacto, riesgo de mantenimiento y prioridad de corrección.

> Todas las ubicaciones (`archivo:línea`) corresponden al tag **`estado-inicial`** (commit `632bf76`). La descripción del sistema base (Etapa 1) está en el [README](../README.md).

---

## 1. Calidad externa vs. calidad interna (Etapa 2)

### 1.1 Calidad externa: qué funciona desde la mirada del usuario

Desde afuera (alguien que consume la API) el sistema **cumple con lo que promete**: todos los casos de uso responden con los datos y los códigos HTTP esperados, y las reglas de negocio se aplican de forma consistente. Esto quedó fijado con **tests de caracterización** (`tests/test_caracterizacion.py`), que prueban la API de punta a punta con el `TestClient` de FastAPI sobre una copia de datos sintéticos (`tests/fixtures/solicitudes.json`).

| Caso de uso | Comportamiento observable | Evidencia (test) |
|---|---|---|
| Registrar solicitud | 201 con prioridad, plazo y responsable calculados según el tipo; queda guardada en el archivo | `test_alta_valida`, `test_plazos_prioridades_y_responsables_por_tipo` |
| Validar el alta | 400 con mensaje específico para cada dato inválido (8 casos) | `test_alta_invalida_devuelve_400` |
| Evitar duplicados | 409 si el alumno ya tiene una abierta del mismo tipo; se permite si la anterior está cerrada | `test_no_se_permiten_dos_abiertas_del_mismo_tipo` |
| Consultar / filtrar | Listado con filtros por estado, tipo y prioridad (combinables); 400 si el filtro no existe; 404 si el id no existe | `test_listar_todas_con_formato_de_salida`, `test_filtros`, `test_filtros_invalidos_devuelven_400`, `test_consultar_por_id` |
| Cambiar estado | Respeta el ciclo `PENDIENTE → EN_PROCESO → RESUELTA` / `→ RECHAZADA`; 422 si la transición no está permitida; rechazar exige motivo | `test_transiciones_de_estado`, `test_rechazar_exige_motivo` |
| Asignar responsable | Asigna, normaliza el email y pasa la solicitud a `EN_PROCESO`; 422 si está cerrada | `test_asignar_responsable` |
| Reporte | Totales por estado, tipo, prioridad y vencidas, en JSON o texto plano | `test_reporte_resumen_json`, `test_reporte_resumen_texto` |

Resultado de la ejecución sobre `estado-inicial`:

```
$ pytest
....................                                                     [100%]
tests/test_caracterizacion.py: 12 warnings
  app\gestor.py:197: DeprecationWarning: datetime.datetime.utcnow() is deprecated ...
20 passed, 12 warnings in 0.45s
```

El único aviso es la API deprecada de `datetime` (ver CS-13): hoy no afecta al usuario, pero adelanta un problema de evolución.

### 1.2 Defectos externos latentes (no cubiertos por los tests)

Los tests cubren el "camino feliz" y los errores previstos. Probando entradas con **tipos de dato inesperados** aparecen fallas que el usuario sí vería. Son consecuencia directa de la calidad interna (validación manual, sin modelos de entrada — CS-09):

| Entrada | Esperado | Obtenido | Causa |
|---|---|---|---|
| `POST /solicitudes` con `"nombre": 123` | 400 | **500** | `nombre.strip()` sobre un `int` (`app/gestor.py:55`) |
| `POST /solicitudes` con `"email": 5` | 400 | **500** | `"@" not in email` sobre un `int` (`app/gestor.py:61`) |
| `PUT /solicitudes/1/estado` con `"motivo": 12345` | 400 | **500** | `b["motivo"].strip()` (`app/main.py:95`) |
| `POST /solicitudes` con `"email": "a@."` | 400 | 201 | la validación solo busca `@` y `.` |
| `POST /solicitudes` con `"urgente": 1` | sin efecto | prioridad ALTA | `urgente == True` es verdadero para `1` en Python (`app/gestor.py:87`) |

Se dejan registrados como hallazgo del diagnóstico. Corregirlos **cambia el comportamiento externo**, por lo que no forman parte de un refactoring puro: si se corrigen debe hacerse como cambio explícito y con su test.

### 1.3 Calidad interna: problemas en la estructura

Mirando el código, la imagen es otra:

- **Una sola clase hace casi todo.** `GestorSolicitudes` (`app/gestor.py:17-228`) valida, aplica reglas de negocio, persiste en disco, arma la respuesta HTTP, genera el reporte en dos formatos y "envía" mails.
- **Los endpoints también tienen reglas de negocio.** Las transiciones de estado y la asignación (`app/main.py:68-133`) se resuelven en la capa HTTP, modificando el diccionario directamente.
- **No hay modelo de dominio.** Las entidades (solicitud, alumno, responsable, estado) son diccionarios planos y los estados son enteros `0-3` sin nombre.
- **Las reglas por tipo están repartidas.** Prioridad, plazo y responsable se calculan con tres cadenas `if/elif` distintas, y la lista de tipos válidos está repetida.
- **Errores silenciados y estado global.** Los fallos de lectura/escritura del archivo se ignoran, y los datos viven en variables globales del módulo.

Indicadores simples sobre `estado-inicial`:

| Indicador | Valor |
|---|---|
| Líneas de `crear_solicitud` | 89 (`app/gestor.py:51-139`) |
| Líneas del endpoint `cambiar_estado` | 41 (`app/main.py:68-108`) |
| Responsabilidades distintas en `GestorSolicitudes` | 7 (validar, reglas, persistir, formatear, reportar en JSON, reportar en texto, notificar) |
| Lugares que conocen la lista de tipos | 6 |
| Lugares que traducen texto ↔ número de estado | 3 (`app/gestor.py:141-150`, `app/main.py:27-37`, `app/main.py:74-82`) |
| Bloques `except` que ocultan el error | 2 |

### 1.4 Cómo la estructura interna afecta la mantenibilidad, la legibilidad y la evolución

Lo que el usuario ve está bien, pero la estructura interna hace que cada cambio sea caro y riesgoso. Algunos escenarios de cambio realistas:

| Escenario de evolución | Qué habría que tocar hoy | Riesgo |
|---|---|---|
| Agregar un tipo nuevo (por ejemplo `CAMBIO_COMISION`) | 6 lugares: validación (`gestor.py:65`), prioridad (`:77-86`), plazo (`:91-100`), responsable (`:105-110`), contadores del reporte (`:184`) y filtro (`main.py:42`) | Si se olvida uno, el sistema queda inconsistente. Si se olvida el del reporte, `generar_reporte` lanza `KeyError` y el endpoint de reportes devuelve 500 |
| Cambiar la regla de "vencida" (por ejemplo, contar solo días hábiles) | Dos implementaciones distintas (`gestor.py:171` y `:195-199`) | El listado y el reporte pueden mostrar números distintos |
| Migrar de archivo JSON a una base de datos | `open()`/`json` están dentro de la lógica (`gestor.py:21-39`) y los endpoints mutan los dicts y llaman a `guardar()` | Reescribir el gestor y los endpoints, sin interfaz que lo aísle |
| Enviar mails reales en lugar de `print` | Dos lugares (`gestor.py:137`, `main.py:106`), uno en el gestor y otro en el endpoint | Notificaciones inconsistentes; no se pueden desactivar en tests |
| Corregir el texto del mensaje de duplicado | `main.py:17` busca `"Ya existe"` en el texto para decidir el 409 | Un cambio de redacción cambia el código HTTP |
| Que otro integrante entienda `cambiar_estado` | Leer números mágicos (`nuevo == 3`), variables como `flag`, `b`, `s`, y un comentario `# no tocar, anda` | Lectura lenta y miedo a modificar |

**Conclusión de la Etapa 2:** la calidad externa es aceptable y está demostrada con tests. La calidad interna es baja: la mantenibilidad sufre por la concentración de responsabilidades y la duplicación, la legibilidad por nombres y números sin significado, y la evolución futura por el acoplamiento a la persistencia y la falta de modelo de dominio. Esa diferencia es la **deuda técnica** que se detalla en la sección siguiente.

---

## 2. Deuda técnica y code smells (Etapa 3)

### 2.1 Criterios

- **Impacto**: qué consecuencia tiene el problema sobre el producto o el equipo.
- **Riesgo de mantenimiento**: probabilidad de introducir un error al modificar esa zona (Alto / Medio / Bajo).
- **Prioridad de corrección**:
  - **Alta**: puede ocultar fallas o perder datos, o bloquea extender el sistema.
  - **Media**: encarece los cambios frecuentes.
  - **Baja**: afecta solo la legibilidad.

La columna *Mejora sugerida* es una orientación para las etapas siguientes (SOLID, refactoring). No describe cambios ya aplicados.

### 2.2 Inventario

| ID | Smell / debilidad | Ubicación | Evidencia | Impacto | Riesgo | Prioridad | Mejora sugerida |
|---|---|---|---|---|---|---|---|
| CS-01 | **God class** | `app/gestor.py:17-228` | `GestorSolicitudes` tiene 7 responsabilidades: valida, calcula prioridad/plazo/responsable, persiste, formatea la salida HTTP, genera el reporte en JSON y en texto, y notifica | Cualquier cambio toca la misma clase; no se puede probar una parte sin las demás | Alto | Alta | Separar responsabilidades (SRP) |
| CS-02 | **Long method** | `app/gestor.py:51-139` | `crear_solicitud` tiene 89 líneas: 7 validaciones, chequeo de duplicados, 3 cadenas `if/elif`, armado del dict, guardado y notificación | Difícil de leer; modificar una regla puede romper otra | Alto | Alta | Extract Method |
| CS-03 | **Long parameter list / data clump** | `app/gestor.py:51`, `app/main.py:15` | 8 parámetros posicionales. `nombre, apellido, legajo, email, carrera` siempre viajan juntos y se guardan planos en la solicitud | Es fácil pasar argumentos en otro orden sin que nada falle; agregar un dato obliga a cambiar todas las firmas | Medio | Alta | Introduce Parameter Object |
| CS-04 | **Condicional por tipo repetido (shotgun surgery)** | `app/gestor.py:65`, `:77-86`, `:91-100`, `:105-110`, `:184`; `app/main.py:42` | Tres cadenas `if/elif tipo == ...` que deben estar sincronizadas, más la lista de tipos repetida en 3 lugares | Agregar un tipo exige editar 6 lugares; si se olvida el del reporte, este devuelve 500 (viola OCP) | Alto | Alta | Configuración por tipo o polimorfismo (OCP) |
| CS-05 | **Manejo de errores deficiente** | `app/gestor.py:31-32`, `:38-39`, `:56-74`; `app/main.py:16-19` | (a) **Errores tragados:** `except: pass` al guardar hace que, si falla la escritura, la API responda 201/200 y el cambio se pierda; `except Exception` al cargar hace que, si el JSON está corrupto, el sistema arranque vacío sin avisar y el próximo guardado **sobrescriba** el archivo. (b) **Error detectado por texto:** el gestor devuelve `{"error": ...}` en lugar de lanzar excepciones, y el endpoint decide el 409 buscando `"Ya existe"` en el mensaje | Pérdida silenciosa de datos, imposible de diagnosticar; cambiar la redacción de un mensaje cambia el código HTTP | Alto | Alta | Propagar o registrar los errores (500) y usar excepciones propias del dominio |
| CS-06 | **Lógica de negocio en el controlador** | `app/main.py:68-108`, `:111-133` | Las reglas de transición, el motivo de rechazo, el cierre y la asignación están en los endpoints, que modifican el dict directamente (`s["estado"] = nuevo`, `main.py:99`) y llaman a `gestor.guardar()` | Las reglas no se pueden reutilizar ni probar sin HTTP; no hay límite entre capas | Alto | Alta | Mover la responsabilidad al dominio o a un servicio |
| CS-07 | **Lógica duplicada (y divergente)** | Vencida: `app/gestor.py:171` y `:195-199`. Email: `app/gestor.py:61` y `app/main.py:121`. Estado texto→número: `app/main.py:28-36` y `:74-82`. Mensaje de mail: `app/gestor.py:137` y `app/main.py:106`. "No encontrada": `app/main.py:60-62`, `:70-72`, `:113-115` | La regla "está vencida" está escrita de dos formas distintas: `fromisoformat` con zona horaria en `formatear`, y `strptime` + `utcnow()` en `generar_reporte`. Además, "abierta" aparece como `estado == 0 or estado == 1` en un lugar y como `estado < 2` en otro. El resto de la lógica está copiada tal cual en varios lugares | Corregir un bug en una copia deja el error en las demás; el listado y el reporte pueden divergir | Medio | Alta | Move Method (la solicitud sabe si está vencida) y Extract Function para el resto |
| CS-08 | **Dependencias concretas en lugar de abstracciones** | Persistencia: `app/gestor.py:7`, `:21-39`; `app/main.py:10`. Notificación: `app/gestor.py:137`, `app/main.py:106` | La ruta del archivo, `open()` y `json` están dentro de la lógica, y el gestor se instancia al importar `main.py`. El "mail" es un `print` escrito en dos capas distintas | No se puede cambiar el almacenamiento ni el canal de notificación, ni reemplazarlos en tests (por ejemplo, un repositorio en memoria o un notificador silencioso) | Medio | Media | Inversión de dependencias (DIP): repositorio y notificador inyectados |
| CS-09 | **Entrada sin tipado ni validación de tipos** | `app/main.py:14`, `:69`, `:112`; `app/gestor.py:55-68` | Los bodies se reciben como `dict` y se leen con `b.get(...)`; nunca se verifica el tipo del dato. Provoca los **500** de la sección 1.2 | Errores internos visibles al usuario; `/docs` no documenta qué campos espera cada endpoint | Medio | Media | Modelos de entrada (Pydantic), conservando los códigos y mensajes actuales |
| CS-10 | **Estado global mutable** | `app/gestor.py:9-10`, `:22`, `:41-42`, `:52` | `solicitudes` y `ultimo_id` son globales modificadas con `global`; `get_todas()` devuelve la lista interna, que cualquiera puede modificar | Efectos colaterales difíciles de rastrear; dos instancias del gestor comparten datos. Como FastAPI ejecuta los endpoints síncronos en paralelo, `ultimo_id += 1` y la escritura del archivo pueden pisarse | Medio | Media | Encapsular el estado y devolver copias |
| CS-11 | **Números y strings mágicos (primitive obsession)** | `app/gestor.py:73`, `:87`, `:101`, `:113`, `:126`, `:195`; `app/main.py:29-36`, `:86-90`, `:99`, `:123` | Estados `0/1/2/3`, `estado < 2`, `"URG"`, plazo máximo `5`, `24 * 60 * 60` | No se entiende la intención; un número equivocado pasa desapercibido | Medio | Media | Constantes y `Enum` |
| CS-12 | **Tests frágiles por orden y estado global** | `tests/test_caracterizacion.py:26-39`, `:52` | Los tests comparten un cliente y un archivo con `scope="module"`, y dependen del orden ("Reportes (antes de modificar datos)"). Además, `DATA_FILE` debe definirse **antes** de importar `app.main` porque la ruta se lee al importar | Reordenar o agregar tests puede romper otros sin que haya cambiado el código, y eso debilita la red de seguridad para refactorizar | Medio | Media | Datos aislados por test e inyección del repositorio |
| CS-13 | **Problemas menores de higiene del código** | API deprecada: `app/gestor.py:197`. Nombres: `app/gestor.py:25`, `:44`, `:78`, `:106`, `:116`, `:181`; `app/main.py:14`, `:25`, `:28`, `:52`, `:86`. Código muerto: `app/gestor.py:219-228`, `app/main.py:66-67` | (a) `datetime.utcnow()` está deprecado (los tests muestran el `DeprecationWarning`). (b) Nombres como `d`, `p`, `r`, `x`, `b`, `data2`, `e`, `tmp` y `flag`; el parámetro `id` tapa la función nativa; los recorridos usan `for i in range(len(...))`. (c) `calcular_prioridad_vieja` no se usa, `buscar_por_legajo` está comentado y hay un comentario `# no tocar, anda` | Lectura lenta, ruido y miedo a modificar; el código se va a romper al actualizar Python | Bajo | Baja | Usar `datetime.now(timezone.utc)`, Rename Variable, Remove Dead Code y reemplazar el comentario por tests |

### 2.3 Priorización

El orden propuesto para atacar la deuda combina prioridad, riesgo y frecuencia de cambio de cada zona:

1. **Prioridad alta (7): CS-01 a CS-07.** Concentran la mayor parte del costo de cambio (CS-01, CS-02, CS-04, CS-06) o pueden ocultar fallas y pérdida de datos (CS-05). CS-02, CS-03 y CS-07 son además puntos directos para los refactorings obligatorios: Extract Method, Introduce Parameter Object y Move Method.
2. **Prioridad media (5): CS-08 a CS-12.** Conviene abordar CS-12 **antes** de refactorizar, porque los tests son la red de seguridad que garantiza que el comportamiento externo no cambie.
3. **Prioridad baja (1): CS-13.** Es de bajo riesgo y se puede resolver mientras se trabaja en las zonas afectadas.

| Prioridad | Cantidad | Smells |
|---|---|---|
| Alta | 7 | CS-01 a CS-07 |
| Media | 5 | CS-08 a CS-12 |
| Baja | 1 | CS-13 |
| **Total** | **13** |
