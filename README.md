# Datos Demográficos de México

Colección de scripts para descargar y procesar datos demográficos de México desde fuentes oficiales, generando archivos JSON listos para usar en aplicaciones.

Si este proyecto te es útil, considera darle una estrella en GitHub ⭐ — ayuda a que más personas lo encuentren.

## Fuentes de datos

| Fuente | Datos | Script |
|--------|-------|--------|
| [INEGI](https://www.inegi.org.mx) — API Catálogo Único de Claves Geoestadísticas | Estados, municipios y localidades | `scripts/1_datos_inegi.py` |
| [SEPOMEX](https://www.correosdemexico.gob.mx) — Correos de México | Colonias, códigos postales y asentamientos | `scripts/2_datos_sepomex.py` |

## Estructura del proyecto

```
mexico-geodata/
├── scripts/
│   ├── 1_datos_inegi.py       # Descarga catálogos de INEGI
│   └── 2_datos_sepomex.py     # Procesa el archivo TXT de SEPOMEX
└── geodata/
    ├── inegi/
    │   ├── estados.json
    │   ├── municipios.json
    │   ├── localidades.json
    │   └── errores_localidades.json   # Solo si hubo errores
    └── sepomex/
        ├── colonias.json
        ├── codigos_postales.json
        ├── tipos_asentamiento.json
        └── resumen_sepomex.json
```

## Requisitos

- Python 3.7+
- Sin dependencias externas (solo librerías estándar)

## Uso

### 1. Datos INEGI

Descarga los 32 estados, ~2,500 municipios y ~300,000 localidades directamente desde la API pública de INEGI.

```bash
# Descarga completa (estados + municipios + localidades)
python scripts/1_datos_inegi.py

# Solo estados y municipios (más rápido, ~1 minuto)
python scripts/1_datos_inegi.py --sin-localidades

# Ajustar el delay entre requests (default: 0.3s)
python scripts/1_datos_inegi.py --delay 0.5
```

Los archivos se guardan en `geodata/inegi/`.

### 2. Datos SEPOMEX

Procesa el archivo TXT oficial de SEPOMEX con ~145,000 asentamientos y códigos postales.

**Paso previo — descargar el archivo TXT:**
1. Ve a https://www.correosdemexico.gob.mx/SSLServicios/ConsultaCP/CodigoPostal_Exportar.aspx
2. Selecciona **"Todos"** en el campo de estado
3. Selecciona formato **TXT**
4. Descarga y descomprime el `.zip`

```bash
# Procesar el archivo descargado
python scripts/2_datos_sepomex.py CPdescarga.txt

# Especificar codificación manualmente (default: auto-detectar)
python scripts/2_datos_sepomex.py CPdescarga.txt --encoding latin-1
```

Los archivos se guardan en `geodata/sepomex/`.

## Archivos generados

### INEGI

| Archivo | Descripción |
|---------|-------------|
| `estados.json` | 32 entidades federativas con clave y nombre |
| `municipios.json` | ~2,500 municipios con clave de estado y municipio |
| `localidades.json` | ~300,000 localidades con coordenadas y claves |

### SEPOMEX

| Archivo | Descripción |
|---------|-------------|
| `colonias.json` | ~145,000 asentamientos con CP, municipio, estado y zona |
| `codigos_postales.json` | CPs únicos con su municipio y estado correspondiente |
| `tipos_asentamiento.json` | Catálogo de tipos: Colonia, Fraccionamiento, Barrio, etc. |
| `resumen_sepomex.json` | Estadísticas del procesamiento |
