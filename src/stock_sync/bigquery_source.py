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
        enabled_sites = list(c.enabled_erp_site_ids)
        sql = f"""
        WITH warehouse_site AS (
          SELECT DISTINCT
            TRIM(CAST(bs.`{c.warehouse_sites_site_column}` AS STRING)) AS sitio,
            TRIM(CAST(bs.`{c.warehouse_sites_name_column}` AS STRING)) AS nombre_sitio_erp,
            TRIM(bodega) AS bodega
          FROM `{c.warehouse_sites_table}` bs
          CROSS JOIN UNNEST(
            SPLIT(
              REPLACE(
                REPLACE(
                  REPLACE(
                    REPLACE(CAST(bs.`{c.warehouse_sites_warehouses_column}` AS STRING), '[', ''),
                    ']',
                    ''
                  ),
                  '"',
                  ''
                ),
                ' ',
                ''
              ),
              ','
            )
          ) AS bodega
          WHERE bs.`{c.warehouse_sites_site_column}` IS NOT NULL
            AND bs.`{c.warehouse_sites_warehouses_column}` IS NOT NULL
            AND TRIM(bodega) != ''
            AND TRIM(CAST(bs.`{c.warehouse_sites_site_column}` AS STRING))
              IN UNNEST(@enabled_sites)
        ),
        duplicate_links AS (
          SELECT sitio, bodega, COUNT(*) AS source_rows
          FROM (
            SELECT
              TRIM(CAST(bs.`{c.warehouse_sites_site_column}` AS STRING)) AS sitio,
              TRIM(bodega) AS bodega
            FROM `{c.warehouse_sites_table}` bs
            CROSS JOIN UNNEST(
              SPLIT(
                REPLACE(
                  REPLACE(
                    REPLACE(
                      REPLACE(CAST(bs.`{c.warehouse_sites_warehouses_column}` AS STRING), '[', ''),
                      ']',
                      ''
                    ),
                    '"',
                    ''
                  ),
                  ' ',
                  ''
                ),
                ','
              )
            ) AS bodega
            WHERE TRIM(CAST(bs.`{c.warehouse_sites_site_column}` AS STRING))
              IN UNNEST(@enabled_sites)
              AND TRIM(bodega) != ''
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
                bigquery.ArrayQueryParameter("enabled_sites", "STRING", enabled_sites),
            ]
        )
        return self.client.query(sql, job_config=job_config).result().to_dataframe()

    def fetch_site_mapping(self) -> pd.DataFrame:
        c = self.config
        if not (
            c.site_mapping_table
            and c.site_mapping_erp_column
            and c.site_mapping_shopify_column
        ):
            return pd.DataFrame(columns=["sitio_erp", "sitio_shopify"])
        sql = f"""
        SELECT DISTINCT
          TRIM(CAST(`{c.site_mapping_erp_column}` AS STRING)) AS sitio_erp,
          TRIM(CAST(`{c.site_mapping_shopify_column}` AS STRING)) AS sitio_shopify
        FROM `{c.site_mapping_table}`
        WHERE `{c.site_mapping_erp_column}` IS NOT NULL
          AND `{c.site_mapping_shopify_column}` IS NOT NULL
        """
        return self.client.query(sql).result().to_dataframe()
