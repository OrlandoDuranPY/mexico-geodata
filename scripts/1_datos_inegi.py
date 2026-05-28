"""
Script para descargar catálogos de INEGI (estados, municipios, localidades)
desde la API pública del Catálogo Único de Claves Geoestadísticas.

Genera 3 archivos JSON:
  - estados.json
  - municipios.json
  - localidades.json

Uso:
  python descargar_inegi.py
  python descargar_inegi.py --sin-localidades   (solo estados y municipios, más rápido)
"""

import json
import time
import sys
import os
import argparse
import urllib.request
import urllib.error

BASE_URL = "https://gaia.inegi.org.mx/wscatgeo/v2"

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


def fetch_json(url, max_retries=3, delay=0.5):
    """Hace un GET a la URL y devuelve el JSON parseado. Reintenta en caso de error."""
    import ssl
    ctx = ssl.create_default_context()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-MX,es;q=0.9",
    }

    for intento in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if intento < max_retries:
                log_warn(f"Intento {intento}/{max_retries} falló para {url}: {e}. Reintentando en {delay * intento}s...")
                time.sleep(delay * intento)
            else:
                log_error(f"Falló después de {max_retries} intentos: {url}")
                raise
        except json.JSONDecodeError as e:
            log_error(f"Respuesta no es JSON válido de {url}: {e}")
            raise


def guardar_json(data, filepath):
    """Guarda datos como JSON con formato legible y codificación UTF-8."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    log_ok(f"Guardado: {filepath} ({len(data)} registros, {size_mb:.1f} MB)")


def descargar_estados():
    """Descarga los 32 estados (entidades federativas)."""
    log_info("Descargando estados...")
    url = f"{BASE_URL}/mgee/"
    data = fetch_json(url)
    estados = data.get("datos", [])
    log_ok(f"Se obtuvieron {len(estados)} estados")
    return estados


def descargar_municipios(estados, delay=0.3):
    """Descarga los municipios de cada estado."""
    log_info("Descargando municipios...")
    todos_municipios = []
    total = len(estados)

    for i, estado in enumerate(estados, 1):
        cve_ent = estado["cve_ent"]
        nombre = estado["nomgeo"]
        url = f"{BASE_URL}/mgem/{cve_ent}"

        try:
            data = fetch_json(url)
            municipios = data.get("datos", [])
            todos_municipios.extend(municipios)
            print(f"  [{i:2d}/{total}] {nombre}: {len(municipios)} municipios")
        except Exception as e:
            log_error(f"  [{i:2d}/{total}] Error en {nombre} ({cve_ent}): {e}")

        time.sleep(delay)

    log_ok(f"Total de municipios: {len(todos_municipios)}")
    return todos_municipios


def descargar_localidades(municipios, delay=0.3):
    """Descarga las localidades de cada municipio."""
    log_info("Descargando localidades (esto puede tardar ~20-40 minutos)...")
    todas_localidades = []
    total = len(municipios)
    errores = []

    for i, mun in enumerate(municipios, 1):
        cve_ent = mun["cve_ent"]
        cve_mun = mun["cve_mun"]
        nombre_mun = mun["nomgeo"]
        url = f"{BASE_URL}/localidades/{cve_ent}/{cve_mun}"

        try:
            data = fetch_json(url)
            localidades = data.get("datos", [])
            todas_localidades.extend(localidades)

            # Mostrar progreso cada 50 municipios o al final
            if i % 50 == 0 or i == total:
                print(f"  [{i:4d}/{total}] Localidades acumuladas: {len(todas_localidades):,}")
        except Exception as e:
            errores.append({"cve_ent": cve_ent, "cve_mun": cve_mun, "nombre": nombre_mun, "error": str(e)})
            if i % 50 == 0 or i == total:
                print(f"  [{i:4d}/{total}] Localidades acumuladas: {len(todas_localidades):,} (errores: {len(errores)})")

        time.sleep(delay)

    log_ok(f"Total de localidades: {len(todas_localidades):,}")

    if errores:
        log_warn(f"Hubo {len(errores)} municipios con error:")
        for err in errores[:10]:
            print(f"    - {err['nombre']} ({err['cve_ent']}-{err['cve_mun']}): {err['error']}")
        if len(errores) > 10:
            print(f"    ... y {len(errores) - 10} más")

    return todas_localidades, errores


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output = os.path.join(project_root, "geodata", "inegi")

    parser = argparse.ArgumentParser(description="Descarga catálogos de INEGI (estados, municipios, localidades)")
    parser.add_argument("--sin-localidades", action="store_true", help="Solo descargar estados y municipios (más rápido)")
    parser.add_argument("--delay", type=float, default=0.3, help="Segundos entre requests (default: 0.3)")
    args = parser.parse_args()

    os.makedirs(output, exist_ok=True)

    print(f"\n{Color.BOLD}{'='*60}")
    print(f"  DESCARGA DE CATÁLOGOS INEGI")
    print(f"  Fuente: API Catálogo Único de Claves Geoestadísticas")
    print(f"{'='*60}{Color.RESET}\n")

    inicio = time.time()

    # 1. Estados
    estados = descargar_estados()
    guardar_json(estados, os.path.join(output, "estados.json"))
    print()

    # 2. Municipios
    municipios = descargar_municipios(estados, delay=args.delay)
    guardar_json(municipios, os.path.join(output, "municipios.json"))
    print()

    # 3. Localidades (opcional)
    if not args.sin_localidades:
        localidades, errores = descargar_localidades(municipios, delay=args.delay)
        guardar_json(localidades, os.path.join(output, "localidades.json"))

        if errores:
            guardar_json(errores, os.path.join(output, "errores_localidades.json"))
        print()
    else:
        log_info("Saltando localidades (--sin-localidades)")
        print()

    # Resumen
    elapsed = time.time() - inicio
    minutos = int(elapsed // 60)
    segundos = int(elapsed % 60)

    print(f"{Color.BOLD}{'='*60}")
    print(f"  RESUMEN")
    print(f"{'='*60}{Color.RESET}")
    print(f"  Estados:     {len(estados):>10,}")
    print(f"  Municipios:  {len(municipios):>10,}")
    if not args.sin_localidades:
        print(f"  Localidades: {len(localidades):>10,}")
    print(f"  Tiempo:      {minutos}m {segundos}s")
    print(f"  Archivos en: {os.path.abspath(output)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()