import re
import unicodedata
from dataclasses import dataclass

from rfq_intelligence.product import ConnectionGender, ProductFamily


@dataclass(frozen=True, slots=True)
class QueryAttributes:
    family: ProductFamily | None = None
    material: str | None = None
    thread_type: str | None = None
    thread_size: str | None = None
    tube_outer_mm: int | None = None
    tube_inner_mm: int | None = None
    color: str | None = None
    profile: str | None = None
    connection_gender: ConnectionGender | None = None


def extract_query_attributes(query: str) -> QueryAttributes:
    text = _normalize_text(query)

    family = _extract_family(text)
    material = _extract_material(text)
    thread_type, thread_size = _extract_thread(text)
    tube_outer_mm, tube_inner_mm = _extract_tube_dimensions(text)
    color = _extract_color(text)
    profile = _extract_profile(text)
    connection_gender = _extract_connection_gender(text)

    return QueryAttributes(
        family=family,
        material=material,
        thread_type=thread_type,
        thread_size=thread_size,
        tube_outer_mm=tube_outer_mm,
        tube_inner_mm=tube_inner_mm,
        color=color,
        profile=profile,
        connection_gender=connection_gender,
    )


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)

    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )

    text = without_accents.lower()
    text = text.replace("×", "x")

    return " ".join(text.split())


def _extract_family(text: str) -> ProductFamily | None:
    if _contains_word(text, "vanne"):
        return "valve"

    if _contains_word(text, "raccord"):
        return "fitting"

    if _contains_word(text, "coupleur") or _contains_word(text, "embout"):
        return "coupler"

    if _contains_word(text, "tube") or _contains_word(text, "tuyau"):
        return "tube"

    return None


def _extract_material(text: str) -> str | None:
    if "acier inoxydable" in text or _contains_word(text, "inox"):
        return "stainless_steel"

    if _contains_word(text, "laiton"):
        return "brass"

    if _contains_word(text, "polyurethane") or _contains_word(text, "pu"):
        return "polyurethane"

    if _contains_word(text, "polyamide") or _contains_word(text, "pa"):
        return "polyamide"

    if _contains_word(text, "bronze"):
        return "bronze"

    return None


def _extract_thread(text: str) -> tuple[str | None, str | None]:
    metric_match = re.search(r"\bm\s*(10|12)\b", text)

    if metric_match:
        size = metric_match.group(1)
        return "M", f"M{size}"

    gas_match = re.search(
        r"\bg\s*(1/2|1/4|3/4|3/8)\b",
        text,
    )

    if gas_match:
        return "G", gas_match.group(1)

    if "trois huitiemes" in text:
        return None, "3/8"

    if "trois quarts" in text:
        return None, "3/4"

    if "demi pouce" in text or _contains_word(text, "demi"):
        return None, "1/2"

    if "quart de pouce" in text or _contains_word(text, "quart"):
        return None, "1/4"

    fraction_match = re.search(
        r"(?<!\d)(1/2|1/4|3/4|3/8)(?!\d)",
        text,
    )

    if fraction_match:
        return None, fraction_match.group(1)

    inch_match = re.search(
        r"\b(\d+(?:[.,]\d+)?)\s*pouces?\b",
        text,
    )

    if inch_match:
        return None, inch_match.group(1).replace(",", ".")

    return None, None


def _extract_tube_dimensions(
    text: str,
) -> tuple[int | None, int | None]:
    explicit_dimensions_match = re.search(
        r"\bdiametre\s+exterieur\s+(\d+)"
        r"\s+(?:mm\s+)?interieur\s+(\d+)\b",
        text,
    )

    if explicit_dimensions_match:
        return (
            int(explicit_dimensions_match.group(1)),
            int(explicit_dimensions_match.group(2)),
        )

    dimensions_match = re.search(
        r"\b(\d+)\s*(?:x|par)\s*(\d+)\b",
        text,
    )

    if dimensions_match:
        return (
            int(dimensions_match.group(1)),
            int(dimensions_match.group(2)),
        )

    diameter_match = re.search(
        r"\bdiametre\s*(?:exterieur\s*)?(?:de\s*)?(\d+)\b",
        text,
    )

    if diameter_match:
        return int(diameter_match.group(1)), None

    tube_match = re.search(
        r"\b(?:tube|tuyau)\s*(?:de\s*)?(?:ø\s*)?(\d+)\s*(?:mm)?\b",
        text,
    )

    if tube_match:
        return int(tube_match.group(1)), None

    return None, None


def _extract_color(text: str) -> str | None:
    if _contains_word(text, "bleu") or _contains_word(text, "blue"):
        return "blue"

    if _contains_word(text, "noir") or _contains_word(text, "black"):
        return "black"

    return None


def _extract_profile(text: str) -> str | None:
    if _contains_word(text, "aro"):
        return "aro"

    if _contains_word(text, "cejn"):
        return "cejn"

    if "6150" in text:
        return "iso_6150_b"

    return None


def _extract_connection_gender(
    text: str,
) -> ConnectionGender | None:
    if _contains_word(text, "femelle"):
        return "female"

    if _contains_word(text, "male"):
        return "male"

    return None


def _contains_word(text: str, word: str) -> bool:
    return (
        re.search(
            rf"\b{re.escape(word)}\b",
            text,
        )
        is not None
    )
