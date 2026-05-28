"""
Script para procesar el archivo TXT de SEPOMEX (Correos de México)
y generar JSON de colonias/asentamientos con códigos postales.

PASO PREVIO - Descargar el archivo TXT:
  1. Ve a: https://www.correosdemexico.gob.mx/SSLServicios/ConsultaCP/CodigoPostal_Exportar.aspx
  2. Selecciona "---------- T o d o s ----------"
  3. Selecciona formato "TXT"
  4. Descarga y descomprime el archivo .zip
  5. Dentro encontrarás un archivo .txt (ej: CPdescarga.txt)

Uso:
  python procesar_sepomex.py CPdescarga.txt
  python procesar_sepomex.py CPdescarga.txt --encoding latin-1

Genera:
  - colonias.json           → Todos los asentamientos (~145,000+ registros)
  - codigos_postales.json   → Relación CP → municipio → estado
  - tipos_asentamiento.json → Catálogo de tipos (Colonia, Fraccionamiento, Barrio, etc.)
  - resumen_sepomex.json    → Estadísticas del procesamiento
"""

import json
import csv
import sys
import os
import argparse
from collections import Counter, defaultdict

# Colores para la terminal
class Color:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log_info(msg):
    print(f"{Color.CYAN}[INFO]{Color.RESET} {msg}")

def log_ok(msg):
    print(f"{Color.GREEN}[OK]{Color.RESET} {msg}")

def log_warn(msg):
    print(f"{Color.YELLOW}[WARN]{Color.RESET} {msg}")

def log_error(msg):
    print(f"{Color.RED}[ERROR]{Color.RESET} {msg}")


def guardar_json(data, filepath):
    """Guarda datos como JSON con formato legible y codificación UTF-8."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    registros = len(data) if isinstance(data, list) else len(data.keys()) if isinstance(data, dict) else 0
    log_ok(f"Guardado: {filepath} ({registros} registros, {size_mb:.1f} MB)")


def detectar_encoding(filepath):
    """Intenta detectar la codificación del archivo."""
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                f.read(5000)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "latin-1"  # fallback


def leer_archivo_sepomex(filepath, encoding=None):
    """
    Lee el archivo TXT de SEPOMEX y devuelve una lista de diccionarios.
    
    El archivo TXT de SEPOMEX tiene:
    - Línea 1: Leyenda legal (se salta)
    - Línea 2: Encabezados separados por |
    - Líneas 3+: Datos separados por |
    """
    if encoding is None:
        encoding = detectar_encoding(filepath)
        log_info(f"Codificación detectada: {encoding}")

    registros = []
    errores_linea = 0

    # Nombres de los campos del archivo SEPOMEX
    campos = [
        "d_codigo",           # Código Postal
        "d_asenta",           # Nombre del asentamiento (colonia)
        "d_tipo_asenta",      # Tipo de asentamiento (Colonia, Fraccionamiento, etc.)
        "D_mnpio",            # Nombre del municipio
        "d_estado",           # Nombre del estado
        "d_ciudad",           # Nombre de la ciudad
        "d_CP",               # CP de la administración postal
        "c_estado",           # Clave del estado (INEGI)
        "c_oficina",          # Clave oficina postal
        "c_CP",               # Campo vacío
        "c_tipo_asenta",      # Clave tipo de asentamiento
        "c_mnpio",            # Clave municipio (INEGI)
        "id_asenta_cpcons",   # ID único del asentamiento (nivel municipal)
        "d_zona",             # Zona: Urbano / Rural / Semiurbano
        "c_cve_ciudad",       # Clave de la ciudad
    ]

    with open(filepath, "r", encoding=encoding) as f:
        lineas = f.readlines()

    # Saltar las primeras líneas (leyenda legal y encabezados)
    # Buscar la línea de encabezados que contiene "d_codigo"
    inicio_datos = 0
    for i, linea in enumerate(lineas):
        if "d_codigo" in linea.lower():
            inicio_datos = i + 1
            # Usar los encabezados del archivo si los tiene
            encabezados_archivo = [h.strip() for h in linea.split("|")]
            if len(encabezados_archivo) >= 14:
                campos = encabezados_archivo
            break

    if inicio_datos == 0:
        # Si no encontramos encabezados, asumimos que la línea 1 es leyenda y línea 2 son datos
        # o línea 1 leyenda, línea 2 encabezados, línea 3+ datos
        for i, linea in enumerate(lineas):
            partes = linea.strip().split("|")
            if len(partes) >= 14:
                # Verificar si es dato (el primer campo es un CP de 5 dígitos)
                if partes[0].strip().isdigit() and len(partes[0].strip()) == 5:
                    inicio_datos = i
                    break
                else:
                    # Podría ser la línea de encabezados
                    campos = [h.strip() for h in partes]
                    inicio_datos = i + 1

    log_info(f"Datos inician en línea {inicio_datos + 1}")
    log_info(f"Total de líneas en archivo: {len(lineas)}")

    for num_linea, linea in enumerate(lineas[inicio_datos:], start=inicio_datos + 1):
        linea = linea.strip()
        if not linea:
            continue

        partes = linea.split("|")

        if len(partes) < 14:
            errores_linea += 1
            continue

        registro = {}
        for j, campo in enumerate(campos):
            if j < len(partes):
                registro[campo.strip()] = partes[j].strip()
            else:
                registro[campo.strip()] = ""

        registros.append(registro)

    if errores_linea > 0:
        log_warn(f"Se saltaron {errores_linea} líneas con formato incorrecto")

    log_ok(f"Se leyeron {len(registros):,} registros del archivo SEPOMEX")
    return registros


def normalizar_registros(registros):
    """
    Normaliza los nombres de campos y limpia los datos.
    Genera un formato consistente para el JSON de salida.
    """
    colonias = []

    for reg in registros:
        # Normalizar nombres de campos (el archivo tiene inconsistencias: D_mnpio vs d_mnpio)
        r = {k.lower().strip(): v for k, v in reg.items()}

        colonia = {
            "codigo_postal":      r.get("d_codigo", "").strip(),
            "nombre":             r.get("d_asenta", "").strip(),
            "tipo_asentamiento":  r.get("d_tipo_asenta", "").strip(),
            "municipio":          r.get("d_mnpio", "").strip(),
            "estado":             r.get("d_estado", "").strip(),
            "ciudad":             r.get("d_ciudad", "").strip(),
            "zona":               r.get("d_zona", "").strip(),
            "cve_estado":         r.get("c_estado", "").strip(),
            "cve_municipio":      r.get("c_mnpio", "").strip(),
            "cve_tipo_asenta":    r.get("c_tipo_asenta", "").strip(),
            "cve_ciudad":         r.get("c_cve_ciudad", "").strip(),
            "id_asentamiento":    r.get("id_asenta_cpcons", "").strip(),
            "cp_administracion":  r.get("d_cp", "").strip(),
        }

        colonias.append(colonia)

    return colonias


def generar_catalogo_tipos(colonias):
    """Genera catálogo de tipos de asentamiento con sus claves."""
    tipos = {}
    for col in colonias:
        clave = col["cve_tipo_asenta"]
        nombre = col["tipo_asentamiento"]
        if clave and nombre and clave not in tipos:
            tipos[clave] = nombre

    # Ordenar por clave
    tipos_lista = [
        {"clave": k, "nombre": v}
        for k, v in sorted(tipos.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999)
    ]
    return tipos_lista


def generar_codigos_postales(colonias):
    """Genera catálogo de códigos postales únicos con su municipio y estado."""
    cps = {}
    for col in colonias:
        cp = col["codigo_postal"]
        if cp and cp not in cps:
            cps[cp] = {
                "codigo_postal": cp,
                "municipio": col["municipio"],
                "estado": col["estado"],
                "ciudad": col["ciudad"],
                "zona": col["zona"],
                "cve_estado": col["cve_estado"],
                "cve_municipio": col["cve_municipio"],
                "cp_administracion": col["cp_administracion"],
            }

    return sorted(cps.values(), key=lambda x: x["codigo_postal"])


def generar_resumen(colonias):
    """Genera estadísticas del procesamiento."""
    estados = Counter(col["estado"] for col in colonias)
    tipos = Counter(col["tipo_asentamiento"] for col in colonias)
    zonas = Counter(col["zona"] for col in colonias)
    cps_unicos = len(set(col["codigo_postal"] for col in colonias))
    municipios_unicos = len(set((col["cve_estado"], col["cve_municipio"]) for col in colonias))

    return {
        "total_registros": len(colonias),
        "codigos_postales_unicos": cps_unicos,
        "estados": len(estados),
        "municipios_unicos": municipios_unicos,
        "por_estado": dict(estados.most_common()),
        "por_tipo_asentamiento": dict(tipos.most_common()),
        "por_zona": dict(zonas.most_common()),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Procesa el archivo TXT de SEPOMEX y genera JSON de colonias",
        epilog="""
Descarga el archivo TXT desde:
  https://www.correosdemexico.gob.mx/SSLServicios/ConsultaCP/CodigoPostal_Exportar.aspx
  (Selecciona "Todos" y formato "TXT")
        """
    )
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output = os.path.join(project_root, "geodata", "sepomex")

    parser.add_argument("archivo", help="Ruta al archivo TXT de SEPOMEX (ej: CPdescarga.txt)")
    parser.add_argument("--encoding", "-e", default=None, help="Codificación del archivo (default: auto-detectar, normalmente latin-1)")
    args = parser.parse_args()

    if not os.path.isfile(args.archivo):
        log_error(f"No se encontró el archivo: {args.archivo}")
        print(f"\nDescarga el archivo TXT desde:")
        print(f"  https://www.correosdemexico.gob.mx/SSLServicios/ConsultaCP/CodigoPostal_Exportar.aspx")
        print(f"  Selecciona 'Todos' y formato 'TXT', descomprime el .zip")
        sys.exit(1)

    os.makedirs(output, exist_ok=True)

    print(f"\n{Color.BOLD}{'='*60}")
    print(f"  PROCESAMIENTO DE CATÁLOGO SEPOMEX")
    print(f"  Fuente: Servicio Postal Mexicano (Correos de México)")
    print(f"{'='*60}{Color.RESET}\n")

    # 1. Leer archivo
    registros = leer_archivo_sepomex(args.archivo, encoding=args.encoding)
    print()

    # 2. Normalizar
    log_info("Normalizando registros...")
    colonias = normalizar_registros(registros)
    log_ok(f"Normalizados {len(colonias):,} registros")
    print()

    # 3. Guardar colonias
    guardar_json(colonias, os.path.join(output, "colonias.json"))

    # 4. Generar y guardar códigos postales únicos
    cps = generar_codigos_postales(colonias)
    guardar_json(cps, os.path.join(output, "codigos_postales.json"))

    # 5. Generar y guardar catálogo de tipos de asentamiento
    tipos = generar_catalogo_tipos(colonias)
    guardar_json(tipos, os.path.join(output, "tipos_asentamiento.json"))

    # 6. Resumen
    resumen = generar_resumen(colonias)
    guardar_json(resumen, os.path.join(output, "resumen_sepomex.json"))

    print()
    print(f"{Color.BOLD}{'='*60}")
    print(f"  RESUMEN")
    print(f"{'='*60}{Color.RESET}")
    print(f"  Colonias/asentamientos: {resumen['total_registros']:>10,}")
    print(f"  Códigos postales:       {resumen['codigos_postales_unicos']:>10,}")
    print(f"  Estados:                {resumen['estados']:>10,}")
    print(f"  Municipios:             {resumen['municipios_unicos']:>10,}")
    print()
    print(f"  Tipos de asentamiento:")
    for tipo, cantidad in sorted(resumen["por_tipo_asentamiento"].items(), key=lambda x: -x[1])[:10]:
        print(f"    {tipo:<30s} {cantidad:>8,}")
    if len(resumen["por_tipo_asentamiento"]) > 10:
        print(f"    ... y {len(resumen['por_tipo_asentamiento']) - 10} tipos más")
    print()
    print(f"  Archivos en: {os.path.abspath(output)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()