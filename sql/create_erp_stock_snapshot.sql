-- Crea o reemplaza una tabla física para que Streamlit pueda leerla sin BigQuery Job User.
-- Este SQL debe ejecutarse con una cuenta/proceso que SÍ tenga permisos de jobs.
--
-- Reemplazar:
--   `proyecto.dataset.stock_sync_erp_snapshot`
-- por la tabla destino final.

CREATE OR REPLACE TABLE `proyecto.dataset.stock_sync_erp_snapshot` AS
WITH warehouse_site_raw AS (
  SELECT
    TRIM(CAST(bs.idsitio AS STRING)) AS sitio,
    CAST(NULL AS STRING) AS nombre_sitio_erp,
    TRIM(CAST(bs.bodega AS STRING)) AS bodega
  FROM `forus-analitica-prod-datalake.pe_bronze.stg_pe_ecommerce_cen_bodegas_sitios` bs
  WHERE bs.idsitio IS NOT NULL
    AND bs.bodega IS NOT NULL
    AND TRIM(CAST(bs.bodega AS STRING)) != ''
    AND TRIM(CAST(bs.idsitio AS STRING)) IN ('2', '4', '6', '24', '102', '103')
),
warehouse_site AS (
  SELECT DISTINCT sitio, nombre_sitio_erp, bodega
  FROM warehouse_site_raw
),
duplicate_links AS (
  SELECT sitio, bodega, COUNT(*) AS source_rows
  FROM warehouse_site_raw
  GROUP BY 1, 2
),
active_warehouses AS (
  SELECT
    TRIM(CAST(numbodega AS STRING)) AS bodega,
    ANY_VALUE(TRIM(CAST(nombrebodega AS STRING))) AS nombrebodega,
    MAX(COALESCE(SAFE_CAST(stock_seguridad AS NUMERIC), 0)) AS stock_seguridad
  FROM `forus-analitica-prod-datalake.pe_bronze.stg_pe_ecommerce_cen_bodegas_ecommerce`
  WHERE SAFE_CAST(estado AS INT64) = 1
  GROUP BY 1
),
latest_stock AS (
  SELECT * EXCEPT(row_num)
  FROM (
    SELECT
      TRIM(CAST(id_producto AS STRING)) AS id_producto,
      TRIM(CAST(codigo_tienda AS STRING)) AS codigo_tienda,
      CAST(conca AS STRING) AS conca,
      CAST(talla AS STRING) AS talla,
      fecha_corte,
      COALESCE(SAFE_CAST(stock_tiendas AS NUMERIC), 0) AS stock_tiendas,
      COALESCE(SAFE_CAST(reserva_retail AS NUMERIC), 0) AS reserva_retail,
      COALESCE(SAFE_CAST(disponible AS NUMERIC), 0) AS disponible,
      COALESCE(SAFE_CAST(reserva_ecommerce AS NUMERIC), 0) AS reserva_ecommerce,
      COALESCE(SAFE_CAST(merma AS NUMERIC), 0) AS merma,
      COALESCE(SAFE_CAST(segunda AS NUMERIC), 0) AS segunda,
      ROW_NUMBER() OVER (
        PARTITION BY TRIM(CAST(id_producto AS STRING)),
                     TRIM(CAST(codigo_tienda AS STRING))
        ORDER BY
          fecha_corte DESC,
          (
            IF(stock_tiendas IS NULL, 0, 1)
            + IF(reserva_retail IS NULL, 0, 1)
            + IF(disponible IS NULL, 0, 1)
            + IF(reserva_ecommerce IS NULL, 0, 1)
            + IF(merma IS NULL, 0, 1)
            + IF(segunda IS NULL, 0, 1)
          ) DESC
      ) AS row_num
    FROM `forus-analitica-prod-datalake.pe_bronze.stg_pe_central_stock_bi`
  )
  WHERE row_num = 1
    AND EXTRACT(YEAR FROM fecha_corte) = EXTRACT(YEAR FROM CURRENT_DATE("America/Lima"))
)
SELECT
  ws.sitio,
  ws.sitio AS sitio_erp,
  ws.nombre_sitio_erp,
  s.id_producto,
  s.codigo_tienda,
  s.conca,
  s.talla,
  s.fecha_corte AS fecha_corte_erp,
  aw.nombrebodega,
  aw.stock_seguridad AS stock_seguridad_aplicado,
  GREATEST(
    s.stock_tiendas + s.reserva_retail + s.disponible
    - s.reserva_ecommerce - s.merma - s.segunda
    - IF(
        s.stock_tiendas + s.reserva_retail + s.disponible
        - s.reserva_ecommerce - s.merma - s.segunda > 0,
        aw.stock_seguridad,
        0
      ),
    0
  ) AS stock_erp_sitio,
  IF(dl.source_rows > 1, TRUE, FALSE) AS relacion_bodega_sitio_duplicada,
  CURRENT_TIMESTAMP() AS fecha_generacion_snapshot
FROM latest_stock s
JOIN active_warehouses aw ON aw.bodega = s.codigo_tienda
JOIN warehouse_site ws ON ws.bodega = aw.bodega
LEFT JOIN duplicate_links dl USING (sitio, bodega);
