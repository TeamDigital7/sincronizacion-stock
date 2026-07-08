from __future__ import annotations

from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd

from .config import BigQueryConfig


class BigQuerySource:
    def __init__(self, config: BigQueryConfig, service_account_info: dict):
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        self.config = config
        self.client = bigquery.Client(
            project=config.job_project_id,
            credentials=credentials,
            location=config.location,
        )

    def fetch_erp_stock(self, sites: list[str] | None = None) -> pd.DataFrame:
        c = self.config
        sql = f"""
        WITH warehouse_site AS (
          SELECT DISTINCT
            TRIM(CAST(bs.sitio AS STRING)) AS sitio,
            TRIM(CAST(bs.bodega AS STRING)) AS bodega
          FROM `{c.warehouse_sites_table}` bs
          WHERE bs.sitio IS NOT NULL AND bs.bodega IS NOT NULL
        ),
        duplicate_links AS (
          SELECT sitio, bodega, COUNT(*) AS source_rows
          FROM (
            SELECT
              TRIM(CAST(sitio AS STRING)) AS sitio,
              TRIM(CAST(bodega AS STRING)) AS bodega
            FROM `{c.warehouse_sites_table}`
          )
          GROUP BY 1, 2
        ),
        active_warehouses AS (
          SELECT
            TRIM(CAST(numbodega AS STRING)) AS bodega,
            ANY_VALUE(TRIM(CAST(nombrebodega AS STRING))) AS nombrebodega,
            MAX(COALESCE(SAFE_CAST(stock_seguridad AS NUMERIC), 0)) AS stock_seguridad
          FROM `{c.warehouses_table}`
          WHERE UPPER(TRIM(CAST(estado AS STRING))) = 'ACTIVO'
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
                ORDER BY fecha_corte DESC
              ) AS row_num
            FROM `{c.stock_table}`
          )
          WHERE row_num = 1
        )
        SELECT
          ws.sitio,
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
          IF(dl.source_rows > 1, TRUE, FALSE) AS relacion_bodega_sitio_duplicada
        FROM latest_stock s
        JOIN active_warehouses aw ON aw.bodega = s.codigo_tienda
        JOIN warehouse_site ws ON ws.bodega = aw.bodega
        LEFT JOIN duplicate_links dl USING (sitio, bodega)
        WHERE (NOT @filter_sites OR ws.sitio IN UNNEST(@sites))
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("filter_sites", "BOOL", bool(sites)),
                bigquery.ArrayQueryParameter("sites", "STRING", sites or []),
            ]
        )
        return self.client.query(sql, job_config=job_config).result().to_dataframe()
