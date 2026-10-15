from pathlib import Path

import pytest

from rfq_intelligence.catalog import load_catalog


def test_load_catalog_returns_products(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "\n".join(
            [
                (
                    "sku,name,family,material,thread_type,thread_size,"
                    "tube_outer_mm,tube_inner_mm,color,profile,"
                    "connection_gender,sales_unit,pack_size,"
                    "base_price_eur,stock_qty,lead_time_days,active"
                ),
                ("VAN-BR-050,Vanne laiton,valve,brass,G,1/2,,,,,,piece,1,12.80,10,2,true"),
            ]
        ),
        encoding="utf-8",
    )

    products = load_catalog(catalog_path)

    assert len(products) == 1
    assert products[0].sku == "VAN-BR-050"
    assert products[0].name == "Vanne laiton"


def test_load_catalog_rejects_duplicate_skus(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "\n".join(
            [
                (
                    "sku,name,family,material,thread_type,thread_size,"
                    "tube_outer_mm,tube_inner_mm,color,profile,"
                    "connection_gender,sales_unit,pack_size,"
                    "base_price_eur,stock_qty,lead_time_days,active"
                ),
                ("VAN-BR-050,Vanne laiton,valve,brass,G,1/2,,,,,,piece,1,12.80,10,2,true"),
                ("VAN-BR-050,Autre vanne,valve,brass,G,1/2,,,,,,piece,1,13.50,5,2,true"),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Duplicate product SKU: VAN-BR-050"):
        load_catalog(catalog_path)
