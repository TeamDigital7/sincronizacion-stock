from __future__ import annotations

from datetime import date

import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

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

    def fetch_erp_snapshot(
        self,
        sites: list[str] | None = None,
        expected_date: date | None = None,
    ) -> pd.DataFrame:
        if not self.config.erp_snapshot_table:
            raise ValueError("Falta [bigquery].erp_snapshot_table para mode = 'snapshot'")
        table = self.client.get_table(self.config.erp_snapshot_table)
        rows = self.client.list_rows(table)
        frame = pd.DataFrame([dict(row.items()) for row in rows])
        if frame.empty:
            return self._empty_erp_frame()
        if "sitio" not in frame.columns:
            raise ValueError("La tabla snapshot debe incluir la columna sitio")
        if expected_date:
            if "fecha_corte_erp" not in frame.columns:
                raise ValueError("La tabla snapshot debe incluir fecha_corte_erp")
            frame = frame[
                pd.to_datetime(frame["fecha_corte_erp"], errors="coerce").dt.date
                == expected_date
            ]
            if frame.empty:
                raise ValueError(
                    f"No existe stock ERP para la fecha esperada {expected_date.isoformat()}"
                )
        frame["sitio"] = frame["sitio"].astype("string").str.strip()
        if sites:
            normalized_sites = {str(site).strip() for site in sites}
            frame = frame[frame["sitio"].isin(normalized_sites)]
        return frame

    def fetch_erp_stock(
        self,
        sites: list[str] | None = None,
        allowed_brands_by_site: dict[str, tuple[str, ...]] | None = None,
        expected_date: date | None = None,
    ) -> pd.DataFrame:
        if self.config.mode == "snapshot":
            return self.fetch_erp_snapshot(sites, expected_date)
        c = self.config
        if expected_date:
            self._assert_expected_stock_date(expected_date)
        enabled_sites = list(c.enabled_erp_site_ids)
        brand_pairs = sorted(
            {
                (str(site).strip(), str(brand).strip().upper())
                for site, brands in (allowed_brands_by_site or {}).items()
                for brand in brands
                if str(site).strip() and str(brand).strip()
            }
        )
        warehouse_site_cte = self._warehouse_site_cte()
        product_master_join = ""
        product_master_filter = ""
        if c.product_master_table:
            product_master_join = f"""
        JOIN `{c.product_master_table}` pm
          ON TRIM(CAST(pm.{c.product_master_id_column} AS STRING)) = s.id_producto"""
            product_master_filter = f"""
          AND (
            NOT @filter_brands
            OR ws.sitio NOT IN UNNEST(@brand_filtered_sites)
            OR EXISTS (
              SELECT 1
              FROM UNNEST(@brand_sites) AS brand_site WITH OFFSET position
              JOIN UNNEST(@brands) AS allowed_brand WITH OFFSET brand_position
                ON position = brand_position
              WHERE brand_site = ws.sitio
                AND allowed_brand = UPPER(TRIM(pm.{c.product_master_brand_column}))
            )
          )
          AND NOT (
            UPPER(TRIM(pm.{c.product_master_size_column})) LIKE 'K%'
            OR TRIM(pm.{c.product_master_size_column}) = '000'
          )"""
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
            FROM `{c.stock_table}`
            WHERE SAFE_CAST(`{c.stock_transit_column}` AS NUMERIC) = 0
              AND (
                @expected_stock_date IS NULL
                OR DATE(fecha_corte) = @expected_stock_date
              )
          )
          WHERE row_num = 1
            AND (
              @expected_stock_date IS NULL
              OR DATE(fecha_corte) = @expected_stock_date
            )
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
        {product_master_join}
        WHERE (NOT @filter_sites OR ws.sitio IN UNNEST(@sites))
        {product_master_filter}
        """
        query_parameters = [
            bigquery.ScalarQueryParameter("filter_sites", "BOOL", bool(sites)),
            bigquery.ArrayQueryParameter("sites", "STRING", sites or []),
            bigquery.ArrayQueryParameter("enabled_sites", "STRING", enabled_sites),
            bigquery.ScalarQueryParameter(
                "expected_stock_date", "DATE", expected_date
            ),
        ]
        if c.product_master_table:
            query_parameters += [
                bigquery.ScalarQueryParameter("filter_brands", "BOOL", bool(brand_pairs)),
                bigquery.ArrayQueryParameter(
                    "brand_filtered_sites",
                    "STRING",
                    sorted({site for site, _ in brand_pairs}),
                ),
                bigquery.ArrayQueryParameter(
                    "brand_sites", "STRING", [site for site, _ in brand_pairs]
                ),
                bigquery.ArrayQueryParameter(
                    "brands", "STRING", [brand for _, brand in brand_pairs]
                ),
            ]
        job_config = bigquery.QueryJobConfig(
            query_parameters=query_parameters
        )
        return self.client.query(sql, job_config=job_config).result().to_dataframe()

    def _assert_expected_stock_date(self, expected_date: date) -> None:
        c = self.config
        sql = f"""
        SELECT COUNT(*) AS filas
        FROM `{c.stock_table}`
        WHERE DATE(fecha_corte) = @expected_stock_date
          AND SAFE_CAST(`{c.stock_transit_column}` AS NUMERIC) = 0
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(
                    "expected_stock_date", "DATE", expected_date
                )
            ]
        )
        frame = self.client.query(sql, job_config=job_config).result().to_dataframe()
        if frame.empty or int(frame.iloc[0]["filas"]) == 0:
            raise ValueError(
                f"No existe stock ERP para la fecha esperada {expected_date.isoformat()}"
            )

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

    def diagnostics(self) -> dict[str, pd.DataFrame]:
        """Consultas de solo lectura para depurar por qué el cruce ERP viene vacío.
        No modifica nada; solo cuenta filas y muestra valores distintos reales."""
        c = self.config
        site = c.warehouse_sites_site_column
        results: dict[str, pd.DataFrame] = {}
        results["stock_table_filas"] = self.client.query(
            f"SELECT COUNT(*) AS filas FROM `{c.stock_table}`"
        ).result().to_dataframe()
        results["warehouses_estado"] = self.client.query(
            f"""
            SELECT estado, COUNT(*) AS filas
            FROM `{c.warehouses_table}`
            GROUP BY estado
            ORDER BY filas DESC
            """
        ).result().to_dataframe()
        results["sitios_disponibles"] = self.client.query(
            f"""
            SELECT `{site}` AS sitio, COUNT(*) AS filas
            FROM `{c.warehouse_sites_table}`
            GROUP BY sitio
            ORDER BY filas DESC
            LIMIT 50
            """
        ).result().to_dataframe()
        if c.product_master_table:
            results["marcas_disponibles"] = self.client.query(
                f"""
                SELECT `{c.product_master_brand_column}` AS marca, COUNT(*) AS filas
                FROM `{c.product_master_table}`
                GROUP BY marca
                ORDER BY filas DESC
                LIMIT 100
                """
            ).result().to_dataframe()
        return results
