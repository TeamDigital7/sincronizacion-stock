from datetime import date

import pandas as pd
import pytest

from stock_sync.bigquery_source import BigQuerySource
from stock_sync.config import BigQueryConfig


class FakeQuery:
    def __init__(self, frame=None):
        self.frame = frame if frame is not None else pd.DataFrame()

    def result(self):
        return self

    def to_dataframe(self):
        return self.frame


class FakeClient:
    def __init__(self, frames=None):
        self.sql = ""
        self.job_config = None
        self.frames = list(frames or [])

    def query(self, sql, job_config=None):
        self.sql = sql
        self.job_config = job_config
        return FakeQuery(self.frames.pop(0) if self.frames else None)


def test_query_filters_transit_and_keeps_brand_rules_separated_by_site():
    config = BigQueryConfig(
        project_id="project",
        job_project_id="project",
        location="US",
        stock_table="project.dataset.stock",
        warehouses_table="project.dataset.warehouses",
        warehouse_sites_table="project.dataset.sites",
        warehouse_sites_warehouse_column="warehouse",
        warehouse_sites_warehouses_column=None,
        product_master_table="project.dataset.products",
    )
    source = BigQuerySource.__new__(BigQuerySource)
    source.config = config
    source.client = FakeClient()

    source.fetch_erp_stock(
        ["2", "4"],
        allowed_brands_by_site={
            "2": ("COLUMBIA",),
            "4": ("ROCKFORD", "COLUMBIA", "SOREL"),
        },
    )

    assert "SAFE_CAST(`transito` AS NUMERIC) = 0" in source.client.sql
    parameters = {
        parameter.name: parameter for parameter in source.client.job_config.query_parameters
    }
    assert parameters["brand_sites"].values == ["2", "4", "4", "4"]
    assert parameters["brands"].values == ["COLUMBIA", "COLUMBIA", "ROCKFORD", "SOREL"]


def test_query_stops_when_expected_stock_date_is_missing():
    config = BigQueryConfig(
        project_id="project",
        job_project_id="project",
        location="US",
        stock_table="project.dataset.stock",
        warehouses_table="project.dataset.warehouses",
        warehouse_sites_table="project.dataset.sites",
        warehouse_sites_warehouse_column="warehouse",
        warehouse_sites_warehouses_column=None,
    )
    source = BigQuerySource.__new__(BigQuerySource)
    source.config = config
    source.client = FakeClient([pd.DataFrame([{"filas": 0}])])

    with pytest.raises(ValueError, match="2026-10-13"):
        source.fetch_erp_stock(["2"], expected_date=date(2026, 10, 13))
