---
name: Organizar_Proyecto
description: Reorganiza la raíz desordenada de un módulo en una estructura navegable sin romper el código que referencia esas rutas. Usar SOLO si el usuario escribe "/Organizar_Proyecto"; si pide con palabras reorganizar u ordenar una carpeta, confirma primero. No sirve para mover un solo archivo sin referencias.
---

# Organizar Proyecto

1. **Inventaria la raíz** (`Get-ChildItem -Force`) y clasifica cada elemento:
   - **Ancla fija**, nunca se mueve: `.git`, `.claude/` (Claude Code solo lo busca en la raíz del proyecto abierto), `docs/`
     (enlazado por ruta relativa), el `CLAUDE.md` superior si otro lo enlaza.
   - **Producto**: lo que el usuario abre y edita (un `.xlsx`). **Fuente/datos**: documentos de entrada, JSON.
   - **Sistema**: código, tests, respaldos, legado. **Huérfano**: pertenece a otro nivel.
   - **Caché regenerable** (`__pycache__/`, `.pytest_cache/`): se borra, no se mueve.
2. **Separa versionado de no versionado** con `git ls-files <carpeta>`, sin asumir. Los datos reales suelen estar gitignorados
   y eso decide el método del paso 5.
3. **Propón la estructura y espera aprobación explícita**: 2 a 4 carpetas, en el vocabulario del proyecto (`Excel/`,
   `Sistema/`, no `data/` ni `src/`). Son datos reales sin red de seguridad.
4. **Encuentra todas las referencias de ruta antes de mover**: la constante raíz, `sys.path.insert` y las menciones en
   `CLAUDE.md`, `SKILL.md` y `.gitignore`. Si están dispersas, dilo: vale la pena centralizarlas.
5. **Mueve**: versionados con `git mv`; gitignorados con `Move-Item`, nunca `git mv`. Antes de mover un archivo de Office,
   verifica que no esté abierto (ábrelo en `ReadWrite` exclusivo; si falla, pide cerrarlo).
6. **Actualiza las referencias** del paso 4. No ejecutes nada del proyecto en el estado intermedio.
7. **Verifica antes y después** con un comando de solo lectura (`driver.py status`) o las pruebas, sin diferencias. Si no hay,
   importa el script principal y confirma que no lanza `FileNotFoundError`.
8. **Limpia las cachés** de la ubicación vieja.

No anides `.claude/` ni `docs/` en una subcarpeta nueva: se dejan de encontrar las skills y se rompen los enlaces.
