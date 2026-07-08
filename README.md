# Forus Stock Sync

Aplicación independiente para comparar el stock publicable del ERP en BigQuery con
el inventario `available` de Shopify por SKU, sitio y ubicación.

## Reglas implementadas

- Último registro ERP por `id_producto + codigo_tienda`.
- Relación confirmada `codigo_tienda = numbodega`.
- Solo bodegas activas y asignadas al sitio.
- Stock base: `stock_tiendas + reserva_retail + disponible
  - reserva_ecommerce - merma - segunda`.
- Stock de seguridad descontado por SKU–bodega cuando el stock base es positivo.
- Resultado mínimo cero y tolerancia de comparación igual a cero.
- `FULL OUTER JOIN` para detectar registros exclusivos de cualquiera de las fuentes.
- Detección de relaciones bodega–sitio duplicadas sin multiplicar el stock.

## Instalación

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .streamlit\secrets.example.toml .streamlit\secrets.toml
```

Complete `.streamlit/secrets.toml` con los IDs de tabla, cuenta de servicio, usuarios,
tokens y el mapeo de cada ubicación Shopify a `codigo_tienda`. El archivo real está
excluido de Git.

La zona horaria operativa es `America/Lima` (UTC−5) y la conciliación programada debe
ejecutarse todos los días a las `08:00`. En un planificador configurado en UTC, esto
equivale a `13:00 UTC` y a la expresión cron `0 13 * * *`. El planificador del entorno
de despliegue debe invocar el proceso; una sesión de Streamlit no sustituye un
servicio de tareas programadas.

La app usa únicamente `admin_access_token`; `client_id` y `client_secret` no son
necesarios para un token ya emitido. El token requiere `read_inventory`.

## Ejecución

```powershell
streamlit run app.py
```

## Pruebas

```powershell
pytest
ruff check .
```

## Decisiones operativas pendientes

- Confirmar que los valores de `Bodegas_Sitios.sitio` coinciden exactamente con las
  claves `columbia`, `rockford` y `hush_puppies`; si no, deben configurarse con esos
  nombres o agregarse un mapeo.
- Configurar en el entorno de despliegue el disparador diario de las `08:00`
  (`America/Lima`, UTC−5). La aplicación conserva también la ejecución manual.
- No se recibió un campo de unidad de medida. El sistema compara unidades enteras y
  no realiza conversiones; una futura fuente de UDM debe validarse antes del cruce.
