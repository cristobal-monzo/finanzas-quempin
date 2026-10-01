# -*- coding: utf-8 -*-
"""
driver.py -- arnes de ejecucion para la skill Registro_Analisis_Financiero.

No reimplementa la logica: importa analisis_financiero.py desde Sistema/ y
expone cuatro comandos:

  status           -> Solo lectura (dry_run=True): que carpetas de proyecto
                      se crearian, que categorias de Centro de Costos caen
                      en "Otros" por no tener mapeo explicito, sin tocar
                      ningun archivo.

  run              -> Ejecucion real: backup, crea carpetas de proyecto
                      nuevas, regenera "Detalle Costos Reales" y las
                      formulas de "Proyectos"/"Indicadores"/"Clientes"/
                      "Glosario KPIs", guarda el Excel, y regenera el
                      visualizador web (ya encadenado dentro de ejecutar()).

  confirmar-cliente -> Sin argumentos: lista clientes pendientes de revision
                      (columna "Cliente" en fuente roja). "--todos" o una
                      lista de TAGs: aplica la sugerencia y recolorea azul
                      marino.

  visualizador     -> Regenera solo el dashboard HTML (Visualizador Web/
                      build/index.html) a partir del Excel actual, sin
                      correr todo run.

  intercambio      -> Buzón de la carpeta Intercambio (costos proyectados
                      enviados desde el Formulador de proyectos): qué se
                      aplicaría en el próximo run y qué espera una
                      decisión. Solo lectura. Con "confirmar <id>" autoriza
                      a reemplazar los valores escritos a mano que ese envío
                      tenía en conflicto y corre run; con "descartar <id>"
                      lo archiva sin tocar el Excel; con "publicar" deja al
                      día la lista de proyectos que ve el Formulador, sin
                      escribir el Excel (solo lo lee).

  formulaciones    -> Presupuestos del repositorio del Formulador (pedido del
                      usuario 2026-09-30). Sin argumentos es solo lectura:
                      novedades desde la última revisión, entregas por
                      archivo por incorporar, y adjudicados que faltan en el
                      Análisis Financiero. «incorporar» lleva las entregas por
                      archivo al repositorio; «revisadas» marca todo como
                      visto; «cargar <uid|código> <TAG> [--nombre ...]» deja
                      el envío de costos en el buzón (se aplica en el próximo
                      run).

Uso:
  python driver.py status
  python driver.py run
  python driver.py confirmar-cliente [--todos|TAG ...]
  python driver.py visualizador
  python driver.py intercambio [publicar | confirmar <id> | descartar <id>]
  python driver.py formulaciones [incorporar | revisadas | cargar <uid|código [vN]> <TAG> [--nombre "..."]]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "Sistema"))

sys.dont_write_bytecode = True
import analisis_financiero as af  # noqa: E402


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


def cmd_status(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

    cfg = af.PAISES[pais]
    print("=" * 70)
    print(f"  ESTADO ANÁLISIS FINANCIERO - {pais} (solo lectura, no escribe nada)")
    print("=" * 70)

    print(f"\nExcel de trabajo: {cfg['ruta_excel_af']}")
    print(f"  Existe: {cfg['ruta_excel_af'].exists()}")
    print(f"\nExcel Centro de Costos: {cfg['ruta_excel_cc']}")
    print(f"  Existe: {cfg['ruta_excel_cc'].exists()}")

    resumen = af.ejecutar(dry_run=True, pais=pais)

    if resumen["proyectos_nuevos"]:
        print(
            f"\nProyectos nuevos que SE CREARÍAN en 'Proyectos' (TAG + Nombre, "
            f"el resto queda en blanco): {', '.join(resumen['proyectos_nuevos'])}"
        )

    if resumen["carpetas_creadas"]:
        print(f"\nCarpetas de proyecto que SE CREARÍAN: {', '.join(resumen['carpetas_creadas'])}")
    else:
        print("\nNo hay carpetas de proyecto nuevas por crear.")

    if resumen["categorias_no_mapeadas"]:
        print(
            "\nCategorías de Centro de Costos sin mapeo explícito (caerían en 'Otros'): "
            + ", ".join(resumen["categorias_no_mapeadas"])
        )

    if resumen["avisos"]:
        print("\nAvisos:")
        for aviso in resumen["avisos"]:
            print(f"  [AVISO] {aviso}")

    if resumen.get("alertas"):
        print("\nAlertas de proyectos (datos a revisar o sobrecosto):")
        for alerta in resumen["alertas"]:
            print(f"  [ALERTA] {alerta}")

    if resumen.get("intercambio"):
        print("\nIntercambio con el Formulador de proyectos:")
        af.imprimir_intercambio(resumen["intercambio"], aplicado=False)

    print("\n" + "=" * 70)
    print("  Nada fue escrito. Para ejecutar de verdad: python driver.py run")
    print("=" * 70)
    return 0


def cmd_run(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    af.main(pais=pais)
    return 0


def cmd_confirmar_cliente(args: list[str], pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cfg = af.PAISES[pais]

    if not args:
        pendientes = af.confirmar_clientes_pendientes(None, ruta_excel=cfg["ruta_excel_af"])
        print(f"\nClientes pendientes de confirmar: {len(pendientes)}")
        for p in pendientes:
            print(
                f"  - {p['tag']}: '{p['nombre_proyecto']}' -> sugerido "
                f"'{p['cliente_sugerido']}' (similitud {p['similitud']})"
            )
        if pendientes:
            print(
                "\nPara aplicar: python driver.py confirmar-cliente --todos"
                " (o 'python driver.py confirmar-cliente <TAG> ...' para solo algunos)"
            )
        return 0

    objetivo = "TODOS" if args == ["--todos"] else args
    aplicados = af.confirmar_clientes_pendientes(objetivo, ruta_excel=cfg["ruta_excel_af"])
    if not aplicados:
        print("\nNo hay clientes pendientes que coincidan con lo pedido.")
    for p in aplicados:
        print(f"  [OK] {p['tag']} -> Cliente '{p['cliente_sugerido']}' confirmado (azul marino).")
    return 0


def cmd_visualizador(pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    raiz_viz = af.PAISES[pais]["raiz_visualizador_web"]
    ruta_build_script = raiz_viz / "build_visualizador.py"
    if not ruta_build_script.exists():
        print(f"[INFO] Visualizador Web de {pais} aún no implementado -- nada que regenerar.")
        return 0
    ya_en_path = str(raiz_viz) in sys.path
    if not ya_en_path:
        sys.path.insert(0, str(raiz_viz))
    sys.dont_write_bytecode = True
    sys.modules.pop("build_visualizador", None)
    import build_visualizador as bv
    return bv.build()


def cmd_intercambio(args: list[str], pais: str = "CL") -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cfg = af.PAISES[pais]
    raiz = cfg.get("raiz_intercambio")
    if raiz is None:
        print(f"[INFO] {cfg.get('aviso_sin_intercambio') or f'El intercambio con el Formulador no está activo para {pais}.'}")
        return 0

    if args and args[0] == "publicar":
        resultado = af.publicar_intercambio(pais=pais)
        if resultado["error"]:
            print(f"[ERROR] {resultado['error']}")
            return 1
        print(f"[OK] Lista de {resultado['proyectos']} proyectos publicada para el Formulador en {resultado['ruta']}")
        print("     El Excel no se modificó. Los envíos del buzón se aplican en el próximo run.")
        return 0

    if args and args[0] in ("confirmar", "descartar"):
        if len(args) != 2:
            print(f"Uso: python driver.py intercambio {args[0]} <id>")
            return 2
        accion, id_mensaje = args
        if accion == "descartar":
            if not af.pf.descartar(raiz, id_mensaje):
                print(f"[INFO] No hay un envío con id {id_mensaje} en el buzón.")
                return 1
            print(f"[OK] Envío {id_mensaje} descartado: quedó en .Herramientas formulación/Intercambio/procesado/ y el Excel no cambió.")
            print("     El Formulador lo verá como descartado después del próximo run.")
            return 0
        if not af.pf.confirmar(id_mensaje, raiz, cfg["ruta_estado_intercambio"]):
            print(f"[INFO] No hay un envío con id {id_mensaje} en el buzón.")
            return 1
        print(f"[OK] Envío {id_mensaje} confirmado: se reemplazan los valores escritos a mano. Corriendo run...\n")
        af.main(pais=pais)
        return 0

    print("=" * 70)
    print(f"  INTERCAMBIO CON EL FORMULADOR - {pais} (solo lectura)")
    print("=" * 70)
    print(f"\nCarpeta: {raiz}")
    if not af.pf.intercambio.es_carpeta_de_intercambio(raiz):
        print("  Todavía no existe: el próximo run la crea. En el Formulador se conecta desde")
        print("  «Enviar costos al Análisis Financiero» eligiendo esa carpeta.")
    resumen = af.ejecutar(dry_run=True, pais=pais)
    if resumen.get("intercambio"):
        print()
        af.imprimir_intercambio(resumen["intercambio"], aplicado=False)
    else:
        print("\nEl buzón no tiene envíos del Formulador.")
    for aviso in resumen["avisos"]:
        if aviso.startswith("Intercambio"):
            print(f"  [AVISO] {aviso}")
    return 0


def _buscar_presupuesto(repositorio: list[dict], clave: str) -> list[dict]:
    """Por uid, o por código (con «vN» opcional: «QPN-2026-001 v2»)."""
    exacto = [i for i in repositorio if i["uid"] == clave]
    if exacto:
        return exacto
    partes = clave.rsplit(" v", 1)
    codigo = partes[0].strip()
    version = partes[1].strip() if len(partes) == 2 and partes[1].strip().isdigit() else None
    return [i for i in repositorio if str(i["datos"].get("codigo") or "") == codigo
            and (version is None or str(i["datos"].get("version")) == version) and not i["datos"].get("eliminado")]


def cmd_formulaciones(args: list[str], pais: str = "CL") -> int:
    """Presupuestos del repositorio del Formulador (pedido del usuario,
    2026-09-30): qué hay nuevo, qué adjudicado falta cargar en el Análisis
    Financiero, y los comandos para hacerlo con Claude."""
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    cfg = af.PAISES[pais]
    raiz = cfg.get("raiz_intercambio")
    if raiz is None:
        print(f"[INFO] {cfg.get('aviso_sin_intercambio') or f'El intercambio con el Formulador no está activo para {pais}.'}")
        return 0
    fz = af.pf.formulaciones
    sub = args[0] if args else ""

    if sub == "incorporar":
        resultados = fz.incorporar_buzon(raiz)
        if not resultados:
            print("[OK] No hay presupuestos entregados por archivo en el buzón.")
        for r in resultados:
            print(f"[{r['estado'].upper()}] " + " ".join(r["detalle"]))
        return 0

    if sub == "revisadas":
        n = fz.marcar_revisadas(fz.leer_repositorio(raiz))
        print(f"[OK] {n} presupuesto(s) marcados como revisados: el próximo resumen muestra solo lo que cambie desde ahora.")
        return 0

    if sub == "cargar":
        nombre = ""
        resto = list(args[1:])
        if "--nombre" in resto:
            i = resto.index("--nombre")
            nombre = " ".join(resto[i + 1:]).strip()
            resto = resto[:i]
        if len(resto) < 2:
            print('Uso: python driver.py formulaciones cargar <uid|código [vN]> <TAG> [--nombre "Nombre si el TAG es nuevo"]')
            return 2
        tag = af.pf.normalizar_tag(resto[-1])
        clave = " ".join(resto[:-1])
        encontrados = _buscar_presupuesto(fz.leer_repositorio(raiz), clave)
        if len(encontrados) != 1:
            print(f"[ERROR] {'No hay' if not encontrados else 'Hay varios'} presupuestos para «{clave}»"
                  + ("" if not encontrados else ": " + ", ".join(f"{i['uid']} ({fz.titulo_legible(i['datos'])})" for i in encontrados)))
            return 1
        item = encontrados[0]
        sobre = af.pf.intercambio.leer_publicacion(raiz, af.pf.PUBLICACION) or {}
        proyectos = ((sobre.get("datos") if isinstance(sobre, dict) else None) or {}).get("proyectos") or []
        destino = next((p for p in proyectos if p.get("tag") == tag), None)
        if destino is None and not nombre:
            print(f"[ERROR] {tag} no está en la lista del Análisis Financiero. Si es un proyecto nuevo, agrega --nombre \"Nombre del proyecto\".")
            return 1
        autor = item["autor"] or item["datos"].get("responsable") or ""
        try:
            mensaje = af.pf.mensaje_desde_formulacion(
                item, tag, nombre="" if destino else nombre,
                visto=(destino or {}).get("proyectados") if destino else None,
                usuario=f"{autor} (cargado con Claude)".strip(),
            )
        except ValueError as exc:
            print(f"[ERROR] {exc}")
            return 1
        ruta = af.pf.intercambio.enviar(raiz, mensaje)
        print(f"[OK] {fz.titulo_legible(item['datos'])} -> {tag}: envío {mensaje['id']} en el buzón ({ruta.name}).")
        print("     Se aplica en el próximo run del Análisis Financiero, con respaldo y sin pisar valores escritos a mano que no se vieron.")
        return 0

    # Sin subcomando: resumen de solo lectura
    repositorio = fz.leer_repositorio(raiz)
    revisadas = fz.leer_revisadas()
    nov = fz.novedades(repositorio, revisadas)
    adjudicados = af.pf.adjudicados_para_af(raiz, cfg["ruta_estado_intercambio"])
    entregas = fz.entregas_en_buzon(raiz)
    print("=" * 70)
    print(f"  PRESUPUESTOS DEL FORMULADOR - {pais} (solo lectura)")
    print("=" * 70)
    print(f"\nRepositorio: {fz.carpeta_repositorio(raiz)}")
    activos = [i for i in repositorio if not i["datos"].get("eliminado")]
    print(f"  {len(activos)} presupuesto(s), {sum(1 for i in activos if i['datos'].get('estado') == 'Adjudicada')} adjudicado(s)")
    if entregas:
        print(f"\nEntregados por archivo en el buzón, por incorporar ({len(entregas)}): se incorporan en el próximo run"
              " o con «formulaciones incorporar».")
        for m in entregas:
            print(f"  - {fz.titulo_legible(m.get('datos') or {})} · por {(m.get('origen') or {}).get('usuario') or '—'}")
    desde = f" desde la última revisión ({revisadas['fecha'][:16].replace('T', ' ')})" if revisadas.get("fecha") else ""
    if nov["nuevos"] or nov["cambiados"]:
        print(f"\nNovedades{desde}:")
        for i in nov["nuevos"]:
            print(f"  [NUEVO] {fz.linea(i)}")
        for i in nov["cambiados"]:
            print(f"  [CAMBIÓ] {fz.linea(i)}")
        print("  Después de revisarlos con el usuario: python driver.py formulaciones revisadas")
    else:
        print(f"\nSin novedades{desde}.")
    if adjudicados:
        print("\nAdjudicados y el Análisis Financiero:")
        etiquetas = {"cargado": "CARGADO", "en-buzon": "EN BUZÓN", "cargar": "CARGAR", "elegir-tag": "ELEGIR TAG", "sin-resumen": "SIN RESUMEN"}
        for f in adjudicados:
            item = f["item"]
            print(f"  [{etiquetas[f['accion']]}] {fz.titulo_legible(item['datos'])} ({item['uid']}): {f['detalle']}")
            if f["costos"] and f["accion"] in ("cargar", "elegir-tag"):
                print("      Costos del presupuesto: " + ", ".join(f"{c} {af.pf._pesos(v)}" for c, v in f["costos"].items()))
            if f["accion"] == "cargar" and f["proyectados"]:
                print("      Hoy en el Análisis Financiero: " + ", ".join(
                    f"{c} {af.pf._pesos(v) if isinstance(v, (int, float)) else '—'}" for c, v in f["proyectados"].items()))
            if f["accion"] == "cargar":
                print(f"      Para cargar: python driver.py formulaciones cargar {item['uid']} {f['tag']}")
            elif f["accion"] == "elegir-tag":
                print(f"      Sugerido: {f['sugerido'] or '(ninguno claro)'} -- preguntar al usuario y luego:"
                      f" python driver.py formulaciones cargar {item['uid']} <TAG> [--nombre \"...\" si es nuevo]")
    return 0


def main() -> int:
    comandos = ("status", "run", "confirmar-cliente", "visualizador", "intercambio", "formulaciones")
    if len(sys.argv) < 2 or sys.argv[1] not in comandos:
        print("Uso: python driver.py [status|run|confirmar-cliente [--todos|TAG ...]|visualizador"
              "|intercambio [publicar|confirmar <id>|descartar <id>]"
              "|formulaciones [incorporar|revisadas|cargar <uid|código> <TAG> [--nombre ...]]] [--pais CL|PE]")
        return 2
    comando = sys.argv[1]
    pais, resto = _extraer_pais(sys.argv[2:])
    if comando == "status":
        return cmd_status(pais=pais)
    if comando == "intercambio":
        return cmd_intercambio(resto, pais=pais)
    if comando == "formulaciones":
        return cmd_formulaciones(resto, pais=pais)
    if comando == "confirmar-cliente":
        return cmd_confirmar_cliente(resto, pais=pais)
    if comando == "visualizador":
        return cmd_visualizador(pais=pais)
    return cmd_run(pais=pais)


if __name__ == "__main__":
    raise SystemExit(main())
