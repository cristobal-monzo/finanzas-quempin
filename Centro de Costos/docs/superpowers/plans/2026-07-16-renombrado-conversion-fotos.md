# Renombrado y conversión HEIC→JPG de fotos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Renombrar cada foto/PDF en `Documentos Centro de Costos/<Proyecto>/` a `<N° Ref>_<TagProveedor>_<Fecha ISO>.<ext>`, convirtiendo `.HEIC` a `.jpg` en el proceso, tanto para documentos nuevos como retroactivamente para los ya registrados en `Master`.

**Architecture:** Un solo paso idempotente agregado a `auditor_centro_costos.py`: por cada fila de `Master` calcula el nombre esperado del archivo, compara contra el nombre físico actual (resuelto vía `Archivo origen` o, para los 24 documentos del bootstrap, vía `reconciliacion_archivos.json`), y si difiere renombra/convierte y actualiza `Master`. Las funciones de cálculo (nombre esperado, resolución de ruta, plan de acción) son puras y no tocan disco — se usan tanto para el preview de `status` como para la ejecución real de `run`.

**Tech Stack:** Python 3, `Pillow` + `pillow_heif` (ya instalados) para la conversión HEIC→JPG, `openpyxl` (ya en uso) para leer/escribir `Master`, `pytest` (nuevo, se instala en Task 1) para las pruebas.

## Global Constraints

Copiadas verbatim de
[docs/superpowers/specs/2026-07-16-renombrado-conversion-fotos-design.md](../specs/2026-07-16-renombrado-conversion-fotos-design.md):

- Patrón de nombre: `<N° Ref>_<TagProveedor>_<Fecha ISO>.<ext>` (ej. `UMAG-001_Shell_2026-07-15.jpg`).
- `TagProveedor` = el tag corto de `Master.Proveedor` (columna 7), nunca la razón social completa (columna 8, oculta).
- `Fecha ISO` = `Master.Fecha` (almacenada `dd/mm/yyyy` o como objeto fecha) convertida a `yyyy-mm-dd`.
- Sanitización: espacios y `\ / : * ? " < > |` se reemplazan por `_`.
- `.heic`/`.HEIC` → se convierte a `.jpg` (Pillow + `pillow_heif`, `ImageOps.exif_transpose()`, calidad JPEG 90, sin redimensionar) y el original se borra tras una conversión exitosa.
- `.png`/`.jpg`/`.jpeg`/`.pdf` → solo se renombran/mueven, nunca se recodifican.
- Debe cubrir documentos nuevos **y**, retroactivamente, los ya registrados en `Master` (incluidos los 24 del bootstrap) con el **mismo** mecanismo idempotente — no una migración separada.
- La ubicación física del archivo es el `Proyecto` embebido en la ruta relativa de `Archivo origen` (o de `reconciliacion_archivos.json` para el bootstrap) — **nunca** `Master.Proyecto` actual, porque pueden diferir (ver nota de `UMAG-002` en `reconciliacion_archivos.json`: vive físicamente en `UMAG/` pero su `Proyecto` en Master dice `Gastos Generales`).
- `status` (solo lectura) muestra el preview de qué se renombraría/convertiría, sin tocar nada. `run` ejecuta.
- Errores (archivo no encontrado, falla de conversión) → advertencia en el informe de auditoría, no interrumpen la corrida.
- Tras renombrar/convertir, se actualiza `Master.Archivo origen` (columna 15) y `Master.Fecha modificación` (columna 16, con el mtime real del archivo resultante) — excepción deliberada a la regla de oro de "nunca tocar una fila ya escrita", igual que la migración de `Proveedor (Razón Social)` ya documentada en el código.
- Sin backup adicional de fotos antes de la pasada retroactiva — decisión explícita del usuario, riesgo aceptado.
- Ningún test corre contra `Centro de Costos.xlsx` ni `Documentos Centro de Costos/` reales — todo con fixtures/`tmp_path`.

---

## File Structure

- **Modify `auditor_centro_costos.py`**: agrega una nueva sección `── RENOMBRADO Y CONVERSIÓN DE ARCHIVOS ──` (funciones puras + ejecución en disco), extiende `leer_master()` con dos campos nuevos por fila, y agrega un paso nuevo a `main()`.
- **Modify `.claude/skills/Registro_Centro_de_Costos/driver.py`**: agrega una función `mostrar_preview_renombrados()` y la llama desde `cmd_status()`.
- **Create `tests/conftest.py`**: agrega la raíz del módulo a `sys.path` para que los tests puedan hacer `import auditor_centro_costos`.
- **Create `tests/test_renombrado_fotos.py`**: todos los tests de esta funcionalidad (funciones puras de `auditor_centro_costos.py`).
- **Create `tests/test_driver_preview_renombrados.py`**: test de `mostrar_preview_renombrados()` en `driver.py`.

---

### Task 1: Sanitización y cálculo del nombre esperado

**Files:**
- Modify: `auditor_centro_costos.py` (nueva sección, antes de `# --- MAIN ---` en la línea 703)
- Create: `tests/conftest.py`
- Create: `tests/test_renombrado_fotos.py`

**Interfaces:**
- Produces: `CARACTERES_INVALIDOS_ARCHIVO` (regex compilado), `sanitizar_nombre(texto: str) -> str`, `fecha_iso_desde_valor(valor) -> str`, `nombre_esperado_archivo(n_ref: str, proveedor_tag: str, fecha_valor, extension: str) -> str`. Estas tres funciones las usará Task 3.

- [ ] **Step 1: Instalar pytest**

Run: `python -m pip install pytest`
Expected: `Successfully installed pytest-...` (o "Requirement already satisfied" si ya estuviera).

- [ ] **Step 2: Crear `tests/conftest.py`**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [ ] **Step 3: Escribir los tests que fallan**

Crear `tests/test_renombrado_fotos.py`:

```python
from datetime import datetime

import auditor_centro_costos as acc


def test_sanitizar_nombre_reemplaza_caracteres_invalidos():
    assert acc.sanitizar_nombre('Fandos: "Shell" *Ruta/68*') == "Fandos_Shell_Ruta_68_"


def test_sanitizar_nombre_reemplaza_espacios():
    assert acc.sanitizar_nombre("Estaciones de Servicio") == "Estaciones_de_Servicio"


def test_fecha_iso_desde_datetime():
    assert acc.fecha_iso_desde_valor(datetime(2026, 7, 15)) == "2026-07-15"


def test_fecha_iso_desde_string_dd_mm_yyyy():
    assert acc.fecha_iso_desde_valor("15/07/2026") == "2026-07-15"


def test_fecha_iso_desde_string_invalida_se_sanitiza():
    assert acc.fecha_iso_desde_valor("fecha rara") == "fecha_rara"


def test_nombre_esperado_archivo_heic_pasa_a_jpg():
    nombre = acc.nombre_esperado_archivo("UMAG-001", "Shell", "15/07/2026", ".HEIC")
    assert nombre == "UMAG-001_Shell_2026-07-15.jpg"


def test_nombre_esperado_archivo_pdf_mantiene_extension():
    nombre = acc.nombre_esperado_archivo("CFLI-002", "Beckman", datetime(2026, 1, 5), ".pdf")
    assert nombre == "CFLI-002_Beckman_2026-01-05.pdf"


def test_nombre_esperado_archivo_sin_proveedor():
    nombre = acc.nombre_esperado_archivo("GGEN-001", "", "01/01/2026", ".jpg")
    assert nombre == "GGEN-001_SinProveedor_2026-01-01.jpg"
```

- [ ] **Step 4: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: FAIL — `AttributeError: module 'auditor_centro_costos' has no attribute 'sanitizar_nombre'` (u otras funciones no definidas).

- [ ] **Step 5: Implementar las funciones**

En `auditor_centro_costos.py`, insertar esta sección completa inmediatamente antes de la línea `# --- MAIN ---------------------------------------------------------------------` (línea 703):

```python
# ── RENOMBRADO Y CONVERSIÓN DE ARCHIVOS ─────────────────────────────────────
# Renombra cada foto/PDF a "<N Ref>_<TagProveedor>_<Fecha ISO>.<ext>" y convierte
# HEIC->JPG. Cubre documentos nuevos y, retroactivamente, los ya registrados en
# Master (incluidos los del bootstrap via reconciliacion_archivos.json), con el
# mismo mecanismo idempotente: se compara el nombre fisico actual contra el
# esperado y solo se actua si difieren.

CARACTERES_INVALIDOS_ARCHIVO = re.compile(r'[\\/:*?"<>|]')


def sanitizar_nombre(texto):
    """Reemplaza espacios y caracteres invalidos en nombres de archivo Windows
    (\\ / : * ? " < > |) por '_'."""
    limpio = CARACTERES_INVALIDOS_ARCHIVO.sub("_", texto)
    return re.sub(r"\s+", "_", limpio.strip())


def fecha_iso_desde_valor(valor):
    """Convierte Master.Fecha (datetime/date, o string 'dd/mm/yyyy') a 'yyyy-mm-dd'.
    Si no se puede interpretar, sanitiza el valor tal cual para no romper el nombre."""
    if isinstance(valor, datetime):
        return valor.strftime("%Y-%m-%d")
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")
    if isinstance(valor, str):
        try:
            return datetime.strptime(valor, "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return sanitizar_nombre(valor)
    return "sin-fecha"


def nombre_esperado_archivo(n_ref, proveedor_tag, fecha_valor, extension):
    """Nombre de archivo esperado: '<N Ref>_<TagProveedor>_<Fecha ISO><ext>'.
    Los .heic/.HEIC pasan a .jpg (se convierten); el resto conserva su extension."""
    tag = sanitizar_nombre(proveedor_tag or "SinProveedor")
    fecha = fecha_iso_desde_valor(fecha_valor)
    ext = extension.lower()
    if ext == ".heic":
        ext = ".jpg"
    return f"{n_ref}_{tag}_{fecha}{ext}"
```

- [ ] **Step 6: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: 8 passed.

- [ ] **Step 7: Commit**

```bash
git add auditor_centro_costos.py tests/conftest.py tests/test_renombrado_fotos.py
git commit -m "feat: agregar calculo de nombre esperado para renombrado de fotos"
```

(Si el directorio no es un repositorio git, omitir este paso y avisar al usuario.)

---

### Task 2: Resolución de la ubicación física actual del archivo

**Files:**
- Modify: `auditor_centro_costos.py` (función `leer_master`, líneas 268-299; nuevas funciones en la sección de Task 1)
- Modify: `tests/test_renombrado_fotos.py` (agregar tests)

**Interfaces:**
- Consumes: nada nuevo de Task 1 (funciones independientes).
- Produces: `construir_reconciliacion_inversa(reconciliacion: dict) -> dict` y `resolver_ruta_actual(fila_dict: dict, reconciliacion_inversa: dict) -> str | None`. `fila_dict` debe traer las claves `n_ref`, `archivo_origen`, `proveedor_tag`, `fecha` (`leer_master` se extiende en este task para incluir las dos últimas). Task 3 consume ambas funciones.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_renombrado_fotos.py`:

```python
def test_construir_reconciliacion_inversa():
    reconciliacion = {
        "UMAG\\IMG_7530.HEIC": "UMAG-001",
        "UMAG\\IMG_7534.HEIC": "UMAG-002",
    }
    inversa = acc.construir_reconciliacion_inversa(reconciliacion)
    assert inversa == {
        "UMAG-001": "UMAG\\IMG_7530.HEIC",
        "UMAG-002": "UMAG\\IMG_7534.HEIC",
    }


def test_resolver_ruta_actual_usa_archivo_origen_si_esta_poblado():
    fila = {"n_ref": "UMAG-050", "archivo_origen": "UMAG\\IMG_9999.HEIC"}
    assert acc.resolver_ruta_actual(fila, {}) == "UMAG\\IMG_9999.HEIC"


def test_resolver_ruta_actual_usa_reconciliacion_si_archivo_origen_vacio():
    fila = {"n_ref": "UMAG-002", "archivo_origen": None}
    inversa = {"UMAG-002": "UMAG\\IMG_7534.HEIC"}
    # Nota: UMAG-002 vive fisicamente en UMAG/ aunque Master.Proyecto diga
    # "Gastos Generales" para esa fila (reasignacion manual) -- por eso
    # resolver_ruta_actual NUNCA debe mirar fila["proyecto"].
    assert acc.resolver_ruta_actual(fila, inversa) == "UMAG\\IMG_7534.HEIC"


def test_resolver_ruta_actual_devuelve_none_si_no_hay_dato():
    fila = {"n_ref": "UMAG-099", "archivo_origen": None}
    assert acc.resolver_ruta_actual(fila, {}) is None
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: los 4 tests nuevos fallan con `AttributeError` (funciones no definidas); los 8 de Task 1 siguen pasando.

- [ ] **Step 3: Implementar las funciones**

Agregar al final de la sección `── RENOMBRADO Y CONVERSIÓN DE ARCHIVOS ──` en `auditor_centro_costos.py` (después de `nombre_esperado_archivo`):

```python
def construir_reconciliacion_inversa(reconciliacion):
    """{n_ref: ruta_relativa} a partir del mapeo 'ruta_relativa -> n_ref' de
    reconciliacion_archivos.json."""
    return {n_ref: ruta for ruta, n_ref in reconciliacion.items()}


def resolver_ruta_actual(fila_dict, reconciliacion_inversa):
    """Ruta relativa ('Proyecto\\archivo.ext') del archivo fisico actual para
    una fila de Master, o None si no se puede determinar.

    OJO: la ubicacion fisica puede NO coincidir con Master.Proyecto (ver nota
    de UMAG-002 en reconciliacion_archivos.json) -- por eso se usa el Proyecto
    embebido en la propia ruta relativa (de Archivo origen o de la
    reconciliacion), nunca fila_dict['proyecto']."""
    if fila_dict.get("archivo_origen"):
        return str(fila_dict["archivo_origen"])
    return reconciliacion_inversa.get(fila_dict["n_ref"])
```

- [ ] **Step 4: Extender `leer_master` con `proveedor_tag` y `fecha`**

En `auditor_centro_costos.py`, dentro de `leer_master` (alrededor de la línea 294), cambiar:

```python
        filas.append({
            "fila": r, "n_ref": n_ref, "proyecto": proyecto,
            "archivo_origen": archivo_origen,
        })
```

por:

```python
        filas.append({
            "fila": r, "n_ref": n_ref, "proyecto": proyecto,
            "archivo_origen": archivo_origen,
            "proveedor_tag": ws_master.cell(row=r, column=7).value,
            "fecha": ws_master.cell(row=r, column=4).value,
        })
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add auditor_centro_costos.py tests/test_renombrado_fotos.py
git commit -m "feat: resolver ubicacion fisica actual de un documento para renombrado"
```

---

### Task 3: Planificación del renombrado (sin tocar disco)

**Files:**
- Modify: `auditor_centro_costos.py` (nuevas funciones en la sección de renombrado)
- Modify: `tests/test_renombrado_fotos.py`

**Interfaces:**
- Consumes: `nombre_esperado_archivo` (Task 1), `resolver_ruta_actual` (Task 2), constante `RAIZ_DOCS` (ya existe en el módulo).
- Produces: `planificar_renombrado_fila(fila_dict: dict, reconciliacion_inversa: dict) -> dict` con claves `n_ref`, `fila`, `accion` (uno de `"ya_correcto"`, `"renombrar"`, `"convertir_heic"`, `"archivo_no_encontrado"`), `ruta_actual` (`Path | None`), `ruta_nueva` (`Path | None`), `nombre_nuevo` (`str | None`); y `planificar_renombrados(filas_master: list[dict], reconciliacion_inversa: dict) -> list[dict]`. Task 4 y Task 5 consumen ambas.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_renombrado_fotos.py`:

```python
def test_planificar_renombrado_fila_ya_correcto(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "UMAG-001_Shell_2026-07-15.jpg").write_bytes(b"contenido")

    fila = {
        "fila": 2, "n_ref": "UMAG-001",
        "archivo_origen": "UMAG\\UMAG-001_Shell_2026-07-15.jpg",
        "proveedor_tag": "Shell", "fecha": "15/07/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "ya_correcto"
    assert item["fila"] == 2
    assert item["nombre_nuevo"] == "UMAG-001_Shell_2026-07-15.jpg"


def test_planificar_renombrado_fila_renombrar_sin_conversion(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "CFLI").mkdir()
    (tmp_path / "CFLI" / "factura_original.pdf").write_bytes(b"contenido")

    fila = {
        "fila": 5, "n_ref": "CFLI-003",
        "archivo_origen": "CFLI\\factura_original.pdf",
        "proveedor_tag": "Beckman", "fecha": "01/02/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "renombrar"
    assert item["nombre_nuevo"] == "CFLI-003_Beckman_2026-02-01.pdf"
    assert item["ruta_actual"] == tmp_path / "CFLI" / "factura_original.pdf"
    assert item["ruta_nueva"] == tmp_path / "CFLI" / "CFLI-003_Beckman_2026-02-01.pdf"


def test_planificar_renombrado_fila_convertir_heic(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "IMG_9999.HEIC").write_bytes(b"contenido")

    fila = {
        "fila": 8, "n_ref": "UMAG-025",
        "archivo_origen": "UMAG\\IMG_9999.HEIC",
        "proveedor_tag": "Anwo", "fecha": "20/03/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "convertir_heic"
    assert item["nombre_nuevo"] == "UMAG-025_Anwo_2026-03-20.jpg"


def test_planificar_renombrado_fila_archivo_no_existe_en_disco(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()

    fila = {
        "fila": 9, "n_ref": "UMAG-030",
        "archivo_origen": "UMAG\\NoExiste.jpg",
        "proveedor_tag": "Anwo", "fecha": "20/03/2026",
    }
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "archivo_no_encontrado"


def test_planificar_renombrado_fila_sin_ruta_resoluble(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    fila = {"fila": 10, "n_ref": "UMAG-099", "archivo_origen": None,
            "proveedor_tag": "Anwo", "fecha": "20/03/2026"}
    item = acc.planificar_renombrado_fila(fila, {})
    assert item["accion"] == "archivo_no_encontrado"


def test_planificar_renombrados_procesa_varias_filas(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "a.jpg").write_bytes(b"x")
    (tmp_path / "UMAG" / "UMAG-002_Shell_2026-01-01.jpg").write_bytes(b"x")

    filas = [
        {"fila": 2, "n_ref": "UMAG-001", "archivo_origen": "UMAG\\a.jpg",
         "proveedor_tag": "Shell", "fecha": "01/01/2026"},
        {"fila": 3, "n_ref": "UMAG-002", "archivo_origen": "UMAG\\UMAG-002_Shell_2026-01-01.jpg",
         "proveedor_tag": "Shell", "fecha": "01/01/2026"},
    ]
    planes = acc.planificar_renombrados(filas, {})
    assert [p["accion"] for p in planes] == ["renombrar", "ya_correcto"]
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: los 6 tests nuevos fallan con `AttributeError`; los 12 anteriores siguen pasando.

- [ ] **Step 3: Implementar las funciones**

Agregar al final de la sección de renombrado en `auditor_centro_costos.py`:

```python
def planificar_renombrado_fila(fila_dict, reconciliacion_inversa):
    """Calcula (sin tocar disco) que accion corresponde para una fila de Master:
    {'n_ref', 'fila', 'accion', 'ruta_actual', 'ruta_nueva', 'nombre_nuevo'}.
    'accion' es uno de: 'ya_correcto', 'renombrar', 'convertir_heic',
    'archivo_no_encontrado'. Se usa tanto para el preview de status como,
    antes de ejecutar, para el run real."""
    base = {
        "n_ref": fila_dict["n_ref"], "fila": fila_dict["fila"],
        "ruta_actual": None, "ruta_nueva": None, "nombre_nuevo": None,
    }

    ruta_relativa = resolver_ruta_actual(fila_dict, reconciliacion_inversa)
    if not ruta_relativa:
        return {**base, "accion": "archivo_no_encontrado"}

    proyecto_fisico, nombre_archivo = ruta_relativa.split("\\", 1)
    ruta_actual = RAIZ_DOCS / proyecto_fisico / nombre_archivo
    if not ruta_actual.exists():
        return {**base, "accion": "archivo_no_encontrado", "ruta_actual": ruta_actual}

    extension_actual = ruta_actual.suffix
    nombre_nuevo = nombre_esperado_archivo(
        fila_dict["n_ref"], fila_dict["proveedor_tag"], fila_dict["fecha"], extension_actual
    )
    ruta_nueva = ruta_actual.parent / nombre_nuevo

    if ruta_actual.name == nombre_nuevo:
        return {**base, "accion": "ya_correcto", "ruta_actual": ruta_actual,
                "ruta_nueva": ruta_actual, "nombre_nuevo": nombre_nuevo}

    accion = "convertir_heic" if extension_actual.lower() == ".heic" else "renombrar"
    return {**base, "accion": accion, "ruta_actual": ruta_actual,
            "ruta_nueva": ruta_nueva, "nombre_nuevo": nombre_nuevo}


def planificar_renombrados(filas_master, reconciliacion_inversa):
    """planificar_renombrado_fila() aplicado a cada fila de Master. No toca disco."""
    return [planificar_renombrado_fila(fm, reconciliacion_inversa) for fm in filas_master]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add auditor_centro_costos.py tests/test_renombrado_fotos.py
git commit -m "feat: planificar renombrado/conversion de archivos sin tocar disco"
```

---

### Task 4: Conversión HEIC→JPG y ejecución en disco

**Files:**
- Modify: `auditor_centro_costos.py` (nuevas funciones + import de `PIL`/`pillow_heif` dentro de la función, para no cargar esas librerías si nunca se usa esta ruta)
- Modify: `tests/test_renombrado_fotos.py`

**Interfaces:**
- Consumes: nada de tasks anteriores (funciones autónomas que reciben `Path`s).
- Produces: `convertir_heic_a_jpg(ruta_origen: Path, ruta_destino: Path) -> None` y `ejecutar_plan_renombrado(item: dict) -> tuple[bool, str | None]` (`item` es el dict que devuelve `planificar_renombrado_fila`). Task 5 consume `ejecutar_plan_renombrado`.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_renombrado_fotos.py`:

```python
def _crear_heic_de_prueba(ruta, color=(200, 50, 50), size=(10, 10)):
    from PIL import Image
    import pillow_heif

    img = Image.new("RGB", size, color=color)
    heif_file = pillow_heif.from_pillow(img)
    heif_file.save(str(ruta))


def test_convertir_heic_a_jpg(tmp_path):
    from PIL import Image

    origen = tmp_path / "foto.heic"
    destino = tmp_path / "foto.jpg"
    _crear_heic_de_prueba(origen, color=(200, 50, 50))

    acc.convertir_heic_a_jpg(origen, destino)

    assert destino.exists()
    with Image.open(destino) as img:
        assert img.format == "JPEG"
        assert img.size == (10, 10)


def test_ejecutar_plan_renombrado_renombra_sin_convertir(tmp_path):
    ruta_actual = tmp_path / "factura.pdf"
    ruta_actual.write_bytes(b"contenido")
    ruta_nueva = tmp_path / "CFLI-003_Beckman_2026-02-01.pdf"

    item = {"accion": "renombrar", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is True
    assert error is None
    assert ruta_nueva.exists()
    assert not ruta_actual.exists()


def test_ejecutar_plan_renombrado_convierte_heic_y_borra_original(tmp_path):
    ruta_actual = tmp_path / "IMG_9999.HEIC"
    _crear_heic_de_prueba(ruta_actual)
    ruta_nueva = tmp_path / "UMAG-025_Anwo_2026-03-20.jpg"

    item = {"accion": "convertir_heic", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is True
    assert error is None
    assert ruta_nueva.exists()
    assert not ruta_actual.exists()


def test_ejecutar_plan_renombrado_conversion_fallida_no_borra_original(tmp_path):
    ruta_actual = tmp_path / "corrupto.HEIC"
    ruta_actual.write_bytes(b"esto no es un heic valido")
    ruta_nueva = tmp_path / "UMAG-025_Anwo_2026-03-20.jpg"

    item = {"accion": "convertir_heic", "ruta_actual": ruta_actual, "ruta_nueva": ruta_nueva}
    ok, error = acc.ejecutar_plan_renombrado(item)

    assert ok is False
    assert error is not None
    assert ruta_actual.exists()
    assert not ruta_nueva.exists()


def test_ejecutar_plan_renombrado_ya_correcto_no_hace_nada(tmp_path):
    ruta = tmp_path / "UMAG-001_Shell_2026-07-15.jpg"
    ruta.write_bytes(b"contenido")
    item = {"accion": "ya_correcto", "ruta_actual": ruta, "ruta_nueva": ruta}
    ok, error = acc.ejecutar_plan_renombrado(item)
    assert ok is True
    assert error is None
    assert ruta.exists()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: los 5 tests nuevos fallan con `AttributeError`; los 18 anteriores siguen pasando.

- [ ] **Step 3: Implementar las funciones**

Agregar al final de la sección de renombrado en `auditor_centro_costos.py`:

```python
def convertir_heic_a_jpg(ruta_origen, ruta_destino):
    """Decodifica un HEIC y lo guarda como JPG, respetando la orientacion EXIF
    (las fotos de celular la traen y sin esto quedarian rotadas). Calidad 90,
    sin redimensionar -- son documentos tributarios que pueden necesitar zoom."""
    from PIL import Image, ImageOps
    import pillow_heif

    pillow_heif.register_heif_opener()
    with Image.open(ruta_origen) as imagen:
        imagen = ImageOps.exif_transpose(imagen)
        imagen.convert("RGB").save(str(ruta_destino), "JPEG", quality=90)


def ejecutar_plan_renombrado(item):
    """Ejecuta en disco la accion de un item de planificar_renombrado_fila
    ('renombrar' o 'convertir_heic'; 'ya_correcto'/'archivo_no_encontrado' no
    hacen nada). Devuelve (ok, error) -- no toca Master, eso lo hace el
    llamador (Task 5)."""
    if item["accion"] == "renombrar":
        item["ruta_actual"].rename(item["ruta_nueva"])
        return True, None

    if item["accion"] == "convertir_heic":
        try:
            convertir_heic_a_jpg(item["ruta_actual"], item["ruta_nueva"])
        except Exception as e:
            return False, str(e)
        item["ruta_actual"].unlink()
        return True, None

    return True, None
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: 23 passed.

- [ ] **Step 5: Commit**

```bash
git add auditor_centro_costos.py tests/test_renombrado_fotos.py
git commit -m "feat: ejecutar conversion HEIC->JPG y renombrado en disco"
```

---

### Task 5: Orquestación e integración en `main()`

**Files:**
- Modify: `auditor_centro_costos.py` (nueva función `aplicar_renombrados`, nuevo paso en `main()`, nueva sección en el informe de auditoría, línea nueva en el resumen final)
- Modify: `tests/test_renombrado_fotos.py`

**Interfaces:**
- Consumes: `planificar_renombrados` (Task 3), `ejecutar_plan_renombrado` (Task 4).
- Produces: `aplicar_renombrados(ws_master, filas_master: list[dict], reconciliacion_inversa: dict) -> tuple[int, list[dict]]` — devuelve `(cantidad_renombrados, advertencias)`, donde cada advertencia es `{"n_ref": str, "detalle": str}`. Esta función queda disponible para `main()` (en este task) y para `driver.py` (Task 6, que reutiliza `planificar_renombrados` directamente, no `aplicar_renombrados`, porque `status` no ejecuta nada).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_renombrado_fotos.py`. Estos tests usan un stub minimo de hoja de Excel (una lista mutable indexada por (fila, columna)) para no depender de abrir un `.xlsx` real:

```python
class _WsFake:
    """Reemplaza una worksheet de openpyxl para estos tests: solo soporta
    cell(row, column, value=None), que basta para lo que aplicar_renombrados usa."""

    def __init__(self):
        self.valores = {}

    def cell(self, row, column, value=None):
        clave = (row, column)
        if value is not None:
            self.valores[clave] = value
        return _CeldaFake(self, clave)


class _CeldaFake:
    def __init__(self, ws, clave):
        self._ws = ws
        self._clave = clave

    @property
    def value(self):
        return self._ws.valores.get(self._clave)

    @value.setter
    def value(self, v):
        self._ws.valores[self._clave] = v


def test_aplicar_renombrados_renombra_y_actualiza_master(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "CFLI").mkdir()
    (tmp_path / "CFLI" / "factura_original.pdf").write_bytes(b"contenido")

    ws = _WsFake()
    filas = [{"fila": 5, "n_ref": "CFLI-003", "archivo_origen": "CFLI\\factura_original.pdf",
              "proveedor_tag": "Beckman", "fecha": "01/02/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 1
    assert advertencias == []
    assert ws.cell(row=5, column=15).value == "CFLI\\CFLI-003_Beckman_2026-02-01.pdf"
    assert ws.cell(row=5, column=16).value is not None
    assert (tmp_path / "CFLI" / "CFLI-003_Beckman_2026-02-01.pdf").exists()


def test_aplicar_renombrados_ya_correcto_no_cuenta_ni_toca_master(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "UMAG-001_Shell_2026-07-15.jpg").write_bytes(b"contenido")

    ws = _WsFake()
    filas = [{"fila": 2, "n_ref": "UMAG-001", "archivo_origen": "UMAG\\UMAG-001_Shell_2026-07-15.jpg",
              "proveedor_tag": "Shell", "fecha": "15/07/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 0
    assert advertencias == []
    assert ws.cell(row=2, column=15).value is None


def test_aplicar_renombrados_archivo_no_encontrado_genera_advertencia(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()

    ws = _WsFake()
    filas = [{"fila": 3, "n_ref": "UMAG-030", "archivo_origen": "UMAG\\NoExiste.jpg",
              "proveedor_tag": "Anwo", "fecha": "20/03/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 0
    assert len(advertencias) == 1
    assert advertencias[0]["n_ref"] == "UMAG-030"


def test_aplicar_renombrados_conversion_fallida_genera_advertencia(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "UMAG").mkdir()
    (tmp_path / "UMAG" / "corrupto.HEIC").write_bytes(b"no es un heic valido")

    ws = _WsFake()
    filas = [{"fila": 4, "n_ref": "UMAG-031", "archivo_origen": "UMAG\\corrupto.HEIC",
              "proveedor_tag": "Anwo", "fecha": "20/03/2026"}]

    renombrados, advertencias = acc.aplicar_renombrados(ws, filas, {})

    assert renombrados == 0
    assert len(advertencias) == 1
    assert advertencias[0]["n_ref"] == "UMAG-031"
    assert (tmp_path / "UMAG" / "corrupto.HEIC").exists()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: los 4 tests nuevos fallan con `AttributeError`; los 23 anteriores siguen pasando.

- [ ] **Step 3: Implementar `aplicar_renombrados`**

Agregar al final de la sección de renombrado en `auditor_centro_costos.py`:

```python
def aplicar_renombrados(ws_master, filas_master, reconciliacion_inversa):
    """Recorre filas_master, ejecuta los renombrados/conversiones pendientes y
    actualiza Master.Archivo origen (col 15) y Master.Fecha modificacion
    (col 16, con el mtime real del archivo resultante) en las filas afectadas.
    Excepcion deliberada a la regla de oro de "nunca tocar una fila ya
    escrita" -- mismo tipo de excepcion que migrar_columna_proveedor().
    Devuelve (cantidad_renombrados, advertencias)."""
    renombrados = 0
    advertencias = []

    for item in planificar_renombrados(filas_master, reconciliacion_inversa):
        if item["accion"] == "archivo_no_encontrado":
            advertencias.append({
                "n_ref": item["n_ref"],
                "detalle": "Archivo fisico no encontrado para renombrar/convertir.",
            })
            continue
        if item["accion"] == "ya_correcto":
            continue

        ok, error = ejecutar_plan_renombrado(item)
        if not ok:
            advertencias.append({
                "n_ref": item["n_ref"],
                "detalle": f"Fallo la conversion HEIC: {error}",
            })
            continue

        proyecto_fisico = item["ruta_nueva"].parent.name
        ws_master.cell(row=item["fila"], column=15, value=f"{proyecto_fisico}\\{item['nombre_nuevo']}")
        mtime = datetime.fromtimestamp(item["ruta_nueva"].stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        ws_master.cell(row=item["fila"], column=16, value=mtime)
        renombrados += 1

    return renombrados, advertencias
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: 27 passed.

- [ ] **Step 5: Integrar en `main()`**

En `auditor_centro_costos.py`, dentro de `main()`, localizar el bloque de PASO 8 (líneas 835-845):

```python
    print("\n--- PASO 8: Regenerar hojas de proyecto ---")
    ultima_master = fila_master - 1
    for proyecto in sorted(proyectos_tocados):
        filas_de_este_proyecto = [
            r for r in range(2, ultima_master + 1)
            if ws_master.cell(row=r, column=2).value == proyecto
        ]
        if not filas_de_este_proyecto:
            continue
        regenerar_hoja_proyecto(wb, proyecto, filas_de_este_proyecto, colores.get(proyecto))
        print(f"  [OK] Hoja '{proyecto}' regenerada ({len(filas_de_este_proyecto)} documento(s))")

    print("\n--- PASO 9: Formato final ---")
```

Insertar un nuevo paso entre ambos (reemplazar solo la línea `print("\n--- PASO 9: Formato final ---")` por el bloque siguiente, que la incluye renumerada):

```python
    print("\n--- PASO 9: Renombrar y convertir archivos ---")
    reconciliacion_inversa = construir_reconciliacion_inversa(reconciliacion)
    filas_master_actual, _, _ = leer_master(ws_master)
    renombrados, advertencias_renombrado = aplicar_renombrados(
        ws_master, filas_master_actual, reconciliacion_inversa
    )
    print(f"  [OK] {renombrados} archivo(s) renombrado(s)/convertido(s).")
    for adv in advertencias_renombrado:
        print(f"  [WARN] {adv['n_ref']}: {adv['detalle']}")

    print("\n--- PASO 10: Formato final ---")
```

Después de esta inserción, renumerar los pasos siguientes: buscar `print("\n--- PASO 10: Guardar ---")` (línea 856 original) y cambiarlo a `print("\n--- PASO 11: Guardar ---")`; buscar `print("\n--- PASO 11: Verificaciones aritmeticas (sobre todo el JSON) ---")` (línea 864 original) y cambiarlo a `print("\n--- PASO 12: Verificaciones aritmeticas (sobre todo el JSON) ---")`.

- [ ] **Step 6: Agregar sección al informe de auditoría y al resumen final**

En `auditor_centro_costos.py`, dentro de `main()`, localizar el bloque de la sección 4 del informe (líneas 895-901):

```python
    print("\n4. LIMITACIONES DE REGISTRO")
    if limitaciones:
        for lim in limitaciones:
            print(f"   * {lim['archivo']} | Proyecto: {lim['proyecto']}")
            print(f"     {lim['detalle']} Accion: {lim['accion']}")
    else:
        print("   Sin hallazgos.")
```

Agregar inmediatamente después (antes de `print("\n" + "-" * 70)`):

```python

    print("\n5. RENOMBRADO/CONVERSION DE ARCHIVOS")
    if advertencias_renombrado:
        for adv in advertencias_renombrado:
            print(f"   * {adv['n_ref']}: {adv['detalle']}")
    else:
        print("   Sin hallazgos.")
```

Localizar el resumen final (líneas 906-909):

```python
    print(f"  {'Documentos nuevos registrados:':<40} {registrados_ok}")
    print(f"  {'Documentos omitidos (ya registrados):':<40} {len(omitidos)}")
    print(f"  {'Posibles duplicados:':<40} {len(posibles_duplicados)}")
    print(f"  {'Limitaciones (faltan datos en JSON):':<40} {len(limitaciones)}")
```

Agregar una línea al final:

```python
    print(f"  {'Documentos nuevos registrados:':<40} {registrados_ok}")
    print(f"  {'Documentos omitidos (ya registrados):':<40} {len(omitidos)}")
    print(f"  {'Posibles duplicados:':<40} {len(posibles_duplicados)}")
    print(f"  {'Limitaciones (faltan datos en JSON):':<40} {len(limitaciones)}")
    print(f"  {'Archivos renombrados/convertidos:':<40} {renombrados}")
```

- [ ] **Step 7: Correr toda la suite y verificar que pasa**

Run: `python -m pytest tests/test_renombrado_fotos.py -v`
Expected: 27 passed.

- [ ] **Step 8: Commit**

```bash
git add auditor_centro_costos.py tests/test_renombrado_fotos.py
git commit -m "feat: integrar renombrado/conversion de archivos en el flujo principal"
```

---

### Task 6: Preview en `driver.py status`

**Files:**
- Modify: `.claude/skills/Registro_Centro_de_Costos/driver.py`
- Create: `tests/test_driver_preview_renombrados.py`

**Interfaces:**
- Consumes: `acc.construir_reconciliacion_inversa` (Task 2), `acc.planificar_renombrados` (Task 3) — vía el módulo `auditor_centro_costos` ya importado en `driver.py` como `acc`.
- Produces: `mostrar_preview_renombrados(filas_master: list[dict], reconciliacion: dict) -> None` en `driver.py` (imprime a stdout, no devuelve nada, no toca disco).

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_driver_preview_renombrados.py`:

```python
import importlib.util
import sys
from pathlib import Path

import auditor_centro_costos as acc

_DRIVER_PATH = (
    Path(__file__).resolve().parent.parent
    / ".claude" / "skills" / "Registro_Centro_de_Costos" / "driver.py"
)
_spec = importlib.util.spec_from_file_location("driver_bajo_prueba", _DRIVER_PATH)
driver = importlib.util.module_from_spec(_spec)
sys.modules["driver_bajo_prueba"] = driver
_spec.loader.exec_module(driver)


def test_mostrar_preview_renombrados_lista_pendientes_y_no_encontrados(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(acc, "RAIZ_DOCS", tmp_path)
    (tmp_path / "CFLI").mkdir()
    (tmp_path / "CFLI" / "factura_original.pdf").write_bytes(b"contenido")

    filas_master = [
        {"fila": 5, "n_ref": "CFLI-003", "archivo_origen": "CFLI\\factura_original.pdf",
         "proveedor_tag": "Beckman", "fecha": "01/02/2026"},
        {"fila": 9, "n_ref": "UMAG-030", "archivo_origen": "UMAG\\NoExiste.jpg",
         "proveedor_tag": "Anwo", "fecha": "20/03/2026"},
    ]

    driver.mostrar_preview_renombrados(filas_master, {})

    salida = capsys.readouterr().out
    assert "renombrarian/convertirian si corres 'run': 1" in salida
    assert "CFLI-003" in salida
    assert "factura_original.pdf -> CFLI-003_Beckman_2026-02-01.pdf" in salida
    assert "1 fila(s) sin archivo fisico encontrado" in salida
    assert "UMAG-030" in salida
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_driver_preview_renombrados.py -v`
Expected: FAIL — `AttributeError: module 'driver_bajo_prueba' has no attribute 'mostrar_preview_renombrados'`.

- [ ] **Step 3: Implementar `mostrar_preview_renombrados` y llamarla desde `cmd_status`**

En `driver.py`, agregar esta función nueva inmediatamente antes de `def cmd_status():` (línea 35):

```python
def mostrar_preview_renombrados(filas_master, reconciliacion):
    """Preview de status (solo lectura): que archivos se renombrarian/
    convertirian si se corriera 'run', sin tocar disco."""
    reconciliacion_inversa = acc.construir_reconciliacion_inversa(reconciliacion)
    planes = acc.planificar_renombrados(filas_master, reconciliacion_inversa)
    a_renombrar = [p for p in planes if p["accion"] in ("renombrar", "convertir_heic")]
    no_encontrados = [p for p in planes if p["accion"] == "archivo_no_encontrado"]

    print(f"\nArchivos que se renombrarian/convertirian si corres 'run': {len(a_renombrar)}")
    for p in a_renombrar:
        print(f"  - {p['n_ref']}: {p['ruta_actual'].name} -> {p['nombre_nuevo']} ({p['accion']})")

    if no_encontrados:
        print(f"\n[WARN] {len(no_encontrados)} fila(s) sin archivo fisico encontrado para renombrar:")
        for p in no_encontrados:
            print(f"  - {p['n_ref']}")
```

En `cmd_status()`, localizar el bloque de la verificación aritmética (líneas 105-112):

```python
    print("\nVerificación aritmética sobre TODO datos_extraidos.json (Neto vs IVA 19%):")
    inconsistencias = acc.verificar_aritmetica(datos_json)
    if inconsistencias:
        for inc in inconsistencias:
            print(f"  * Doc {inc['n_documento']} ({inc['archivo']}): "
                  f"Neto={inc['neto']:,} IVA={inc['iva']:,} esperado={inc['iva_esperado']:,}")
    else:
        print("  Sin inconsistencias.")
```

Agregar inmediatamente después (antes de `print("\n" + "=" * 70)` de cierre):

```python

    mostrar_preview_renombrados(filas_master, reconciliacion)
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_driver_preview_renombrados.py -v`
Expected: 1 passed.

- [ ] **Step 5: Correr toda la suite completa**

Run: `python -m pytest tests/ -v`
Expected: 28 passed.

- [ ] **Step 6: Commit**

```bash
git add ".claude/skills/Registro_Centro_de_Costos/driver.py" tests/test_driver_preview_renombrados.py
git commit -m "feat: previsualizar renombrado/conversion de archivos en status"
```

---

## Después de completar todas las tareas

Antes de correr `run` contra `Centro de Costos.xlsx` real:

1. Correr `/Registro_Centro_de_Costos status` y revisar la sección nueva de preview — confirmar que los nombres esperados se ven razonables para los 24 documentos del bootstrap y para cualquier documento pendiente.
2. Solo entonces correr `/Registro_Centro_de_Costos run`, y revisar la sección 5 del informe de auditoría (advertencias de renombrado) y el resumen final.
3. Actualizar `ERRORES.md` documentando la excepción a la regla de oro (igual que la migración de `Proveedor (Razón Social)`), y actualizar `CLAUDE.md` / `Formato Centro de Costos.md` si el formato de `Archivo origen` cambia de forma visible para el usuario.
