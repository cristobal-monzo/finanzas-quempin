# Diseño: prototipo OCR local para Centro de Costos

Fecha: 2026-07-24  
Estado: aprobado conceptualmente; pendiente de revisión escrita  
Ámbito: prototipo local y aislado, sin integración productiva

## 1. Objetivo

Construir un prototipo local que extraiga información estructurada desde las
facturas y boletas del Centro de Costos, valide su coherencia y mida su
precisión usando los documentos ya registrados como referencia.

El propósito es reducir el uso de modelos generativos y el trabajo manual sin
arriesgar el libro maestro ni el flujo actual. La extracción OCR, las reglas y
el benchmark no consumirán tokens de Claude u OpenAI.

## 2. Límites de la primera etapa

El prototipo:

- Leerá documentos reales existentes con acceso de solo lectura.
- Leerá datos registrados existentes únicamente para construir la verdad de
  referencia del benchmark.
- Escribirá resultados exclusivamente dentro de su propia carpeta.
- Generará candidatos compatibles con el esquema de `datos_extraidos.json`.
- Clasificará cada resultado como coherente, revisable o rechazado.
- Proporcionará trazabilidad entre cada campo extraído y el texto OCR que lo
  originó.

El prototipo no:

- Modificará `Centro de Costos.xlsx`.
- Modificará `Sistema/datos_extraidos.json`.
- Renombrará, moverá ni copiará facturas.
- Ejecutará el auditor productivo.
- Actualizará el visualizador web.
- Registrará automáticamente un documento.
- Enviará imágenes o datos financieros a servicios externos.
- Usará un modelo generativo local o remoto en esta etapa.

## 3. Condiciones observadas

- El corpus inicial contiene 31 archivos: 23 `.jpg` y 8 `.jpeg`.
- Los documentos se encuentran organizados por proyecto.
- Node.js está disponible en el equipo.
- No se detectó Python, Tesseract, ImageMagick ni otro motor OCR accesible
  mediante el `PATH` inspeccionado.
- El pipeline productivo actual es determinista después de que
  `datos_extraidos.json` contiene una entrada completa.
- El principal espacio de ahorro se encuentra antes del pipeline productivo:
  lectura, transcripción y estructuración de cada comprobante.

Estas condiciones deberán comprobarse nuevamente al comenzar la implementación
porque el entorno puede cambiar.

## 4. Enfoques considerados

### 4.1 Tesseract.js con reglas deterministas

Es el enfoque elegido para el primer benchmark.

Ventajas:

- Funciona sobre Node.js y no necesita un servicio externo.
- No consume tokens.
- Permite distribuir el prototipo como un proyecto aislado.
- Es suficiente para establecer una línea base medible.

Riesgos:

- Precisión limitada en imágenes borrosas, inclinadas o con tablas complejas.
- La reconstrucción de líneas de ítems puede necesitar reglas específicas.
- El preprocesamiento de imágenes influirá considerablemente en el resultado.

### 4.2 PaddleOCR

Se reserva como motor alternativo si Tesseract.js no alcanza los criterios de
aceptación.

Ventajas:

- Mejor soporte potencial para orientación, estructura y tablas.
- Ejecución local y sin tokens.

Costos:

- Requiere instalar Python y dependencias más pesadas.
- Aumenta la complejidad de distribución y mantenimiento.

### 4.3 Modelo visual local

Queda fuera del alcance inicial. Podría comprender mejor documentos complejos,
pero introduce modelos grandes, requisitos de hardware y un comportamiento
menos determinista.

## 5. Arquitectura

La arquitectura separará la extracción, interpretación y validación para poder
cambiar el motor OCR sin reescribir el resto del sistema.

```text
Descubrimiento de documentos
            |
            v
Preprocesamiento de imagen
            |
            v
Adaptador OCR local
            |
            v
Extracción de campos e ítems
            |
            v
Normalización de valores
            |
            v
Validaciones cruzadas
            |
            v
Candidato coherente / Revisión / Rechazado
```

### 5.1 Descubrimiento

Recibirá rutas explícitas o un manifiesto. No recorrerá ni procesará
automáticamente toda la carpeta productiva sin una orden de prueba.

El proyecto se obtendrá de la carpeta que contiene el documento. El OCR nunca
inferirá ni reemplazará el proyecto.

### 5.2 Preprocesamiento

Producirá una representación temporal en memoria o en un directorio de trabajo
local ignorado por Git. Las operaciones previstas son:

- Corrección de orientación.
- Escala para mejorar caracteres pequeños.
- Conversión a escala de grises.
- Mejora de contraste.
- Reducción moderada de ruido.
- Variantes de umbral cuando la imagen lo requiera.

El documento original nunca se sobrescribirá.

### 5.3 Adaptador OCR

La interfaz del motor devolverá:

- Texto completo.
- Bloques o líneas.
- Confianza disponible.
- Coordenadas disponibles.
- Motor y versión.
- Tiempo de procesamiento.

La primera implementación utilizará Tesseract.js con español. La interfaz
permitirá añadir PaddleOCR sin modificar extracción, validación ni benchmark.

### 5.4 Extracción

La extracción se dividirá en campos de cabecera e ítems.

Campos críticos:

- Proyecto.
- Tipo de documento.
- Fecha.
- Número de documento.
- Proveedor.
- Razón social.
- RUT.
- Neto.
- IVA.
- Total.

Campos de ítems:

- Nombre o descripción.
- Categoría propuesta.
- Cantidad.
- Precio unitario sin IVA.
- Total sin IVA.
- Total con IVA cuando esté explícito o sea derivable.

Cada campo incluirá valor original, valor normalizado, confianza, origen OCR y
reglas utilizadas.

### 5.5 Normalización

La normalización será determinista:

- Fechas a `YYYY-MM-DD`.
- RUT sin ambigüedad de puntos y guion.
- Montos como números enteros CLP cuando corresponda.
- Separadores de miles y decimales interpretados según contexto.
- Espacios y caracteres OCR frecuentes corregidos solo mediante reglas
  explícitas y auditables.
- Proveedores vinculados a un catálogo local por RUT, razón social y alias.

Una corrección ambigua reducirá la confianza o enviará el documento a revisión.

## 6. Validación

La validación es una barrera obligatoria, independiente de la confianza
declarada por el OCR.

### 6.1 Reglas críticas

Un documento no podrá ser `candidato_coherente` si incumple alguna de estas
condiciones:

1. Proyecto obtenido de una carpeta válida.
2. Proveedor identificado sin conflicto.
3. RUT válido y consistente con el proveedor cuando esté disponible.
4. Fecha válida y dentro de un rango razonable configurable.
5. Número de documento presente.
6. Neto, IVA y total numéricos.
7. `neto + IVA = total`, dentro de una tolerancia configurable.
8. IVA compatible con 19% cuando el tipo de documento lo requiera.
9. Suma de ítems compatible con el neto.
10. Ausencia de duplicado por proveedor, número de documento y monto.
11. Confianza mínima en todos los campos críticos.

### 6.2 Reglas de advertencia

Las advertencias no rechazarán automáticamente, pero impedirán que el resultado
se considere listo sin revisión cuando afecten campos relevantes:

- Descripción de ítem poco legible.
- Categoría no encontrada.
- Diferencia de redondeo aceptable pero inusual.
- Cantidad implícita.
- Precio unitario derivado.
- RUT ausente en el documento, aunque el proveedor sea reconocible.

### 6.3 Estados

- `candidato_coherente`: supera todas las reglas críticas.
- `requiere_revision`: existe información suficiente, pero una regla crítica o
  advertencia configurada necesita revisión humana.
- `rechazado`: faltan datos esenciales o la imagen no permite una extracción
  útil.

Ninguno de estos estados autoriza escritura productiva durante el prototipo.

## 7. Esquema de salida

Cada ejecución generará un resultado auditable con:

- Identificador estable de la prueba.
- Ruta de origen relativa o identificador seguro.
- Huella del archivo para detectar repeticiones.
- Motor OCR y versión.
- Texto OCR.
- Campos extraídos con evidencia.
- Ítems extraídos con evidencia.
- Resultado de cada regla.
- Estado final y motivos.
- Duración de cada etapa.
- Candidato en el esquema esperado por `datos_extraidos.json`.

Las salidas con datos reales quedarán bajo `salidas/`, directorio excluido de
Git.

## 8. Benchmark

### 8.1 Fuentes

El benchmark utilizará las 31 facturas reales con acceso de solo lectura. La
verdad de referencia se obtendrá de los registros existentes y se materializará
solo dentro de las salidas locales ignoradas por Git.

No se copiarán imágenes al prototipo.

### 8.2 Separación del corpus

Se construirá una separación reproducible:

- Conjunto de ajuste: aproximadamente 70%.
- Conjunto de evaluación final: aproximadamente 30%.

La separación intentará conservar variedad de proveedores, proyectos y calidad
de imagen. Los resultados del conjunto final no se usarán para ajustar reglas
antes de emitir el informe final.

### 8.3 Métricas

Se medirán:

- Exactitud exacta y normalizada por campo.
- Exactitud de proveedor y RUT.
- Exactitud de fecha y número de documento.
- Error absoluto en neto, IVA y total.
- Porcentaje de documentos que concilian.
- Exactitud en cantidad de ítems.
- Exactitud por campo de ítem.
- Porcentaje por estado.
- Falsos `candidato_coherente`.
- Tiempo promedio y percentil 95 por documento.
- Consumo de tokens externos, que debe ser cero.

### 8.4 Criterios de éxito

La primera etapa se considerará prometedora si consigue:

- Cero aceptaciones falsas conocidas.
- Detección del 100% de las incoherencias monetarias conocidas.
- Al menos 95% de exactitud en proveedor, fecha, folio y totales.
- Al menos 85% de exactitud inicial en ítems.
- Al menos 60% de documentos como `candidato_coherente`.
- Cero escrituras sobre el flujo productivo.
- Cero tokens de modelos generativos.

No alcanzar un criterio no provocará integración parcial. El informe deberá
recomendar mejorar preprocesamiento, incorporar PaddleOCR o detener el enfoque.

## 9. Seguridad y privacidad

- El procesamiento será local.
- No habrá llamadas de red durante el OCR.
- Los documentos financieros no se incluirán en Git.
- Los resultados con texto, proveedores o montos serán ignorados por Git.
- Los logs permanentes evitarán texto completo salvo que el modo de diagnóstico
  se active explícitamente.
- Las rutas mostradas en reportes compartibles podrán anonimizarse.

La descarga inicial de dependencias y datos de idioma requerirá red, pero la
ejecución normal deberá funcionar sin ella.

## 10. Estructura prevista

```text
Prototipo OCR Centro de Costos/
├── README.md
├── package.json
├── config/
│   ├── proveedores.example.json
│   └── validaciones.json
├── docs/
│   ├── specs/
│   └── plans/
├── schemas/
│   └── candidato.schema.json
├── src/
│   ├── cli.js
│   ├── descubrir-documentos.js
│   ├── preprocesar-imagen.js
│   ├── motores/
│   │   ├── interfaz.js
│   │   └── tesseract.js
│   ├── extraer-campos.js
│   ├── extraer-items.js
│   ├── normalizar.js
│   ├── validar.js
│   └── generar-candidato.js
├── tests/
├── benchmark/
└── salidas/
```

La estructura final podrá simplificarse en el plan de implementación si algún
módulo no aporta una separación comprobable.

## 11. Interfaz inicial

El prototipo será una herramienta de línea de comandos para facilitar pruebas
reproducibles.

Operaciones previstas:

- Procesar un documento explícito.
- Ejecutar el conjunto de ajuste.
- Ejecutar la evaluación final.
- Generar un informe sin reprocesar documentos.
- Inspeccionar un resultado y sus reglas.

No existirá un comando de importación productiva en esta etapa.

## 12. Manejo de errores

- Dependencia ausente: detener antes de procesar.
- Archivo no soportado: marcar como rechazado sin modificarlo.
- OCR sin texto útil: resultado rechazado con diagnóstico.
- Error en un documento: registrar el fallo y continuar el lote.
- Salida incompleta: escribir de forma atómica para no dejar JSON truncado.
- Fuente productiva no disponible: detener el benchmark con un mensaje claro.
- Intento de escritura fuera de la carpeta del prototipo: bloquear la
  operación.

## 13. Pruebas

Se exigirán:

- Pruebas unitarias de RUT, fechas y montos.
- Pruebas de separadores y errores OCR frecuentes.
- Pruebas de conciliación de neto, IVA y total.
- Pruebas de suma de ítems.
- Pruebas de duplicados.
- Pruebas de clasificación de estados.
- Pruebas que demuestren que las rutas productivas son de solo lectura.
- Benchmark reproducible.
- Escaneo del repositorio para confirmar que las salidas reales no quedan
  versionadas.

## 14. Evolución posterior

Si el benchmark se aprueba, una segunda especificación podrá diseñar:

1. Revisión humana de candidatos.
2. Exportación explícita de un fragmento JSON.
3. Integración controlada con el pipeline productivo.
4. Ejecución automática al detectar documentos.
5. Uso opcional de IA exclusivamente para excepciones.

Ninguna de estas funciones forma parte del prototipo inicial.

## 15. Decisión

Se implementará primero Tesseract.js detrás de una interfaz intercambiable,
con validación determinista y benchmark contra documentos reales. La seguridad
del flujo actual prevalece sobre la cantidad de documentos automatizados: ante
duda, el resultado requiere revisión.
