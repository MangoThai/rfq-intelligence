import pytest

from rfq_intelligence.normalization import normalize_sku


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("VAN-BR-050", "VANBR050"),
        ("van-br-050", "VANBR050"),
        ("VAN BR 050", "VANBR050"),
        (" van br 050 ", "VANBR050"),
        ("VAN_BR_050", "VANBR050"),
        ("VAN.BR.050", "VANBR050"),
    ],
)
def test_normalize_sku_removes_formatting_variations(
    raw_value: str,
    expected: str,
) -> None:
    assert normalize_sku(raw_value) == expected


def test_normalize_sku_does_not_correct_typo() -> None:
    typo = normalize_sku("RAC-G14-O8")
    real_sku = normalize_sku("RAC-G14-08")

    assert typo == "RACG14O8"
    assert real_sku == "RACG1408"
    assert typo != real_sku


def test_normalize_sku_empty_value_returns_empty_string() -> None:
    assert normalize_sku("   ") == ""
