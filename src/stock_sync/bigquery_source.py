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

    def fetch_erp_snapshot(self, sites: list[str] | None = None) -> pd.DataFrame:
        if not self.config.erp_snapshot_table:
            raise ValueError("Falta [bigquery].erp_snapshot_table para mode = 'snapshot'")
        table = self.client.get_table(self.config.erp_snapshot_table)
        rows = self.client.list_rows(table)
        frame = pd.DataFrame([dict(row.items()) for row in rows])
        if frame.empty:
            return self._empty_erp_frame()
        if "sitio" not in frame.columns:
            raise ValueError("La tabla snapshot debe incluir la columna sitio")
        frame["sitio"] = frame["sitio"].astype("string").str.strip()
        if sites:
            normalized_sites = {str(site).strip() for site in sites}
            frame = frame[frame["sitio"].isin(normalized_sites)]
        return frame

    def fetch_erp_stock(self, sites: list[str] | None = None) -> pd.DataFrame:
        if self.config.mode == "snapshot":
            return self.fetch_erp_snapshot(sites)
        c = self.config
        enabled_sites = list(c.enabled_erp_site_ids)
        warehouse_site_cte = self._warehouse_site_cte()
        sql = f"""
        WITH {warehouse_site_cte},
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
        LEFT JOIN duplicate_links dl ON dl.sitio = ws.sitio AND dl.bodega = ws.bodega
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

    @staticmethod
    def _empty_erp_frame() -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "sitio",
                "sitio_erp",
                "nombre_sitio_erp",
                "id_producto",
                "codigo_tienda",
                "conca",
                "talla",
                "fecha_corte_erp",
                "nombrebodega",
                "stock_seguridad_aplicado",
                "stock_erp_sitio",
                "relacion_bodega_sitio_duplicada",
            ]
        )

    def _warehouse_site_cte(self) -> str:
        c = self.config
        site = c.warehouse_sites_site_column
        name_expr = (
            f"TRIM(CAST(bs.`{c.warehouse_sites_name_column}` AS STRING))"
            if c.warehouse_sites_name_column
            else "CAST(NULL AS STRING)"
        )
        if c.warehouse_sites_warehouse_column:
            warehouse = c.warehouse_sites_warehouse_column
            raw = f"""
        warehouse_site_raw AS (
          SELECT
            TRIM(CAST(bs.`{site}` AS STRING)) AS sitio,
            {name_expr} AS nombre_sitio_erp,
            TRIM(CAST(bs.`{warehouse}` AS STRING)) AS bodega
          FROM `{c.warehouse_sites_table}` bs
          WHERE bs.`{site}` IS NOT NULL
            AND bs.`{warehouse}` IS NOT NULL
            AND TRIM(CAST(bs.`{warehouse}` AS STRING)) != ''
            AND TRIM(CAST(bs.`{site}` AS STRING)) IN UNNEST(@enabled_sites)
        )"""
        else:
            warehouses = c.warehouse_sites_warehouses_column
            raw = f"""
        warehouse_site_raw AS (
          SELECT
            TRIM(CAST(bs.`{site}` AS STRING)) AS sitio,
            {name_expr} AS nombre_sitio_erp,
            TRIM(bodega) AS bodega
          FROM `{c.warehouse_sites_table}` bs
          CROSS JOIN UNNEST(
            SPLIT(
              REPLACE(
                REPLACE(
                  REPLACE(
                    REPLACE(CAST(bs.`{warehouses}` AS STRING), '[', ''),
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
          WHERE bs.`{site}` IS NOT NULL
            AND bs.`{warehouses}` IS NOT NULL
            AND TRIM(bodega) != ''
            AND TRIM(CAST(bs.`{site}` AS STRING)) IN UNNEST(@enabled_sites)
        )"""
        return f"""
        {raw},
        warehouse_site AS (
          SELECT DISTINCT sitio, nombre_sitio_erp, bodega
          FROM warehouse_site_raw
        )"""

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
