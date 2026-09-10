# -*- coding: utf-8 -*-
"""
driver.py — arnés de ejecución para la skill Registro_Centro_de_Costos.

No reimplementa el registrador: importa auditor_centro_costos.py desde la raíz
del proyecto y expone dos comandos seguros de invocar desde un agente:

  status  → SOLO LECTURA. Inventaria Facturas y Boletas/, dice qué
            se registraría (pendientes/omitidos), qué archivos no tienen
            datos (con items) en datos_extraidos.json, y corre la
            verificación aritmética sobre ese JSON. No crea backup ni
            escribe el Excel.

  run     → Ejecución real: equivalente a `python auditor_centro_costos.py`
            (backup + escritura). Idempotente: correrlo varias veces no
            duplica filas (las filas de datos ya escritas nunca se tocan;
            solo se regeneran los pies de tabla y las hojas de proyecto,
            que son 100% derivadas). También detecta ediciones manuales
            hechas en celdas que el script había marcado en rojo y las deja
            "Pendiente" en correcciones_manuales.json/ERRORES.md -- no las
            aplica todavía.

  confirmar → Sin argumentos: preview de solo lectura de las correcciones
            manuales pendientes (detectadas por 'run'). Con '--todos' o una
            lista de N° Ref: las aplica -- recolorea azul marino oscuro y
            propaga el valor a Detalle donde corresponda. Requiere que el
            usuario confirme antes de correr la variante que aplica.

  visualizador → Regenera el visualizador web (Visualizador Web/build/index.html)
            a partir del Excel actual: exporta un snapshot saneado a
            Visualizador Web/data/centro-de-costos.json y lo incrusta en
            Visualizador Web/template.html (versionado, sin datos). No
            modifica el Excel. Ver Visualizador Web/CLAUDE.md.

  separar   → Para un archivo PENDIENTE (sin registrar todavia) que trae mas
            de 1 documento tributario distinto en el mismo encuadre (ej. 2-3
            boletas fotografiadas juntas): genera '--cantidad' copias
            identicas del archivo ('<nombre>_1.<ext>', '<nombre>_2.<ext>',
            ...), respalda el original en Excel/Respaldos/<Mes Año>/ y lo
            borra de la carpeta compartida. No toca el Excel ni
            datos_extraidos.json -- despues de correrlo hay que agregar una
            entrada propia al JSON por cada copia nueva (paso 2 del skill),
            tratando cada una como un pendiente independiente.

  eliminar  → Saca del libro un documento registrado por error -- tipicamente
            el mismo documento tributario registrado dos veces desde dos
            escaneos distintos, que suma su costo dos veces en el proyecto,
            en los KPIs de Analisis Financiero y en el indice de precios.
            Borra sus items de Detalle y su fila de Master, regenera pies y
            hojas de proyecto, y ARCHIVA el archivo fuente en
            Excel/Respaldos/<Mes Año>/ sacandolo de la carpeta compartida
            (si no, el proximo 'run' lo volveria a registrar). No renumera
            los N Ref que quedan: el numero es historico y queda un hueco,
            que es lo correcto. Sin '--aplicar' solo muestra que sacaria.

Uso:
  python driver.py status
  python driver.py run
  python driver.py confirmar
  python driver.py confirmar --todos
  python driver.py confirmar UMAG-014 CFLI-002
  python driver.py visualizador
  python driver.py separar --proyecto "UMAG" --archivo "IMG_1234.jpg" --cantidad 3
  python driver.py eliminar UMAG-042
  python driver.py eliminar UMAG-042 --aplicar
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import auditor_centro_costos as acc  # noqa: E402


def _extraer_pais(argv):
    """Busca '--pais VALOR' en cualquier posicion de argv y lo separa del
    resto -- devuelve (pais, argv_sin_ese_flag). Default 'CL' si no aparece."""
    argv = list(argv)
    if "--pais" in argv:
        idx = argv.index("--pais")
        pais = argv[idx + 1]
        del argv[idx:idx + 2]
        return pais, argv
    return "CL", argv


def _imprimir_lista_truncada(items, formatear, limite=15):
    """Imprime como maximo 'limite' items formateados; si hay mas, resume el
    resto en 1 linea. No cambia ningun dato, solo cuanto texto se imprime."""
    for item in items[:limite]:
        print(formatear(item))
    restantes = len(items) - limite
    if restantes > 0:
        print(f"  ... y {restantes} más.")


def mostrar_preview_renombrados(filas_master, reconciliacion):
    """Preview de status (solo lectura): que archivos se renombrarian/
    convertirian si se corriera 'run', sin tocar disco."""
    reconciliacion_inversa = acc.construir_reconciliacion_inversa(reconciliacion)
    planes = acc.planificar_renombrados(filas_master, reconciliacion_inversa)
    a_renombrar = [p for p in planes if p["accion"] in ("renombrar", "convertir_heic")]
    no_encontrados = [p for p in planes if p["accion"] == "archivo_no_encontrado"]

    print(f"\nArchivos que se renombrarian/convertirian si corres 'run': {len(a_renombrar)}")
    _imprimir_lista_truncada(
        a_renombrar,
        lambda p: f"  - {p['n_ref']}: {p['ruta_actual'].name} -> {p['nombre_nuevo']} ({p['accion']})",
    )

    if no_encontrados:
        print(f"\n[WARN] {len(no_encontrados)} fila(s) sin archivo fisico encontrado para renombrar:")
        _imprimir_lista_truncada(no_encontrados, lambda p: f"  - {p['n_ref']}")


def cmd_status(pais="CL"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    acc.configurar_pais(pais)

    print("=" * 70)
    print(f"  ESTADO CENTRO DE COSTOS - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nRaíz documentos: {acc.RAIZ_DOCS}")
    print(f"  Existe: {acc.RAIZ_DOCS.exists()}")
    print(f"Excel: {acc.RUTA_EXCEL.name}")
    print(f"  Existe: {acc.RUTA_EXCEL.exists()}")
    print(f"JSON datos: {acc.RUTA_JSON.name}")
    print(f"  Existe: {acc.RUTA_JSON.exists()}")
    print(f"Reconciliación (bootstrap de documentos preexistentes): {acc.RUTA_RECONCILIACION.name}")
    print(f"  Existe: {acc.RUTA_RECONCILIACION.exists()}")

    if not acc.RAIZ_DOCS.exists() or not acc.RUTA_JSON.exists():
        print("\n[ERROR] Falta la carpeta de documentos o el JSON. Abortando status.")
        return 1

    import openpyxl

    ws_master = None
    if acc.RUTA_EXCEL.exists():
        wb = openpyxl.load_workbook(str(acc.RUTA_EXCEL), data_only=False)
        print(f"\nHojas existentes: {wb.sheetnames}")
        if "Master" in wb.sheetnames:
            ws_master = wb["Master"]
    else:
        print("\n[INFO] El Excel aún no existe, se crearía desde cero en un 'run'.")

    if ws_master is not None:
        filas_master, max_seq, docs_registrados = acc.leer_master(ws_master)
    else:
        filas_master, max_seq, docs_registrados = [], {}, set()

    reconciliacion = acc.cargar_reconciliacion()
    archivos_registrados = set(reconciliacion.keys())
    for fm in filas_master:
        if fm["archivo_origen"]:
            archivos_registrados.add(str(fm["archivo_origen"]))

    print(f"\nDocumentos ya en Master: {len(filas_master)}")
    print(f"N° Documento distintos ya registrados: {len(docs_registrados)}")
    print(f"Archivos ya cubiertos (Master + reconciliación): {len(archivos_registrados)}")

    pendientes, omitidos = acc.inventariar_archivos(acc.RAIZ_DOCS, archivos_registrados)
    print("\nInventario de Facturas y Boletas/:")
    print(f"  Pendientes (no registrados):            {len(pendientes)}")
    print(f"  Omitidos (ya registrados):               {len(omitidos)}")

    proyectos = sorted({p.name for p in acc.RAIZ_DOCS.iterdir() if p.is_dir()})
    print(f"\nProyectos detectados ({len(proyectos)}): {', '.join(proyectos)}")

    datos_json = acc.cargar_datos_json(acc.RUTA_JSON)
    print(f"\nEntradas en datos_extraidos.json: {len(datos_json)}")

    sin_datos = []
    for info in pendientes:
        dato = acc.buscar_dato_por_archivo(datos_json, info["proyecto"], info["archivo"])
        if not dato or not dato.get("items"):
            sin_datos.append(info)

    print(f"\nPendientes SIN datos (o sin items) en el JSON (bloquean el registro): {len(sin_datos)}")
    _imprimir_lista_truncada(sin_datos, lambda info: f"  - [{info['proyecto']}] {info['archivo']}")

    escribibles = len(pendientes) - len(sin_datos)
    print(f"\nSi corres 'run' ahora se registrarían: {escribibles} documento(s).")

    print(f"\nCuadre de impuesto sobre TODO datos_extraidos.json (Neto vs {acc.NOMBRE_IMPUESTO_PCT}):")
    # Mismo formateo agrupado por severidad que usa el informe de 'run' -- lo
    # provee el modulo, no se duplica aca.
    acc._imprimir_cuadre_impuesto(acc.verificar_aritmetica(datos_json))

    mostrar_preview_renombrados(filas_master, reconciliacion)

    print("\nCambios manuales detectados (preview, no se escribe nada):")
    ruta_backup_anterior = acc.backup_mas_reciente(ruta_backups=acc.RUTA_BACKUPS)
    if ruta_backup_anterior is not None and ws_master is not None:
        wb_anterior = openpyxl.load_workbook(str(ruta_backup_anterior), data_only=False)
        detectadas = acc.detectar_correcciones_manuales(wb_anterior, wb)
        pendientes = acc.registrar_correcciones_pendientes(detectadas, escribir=False)
        if pendientes:
            _imprimir_lista_truncada(
                pendientes,
                lambda c: f"  - {c['n_ref']} / {c['campo']}: '{c['valor_anterior']}' -> '{c['valor_corregido']}'",
            )
        else:
            print("  Ninguno.")
    else:
        print("  No hay backup anterior contra el cual comparar (primera corrida).")

    print("\n" + "=" * 70)
    print("  Nada fue escrito. Para ejecutar de verdad: python driver.py run")
    print("=" * 70)
    return 0


def cmd_run(pais="CL"):
    acc.main(pais=pais)
    return 0


def cmd_confirmar(args, pais="CL"):
    acc.configurar_pais(pais)
    if not args:
        acc.confirmar_correcciones(None)
    elif args == ["--todos"]:
        acc.confirmar_correcciones("TODOS")
    else:
        acc.confirmar_correcciones(args)
    return 0


def _extraer_flag(argv, nombre):
    """Busca '--<nombre> VALOR' en argv y devuelve (valor, argv_sin_ese_flag).
    Lanza ValueError si el flag no aparece o le falta el valor."""
    argv = list(argv)
    if nombre not in argv:
        raise ValueError(f"Falta el flag --{nombre}")
    idx = argv.index(nombre)
    if idx + 1 >= len(argv):
        raise ValueError(f"El flag --{nombre} requiere un valor")
    valor = argv[idx + 1]
    del argv[idx:idx + 2]
    return valor, argv


def cmd_separar(args, pais="CL"):
    acc.configurar_pais(pais)
    try:
        proyecto, resto = _extraer_flag(args, "--proyecto")
        archivo, resto = _extraer_flag(resto, "--archivo")
        cantidad_str, resto = _extraer_flag(resto, "--cantidad")
        cantidad = int(cantidad_str)
    except ValueError as e:
        print(f"[ERROR] {e}")
        print("Uso: python driver.py separar --proyecto <Proyecto> --archivo <archivo> --cantidad N")
        return 2

    try:
        destinos = acc.separar_documento_combinado(proyecto, archivo, cantidad)
    except (ValueError, FileNotFoundError, FileExistsError) as e:
        print(f"[ERROR] {e}")
        return 1

    print(f"[OK] '{archivo}' separado en {len(destinos)} archivo(s):")
    for destino in destinos:
        print(f"  - {destino.name}")
    print("Agrega una entrada propia en datos_extraidos.json por cada archivo de arriba "
          "(mismo 'proyecto', 'archivo' = nombre nuevo) antes de correr 'run'.")
    return 0


def cmd_eliminar(args, pais="CL"):
    """Saca del libro uno o varios documentos registrados por error. Sin
    '--aplicar' solo muestra que sacaria: es la unica operacion que borra una
    fila de datos ya escrita, asi que el default es no escribir."""
    acc.configurar_pais(pais)
    aplicar = "--aplicar" in args
    n_refs = [a for a in args if a != "--aplicar"]
    if not n_refs:
        print("Uso: python driver.py eliminar <N_REF> [<N_REF> ...] [--aplicar]")
        return 2

    try:
        previos, resultados = acc.ejecutar_eliminacion(n_refs, aplicar=aplicar)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1

    print("=" * 70)
    print(f"  {'ELIMINACION APLICADA' if aplicar else 'PREVIEW -- no se escribio nada'}")
    print("=" * 70)
    total = 0
    for p in previos:
        impuesto = p["impuesto"] if isinstance(p["impuesto"], (int, float)) else 0
        total += p["neto"] + impuesto
        print(f"\n  {p['n_ref']}  ({p['proyecto']})")
        print(f"    Documento : {p['n_documento']} de {p['proveedor']}")
        print(f"    Fecha     : {str(p['fecha'])[:10]}")
        print(f"    Neto      : {p['neto']:,.0f}")
        print(f"    Impuesto  : {impuesto:,.0f}")
    print(f"\n  Total que sale del costo: {total:,.0f} {acc.MONEDA}")

    if aplicar:
        for r in resultados:
            print(f"\n  [OK] {r['n_ref']}: {r['items_borrados']} item(s) de Detalle borrado(s)")
            if r["archivo_archivado"]:
                print(f"       Archivo movido a: {r['archivo_archivado']}")
            elif r["archivo_origen"]:
                print(f"       [AVISO] No se encontro el archivo {r['archivo_origen']} "
                      f"-- si reaparece en la carpeta, el proximo 'run' lo registrara de nuevo.")
        print("\n  Falta correr 'run' para propagar a Analisis Financiero y los tableros.")
    else:
        print("\n  Para aplicarlo de verdad, agrega --aplicar")
    return 0


def cmd_visualizador(pais="CL"):
    acc.configurar_pais(pais)
    visualizador_dir = acc.RAIZ_VISUALIZADOR_WEB
    ruta_build_script = visualizador_dir / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    sys.path.insert(0, str(visualizador_dir))
    sys.dont_write_bytecode = True
    import build_visualizador as bv  # noqa: E402
    return bv.build()


def main():
    comandos = ("status", "run", "confirmar", "visualizador", "separar", "eliminar")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar [--todos|N_REF ...]|visualizador|"
              "separar --proyecto P --archivo A --cantidad N|eliminar N_REF ... [--aplicar]] "
              "[--pais CL|PE]")
        return 2

    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])

    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "confirmar":
        return cmd_confirmar(resto, pais=pais)
    if comando == "visualizador":
        return cmd_visualizador(pais=pais)
    if comando == "separar":
        return cmd_separar(resto, pais=pais)
    if comando == "eliminar":
        return cmd_eliminar(resto, pais=pais)
    return cmd_run(pais=pais)


if __name__ == "__main__":
    raise SystemExit(main())
