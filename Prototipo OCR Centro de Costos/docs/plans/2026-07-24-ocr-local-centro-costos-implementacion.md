# Prototipo OCR local para Centro de Costos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un prototipo Node.js aislado que lea comprobantes reales sin modificarlos, ejecute OCR local, extraiga datos, valide su coherencia y mida la precisión contra registros existentes sin escribir en producción.

**Architecture:** El prototipo separa seguridad de rutas, preprocesamiento, motor OCR, extracción, normalización, validación, salida y benchmark. Tesseract.js será el primer motor detrás de una interfaz intercambiable; todas las escrituras estarán confinadas a `Prototipo OCR Centro de Costos/salidas/`.

**Tech Stack:** Node.js 24, módulos ESM, `node:test`, Tesseract.js 6.0.1, Sharp 0.34.4, Ajv 8.17.1 y JSON Schema draft-07.

## Global Constraints

- Las fuentes productivas son de solo lectura.
- No modificar `Centro de Costos.xlsx`, `Sistema/datos_extraidos.json`, el visualizador ni documentos originales.
- No ejecutar el auditor productivo desde el prototipo.
- No copiar, mover ni renombrar facturas.
- No realizar llamadas a modelos generativos locales o remotos.
- El OCR normal debe funcionar sin red después de descargar y almacenar el modelo de idioma durante la preparación inicial.
- Todo archivo con texto OCR, montos, proveedores, rutas reales o resultados del benchmark debe quedar bajo `salidas/` y fuera de Git.
- Un documento nunca se registra automáticamente; el estado más favorable es `candidato_coherente`.
- Ante una ambigüedad crítica, clasificar como `requiere_revision` o `rechazado`.
- Usar `npm.cmd`, no `npm`, en PowerShell porque el wrapper `npm.ps1` está bloqueado por la política de ejecución observada.

---

## File Map

- `package.json`: dependencias fijadas, scripts y requisito de Node.
- `.gitignore`: exclusión de resultados, caché OCR y datos locales.
- `config/validaciones.json`: tolerancias y umbrales versionados.
- `config/proveedores.example.json`: formato de catálogo sin datos reales.
- `schemas/candidato.schema.json`: contrato estructural del resultado.
- `src/seguridad-rutas.js`: resolución y autorización de lecturas/escrituras.
- `src/escritura-atomica.js`: escritura JSON atómica confinada.
- `src/normalizar.js`: fechas, RUT y montos.
- `src/validar.js`: reglas críticas, advertencias y estado final.
- `src/preprocesar-imagen.js`: orientación y variantes de imagen con Sharp.
- `src/motores/tesseract.js`: adaptador OCR y caché local.
- `src/extraer-campos.js`: cabecera y evidencia.
- `src/extraer-items.js`: líneas de ítems y evidencia.
- `src/generar-candidato.js`: composición y validación de esquema.
- `src/procesar-documento.js`: orquestación de un archivo.
- `src/cli.js`: comandos públicos.
- `benchmark/cargar-verdad.js`: lectura de referencias existentes.
- `benchmark/dividir-corpus.js`: separación reproducible 70/30.
- `benchmark/metricas.js`: exactitud, falsos coherentes y tiempos.
- `benchmark/ejecutar.js`: procesamiento por lotes.
- `benchmark/informe.js`: informe anonimizado.
- `tests/`: pruebas unitarias e integración con datos sintéticos.

---

### Task 1: Scaffold seguro y confinamiento de escrituras

**Files:**
- Create: `Prototipo OCR Centro de Costos/package.json`
- Create: `Prototipo OCR Centro de Costos/.gitignore`
- Create: `Prototipo OCR Centro de Costos/config/validaciones.json`
- Create: `Prototipo OCR Centro de Costos/config/proveedores.example.json`
- Create: `Prototipo OCR Centro de Costos/src/seguridad-rutas.js`
- Create: `Prototipo OCR Centro de Costos/src/escritura-atomica.js`
- Create: `Prototipo OCR Centro de Costos/tests/seguridad-rutas.test.js`

**Interfaces:**
- Produces: `resolverFuente(rutaSolicitada): Promise<string>`
- Produces: `resolverSalida(rutaRelativa): string`
- Produces: `escribirJsonAtomico(rutaRelativa, valor): Promise<string>`

- [ ] **Step 1: Write failing path-confinement tests**

```js
// tests/seguridad-rutas.test.js
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { resolverSalida } from "../src/seguridad-rutas.js";

test("resolverSalida acepta una ruta dentro de salidas", () => {
  const result = resolverSalida("pruebas/doc-001.json");
  assert.match(result, /salidas[\\/]pruebas[\\/]doc-001\.json$/);
});

test("resolverSalida bloquea escapes fuera de salidas", () => {
  assert.throws(
    () => resolverSalida("../Centro de Costos/Excel/Centro de Costos.xlsx"),
    /fuera de la carpeta de salidas/
  );
});

test("resolverSalida bloquea rutas absolutas", () => {
  assert.throws(
    () => resolverSalida(path.resolve("archivo.json")),
    /ruta relativa/
  );
});
```

- [ ] **Step 2: Create the package manifest and run the failing test**

```json
{
  "name": "prototipo-ocr-centro-costos",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=24.0.0"
  },
  "scripts": {
    "test": "node --test",
    "test:unit": "node --test tests/*.test.js",
    "ocr": "node src/cli.js",
    "benchmark": "node benchmark/ejecutar.js",
    "benchmark:report": "node benchmark/informe.js"
  },
  "dependencies": {
    "ajv": "8.17.1",
    "sharp": "0.34.4",
    "tesseract.js": "6.0.1"
  }
}
```

Run:

```powershell
npm.cmd install
npm.cmd test
```

Expected: FAIL because `src/seguridad-rutas.js` does not exist.

- [ ] **Step 3: Implement confined paths**

```js
// src/seguridad-rutas.js
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUTPUT_ROOT = path.join(ROOT, "salidas");

function estaDentro(base, candidate) {
  const relative = path.relative(base, candidate);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

export async function resolverFuente(rutaSolicitada) {
  const absolute = path.resolve(rutaSolicitada);
  const info = await fs.stat(absolute);
  if (!info.isFile()) {
    throw new Error(`La fuente no es un archivo: ${absolute}`);
  }
  return absolute;
}

export function resolverSalida(rutaRelativa) {
  if (path.isAbsolute(rutaRelativa)) {
    throw new Error("La salida debe usar una ruta relativa");
  }
  const absolute = path.resolve(OUTPUT_ROOT, rutaRelativa);
  if (!estaDentro(OUTPUT_ROOT, absolute)) {
    throw new Error("Intento de escritura fuera de la carpeta de salidas");
  }
  return absolute;
}

export { ROOT, OUTPUT_ROOT };
```

```js
// src/escritura-atomica.js
import fs from "node:fs/promises";
import path from "node:path";
import { resolverSalida } from "./seguridad-rutas.js";

export async function escribirJsonAtomico(rutaRelativa, valor) {
  const destino = resolverSalida(rutaRelativa);
  const temporal = `${destino}.${process.pid}.tmp`;
  await fs.mkdir(path.dirname(destino), { recursive: true });
  await fs.writeFile(temporal, `${JSON.stringify(valor, null, 2)}\n`, "utf8");
  await fs.rename(temporal, destino);
  return destino;
}
```

- [ ] **Step 4: Add privacy exclusions and safe configuration**

```gitignore
# Datos reales y derivados: nunca versionar
salidas/

# Modelo de idioma y caché OCR descargados localmente
modelos/
.cache/

# Dependencias
node_modules/

# Archivos temporales
*.tmp
```

```json
{
  "tolerancia_clp": 2,
  "tolerancia_iva_porcentaje": 0.02,
  "confianza_critica_minima": 75,
  "fecha_minima": "2020-01-01",
  "fecha_maxima_dias_futuro": 1,
  "extensiones_admitidas": [".jpg", ".jpeg"]
}
```

```json
[
  {
    "rut": "11111111-1",
    "razon_social": "Proveedor de ejemplo",
    "tag": "Ejemplo",
    "aliases": ["PROVEEDOR EJEMPLO"]
  }
]
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
npm.cmd test
git check-ignore -v "Prototipo OCR Centro de Costos/salidas/prueba.json"
```

Expected: all tests PASS; `git check-ignore` points to the prototype `.gitignore`.

Commit:

```powershell
git add -- "Prototipo OCR Centro de Costos/package.json" "Prototipo OCR Centro de Costos/package-lock.json" "Prototipo OCR Centro de Costos/.gitignore" "Prototipo OCR Centro de Costos/config" "Prototipo OCR Centro de Costos/src/seguridad-rutas.js" "Prototipo OCR Centro de Costos/src/escritura-atomica.js" "Prototipo OCR Centro de Costos/tests/seguridad-rutas.test.js"
git commit -m "chore(ocr): crear scaffold local seguro"
```

---

### Task 2: Normalización y contrato JSON

**Files:**
- Create: `Prototipo OCR Centro de Costos/schemas/candidato.schema.json`
- Create: `Prototipo OCR Centro de Costos/src/normalizar.js`
- Create: `Prototipo OCR Centro de Costos/tests/normalizar.test.js`
- Create: `Prototipo OCR Centro de Costos/tests/schema.test.js`

**Interfaces:**
- Produces: `normalizarMonto(texto): number | null`
- Produces: `normalizarFecha(texto): string | null`
- Produces: `normalizarRut(texto): string | null`
- Produces: `validarRut(rut): boolean`

- [ ] **Step 1: Write failing normalization tests**

```js
// tests/normalizar.test.js
import test from "node:test";
import assert from "node:assert/strict";
import {
  normalizarMonto,
  normalizarFecha,
  normalizarRut,
  validarRut
} from "../src/normalizar.js";

test("normaliza montos CLP con símbolos y errores OCR frecuentes", () => {
  assert.equal(normalizarMonto("$ 1.234.567"), 1234567);
  assert.equal(normalizarMonto("12 345"), 12345);
  assert.equal(normalizarMonto("TOTAL: 9O.5OO"), 90500);
  assert.equal(normalizarMonto("sin monto"), null);
});

test("normaliza fechas chilenas sin aceptar fechas imposibles", () => {
  assert.equal(normalizarFecha("24/07/2026"), "2026-07-24");
  assert.equal(normalizarFecha("2026-07-24"), "2026-07-24");
  assert.equal(normalizarFecha("31/02/2026"), null);
});

test("normaliza y valida RUT", () => {
  assert.equal(normalizarRut("76.123.456-0"), "76123456-0");
  assert.equal(normalizarRut("RUT 12.345.678-5"), "12345678-5");
  assert.equal(validarRut("12345678-5"), true);
  assert.equal(validarRut("12345678-9"), false);
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
node --test tests/normalizar.test.js
```

Expected: FAIL because `src/normalizar.js` does not exist.

- [ ] **Step 3: Implement deterministic normalization**

```js
// src/normalizar.js
function fechaValida(year, month, day) {
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day;
}

export function normalizarMonto(texto) {
  if (texto === null || texto === undefined) return null;
  const cleaned = String(texto)
    .toUpperCase()
    .replace(/O/g, "0")
    .replace(/[^\d.,\s-]/g, "")
    .trim();
  const match = cleaned.match(/-?\d[\d.,\s]*/);
  if (!match) return null;
  const digits = match[0].replace(/[^\d-]/g, "");
  if (!/^-?\d+$/.test(digits)) return null;
  return Number.parseInt(digits, 10);
}

export function normalizarFecha(texto) {
  const value = String(texto ?? "").trim();
  let match = value.match(/\b(\d{2})[/-](\d{2})[/-](\d{4})\b/);
  let year;
  let month;
  let day;
  if (match) {
    day = Number(match[1]);
    month = Number(match[2]);
    year = Number(match[3]);
  } else {
    match = value.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
    if (!match) return null;
    year = Number(match[1]);
    month = Number(match[2]);
    day = Number(match[3]);
  }
  if (!fechaValida(year, month, day)) return null;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function normalizarRut(texto) {
  const match = String(texto ?? "")
    .toUpperCase()
    .replace(/\./g, "")
    .match(/(\d{7,8})-?([\dK])/);
  return match ? `${match[1]}-${match[2]}` : null;
}

export function validarRut(rut) {
  const normalized = normalizarRut(rut);
  if (!normalized) return false;
  const [body, supplied] = normalized.split("-");
  let sum = 0;
  let factor = 2;
  for (let index = body.length - 1; index >= 0; index -= 1) {
    sum += Number(body[index]) * factor;
    factor = factor === 7 ? 2 : factor + 1;
  }
  const remainder = 11 - (sum % 11);
  const expected = remainder === 11 ? "0" : remainder === 10 ? "K" : String(remainder);
  return supplied === expected;
}
```

- [ ] **Step 4: Define and test the candidate schema**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "required": ["id_prueba", "origen", "ocr", "campos", "items", "validacion", "candidato"],
  "properties": {
    "id_prueba": { "type": "string", "minLength": 12 },
    "origen": {
      "type": "object",
      "required": ["archivo", "proyecto", "sha256"],
      "properties": {
        "archivo": { "type": "string", "minLength": 1 },
        "proyecto": { "type": "string", "minLength": 1 },
        "sha256": { "type": "string", "pattern": "^[a-f0-9]{64}$" }
      },
      "additionalProperties": false
    },
    "ocr": {
      "type": "object",
      "required": ["motor", "version", "confianza", "texto", "duracion_ms"],
      "properties": {
        "motor": { "type": "string" },
        "version": { "type": "string" },
        "confianza": { "type": "number", "minimum": 0, "maximum": 100 },
        "texto": { "type": "string" },
        "duracion_ms": { "type": "number", "minimum": 0 }
      },
      "additionalProperties": true
    },
    "campos": { "type": "object" },
    "items": { "type": "array" },
    "validacion": {
      "type": "object",
      "required": ["estado", "reglas"],
      "properties": {
        "estado": {
          "enum": ["candidato_coherente", "requiere_revision", "rechazado"]
        },
        "reglas": { "type": "array" }
      },
      "additionalProperties": true
    },
    "candidato": { "type": "object" }
  }
}
```

```js
// tests/schema.test.js
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import Ajv from "ajv";

test("el esquema rechaza un resultado sin validación", () => {
  const schema = JSON.parse(fs.readFileSync("schemas/candidato.schema.json", "utf8"));
  const validate = new Ajv({ allErrors: true }).compile(schema);
  const valid = validate({ id_prueba: "123456789012" });
  assert.equal(valid, false);
  assert.ok(validate.errors.some((error) => error.params.missingProperty === "validacion"));
});
```

- [ ] **Step 5: Run all tests and commit**

Run:

```powershell
npm.cmd test
```

Expected: all tests PASS.

Commit:

```powershell
git add -- "Prototipo OCR Centro de Costos/schemas" "Prototipo OCR Centro de Costos/src/normalizar.js" "Prototipo OCR Centro de Costos/tests/normalizar.test.js" "Prototipo OCR Centro de Costos/tests/schema.test.js"
git commit -m "feat(ocr): normalizar campos y definir contrato"
```

---

### Task 3: Motor de validación coherente

**Files:**
- Create: `Prototipo OCR Centro de Costos/src/validar.js`
- Create: `Prototipo OCR Centro de Costos/tests/validar.test.js`

**Interfaces:**
- Consumes: normalized `campos`, `items`, `confianza`, `catalogo`, `existentes`, `config`
- Produces: `validarDocumento(input): { estado, reglas, errores, advertencias }`

- [ ] **Step 1: Write failing validation tests**

```js
// tests/validar.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { validarDocumento } from "../src/validar.js";

const config = {
  tolerancia_clp: 2,
  tolerancia_iva_porcentaje: 0.02,
  confianza_critica_minima: 75,
  fecha_minima: "2020-01-01",
  fecha_maxima_dias_futuro: 1
};

const base = {
  proyecto: "Proyecto Prueba",
  tipo_documento: "Factura",
  fecha: "2026-07-24",
  n_documento: "1001",
  proveedor: "Ejemplo",
  rut_proveedor: "12345678-5",
  neto: 10000,
  iva: 1900,
  total: 11900
};

test("clasifica coherente cuando todas las reglas críticas pasan", () => {
  const result = validarDocumento({
    campos: base,
    items: [{ total_sin_iva: 10000 }],
    confianza: 92,
    catalogo: [{ rut: "12345678-5", tag: "Ejemplo" }],
    existentes: [],
    config,
    hoy: "2026-07-24"
  });
  assert.equal(result.estado, "candidato_coherente");
  assert.equal(result.errores.length, 0);
});

test("nunca acepta una incoherencia monetaria", () => {
  const result = validarDocumento({
    campos: { ...base, total: 12000 },
    items: [{ total_sin_iva: 10000 }],
    confianza: 99,
    catalogo: [{ rut: "12345678-5", tag: "Ejemplo" }],
    existentes: [],
    config,
    hoy: "2026-07-24"
  });
  assert.equal(result.estado, "requiere_revision");
  assert.ok(result.errores.includes("neto_iva_total_no_concilian"));
});

test("detecta duplicado por proveedor, folio y monto", () => {
  const result = validarDocumento({
    campos: base,
    items: [{ total_sin_iva: 10000 }],
    confianza: 90,
    catalogo: [{ rut: "12345678-5", tag: "Ejemplo" }],
    existentes: [base],
    config,
    hoy: "2026-07-24"
  });
  assert.equal(result.estado, "requiere_revision");
  assert.ok(result.errores.includes("posible_duplicado"));
});
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
node --test tests/validar.test.js
```

Expected: FAIL because `src/validar.js` does not exist.

- [ ] **Step 3: Implement explicit validation rules**

```js
// src/validar.js
import { validarRut } from "./normalizar.js";

function dentroTolerancia(left, right, tolerance) {
  return Number.isFinite(left)
    && Number.isFinite(right)
    && Math.abs(left - right) <= tolerance;
}

function agregar(reglas, id, ok, severidad, detalle) {
  reglas.push({ id, ok, severidad, detalle });
}

export function validarDocumento({
  campos,
  items,
  confianza,
  catalogo,
  existentes,
  config,
  hoy
}) {
  const reglas = [];
  const proveedor = catalogo.find((entry) => entry.rut === campos.rut_proveedor);
  agregar(reglas, "proyecto_presente", Boolean(campos.proyecto), "critica", campos.proyecto);
  agregar(reglas, "proveedor_identificado", Boolean(proveedor), "critica", campos.rut_proveedor);
  agregar(reglas, "rut_valido", validarRut(campos.rut_proveedor), "critica", campos.rut_proveedor);
  agregar(reglas, "fecha_presente", Boolean(campos.fecha), "critica", campos.fecha);
  agregar(
    reglas,
    "fecha_en_rango",
    Boolean(campos.fecha)
      && campos.fecha >= config.fecha_minima
      && campos.fecha <= new Date(
        new Date(`${hoy}T00:00:00Z`).getTime() + config.fecha_maxima_dias_futuro * 86400000
      ).toISOString().slice(0, 10),
    "critica",
    campos.fecha
  );
  agregar(reglas, "folio_presente", Boolean(campos.n_documento), "critica", campos.n_documento);
  const montosPresentes = [campos.neto, campos.iva, campos.total].every(Number.isFinite);
  agregar(reglas, "montos_presentes", montosPresentes, "critica", null);
  agregar(
    reglas,
    "neto_iva_total_concilian",
    montosPresentes && dentroTolerancia(campos.neto + campos.iva, campos.total, config.tolerancia_clp),
    "critica",
    { neto: campos.neto, iva: campos.iva, total: campos.total }
  );
  const ivaEsperado = Number.isFinite(campos.neto) ? campos.neto * 0.19 : Number.NaN;
  const toleranciaIva = Number.isFinite(campos.neto)
    ? Math.max(config.tolerancia_clp, campos.neto * config.tolerancia_iva_porcentaje)
    : 0;
  agregar(
    reglas,
    "iva_compatible",
    campos.tipo_documento !== "Factura"
      || dentroTolerancia(campos.iva, ivaEsperado, toleranciaIva),
    "critica",
    { observado: campos.iva, esperado: ivaEsperado }
  );
  const sumaItems = items.reduce((sum, item) => sum + (item.total_sin_iva ?? 0), 0);
  agregar(
    reglas,
    "items_concilian_neto",
    items.length > 0 && dentroTolerancia(sumaItems, campos.neto, config.tolerancia_clp),
    "critica",
    { suma_items: sumaItems, neto: campos.neto }
  );
  const duplicado = existentes.some((entry) =>
    entry.rut_proveedor === campos.rut_proveedor
    && String(entry.n_documento) === String(campos.n_documento)
    && entry.total === campos.total
  );
  agregar(reglas, "sin_duplicado", !duplicado, "critica", duplicado);
  agregar(
    reglas,
    "confianza_critica",
    confianza >= config.confianza_critica_minima,
    "critica",
    confianza
  );

  const errorNames = {
    sin_duplicado: "posible_duplicado",
    neto_iva_total_concilian: "neto_iva_total_no_concilian",
    items_concilian_neto: "items_no_concilian_neto"
  };
  const errores = reglas.filter((rule) => rule.severidad === "critica" && !rule.ok)
    .map((rule) => errorNames[rule.id] ?? rule.id);
  const advertencias = reglas.filter((rule) => rule.severidad === "advertencia" && !rule.ok)
    .map((rule) => rule.id);
  const esenciales = ["proyecto_presente", "montos_presentes", "proveedor_identificado"];
  const rechazado = reglas.some((rule) => esenciales.includes(rule.id) && !rule.ok);
  return {
    estado: rechazado ? "rechazado" : errores.length > 0 ? "requiere_revision" : "candidato_coherente",
    reglas,
    errores,
    advertencias
  };
}
```

- [ ] **Step 4: Run tests and commit**

Run:

```powershell
npm.cmd test
```

Expected: all tests PASS.

Commit:

```powershell
git add -- "Prototipo OCR Centro de Costos/src/validar.js" "Prototipo OCR Centro de Costos/tests/validar.test.js"
git commit -m "feat(ocr): validar coherencia y duplicados"
```

---

### Task 4: Preprocesamiento y adaptador Tesseract

**Files:**
- Create: `Prototipo OCR Centro de Costos/src/preprocesar-imagen.js`
- Create: `Prototipo OCR Centro de Costos/src/motores/tesseract.js`
- Create: `Prototipo OCR Centro de Costos/tests/preprocesar-imagen.test.js`
- Create: `Prototipo OCR Centro de Costos/tests/fixtures/factura-sintetica.svg`

**Interfaces:**
- Produces: `preprocesarImagen(ruta): Promise<Array<{ nombre, buffer }>>`
- Produces: `crearMotorTesseract(options): Promise<{ reconocer(variantes), cerrar() }>`
- OCR result: `{ motor, version, confianza, texto, lineas, duracion_ms, variante }`

- [ ] **Step 1: Create a synthetic fixture and failing preprocessing test**

```xml
<!-- tests/fixtures/factura-sintetica.svg -->
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1600">
  <rect width="1200" height="1600" fill="white"/>
  <text x="80" y="140" font-family="Arial" font-size="52">FACTURA ELECTRONICA</text>
  <text x="80" y="240" font-family="Arial" font-size="42">RUT 12.345.678-5</text>
  <text x="80" y="320" font-family="Arial" font-size="42">FOLIO 1001</text>
  <text x="80" y="400" font-family="Arial" font-size="42">FECHA 24/07/2026</text>
  <text x="80" y="1150" font-family="Arial" font-size="42">NETO $ 10.000</text>
  <text x="80" y="1220" font-family="Arial" font-size="42">IVA $ 1.900</text>
  <text x="80" y="1290" font-family="Arial" font-size="42">TOTAL $ 11.900</text>
</svg>
```

```js
// tests/preprocesar-imagen.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { preprocesarImagen } from "../src/preprocesar-imagen.js";

test("genera variantes sin modificar la fuente", async () => {
  const variants = await preprocesarImagen("tests/fixtures/factura-sintetica.svg");
  assert.deepEqual(variants.map((entry) => entry.nombre), ["normalizada", "alto_contraste"]);
  assert.ok(variants.every((entry) => Buffer.isBuffer(entry.buffer)));
  assert.ok(variants.every((entry) => entry.buffer.length > 100));
});
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
node --test tests/preprocesar-imagen.test.js
```

Expected: FAIL because `src/preprocesar-imagen.js` does not exist.

- [ ] **Step 3: Implement two safe in-memory variants**

```js
// src/preprocesar-imagen.js
import sharp from "sharp";

export async function preprocesarImagen(ruta) {
  const base = sharp(ruta, { failOn: "error" })
    .rotate()
    .resize({ width: 2000, withoutEnlargement: true })
    .grayscale()
    .normalize();

  const normalizada = await base.clone().sharpen().png().toBuffer();
  const altoContraste = await base.clone()
    .linear(1.25, -18)
    .sharpen({ sigma: 1.2 })
    .png()
    .toBuffer();

  return [
    { nombre: "normalizada", buffer: normalizada },
    { nombre: "alto_contraste", buffer: altoContraste }
  ];
}
```

- [ ] **Step 4: Implement the OCR adapter with local cache**

```js
// src/motores/tesseract.js
import path from "node:path";
import { createWorker, OEM } from "tesseract.js";
import { ROOT } from "../seguridad-rutas.js";

export async function crearMotorTesseract({
  idioma = "spa",
  cachePath = path.join(ROOT, "modelos", "cache"),
  logger = () => {}
} = {}) {
  const worker = await createWorker(idioma, OEM.LSTM_ONLY, { cachePath, logger });

  return {
    async reconocer(variantes) {
      const started = performance.now();
      const results = [];
      for (const variante of variantes) {
        const { data } = await worker.recognize(variante.buffer);
        results.push({
          variante: variante.nombre,
          texto: data.text ?? "",
          confianza: Number(data.confidence ?? 0),
          lineas: data.blocks ?? []
        });
      }
      const best = results.sort((left, right) => right.confianza - left.confianza)[0];
      return {
        motor: "tesseract.js",
        version: "6.0.1",
        confianza: best.confianza,
        texto: best.texto,
        lineas: best.lineas,
        duracion_ms: Math.round(performance.now() - started),
        variante: best.variante
      };
    },
    async cerrar() {
      await worker.terminate();
    }
  };
}
```

- [ ] **Step 5: Run unit tests and one explicit model preparation OCR**

Run:

```powershell
npm.cmd test
node src/cli.js preparar-modelo
```

Expected: unit tests PASS. The first model preparation may access the network and creates only `modelos/cache/`; a second preparation succeeds using the local cache.

- [ ] **Step 6: Commit**

```powershell
git add -- "Prototipo OCR Centro de Costos/src/preprocesar-imagen.js" "Prototipo OCR Centro de Costos/src/motores/tesseract.js" "Prototipo OCR Centro de Costos/tests/preprocesar-imagen.test.js" "Prototipo OCR Centro de Costos/tests/fixtures/factura-sintetica.svg"
git commit -m "feat(ocr): agregar preprocesamiento y motor local"
```

---

### Task 5: Extracción trazable de cabecera e ítems

**Files:**
- Create: `Prototipo OCR Centro de Costos/src/extraer-campos.js`
- Create: `Prototipo OCR Centro de Costos/src/extraer-items.js`
- Create: `Prototipo OCR Centro de Costos/tests/extraer.test.js`
- Create: `Prototipo OCR Centro de Costos/tests/fixtures/ocr-factura.txt`

**Interfaces:**
- Consumes: OCR text and project from folder
- Produces: `extraerCampos({ texto, proyecto, catalogo }): CampoMap`
- Produces: `extraerItems({ texto }): Item[]`
- Field evidence: `{ original, valor, confianza, evidencia }`

- [ ] **Step 1: Add synthetic OCR text and failing extraction tests**

```text
FACTURA ELECTRONICA
PROVEEDOR EJEMPLO SPA
RUT 12.345.678-5
FOLIO 1001
FECHA 24/07/2026
DETALLE
2 FILTRO INDUSTRIAL 5.000 10.000
NETO $ 10.000
IVA 19% $ 1.900
TOTAL $ 11.900
```

```js
// tests/extraer.test.js
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { extraerCampos } from "../src/extraer-campos.js";
import { extraerItems } from "../src/extraer-items.js";

const texto = fs.readFileSync("tests/fixtures/ocr-factura.txt", "utf8");
const catalogo = [{
  rut: "12345678-5",
  razon_social: "Proveedor Ejemplo SpA",
  tag: "Ejemplo",
  aliases: ["PROVEEDOR EJEMPLO"]
}];

test("extrae cabecera con evidencia", () => {
  const fields = extraerCampos({ texto, proyecto: "Proyecto Prueba", catalogo });
  assert.equal(fields.fecha.valor, "2026-07-24");
  assert.equal(fields.n_documento.valor, "1001");
  assert.equal(fields.rut_proveedor.valor, "12345678-5");
  assert.equal(fields.neto.valor, 10000);
  assert.equal(fields.iva.valor, 1900);
  assert.equal(fields.total.valor, 11900);
  assert.match(fields.total.evidencia, /TOTAL/);
});

test("extrae línea de ítem con cantidad, unitario y total", () => {
  const items = extraerItems({ texto });
  assert.deepEqual(items, [{
    nombre_item: "FILTRO INDUSTRIAL",
    descripcion: "FILTRO INDUSTRIAL",
    categoria_item: null,
    cantidad: 2,
    p_unitario_sin_iva: 5000,
    total_sin_iva: 10000,
    total_con_iva: null,
    confianza: 80,
    evidencia: "2 FILTRO INDUSTRIAL 5.000 10.000"
  }]);
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
node --test tests/extraer.test.js
```

Expected: FAIL because the extraction modules do not exist.

- [ ] **Step 3: Implement evidence-first header extraction**

```js
// src/extraer-campos.js
import { normalizarFecha, normalizarMonto, normalizarRut } from "./normalizar.js";

function buscar(texto, expression, normalizer = (value) => value.trim()) {
  const match = texto.match(expression);
  if (!match) return { original: null, valor: null, confianza: 0, evidencia: null };
  return {
    original: match[1],
    valor: normalizer(match[1]),
    confianza: 85,
    evidencia: match[0].trim()
  };
}

export function extraerCampos({ texto, proyecto, catalogo }) {
  const rut = buscar(texto, /RUT\s*:?\s*([\d.K-]+)/i, normalizarRut);
  const supplier = catalogo.find((entry) =>
    entry.rut === rut.valor
    || entry.aliases.some((alias) => texto.toUpperCase().includes(alias.toUpperCase()))
  );
  return {
    proyecto: { original: proyecto, valor: proyecto, confianza: 100, evidencia: "carpeta_origen" },
    tipo_documento: buscar(texto, /\b(FACTURA|BOLETA|GUIA DE DESPACHO)\b/i, (value) =>
      value.toUpperCase().startsWith("FACTURA") ? "Factura"
        : value.toUpperCase().startsWith("BOLETA") ? "Boleta"
          : "Guía de Despacho"
    ),
    fecha: buscar(texto, /(?:FECHA|EMISION)\s*:?\s*(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}-\d{2}-\d{2})/i, normalizarFecha),
    n_documento: buscar(texto, /(?:FOLIO|N[°ºO.]*)\s*:?\s*(\d{1,20})/i),
    rut_proveedor: rut,
    proveedor: {
      original: supplier?.razon_social ?? null,
      valor: supplier?.tag ?? null,
      confianza: supplier ? 95 : 0,
      evidencia: supplier ? `catalogo:${supplier.rut}` : null
    },
    razon_social: {
      original: supplier?.razon_social ?? null,
      valor: supplier?.razon_social ?? null,
      confianza: supplier ? 95 : 0,
      evidencia: supplier ? `catalogo:${supplier.rut}` : null
    },
    neto: buscar(texto, /NETO\s*:?\s*\$?\s*([\d.Oo.,\s]+)/i, normalizarMonto),
    iva: buscar(texto, /IVA(?:\s*19%)?\s*:?\s*\$?\s*([\d.Oo.,\s]+)/i, normalizarMonto),
    total: buscar(texto, /TOTAL\s*:?\s*\$?\s*([\d.Oo.,\s]+)/i, normalizarMonto)
  };
}
```

- [ ] **Step 4: Implement conservative item extraction**

```js
// src/extraer-items.js
import { normalizarMonto } from "./normalizar.js";

const ITEM_LINE = /^\s*(\d+(?:[.,]\d+)?)\s+(.+?)\s+(\$?\s*[\d.Oo.]+)\s+(\$?\s*[\d.Oo.]+)\s*$/;

export function extraerItems({ texto }) {
  const items = [];
  for (const rawLine of texto.split(/\r?\n/)) {
    const match = rawLine.match(ITEM_LINE);
    if (!match) continue;
    const cantidad = Number(match[1].replace(",", "."));
    const unitario = normalizarMonto(match[3]);
    const total = normalizarMonto(match[4]);
    if (!Number.isFinite(cantidad) || !Number.isFinite(unitario) || !Number.isFinite(total)) continue;
    items.push({
      nombre_item: match[2].trim(),
      descripcion: match[2].trim(),
      categoria_item: null,
      cantidad,
      p_unitario_sin_iva: unitario,
      total_sin_iva: total,
      total_con_iva: null,
      confianza: Math.abs(cantidad * unitario - total) <= 2 ? 80 : 55,
      evidencia: rawLine.trim()
    });
  }
  return items;
}
```

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
npm.cmd test
```

Expected: all tests PASS.

Commit:

```powershell
git add -- "Prototipo OCR Centro de Costos/src/extraer-campos.js" "Prototipo OCR Centro de Costos/src/extraer-items.js" "Prototipo OCR Centro de Costos/tests/extraer.test.js" "Prototipo OCR Centro de Costos/tests/fixtures/ocr-factura.txt"
git commit -m "feat(ocr): extraer cabecera e items con evidencia"
```

---

### Task 6: Orquestación, esquema y CLI sin importación productiva

**Files:**
- Create: `Prototipo OCR Centro de Costos/src/generar-candidato.js`
- Create: `Prototipo OCR Centro de Costos/src/procesar-documento.js`
- Create: `Prototipo OCR Centro de Costos/src/cli.js`
- Create: `Prototipo OCR Centro de Costos/tests/procesar-documento.test.js`

**Interfaces:**
- Produces: `generarCandidato(input): ResultadoOCR`
- Produces: `procesarDocumento(options): Promise<{ resultado, rutaSalida }>`
- CLI commands: `preparar-modelo`, `procesar --archivo <path> --proyecto <name> --catalogo <path>`

- [ ] **Step 1: Write failing orchestration test with a fake OCR engine**

```js
// tests/procesar-documento.test.js
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { procesarDocumento } from "../src/procesar-documento.js";

test("procesa una fuente sintética y solo escribe bajo salidas", async () => {
  const fakeEngine = {
    async reconocer() {
      return {
        motor: "fake",
        version: "1",
        confianza: 95,
        texto: [
          "FACTURA",
          "RUT 12.345.678-5",
          "FOLIO 1001",
          "FECHA 24/07/2026",
          "2 FILTRO INDUSTRIAL 5.000 10.000",
          "NETO 10.000",
          "IVA 1.900",
          "TOTAL 11.900"
        ].join("\n"),
        lineas: [],
        duracion_ms: 1,
        variante: "fake"
      };
    }
  };
  const result = await procesarDocumento({
    archivo: "tests/fixtures/factura-sintetica.svg",
    proyecto: "Proyecto Prueba",
    catalogo: [{
      rut: "12345678-5",
      razon_social: "Proveedor Ejemplo SpA",
      tag: "Ejemplo",
      aliases: []
    }],
    existentes: [],
    motor: fakeEngine,
    config: {
      tolerancia_clp: 2,
      tolerancia_iva_porcentaje: 0.02,
      confianza_critica_minima: 75,
      fecha_minima: "2020-01-01",
      fecha_maxima_dias_futuro: 1
    },
    hoy: "2026-07-24",
    salida: "tests/factura-sintetica.json"
  });
  assert.equal(result.resultado.validacion.estado, "candidato_coherente");
  assert.match(result.rutaSalida, /salidas[\\/]tests[\\/]factura-sintetica\.json$/);
  assert.equal(path.isAbsolute(result.rutaSalida), true);
});
```

- [ ] **Step 2: Run the test and confirm failure**

Run:

```powershell
node --test tests/procesar-documento.test.js
```

Expected: FAIL because `src/procesar-documento.js` does not exist.

- [ ] **Step 3: Implement candidate composition and schema validation**

```js
// src/generar-candidato.js
import fs from "node:fs";
import Ajv from "ajv";
import { validarDocumento } from "./validar.js";

const schema = JSON.parse(fs.readFileSync(
  new URL("../schemas/candidato.schema.json", import.meta.url),
  "utf8"
));
const validateSchema = new Ajv({ allErrors: true }).compile(schema);

export function generarCandidato({
  idPrueba,
  origen,
  ocr,
  camposConEvidencia,
  items,
  catalogo,
  existentes,
  config,
  hoy
}) {
  const campos = Object.fromEntries(
    Object.entries(camposConEvidencia).map(([key, value]) => [key, value.valor])
  );
  const confianzaCampos = Object.values(camposConEvidencia)
    .filter((field) => field.valor !== null)
    .map((field) => field.confianza);
  const confianza = Math.min(ocr.confianza, ...confianzaCampos);
  const validacion = validarDocumento({
    campos,
    items,
    confianza,
    catalogo,
    existentes,
    config,
    hoy
  });
  const result = {
    id_prueba: idPrueba,
    origen,
    ocr,
    campos: camposConEvidencia,
    items,
    validacion,
    candidato: {
      archivo: origen.archivo,
      proyecto: campos.proyecto,
      fecha: campos.fecha,
      n_documento: campos.n_documento,
      tipo_documento: campos.tipo_documento,
      proveedor: campos.proveedor,
      proveedor_razon_social: campos.razon_social,
      rut_proveedor: campos.rut_proveedor,
      neto: campos.neto,
      iva: campos.iva,
      total: campos.total,
      items
    }
  };
  if (!validateSchema(result)) {
    throw new Error(`Resultado fuera de esquema: ${JSON.stringify(validateSchema.errors)}`);
  }
  return result;
}
```

- [ ] **Step 4: Implement the single-document pipeline**

```js
// src/procesar-documento.js
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { resolverFuente } from "./seguridad-rutas.js";
import { escribirJsonAtomico } from "./escritura-atomica.js";
import { preprocesarImagen } from "./preprocesar-imagen.js";
import { extraerCampos } from "./extraer-campos.js";
import { extraerItems } from "./extraer-items.js";
import { generarCandidato } from "./generar-candidato.js";

export async function procesarDocumento(options) {
  const source = await resolverFuente(options.archivo);
  const original = await fs.readFile(source);
  const sha256 = crypto.createHash("sha256").update(original).digest("hex");
  const variantes = await preprocesarImagen(source);
  const ocr = await options.motor.reconocer(variantes);
  const campos = extraerCampos({
    texto: ocr.texto,
    proyecto: options.proyecto,
    catalogo: options.catalogo
  });
  const items = extraerItems({ texto: ocr.texto });
  const idPrueba = `${sha256.slice(0, 12)}-${Date.now()}`;
  const resultado = generarCandidato({
    idPrueba,
    origen: {
      archivo: path.basename(source),
      proyecto: options.proyecto,
      sha256
    },
    ocr,
    camposConEvidencia: campos,
    items,
    catalogo: options.catalogo,
    existentes: options.existentes,
    config: options.config,
    hoy: options.hoy
  });
  const rutaSalida = await escribirJsonAtomico(options.salida, resultado);
  return { resultado, rutaSalida };
}
```

- [ ] **Step 5: Implement a minimal CLI with no production import command**

```js
// src/cli.js
import fs from "node:fs/promises";
import path from "node:path";
import { crearMotorTesseract } from "./motores/tesseract.js";
import { procesarDocumento } from "./procesar-documento.js";

function argumento(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : null;
}

async function leerJson(ruta) {
  return JSON.parse(await fs.readFile(ruta, "utf8"));
}

async function main() {
  const command = process.argv[2];
  const motor = await crearMotorTesseract();
  try {
    if (command === "preparar-modelo") {
      console.log("Modelo OCR español preparado en la caché local.");
      return;
    }
    if (command !== "procesar") {
      throw new Error("Uso: preparar-modelo | procesar --archivo RUTA --proyecto NOMBRE --catalogo RUTA");
    }
    const archivo = argumento("--archivo");
    const proyecto = argumento("--proyecto");
    const catalogoPath = argumento("--catalogo");
    if (!archivo || !proyecto || !catalogoPath) {
      throw new Error("Faltan --archivo, --proyecto o --catalogo");
    }
    const config = await leerJson(new URL("../config/validaciones.json", import.meta.url));
    const catalogo = await leerJson(catalogoPath);
    const salida = path.join("documentos", `${path.parse(archivo).name}.json`);
    const { resultado, rutaSalida } = await procesarDocumento({
      archivo,
      proyecto,
      catalogo,
      existentes: [],
      motor,
      config,
      hoy: new Date().toISOString().slice(0, 10),
      salida
    });
    console.log(`${resultado.validacion.estado}: ${rutaSalida}`);
  } finally {
    await motor.cerrar();
  }
}

main().catch((error) => {
  console.error(`[ERROR] ${error.message}`);
  process.exitCode = 1;
});
```

- [ ] **Step 6: Run tests and verify the CLI exposes no import**

Run:

```powershell
npm.cmd test
node src/cli.js
rg -n -i "importar|datos_extraidos|auditor_centro_costos" src
```

Expected: tests PASS; CLI prints only its allowed usage; `rg` finds no production import or auditor invocation.

- [ ] **Step 7: Commit**

```powershell
git add -- "Prototipo OCR Centro de Costos/src/generar-candidato.js" "Prototipo OCR Centro de Costos/src/procesar-documento.js" "Prototipo OCR Centro de Costos/src/cli.js" "Prototipo OCR Centro de Costos/tests/procesar-documento.test.js"
git commit -m "feat(ocr): procesar candidatos sin escritura productiva"
```

---

### Task 7: Verdad de referencia y división reproducible

**Files:**
- Create: `Prototipo OCR Centro de Costos/benchmark/cargar-verdad.js`
- Create: `Prototipo OCR Centro de Costos/benchmark/dividir-corpus.js`
- Create: `Prototipo OCR Centro de Costos/tests/benchmark-fuentes.test.js`

**Interfaces:**
- Produces: `cargarVerdad({ snapshot, datosActuales, datosLegado }): Promise<TruthDoc[]>`
- Produces: `dividirCorpus(documentos, seed): { ajuste, evaluacion }`

- [ ] **Step 1: Write failing tests with synthetic reference files**

```js
// tests/benchmark-fuentes.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { dividirCorpus } from "../benchmark/dividir-corpus.js";

test("la división es reproducible y no solapa documentos", () => {
  const docs = Array.from({ length: 10 }, (_, index) => ({
    id: `doc-${index}`,
    proveedor: `p-${index % 3}`
  }));
  const first = dividirCorpus(docs, "quempin-ocr-v1");
  const second = dividirCorpus(docs, "quempin-ocr-v1");
  assert.deepEqual(first, second);
  assert.equal(first.ajuste.length, 7);
  assert.equal(first.evaluacion.length, 3);
  const ids = new Set([...first.ajuste, ...first.evaluacion].map((doc) => doc.id));
  assert.equal(ids.size, 10);
});
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
node --test tests/benchmark-fuentes.test.js
```

Expected: FAIL because benchmark modules do not exist.

- [ ] **Step 3: Implement deterministic stratified splitting**

```js
// benchmark/dividir-corpus.js
import crypto from "node:crypto";

function score(seed, value) {
  return crypto.createHash("sha256").update(`${seed}:${value}`).digest("hex");
}

export function dividirCorpus(documentos, seed) {
  const groups = Map.groupBy(documentos, (doc) => doc.proveedor ?? "sin-proveedor");
  const ajuste = [];
  const evaluacion = [];
  for (const group of groups.values()) {
    const ordered = [...group].sort((left, right) =>
      score(seed, left.id).localeCompare(score(seed, right.id))
    );
    const evaluationCount = Math.max(1, Math.round(ordered.length * 0.3));
    evaluacion.push(...ordered.slice(0, evaluationCount));
    ajuste.push(...ordered.slice(evaluationCount));
  }
  const targetEvaluation = Math.round(documentos.length * 0.3);
  while (evaluacion.length > targetEvaluation) ajuste.push(evaluacion.pop());
  while (evaluacion.length < targetEvaluation && ajuste.length > 0) evaluacion.push(ajuste.pop());
  return { ajuste, evaluacion };
}
```

- [ ] **Step 4: Implement read-only truth loading**

```js
// benchmark/cargar-verdad.js
import fs from "node:fs/promises";

async function leerJson(ruta) {
  return JSON.parse(await fs.readFile(ruta, "utf8"));
}

function indexarPorDocumento(entries) {
  return new Map(entries
    .filter((entry) => entry.n_documento || entry.numero_documento)
    .map((entry) => [String(entry.n_documento ?? entry.numero_documento), entry]));
}

export async function cargarVerdad({ snapshot, datosActuales, datosLegado }) {
  const [snapshotData, currentData, legacyData] = await Promise.all([
    leerJson(snapshot),
    leerJson(datosActuales),
    leerJson(datosLegado)
  ]);
  const currentByNumber = indexarPorDocumento(currentData);
  const legacyByNumber = indexarPorDocumento(legacyData);
  return snapshotData.documentos.map((doc) => {
    const source = currentByNumber.get(String(doc.n_documento))
      ?? legacyByNumber.get(String(doc.n_documento))
      ?? {};
    return {
      id: doc.ref,
      archivo: doc.archivo_origen,
      proyecto: doc.proyecto,
      proveedor: doc.proveedor_tag,
      razon_social: doc.proveedor_razon_social,
      rut_proveedor: source.rut_proveedor ?? source.rut ?? null,
      fecha: doc.fecha,
      n_documento: String(doc.n_documento),
      neto: doc.total_sin_iva,
      iva: doc.iva,
      total: doc.total_con_iva,
      items: doc.items
    };
  }).filter((doc) => doc.archivo);
}
```

- [ ] **Step 5: Add a source-integrity test**

Add to `tests/benchmark-fuentes.test.js`:

```js
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { cargarVerdad } from "../benchmark/cargar-verdad.js";

test("carga verdad sin modificar las fuentes", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "ocr-truth-"));
  const snapshot = path.join(dir, "snapshot.json");
  const current = path.join(dir, "current.json");
  const legacy = path.join(dir, "legacy.json");
  await fs.writeFile(snapshot, JSON.stringify({
    documentos: [{
      ref: "TEST-001",
      archivo_origen: "doc.jpg",
      proyecto: "Prueba",
      proveedor_tag: "Ejemplo",
      proveedor_razon_social: "Proveedor Ejemplo",
      fecha: "2026-07-24",
      n_documento: "1001",
      total_sin_iva: 10000,
      iva: 1900,
      total_con_iva: 11900,
      items: []
    }]
  }));
  await fs.writeFile(current, JSON.stringify([{ n_documento: "1001", rut_proveedor: "12345678-5" }]));
  await fs.writeFile(legacy, "[]");
  const before = await Promise.all([snapshot, current, legacy].map((file) => fs.readFile(file, "utf8")));
  const truth = await cargarVerdad({ snapshot, datosActuales: current, datosLegado: legacy });
  const after = await Promise.all([snapshot, current, legacy].map((file) => fs.readFile(file, "utf8")));
  assert.equal(truth[0].rut_proveedor, "12345678-5");
  assert.deepEqual(after, before);
});
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
npm.cmd test
```

Expected: all tests PASS.

Commit:

```powershell
git add -- "Prototipo OCR Centro de Costos/benchmark/cargar-verdad.js" "Prototipo OCR Centro de Costos/benchmark/dividir-corpus.js" "Prototipo OCR Centro de Costos/tests/benchmark-fuentes.test.js"
git commit -m "feat(ocr): preparar benchmark reproducible"
```

---

### Task 8: Métricas, ejecución del benchmark e informe

**Files:**
- Create: `Prototipo OCR Centro de Costos/benchmark/metricas.js`
- Create: `Prototipo OCR Centro de Costos/benchmark/ejecutar.js`
- Create: `Prototipo OCR Centro de Costos/benchmark/informe.js`
- Create: `Prototipo OCR Centro de Costos/tests/metricas.test.js`
- Modify: `Prototipo OCR Centro de Costos/README.md`

**Interfaces:**
- Produces: `calcularMetricas(pares): BenchmarkMetrics`
- Produces: `generarInforme(metricas): string`
- Reads production sources; writes only `salidas/benchmark/`

- [ ] **Step 1: Write failing metric tests**

```js
// tests/metricas.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { calcularMetricas } from "../benchmark/metricas.js";

test("cuenta falsos coherentes y exactitud de montos", () => {
  const metrics = calcularMetricas([{
    verdad: { proveedor: "A", fecha: "2026-07-24", n_documento: "1", neto: 100, iva: 19, total: 119, items: [] },
    resultado: {
      candidato: { proveedor: "A", fecha: "2026-07-24", n_documento: "1", neto: 100, iva: 19, total: 120, items: [] },
      validacion: { estado: "candidato_coherente" },
      ocr: { duracion_ms: 100 }
    }
  }]);
  assert.equal(metrics.documentos, 1);
  assert.equal(metrics.exactitud_total, 0);
  assert.equal(metrics.falsos_coherentes, 1);
  assert.equal(metrics.tokens_externos, 0);
});
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```powershell
node --test tests/metricas.test.js
```

Expected: FAIL because `benchmark/metricas.js` does not exist.

- [ ] **Step 3: Implement metrics and acceptance decision**

```js
// benchmark/metricas.js
function ratio(pairs, field) {
  if (pairs.length === 0) return 0;
  return pairs.filter(({ verdad, resultado }) =>
    String(resultado.candidato[field] ?? "") === String(verdad[field] ?? "")
  ).length / pairs.length;
}

function itemSignature(item) {
  return JSON.stringify({
    nombre_item: String(item.nombre_item ?? "").trim().toUpperCase(),
    cantidad: Number(item.cantidad ?? 0),
    p_unitario_sin_iva: Number(item.p_unitario_sin_iva ?? 0),
    total_sin_iva: Number(item.total_sin_iva ?? 0)
  });
}

export function calcularMetricas(pares) {
  const falsosCoherentes = pares.filter(({ verdad, resultado }) => {
    if (resultado.validacion.estado !== "candidato_coherente") return false;
    return ["proveedor", "fecha", "n_documento", "neto", "iva", "total"]
      .some((field) => String(resultado.candidato[field] ?? "") !== String(verdad[field] ?? ""));
  }).length;
  const coherentCount = pares.filter(({ resultado }) =>
    resultado.validacion.estado === "candidato_coherente"
  ).length;
  const itemMatches = pares.filter(({ verdad, resultado }) => {
    const expected = (verdad.items ?? []).map(itemSignature);
    const observed = (resultado.candidato.items ?? []).map(itemSignature);
    return JSON.stringify(observed) === JSON.stringify(expected);
  }).length;
  const monetaryErrors = pares.filter(({ verdad, resultado }) =>
    ["neto", "iva", "total"].some((field) =>
      Number(resultado.candidato[field]) !== Number(verdad[field])
    )
  );
  const monetaryErrorsDetected = monetaryErrors.filter(({ resultado }) =>
    resultado.validacion.estado !== "candidato_coherente"
  ).length;
  const sortedTimes = pares.map(({ resultado }) => resultado.ocr.duracion_ms).sort((a, b) => a - b);
  const p95Index = Math.max(0, Math.ceil(sortedTimes.length * 0.95) - 1);
  return {
    documentos: pares.length,
    exactitud_proveedor: ratio(pares, "proveedor"),
    exactitud_fecha: ratio(pares, "fecha"),
    exactitud_folio: ratio(pares, "n_documento"),
    exactitud_neto: ratio(pares, "neto"),
    exactitud_iva: ratio(pares, "iva"),
    exactitud_total: ratio(pares, "total"),
    exactitud_items: pares.length ? itemMatches / pares.length : 0,
    deteccion_incoherencias_monetarias: monetaryErrors.length
      ? monetaryErrorsDetected / monetaryErrors.length
      : 1,
    candidatos_coherentes: pares.length ? coherentCount / pares.length : 0,
    falsos_coherentes: falsosCoherentes,
    tiempo_p95_ms: sortedTimes[p95Index] ?? 0,
    tokens_externos: 0
  };
}

export function cumpleCriterios(metrics) {
  const criticalAccuracy = Math.min(
    metrics.exactitud_proveedor,
    metrics.exactitud_fecha,
    metrics.exactitud_folio,
    metrics.exactitud_neto,
    metrics.exactitud_iva,
    metrics.exactitud_total
  );
  return {
    aprobado: metrics.falsos_coherentes === 0
      && criticalAccuracy >= 0.95
      && metrics.exactitud_items >= 0.85
      && metrics.deteccion_incoherencias_monetarias === 1
      && metrics.candidatos_coherentes >= 0.60
      && metrics.tokens_externos === 0,
    exactitud_critica_minima: criticalAccuracy
  };
}
```

- [ ] **Step 4: Implement batch execution with per-document isolation**

```js
// benchmark/ejecutar.js
import fs from "node:fs/promises";
import path from "node:path";
import { cargarVerdad } from "./cargar-verdad.js";
import { dividirCorpus } from "./dividir-corpus.js";
import { calcularMetricas, cumpleCriterios } from "./metricas.js";
import { crearMotorTesseract } from "../src/motores/tesseract.js";
import { procesarDocumento } from "../src/procesar-documento.js";
import { escribirJsonAtomico } from "../src/escritura-atomica.js";

const workspace = path.resolve("..");
const cc = path.join(workspace, "Centro de Costos");
const sources = {
  snapshot: path.join(cc, "Visualizador Web", "data", "centro-de-costos.json"),
  datosActuales: path.join(cc, "Sistema", "datos_extraidos.json"),
  datosLegado: path.join(cc, "Sistema", "Legado", "datos_extraidos_legacy_umag.json")
};

async function main() {
  const truth = await cargarVerdad(sources);
  const split = dividirCorpus(truth, "quempin-ocr-v1");
  const setName = process.argv.includes("--evaluacion") ? "evaluacion" : "ajuste";
  const selected = split[setName];
  const config = JSON.parse(await fs.readFile("config/validaciones.json", "utf8"));
  const catalogo = JSON.parse(await fs.readFile("salidas/config/proveedores.json", "utf8"));
  const motor = await crearMotorTesseract();
  const pairs = [];
  const failures = [];
  try {
    for (const verdad of selected) {
      try {
        const image = path.join(
          cc,
          "Sitio de comunicación - Centro de Costos 1",
          "Facturas y Boletas",
          verdad.proyecto,
          verdad.archivo
        );
        const processed = await procesarDocumento({
          archivo: image,
          proyecto: verdad.proyecto,
          catalogo,
          existentes: truth.filter((entry) => entry.id !== verdad.id),
          motor,
          config,
          hoy: new Date().toISOString().slice(0, 10),
          salida: path.join("benchmark", setName, `${verdad.id}.json`)
        });
        pairs.push({ verdad, resultado: processed.resultado });
      } catch (error) {
        failures.push({ id: verdad.id, error: error.message });
      }
    }
  } finally {
    await motor.cerrar();
  }
  const metrics = calcularMetricas(pairs);
  await escribirJsonAtomico(`benchmark/${setName}-resumen.json`, {
    set: setName,
    metrics,
    decision: cumpleCriterios(metrics),
    failures
  });
  if (failures.length > 0) process.exitCode = 2;
}

main().catch((error) => {
  console.error(`[ERROR] ${error.message}`);
  process.exitCode = 1;
});
```

- [ ] **Step 5: Implement an anonymized Markdown report**

```js
// benchmark/informe.js
import fs from "node:fs/promises";
import { escribirJsonAtomico } from "../src/escritura-atomica.js";

function porcentaje(value) {
  return `${(value * 100).toFixed(1)}%`;
}

export function generarInforme(summary) {
  const m = summary.metrics;
  return [
    "# Informe del benchmark OCR local",
    "",
    `Conjunto: ${summary.set}`,
    `Documentos evaluados: ${m.documentos}`,
    `Decisión: ${summary.decision.aprobado ? "APROBADO" : "NO APROBADO"}`,
    "",
    "| Métrica | Resultado |",
    "|---|---:|",
    `| Exactitud proveedor | ${porcentaje(m.exactitud_proveedor)} |`,
    `| Exactitud fecha | ${porcentaje(m.exactitud_fecha)} |`,
    `| Exactitud folio | ${porcentaje(m.exactitud_folio)} |`,
    `| Exactitud neto | ${porcentaje(m.exactitud_neto)} |`,
    `| Exactitud IVA | ${porcentaje(m.exactitud_iva)} |`,
    `| Exactitud total | ${porcentaje(m.exactitud_total)} |`,
    `| Exactitud de ítems | ${porcentaje(m.exactitud_items)} |`,
    `| Incoherencias monetarias detectadas | ${porcentaje(m.deteccion_incoherencias_monetarias)} |`,
    `| Candidatos coherentes | ${porcentaje(m.candidatos_coherentes)} |`,
    `| Falsos coherentes | ${m.falsos_coherentes} |`,
    `| Tiempo p95 | ${m.tiempo_p95_ms} ms |`,
    `| Tokens externos | ${m.tokens_externos} |`,
    "",
    `Fallos técnicos: ${summary.failures.length}`,
    ""
  ].join("\n");
}

async function main() {
  const setName = process.argv.includes("--evaluacion") ? "evaluacion" : "ajuste";
  const summary = JSON.parse(await fs.readFile(`salidas/benchmark/${setName}-resumen.json`, "utf8"));
  const report = generarInforme(summary);
  await escribirJsonAtomico(`benchmark/${setName}-informe.json`, { markdown: report });
  console.log(report);
}

if (process.argv[1].endsWith("informe.js")) {
  main().catch((error) => {
    console.error(`[ERROR] ${error.message}`);
    process.exitCode = 1;
  });
}
```

- [ ] **Step 6: Run tests**

Run:

```powershell
npm.cmd test
```

Expected: all tests PASS.

- [ ] **Step 7: Update README with exact safe commands**

Add:

```markdown
## Ejecución segura

Desde esta carpeta:

1. `npm.cmd install`
2. `node src/cli.js preparar-modelo`
3. `node benchmark/ejecutar.js`
4. `node benchmark/informe.js`

La evaluación final se ejecuta una sola vez, después de cerrar los ajustes:

1. `node benchmark/ejecutar.js --evaluacion`
2. `node benchmark/informe.js --evaluacion`

Ningún comando importa resultados al Centro de Costos.
```

- [ ] **Step 8: Commit**

```powershell
git add -- "Prototipo OCR Centro de Costos/benchmark/metricas.js" "Prototipo OCR Centro de Costos/benchmark/ejecutar.js" "Prototipo OCR Centro de Costos/benchmark/informe.js" "Prototipo OCR Centro de Costos/tests/metricas.test.js" "Prototipo OCR Centro de Costos/README.md"
git commit -m "feat(ocr): medir benchmark y emitir informe"
```

---

### Task 9: Ejecución controlada sobre las 31 facturas

**Files:**
- Create locally but do not commit: `Prototipo OCR Centro de Costos/salidas/config/proveedores.json`
- Create locally but do not commit: `Prototipo OCR Centro de Costos/salidas/benchmark/`
- Create: `Prototipo OCR Centro de Costos/docs/benchmark-resultado.md`

**Interfaces:**
- Consumes all prior tasks
- Produces an anonymized go/no-go report with no supplier names, RUTs, amounts or source paths

- [ ] **Step 1: Generate the private provider catalog from registered references**

Run a local extraction command implemented as a small one-off invocation of `cargarVerdad`:

```powershell
node --input-type=module -e "import fs from 'node:fs/promises'; import path from 'node:path'; import {cargarVerdad} from './benchmark/cargar-verdad.js'; const cc=path.resolve('..','Centro de Costos'); const docs=await cargarVerdad({snapshot:path.join(cc,'Visualizador Web','data','centro-de-costos.json'),datosActuales:path.join(cc,'Sistema','datos_extraidos.json'),datosLegado:path.join(cc,'Sistema','Legado','datos_extraidos_legacy_umag.json')}); const map=new Map(); for(const d of docs){if(d.rut_proveedor&&!map.has(d.rut_proveedor))map.set(d.rut_proveedor,{rut:d.rut_proveedor,razon_social:d.razon_social,tag:d.proveedor,aliases:[d.razon_social].filter(Boolean)});} await fs.mkdir('salidas/config',{recursive:true}); await fs.writeFile('salidas/config/proveedores.json',JSON.stringify([...map.values()],null,2)); console.log('Proveedores privados preparados:',map.size);"
```

Expected: creates `salidas/config/proveedores.json`; `git status --short` does not show it.

- [ ] **Step 2: Verify production sources are unchanged before benchmark**

```powershell
Get-FileHash "..\Centro de Costos\Excel\Centro de Costos.xlsx"
Get-FileHash "..\Centro de Costos\Sistema\datos_extraidos.json"
Get-ChildItem -Recurse -File "..\Centro de Costos\Sitio de comunicación - Centro de Costos 1\Facturas y Boletas" | Sort-Object FullName | Get-FileHash
```

Save the hash output under `salidas/benchmark/hashes-antes.txt`, not in Git.

- [ ] **Step 3: Run only the adjustment set**

```powershell
node benchmark/ejecutar.js
node benchmark/informe.js
```

Expected: results under `salidas/benchmark/ajuste/` and an aggregate report. Do not run `--evaluacion` yet.

- [ ] **Step 4: Adjust only versioned generic rules**

Use failures from the adjustment report to change only:

- `config/validaciones.json`
- `src/preprocesar-imagen.js`
- `src/extraer-campos.js`
- `src/extraer-items.js`

Every change must add a synthetic regression test before implementation. Do not add real providers, RUTs, folios, totals or OCR text to Git.

- [ ] **Step 5: Freeze rules and run final evaluation once**

```powershell
npm.cmd test
node benchmark/ejecutar.js --evaluacion
node benchmark/informe.js --evaluacion
```

Expected: all tests PASS and the final evaluation summary exists.

- [ ] **Step 6: Verify production hashes remain identical**

Repeat the commands from Step 2 and compare:

```powershell
Compare-Object (Get-Content "salidas/benchmark/hashes-antes.txt") (Get-Content "salidas/benchmark/hashes-despues.txt")
```

Expected: no differences.

- [ ] **Step 7: Write the anonymized decision report**

Generate `docs/benchmark-resultado.md` directly from the aggregate summary:

```powershell
node --input-type=module -e "import fs from 'node:fs/promises'; import {execFileSync} from 'node:child_process'; const s=JSON.parse(await fs.readFile('salidas/benchmark/evaluacion-resumen.json','utf8')); const m=s.metrics; const pct=(v)=>(v*100).toFixed(1)+'%'; const commit=execFileSync('git',['rev-parse','--short','HEAD'],{encoding:'utf8'}).trim(); const lines=['# Resultado del benchmark OCR local','',`Fecha de ejecución: ${new Date().toISOString().slice(0,10)}`,`Versión del prototipo: ${commit}`,'Corpus: 31 documentos locales, sin archivos copiados','','## Seguridad','','- Fuentes productivas modificadas: no','- Archivos financieros incorporados a Git: no','- Tokens de modelos generativos: 0','','## Métricas','',`- Exactitud crítica mínima: ${pct(s.decision.exactitud_critica_minima)}`,`- Exactitud de ítems: ${pct(m.exactitud_items)}`,`- Incoherencias monetarias detectadas: ${pct(m.deteccion_incoherencias_monetarias)}`,`- Candidatos coherentes: ${pct(m.candidatos_coherentes)}`,`- Falsos coherentes: ${m.falsos_coherentes}`,`- Tiempo p95: ${m.tiempo_p95_ms} ms`,'','## Decisión','',s.decision.aprobado?'APROBADO':'NO APROBADO','','## Próximo paso permitido','',s.decision.aprobado?'Redactar una especificación separada para revisión humana y exportación explícita.':'Evaluar PaddleOCR o detener la integración.','']; await fs.writeFile('docs/benchmark-resultado.md',lines.join('\n'),'utf8');"
```

Expected: the committed report contains only aggregate metrics, date, commit and decision; it contains no supplier names, RUTs, folios, amounts or source paths.

- [ ] **Step 8: Final privacy scan and commit**

Run:

```powershell
git status --short
rg -n -i "rut|proveedor|folio|total|neto|iva|Sitio de comunicación" "docs/benchmark-resultado.md"
npm.cmd test
```

Expected: no files under `salidas/` appear in Git; the report contains only headings and aggregate metric labels, never real values or identities; all tests PASS.

Commit:

```powershell
git add -- "Prototipo OCR Centro de Costos/docs/benchmark-resultado.md"
git commit -m "docs(ocr): registrar resultado anonimizado del benchmark"
```

---

## Final Verification

Run from `Prototipo OCR Centro de Costos/`:

```powershell
npm.cmd test
git status --short
git check-ignore -v "salidas/benchmark/evaluacion-resumen.json"
rg -n -i "writeFile|rename|copyFile|unlink|rm\\(" src benchmark
rg -n -i "fetch\\(|https?://|openai|anthropic|ollama" src benchmark
```

Expected:

- All tests PASS.
- Only intentional unrelated user changes remain in `git status`.
- Benchmark output is ignored.
- Every write found targets `salidas/` through `escribirJsonAtomico`, except local model cache managed by Tesseract.js.
- No generative-AI or runtime-network integration exists.
- The pre-benchmark and post-benchmark production hashes are identical.
