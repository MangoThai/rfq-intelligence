from decimal import Decimal

from rfq_intelligence.matching import (
    MatchMethod,
    MatchStatus,
    match_exact_sku,
    match_sku,
)
from rfq_intelligence.product import (
    ConnectionGender,
    Product,
    ProductFamily,
    SalesUnit,
)


def make_product(
    sku: str,
    name: str = "Test product",
    *,
    family: ProductFamily = "valve",
    material: str | None = "brass",
    thread_type: str | None = "G",
    thread_size: str | None = "1/2",
    tube_outer_mm: int | None = None,
    tube_inner_mm: int | None = None,
    color: str | None = None,
    profile: str | None = None,
    connection_gender: ConnectionGender | None = None,
    sales_unit: SalesUnit = "piece",
) -> Product:
    return Product(
        sku=sku,
        name=name,
        family=family,
        material=material,
        thread_type=thread_type,
        thread_size=thread_size,
        tube_outer_mm=tube_outer_mm,
        tube_inner_mm=tube_inner_mm,
        color=color,
        profile=profile,
        connection_gender=connection_gender,
        sales_unit=sales_unit,
        pack_size=1,
        base_price_eur=Decimal("10.00"),
        stock_qty=100,
        lead_time_days=2,
        active=True,
    )


def test_match_exact_sku_returns_matching_product() -> None:
    products = [
        make_product("VAN-BR-050"),
        make_product("VAN-BR-075"),
    ]

    result = match_exact_sku("VAN-BR-050", products)

    assert result.status == MatchStatus.EXACT_MATCH
    assert result.product is products[0]
    assert result.method == MatchMethod.EXACT_SKU
    assert result.best_score == 100.0


def test_match_exact_sku_returns_not_found_for_formatting_variation() -> None:
    products = [make_product("VAN-BR-050")]

    result = match_exact_sku("van br 050", products)

    assert result.status == MatchStatus.NOT_FOUND
    assert result.product is None


def test_match_sku_preserves_exact_match_status() -> None:
    products = [make_product("VAN-BR-050")]

    result = match_sku("VAN-BR-050", products)

    assert result.status == MatchStatus.EXACT_MATCH
    assert result.product is products[0]
    assert result.method == MatchMethod.EXACT_SKU


def test_match_sku_matches_normalized_reference() -> None:
    products = [make_product("VAN-BR-050")]

    result = match_sku(" van br 050 ", products)

    assert result.status == MatchStatus.MATCHED
    assert result.product is products[0]
    assert result.method == MatchMethod.NORMALIZED_SKU


def test_match_sku_matches_single_character_typo() -> None:
    products = [
        make_product(
            "RAC-G14-06",
            family="fitting",
            material=None,
            thread_size="1/4",
            tube_outer_mm=6,
        ),
        make_product(
            "RAC-G14-08",
            family="fitting",
            material=None,
            thread_size="1/4",
            tube_outer_mm=8,
        ),
        make_product(
            "RAC-M12-08",
            family="fitting",
            material=None,
            thread_type="M",
            thread_size="M12",
            tube_outer_mm=8,
        ),
    ]

    result = match_sku("RAC-G14-O8", products)

    assert result.status == MatchStatus.MATCHED
    assert result.product is products[1]
    assert result.method == MatchMethod.FUZZY_SKU


def test_match_sku_matches_exact_catalog_description() -> None:
    products = [
        make_product(
            "RAC-G14-06",
            "Raccord droit G1/4 pour tube Ø6 mm",
            family="fitting",
            material=None,
            thread_size="1/4",
            tube_outer_mm=6,
        ),
        make_product(
            "RAC-G14-08",
            "Raccord droit G1/4 pour tube Ø8 mm",
            family="fitting",
            material=None,
            thread_size="1/4",
            tube_outer_mm=8,
        ),
    ]

    result = match_sku(
        "Raccord droit G1/4 pour tube Ø6 mm",
        products,
    )

    assert result.status == MatchStatus.MATCHED
    assert result.product is products[0]
    assert result.method == MatchMethod.EXACT_DESCRIPTION


def test_match_sku_matches_precise_product_description() -> None:
    products = [
        make_product(
            "VAN-BR-075",
            'Vanne à boisseau sphérique laiton 3/4"',
            material="brass",
            thread_size="3/4",
        ),
        make_product(
            "VAN-SS-050",
            'Vanne à boisseau sphérique inox 1/2"',
            material="stainless_steel",
            thread_size="1/2",
        ),
        make_product(
            "VAN-SS-075",
            'Vanne à boisseau sphérique inox 3/4"',
            material="stainless_steel",
            thread_size="3/4",
        ),
    ]

    result = match_sku(
        "vannes à boisseau sphérique inox 3/4",
        products,
    )

    assert result.status == MatchStatus.MATCHED
    assert result.product is products[2]
    assert result.method == MatchMethod.STRUCTURED_ATTRIBUTES


def test_match_sku_returns_ambiguous_for_incomplete_description() -> None:
    products = [
        make_product(
            "VAN-BR-050",
            'Vanne à boisseau sphérique laiton 1/2"',
            material="brass",
            thread_size="1/2",
        ),
        make_product(
            "VAN-SS-050",
            'Vanne à boisseau sphérique inox 1/2"',
            material="stainless_steel",
            thread_size="1/2",
        ),
    ]

    result = match_sku(
        "vannes 1/2",
        products,
    )

    assert result.status == MatchStatus.AMBIGUOUS
    assert result.product is None
    assert result.method == MatchMethod.STRUCTURED_ATTRIBUTES
    assert result.candidates == (products[0], products[1])


def test_match_sku_matches_structured_tube_description() -> None:
    products = [
        make_product(
            "TUB-PU-BL-064",
            "Tube PU bleu 6 x 4 mm",
            family="tube",
            material="polyurethane",
            thread_type=None,
            thread_size=None,
            tube_outer_mm=6,
            tube_inner_mm=4,
            color="blue",
            sales_unit="meter",
        ),
        make_product(
            "TUB-PU-BL-086",
            "Tube PU bleu 8 x 6 mm",
            family="tube",
            material="polyurethane",
            thread_type=None,
            thread_size=None,
            tube_outer_mm=8,
            tube_inner_mm=6,
            color="blue",
            sales_unit="meter",
        ),
    ]

    result = match_sku(
        "tube PU bleu 6x4",
        products,
    )

    assert result.status == MatchStatus.MATCHED
    assert result.product is products[0]
    assert result.method == MatchMethod.STRUCTURED_ATTRIBUTES


def test_match_sku_rejects_unknown_structured_product() -> None:
    products = [
        make_product(
            "TUB-PU-BL-064",
            "Tube PU bleu 6 x 4 mm",
            family="tube",
            material="polyurethane",
            thread_type=None,
            thread_size=None,
            tube_outer_mm=6,
            tube_inner_mm=4,
            color="blue",
            sales_unit="meter",
        ),
        make_product(
            "TUB-PU-BL-086",
            "Tube PU bleu 8 x 6 mm",
            family="tube",
            material="polyurethane",
            thread_type=None,
            thread_size=None,
            tube_outer_mm=8,
            tube_inner_mm=6,
            color="blue",
            sales_unit="meter",
        ),
    ]

    result = match_sku(
        "tube PU bleu 10x8",
        products,
    )

    assert result.status == MatchStatus.NOT_FOUND
    assert result.product is None
    assert result.method == MatchMethod.STRUCTURED_ATTRIBUTES


def test_match_sku_returns_not_found_for_unknown_reference() -> None:
    products = [
        make_product("VAN-BR-050"),
        make_product(
            "RAC-G14-08",
            family="fitting",
            material=None,
            thread_size="1/4",
            tube_outer_mm=8,
        ),
    ]

    result = match_sku("ZX-900", products)

    assert result.status == MatchStatus.NOT_FOUND
    assert result.product is None


def test_match_sku_returns_ambiguous_when_normalization_collides() -> None:
    products = [
        make_product("ABC-123"),
        make_product("ABC123"),
    ]

    result = match_sku("abc 123", products)

    assert result.status == MatchStatus.AMBIGUOUS
    assert result.product is None
    assert result.method == MatchMethod.NORMALIZED_SKU
    assert result.candidates == (products[0], products[1])


def test_match_sku_rejects_material_conflicting_with_explicit_sku() -> None:
    product = make_product(
        "VAN-BR-050",
        'Vanne à boisseau sphérique laiton 1/2"',
        material="brass",
    )

    result = match_sku(
        "VAN-BR-050 inox",
        [product],
    )

    assert result.status == MatchStatus.NOT_FOUND
    assert result.product is None
    assert result.method == MatchMethod.EXPLICIT_SKU


def test_match_sku_rejects_dimension_conflicting_with_explicit_sku() -> None:
    product = make_product(
        "RAC-G14-06",
        "Raccord droit G1/4 pour tube Ø6 mm",
        family="fitting",
        material=None,
        thread_size="1/4",
        tube_outer_mm=6,
    )

    result = match_sku(
        "RAC-G14-06 tube 8",
        [product],
    )

    assert result.status == MatchStatus.NOT_FOUND
    assert result.product is None
    assert result.method == MatchMethod.EXPLICIT_SKU


def test_match_sku_rejects_profile_conflicting_with_explicit_sku() -> None:
    product = make_product(
        "CPL-6150-F-14",
        "Coupleur ISO 6150-B femelle G1/4",
        family="coupler",
        material=None,
        thread_size="1/4",
        profile="iso_6150_b",
        connection_gender="female",
    )

    result = match_sku(
        "CPL-6150-F-14 ARO",
        [product],
    )

    assert result.status == MatchStatus.NOT_FOUND
    assert result.product is None
    assert result.method == MatchMethod.EXPLICIT_SKU
