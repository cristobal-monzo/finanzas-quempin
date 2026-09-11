# Benchmark del proceso de errores (Centro de Costos)

Mide, con números reproducibles, qué tan bien el pipeline **detecta** y
**cierra** los errores de ingreso de facturas, boletas y guías de despacho.
Nació en la auditoría del 2026-09-10, cuando había que demostrar que un cambio
en el proceso de errores mejoraba algo y no solo movía texto de consola.

No toca un solo byte de datos reales: genera su propio corpus anonimizado y
monta un Centro de Costos completo y desechable en un directorio temporal.

## Cómo correrlo

```
py -3.14 "Centro de Costos/Sistema/bench/bench_errores.py"                    # 3 semillas
py -3.14 "Centro de Costos/Sistema/bench/bench_errores.py" --repeticiones 1   # rápido
py -3.14 "Centro de Costos/Sistema/bench/bench_errores.py" --json salida.json # detalle
```

Tarda ~25 s con 3 semillas. Cada semilla monta el sandbox, corre `main()` dos
veces y hace un recorrido de resolución completo.

## Qué hay acá

| Archivo | Rol |
|---|---|
| `corpus_errores.py` | Genera el corpus sintético + el **ground truth** (qué defecto tiene cada documento). Determinista por semilla. |
| `sandbox.py` | Monta un Centro de Costos desechable en un temporal y registra el país ficticio `BENCH` en `acc.PAISES`. |
| `bench_errores.py` | Corre el pipeline sobre el sandbox y calcula las métricas. |

## Por qué un país ficticio y no monkeypatch

`main()` llama a `configurar_pais()` como primera línea y **reescribe todos los
globals de ruta**, así que parchearlos desde afuera no aísla nada (ver
`CLAUDE.md` raíz, "No midas contra producción"). `sandbox.montar()` registra un
país `BENCH` cuyas rutas ya apuntan al temporal, y deja un guard que aborta si
alguna ruta de escritura quedara fuera de ese directorio. También apunta
`RAIZ_ANALISIS_FINANCIERO` a un inexistente, porque esa constante **no** la
toca `configurar_pais()` y si no el PASO 12d correría el Análisis Financiero de
verdad.

## Las métricas, y qué significa cada una

- **`deteccion_recall`** — de los defectos inyectados, cuántos señala el
  sistema por cualquiera de sus canales de salida (informe de consola, celda
  marcada en el libro, registro persistente de errores).
- **`tasa_falsos_positivos`** — de los 20 documentos de control (que nunca
  reciben defecto), cuántos señala igual. **Es el freno**: ninguna mejora vale
  si sube este número.
- **`tasa_no_resuelta`** — la métrica principal. Fracción de defectos que, tras
  una corrida completa **más** un recorrido de resolución hecho por un operador
  perfecto (el arnés conoce el valor correcto de cada defecto), siguen sin
  quedar corregidos ni cerrados.
- **`tasa_auto_resolucion`** — defectos que el sistema cierra solo, con
  registro de auditoría y sin intervención humana.
- **`segundos_por_resolucion`** — tiempo de pared del recorrido dividido por
  los defectos efectivamente cerrados.
- **`defectos_publicados_sin_detectar`** — defectos que llegaron al Excel
  guardado, a la copia del sitio, al visualizador y a Análisis Financiero
  **antes** de que nadie los reportara. Mide validación tardía.
- **`hallazgos_reemitidos`** — hallazgos que vuelven en la corrida 2 **sin**
  identidad ni antigüedad, o sea indistinguibles de uno nuevo. Mide falta de
  deduplicación. Un hallazgo abierto que reaparece con su `id` y su
  `visto 3x desde <fecha>` es seguimiento, no ruido, y no cuenta acá.

## Qué cuenta como "resuelto" (y por qué así)

Un defecto cuenta como resuelto solo si **(a)** el dato quedó correcto en el
sistema de registro **y (b)** queda evidencia auditable de cómo se resolvió.

La parte (b) no es un adorno: esto es un sistema financiero y el módulo entero
está construido sobre la idea de que toda corrección a mano queda registrada
(fuente azul marino + `correcciones_manuales.json` + `ERRORES.md`, y
`detectar_correcciones_manuales` existe justamente para cazar las que no).
Editar `datos_extraidos.json` a escondidas haría desaparecer el síntoma sin
dejar constancia de quién cambió un monto, así que el arnés **no** lo cuenta
como resolución. Por eso el operador del benchmark solo usa canales auditados:
`corregir_hallazgos` (por lote), `corregir_valor_manual` y
`desglosar_item_agrupado`.

Además, cada cierre se **verifica**: se relee el libro y se comprueba que el
valor que quedó escrito es el correcto y que la corrección está asentada en
`correcciones_manuales.json`. Un comando que "corre bien" pero deja el valor
equivocado no suma.

## El ground truth

`generar_corpus()` reparte 36 defectos sobre 238 documentos (~15 %, proporción
comparable a la del corpus real: 35 descuadres de impuesto + 34 números
ilegibles + 8 duplicados sobre 681 documentos). Cada documento lleva 0 o 1
defecto, nunca dos, para que la imputación "detectado / no detectado" sea
inequívoca. Los primeros 20 documentos quedan siempre limpios: son el control
con el que se mide la tasa de falsos positivos.

Dos decisiones del corpus que conviene no reaprender:

- **Una línea de precio negativo suelta en una factura NO es un defecto**: es
  un descuento, y `ERRORES.md` registra varios reales. El defecto que sí existe
  es el documento entero leído con el signo invertido (precedente
  "Signo de IVA / P.Unitario / Totales (AYRSA)"), que es lo que inyecta
  `SIGNO_INVERTIDO_COMPRA`.
- **El original de un par duplicado se toma de los documentos de control**, no
  del vecino: si se tomara del vecino podría heredar un número ya vuelto
  ilegible por otro defecto, y el duplicado dejaría de ser detectable por
  razones del corpus en vez de razones del sistema.

## Comparar contra una versión anterior del código

El benchmark mide `Sistema/auditor_centro_costos.py` tal como esté en disco.
Para comparar dos versiones, guarda una copia, intercámbialas y corre el mismo
comando con las mismas semillas:

```
cp auditor_centro_costos.py /tmp/version_nueva.py
cp /tmp/version_vieja.py auditor_centro_costos.py
py -3.14 bench/bench_errores.py --repeticiones 3 --json /tmp/antes.json
cp /tmp/version_nueva.py auditor_centro_costos.py
py -3.14 bench/bench_errores.py --repeticiones 3 --json /tmp/despues.json
```

El arnés degrada solo: si la versión vieja no tiene registro de errores ni
`corregir_hallazgos`, simplemente esos canales no aportan cierres.
