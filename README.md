# Forus Stock Sync

Aplicación independiente para comparar el stock publicable del ERP en BigQuery con
el inventario `available` de Shopify por SKU, sitio y ubicación.

## Reglas implementadas

- Último registro ERP por `id_producto + codigo_tienda`.
- Relación confirmada `codigo_tienda = numbodega`.
- Solo bodegas activas y asignadas al sitio.
- Sitios ERP considerados: `2`, `4`, `6`, `24`, `102`, `103`.
- Stock base:
  `stock_tiendas + reserva_retail + disponible - reserva_ecommerce - merma - segunda`.
- Stock de seguridad descontado por SKU-bodega cuando el stock base es positivo.
- Resultado mínimo cero y tolerancia de comparación igual a cero.
- `FULL OUTER JOIN` para detectar registros exclusivos de ERP o Shopify.
- Detección de relaciones bodega-sitio duplicadas.

## Configuración

La app está pensada para ejecutarse en modo directo contra BigQuery:

```toml
[bigquery]
mode = "query"
project_id = "forus-analitica-prod-datalake"
job_project_id = "forus-analitica-prod-datalake"
location = "US"
stock_table = "forus-analitica-prod-datalake.pe_bronze.stg_pe_central_stock_bi"
warehouses_table = "forus-analitica-prod-datalake.pe_bronze.stg_pe_ecommerce_cen_bodegas_ecommerce"
warehouse_sites_table = "forus-analitica-prod-datalake.pe_bronze.stg_pe_ecommerce_cen_bodegas_sitios"
warehouse_sites_site_column = "idsitio"
warehouse_sites_warehouse_column = "bodega"
enabled_erp_site_ids = ["2", "4", "6", "24", "102", "103"]
```

Permisos mínimos para la cuenta de servicio:

- `BigQuery Job User` en `job_project_id`.
- `BigQuery Data Viewer` sobre las tablas/dataset origen.

El archivo real `.streamlit/secrets.toml` no debe versionarse.

## Homologación ERP → Shopify

```toml
[site_mapping.erp_to_shopify]
"2" = "columbia"
"4" = "rockford"
"6" = "hush_puppies"
"24" = "bsoul"
"102" = "parfois"
"103" = "vans"
```

Cada valor de la derecha debe existir como bloque `[shopify_sites.<clave>]`.

## Ejecución local

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
streamlit run app.py
```

## Programación diaria

La zona horaria operativa es `America/Lima` (UTC-5). La actualización diaria debe
ejecutarse a las `08:00`, equivalente a `13:00 UTC` (`0 13 * * *`).

## Pruebas

```powershell
pytest
ruff check .
```
