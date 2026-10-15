import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from rapidfuzz import fuzz

from rfq_intelligence.normalization import normalize_sku
from rfq_intelligence.product import Product
from rfq_intelligence.query_attributes import (
    QueryAttributes,
    extract_query_attributes,
)

_FUZZY_SKU_MATCH_THRESHOLD = 85.0
_FUZZY_SKU_MIN_MARGIN = 8.0

_DESCRIPTION_MATCH_THRESHOLD = 95.0
_DESCRIPTION_MIN_MARGIN = 5.0

_DESCRIPTION_AMBIGUOUS_THRESHOLD = 80.0
_DESCRIPTION_AMBIGUOUS_MARGIN = 5.0


class MatchStatus(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


class MatchMethod(StrEnum):
    EXACT_SKU = "EXACT_SKU"
    NORMALIZED_SKU = "NORMALIZED_SKU"
    EXPLICIT_SKU = "EXPLICIT_SKU"
    FUZZY_SKU = "FUZZY_SKU"
    EXACT_DESCRIPTION = "EXACT_DESCRIPTION"
    STRUCTURED_ATTRIBUTES = "STRUCTURED_ATTRIBUTES"
    DESCRIPTION = "DESCRIPTION"


@dataclass(frozen=True, slots=True)
class MatchResult:
    status: MatchStatus
    product: Product | None
    candidates: tuple[Product, ...] = ()
    method: MatchMethod | None = None
    best_score: float | None = None
    second_best_score: float | None = None


def match_exact_sku(
    query: str,
    products: Sequence[Product],
) -> MatchResult:
    matches = tuple(product for product in products if query == product.sku)

    if len(matches) == 1:
        return MatchResult(
            status=MatchStatus.EXACT_MATCH,
            product=matches[0],
            method=MatchMethod.EXACT_SKU,
            best_score=100.0,
        )

    if len(matches) > 1:
        return MatchResult(
            status=MatchStatus.AMBIGUOUS,
            product=None,
            candidates=matches,
            method=MatchMethod.EXACT_SKU,
            best_score=100.0,
            second_best_score=100.0,
        )

    return MatchResult(
        status=MatchStatus.NOT_FOUND,
        product=None,
    )


def match_sku(
    query: str,
    products: Sequence[Product],
) -> MatchResult:
    exact_result = match_exact_sku(
        query=query,
        products=products,
    )

    if exact_result.status != MatchStatus.NOT_FOUND:
        return exact_result

    normalized_result = _match_normalized_sku(
        query=query,
        products=products,
    )

    if normalized_result is not None:
        return normalized_result

    explicit_sku_result = _match_explicit_sku(
        query=query,
        products=products,
    )

    if explicit_sku_result is not None:
        return explicit_sku_result

    exact_description_result = _match_exact_description(
        query=query,
        products=products,
    )

    if exact_description_result is not None:
        return exact_description_result

    structured_result = _match_structured_attributes(
        query=query,
        products=products,
    )

    if structured_result is not None:
        return structured_result

    fuzzy_sku_result = _match_fuzzy_sku(
        query=query,
        products=products,
    )

    if fuzzy_sku_result is not None:
        return fuzzy_sku_result

    return _match_description(
        query=query,
        products=products,
    )


def _match_normalized_sku(
    query: str,
    products: Sequence[Product],
) -> MatchResult | None:
    normalized_query = normalize_sku(query)

    if not normalized_query:
        return None

    matches = tuple(
        product for product in products if normalize_sku(product.sku) == normalized_query
    )

    if len(matches) == 1:
        return MatchResult(
            status=MatchStatus.MATCHED,
            product=matches[0],
            method=MatchMethod.NORMALIZED_SKU,
            best_score=100.0,
        )

    if len(matches) > 1:
        return MatchResult(
            status=MatchStatus.AMBIGUOUS,
            product=None,
            candidates=matches,
            method=MatchMethod.NORMALIZED_SKU,
            best_score=100.0,
            second_best_score=100.0,
        )

    return None


def _match_explicit_sku(
    query: str,
    products: Sequence[Product],
) -> MatchResult | None:
    referenced: list[tuple[Product, str]] = []

    for product in products:
        pattern = re.compile(
            rf"(?<![A-Z0-9]){re.escape(product.sku)}(?![A-Z0-9])",
            flags=re.IGNORECASE,
        )

        if pattern.search(query):
            remaining_text = pattern.sub(" ", query)

            referenced.append(
                (
                    product,
                    remaining_text,
                )
            )

    if not referenced:
        return None

    if len(referenced) > 1:
        return MatchResult(
            status=MatchStatus.AMBIGUOUS,
            product=None,
            candidates=tuple(product for product, _ in referenced),
            method=MatchMethod.EXPLICIT_SKU,
        )

    product, remaining_text = referenced[0]

    attributes = extract_query_attributes(remaining_text)

    if _has_attribute_conflict(
        product=product,
        attributes=attributes,
    ):
        return MatchResult(
            status=MatchStatus.NOT_FOUND,
            product=None,
            method=MatchMethod.EXPLICIT_SKU,
        )

    return MatchResult(
        status=MatchStatus.MATCHED,
        product=product,
        method=MatchMethod.EXPLICIT_SKU,
        best_score=100.0,
    )


def _has_attribute_conflict(
    product: Product,
    attributes: QueryAttributes,
) -> bool:
    comparisons = (
        (
            attributes.material,
            product.material,
        ),
        (
            attributes.thread_type,
            product.thread_type,
        ),
        (
            attributes.thread_size,
            product.thread_size,
        ),
        (
            attributes.tube_outer_mm,
            product.tube_outer_mm,
        ),
        (
            attributes.tube_inner_mm,
            product.tube_inner_mm,
        ),
        (
            attributes.color,
            product.color,
        ),
        (
            attributes.profile,
            product.profile,
        ),
        (
            attributes.connection_gender,
            product.connection_gender,
        ),
    )

    return any(requested is not None and requested != actual for requested, actual in comparisons)


def _match_exact_description(
    query: str,
    products: Sequence[Product],
) -> MatchResult | None:
    normalized_query = _normalize_description(query)

    if not normalized_query:
        return None

    matches = tuple(
        product for product in products if _normalize_description(product.name) == normalized_query
    )

    if len(matches) == 1:
        return MatchResult(
            status=MatchStatus.MATCHED,
            product=matches[0],
            method=MatchMethod.EXACT_DESCRIPTION,
            best_score=100.0,
        )

    if len(matches) > 1:
        return MatchResult(
            status=MatchStatus.AMBIGUOUS,
            product=None,
            candidates=matches,
            method=MatchMethod.EXACT_DESCRIPTION,
            best_score=100.0,
            second_best_score=100.0,
        )

    return None


def _match_structured_attributes(
    query: str,
    products: Sequence[Product],
) -> MatchResult | None:
    attributes = extract_query_attributes(query)

    if not _has_structured_evidence(attributes):
        return None

    candidates = tuple(
        product
        for product in products
        if _product_matches_attributes(
            product=product,
            attributes=attributes,
        )
    )

    if len(candidates) == 0:
        return MatchResult(
            status=MatchStatus.NOT_FOUND,
            product=None,
            method=MatchMethod.STRUCTURED_ATTRIBUTES,
        )

    if len(candidates) == 1:
        return MatchResult(
            status=MatchStatus.MATCHED,
            product=candidates[0],
            method=MatchMethod.STRUCTURED_ATTRIBUTES,
        )

    return MatchResult(
        status=MatchStatus.AMBIGUOUS,
        product=None,
        candidates=candidates,
        method=MatchMethod.STRUCTURED_ATTRIBUTES,
    )


def _product_matches_attributes(
    product: Product,
    attributes: QueryAttributes,
) -> bool:
    if attributes.family is not None and product.family != attributes.family:
        return False

    if attributes.material is not None and product.material != attributes.material:
        return False

    if attributes.thread_type is not None and product.thread_type != attributes.thread_type:
        return False

    if attributes.thread_size is not None and product.thread_size != attributes.thread_size:
        return False

    if attributes.tube_outer_mm is not None and product.tube_outer_mm != attributes.tube_outer_mm:
        return False

    if attributes.tube_inner_mm is not None and product.tube_inner_mm != attributes.tube_inner_mm:
        return False

    if attributes.color is not None and product.color != attributes.color:
        return False

    if attributes.profile is not None and product.profile != attributes.profile:
        return False

    return not (
        attributes.connection_gender is not None
        and product.connection_gender != attributes.connection_gender
    )


def _has_structured_evidence(
    attributes: QueryAttributes,
) -> bool:
    return any(
        value is not None
        for value in (
            attributes.family,
            attributes.material,
            attributes.thread_type,
            attributes.thread_size,
            attributes.tube_outer_mm,
            attributes.tube_inner_mm,
            attributes.color,
            attributes.profile,
            attributes.connection_gender,
        )
    )


def _match_fuzzy_sku(
    query: str,
    products: Sequence[Product],
) -> MatchResult | None:
    normalized_query = normalize_sku(query)

    if not normalized_query or not products:
        return None

    ranked = sorted(
        (
            (
                product,
                float(
                    fuzz.ratio(
                        normalized_query,
                        normalize_sku(product.sku),
                    )
                ),
            )
            for product in products
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    best_product, best_score = ranked[0]

    second_score = ranked[1][1] if len(ranked) > 1 else None

    if best_score < _FUZZY_SKU_MATCH_THRESHOLD:
        return None

    if second_score is not None and best_score - second_score < _FUZZY_SKU_MIN_MARGIN:
        candidates = tuple(
            product for product, score in ranked if best_score - score < _FUZZY_SKU_MIN_MARGIN
        )

        return MatchResult(
            status=MatchStatus.AMBIGUOUS,
            product=None,
            candidates=candidates,
            method=MatchMethod.FUZZY_SKU,
            best_score=best_score,
            second_best_score=second_score,
        )

    return MatchResult(
        status=MatchStatus.MATCHED,
        product=best_product,
        method=MatchMethod.FUZZY_SKU,
        best_score=best_score,
        second_best_score=second_score,
    )


def _match_description(
    query: str,
    products: Sequence[Product],
) -> MatchResult:
    normalized_query = _normalize_description(query)

    if not normalized_query or not products:
        return MatchResult(
            status=MatchStatus.NOT_FOUND,
            product=None,
        )

    ranked = sorted(
        (
            (
                product,
                float(
                    fuzz.WRatio(
                        normalized_query,
                        _normalize_description(product.name),
                    )
                ),
            )
            for product in products
        ),
        key=lambda item: item[1],
        reverse=True,
    )

    best_product, best_score = ranked[0]

    second_score = ranked[1][1] if len(ranked) > 1 else None

    margin = best_score - second_score if second_score is not None else 100.0

    if best_score >= _DESCRIPTION_MATCH_THRESHOLD and margin >= _DESCRIPTION_MIN_MARGIN:
        return MatchResult(
            status=MatchStatus.MATCHED,
            product=best_product,
            method=MatchMethod.DESCRIPTION,
            best_score=best_score,
            second_best_score=second_score,
        )

    if best_score >= _DESCRIPTION_AMBIGUOUS_THRESHOLD and margin < _DESCRIPTION_AMBIGUOUS_MARGIN:
        candidates = tuple(
            product
            for product, score in ranked
            if (
                score >= _DESCRIPTION_AMBIGUOUS_THRESHOLD
                and best_score - score < _DESCRIPTION_AMBIGUOUS_MARGIN
            )
        )

        return MatchResult(
            status=MatchStatus.AMBIGUOUS,
            product=None,
            candidates=candidates,
            method=MatchMethod.DESCRIPTION,
            best_score=best_score,
            second_best_score=second_score,
        )

    return MatchResult(
        status=MatchStatus.NOT_FOUND,
        product=None,
        method=MatchMethod.DESCRIPTION,
        best_score=best_score,
        second_best_score=second_score,
    )


def _normalize_description(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )

    tokens = re.findall(
        r"[a-z0-9]+",
        without_accents.lower(),
    )

    return " ".join(tokens)
