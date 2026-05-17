"""Resolve cave entrance coordinates from gps-kataster release exports.

The Georeferencer data is keyed by the old PIG/CBDG cave id (`dir_id`), while
gps-kataster exports one point per physical cave opening (`object_id`).  Most
caves have one opening, but a few have more than one, so ambiguous matches must
not silently pick the wrong point.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any


MAX_AMBIGUOUS_DISTANCE_M = 100.0
MIN_AMBIGUOUS_DISTANCE_GAP_M = 5.0
LAT_TEMPLATE = "{{ gps_kataster.objects[gps_kataster_object_id].lat }}"
LON_TEMPLATE = "{{ gps_kataster.objects[gps_kataster_object_id].lon }}"
OBJECT_ID_RE = re.compile(r"^\s*gps_kataster_object_id:\s*['\"]?([^'\"\n#]+)", re.MULTILINE)


class GpsKatasterCoordinateError(ValueError):
    """Base error for gps-kataster coordinate resolution."""


class GpsKatasterNoMatchError(GpsKatasterCoordinateError):
    """Raised when no matching gps-kataster object can be found."""


class GpsKatasterAmbiguousMatchError(GpsKatasterCoordinateError):
    """Raised when several gps-kataster openings match one Georeferencer cave."""


@dataclass(frozen=True)
class BestMeasurementRow:
    """One `best-measurements` export row."""

    object_id: str
    category: str
    name_local: str
    cave_id: str
    measurement_id: str
    lat: float
    lon: float
    x_1992: str
    y_1992: str
    source: str
    source_ref: str
    nr_inwent: str
    pig_id: str
    tpn_globalid: str
    verification_status: str


@dataclass(frozen=True)
class CoordinateResolution:
    """Resolved gps-kataster coordinate and matching diagnostics."""

    row: BestMeasurementRow
    matched_by: str
    candidate_count: int
    match_distance_m: float | None = None


class GpsKatasterIndex:
    """Lookup index for gps-kataster `best-measurements` rows."""

    def __init__(
        self,
        rows: list[BestMeasurementRow],
        *,
        max_ambiguous_distance_m: float = MAX_AMBIGUOUS_DISTANCE_M,
        min_ambiguous_distance_gap_m: float = MIN_AMBIGUOUS_DISTANCE_GAP_M,
    ) -> None:
        self.rows = [row for row in rows if row.category == "jaskinia_otwor"]
        self.max_ambiguous_distance_m = max_ambiguous_distance_m
        self.min_ambiguous_distance_gap_m = min_ambiguous_distance_gap_m
        self.by_object_id = {row.object_id: row for row in self.rows}
        self.by_pig_id = _group_by(self.rows, "pig_id")
        self.by_nr_inwent = _group_by(self.rows, "nr_inwent")

    def resolve_meta(self, meta: dict[str, Any]) -> CoordinateResolution:
        """Resolve a gps-kataster opening for one Georeferencer `meta.yaml`."""

        cave = _dict(meta.get("cave"))
        coordinates = _dict(meta.get("coordinates"))

        explicit_object_id = _first_text(
            coordinates.get("gps_kataster_object_id"),
            _dict(coordinates.get("gps_kataster")).get("object_id"),
            _dict(meta.get("gps_kataster")).get("object_id"),
        )
        if explicit_object_id:
            return self._resolve_object_id(explicit_object_id)

        dir_id = _first_text(cave.get("dir_id"))
        inventory_number = _first_text(cave.get("inventory_number"))
        cave_name = _first_text(cave.get("name"))
        previous_lat = _float_or_none(coordinates.get("lat"))
        previous_lon = _float_or_none(coordinates.get("lon"))

        candidates: list[BestMeasurementRow] = []
        matched_by = ""

        pig_id = _pig_id_from_dir_id(dir_id)
        if pig_id:
            candidates = list(self.by_pig_id.get(pig_id, ()))
            matched_by = "pig_id"

        if inventory_number:
            nr_candidates = list(self.by_nr_inwent.get(inventory_number, ()))
            if candidates and nr_candidates:
                nr_ids = {row.object_id for row in nr_candidates}
                intersected = [row for row in candidates if row.object_id in nr_ids]
                if intersected:
                    candidates = intersected
                    matched_by = "pig_id+nr_inwent"
            elif nr_candidates:
                candidates = nr_candidates
                matched_by = "nr_inwent"

        if not candidates:
            keys = ", ".join(
                key
                for key in (
                    f"dir_id={dir_id}" if dir_id else "",
                    f"nr={inventory_number}" if inventory_number else "",
                )
                if key
            )
            raise GpsKatasterNoMatchError(f"Brak dopasowania w gps-kataster ({keys or 'brak kluczy'}).")

        return self._resolve_candidates(
            candidates,
            matched_by=matched_by,
            cave_name=cave_name,
            previous_lat=previous_lat,
            previous_lon=previous_lon,
        )

    def _resolve_object_id(self, object_id: str) -> CoordinateResolution:
        row = self.by_object_id.get(object_id)
        if row is None:
            raise GpsKatasterNoMatchError(f"Brak object_id={object_id} w gps-kataster.")
        return CoordinateResolution(row=row, matched_by="object_id", candidate_count=1)

    def _resolve_candidates(
        self,
        candidates: list[BestMeasurementRow],
        *,
        matched_by: str,
        cave_name: str | None,
        previous_lat: float | None,
        previous_lon: float | None,
    ) -> CoordinateResolution:
        if len(candidates) == 1:
            return CoordinateResolution(row=candidates[0], matched_by=matched_by, candidate_count=1)

        name_matches = [
            row for row in candidates
            if cave_name and _normalise_name(row.name_local) == _normalise_name(cave_name)
        ]
        if len(name_matches) == 1:
            return CoordinateResolution(
                row=name_matches[0],
                matched_by=f"{matched_by}+name",
                candidate_count=len(candidates),
            )

        if previous_lat is not None and previous_lon is not None:
            ranked = sorted(
                (
                    _distance_m(previous_lat, previous_lon, row.lat, row.lon),
                    index,
                    row,
                )
                for index, row in enumerate(candidates)
            )
            best_distance, _, best_row = ranked[0]
            next_distance = ranked[1][0] if len(ranked) > 1 else math.inf
            distance_gap = next_distance - best_distance
            if (
                best_distance <= self.max_ambiguous_distance_m
                and distance_gap >= self.min_ambiguous_distance_gap_m
            ):
                return CoordinateResolution(
                    row=best_row,
                    matched_by=f"{matched_by}+nearest_previous_coordinates",
                    candidate_count=len(candidates),
                    match_distance_m=best_distance,
                )

        raise GpsKatasterAmbiguousMatchError(_ambiguous_message(candidates, matched_by))


def load_best_measurements(path: str | Path) -> GpsKatasterIndex:
    """Load a gps-kataster best-measurements CSV or GeoJSON export."""

    path = Path(path)
    if path.suffix.lower() == ".csv":
        rows = _load_csv(path)
    elif path.suffix.lower() in {".geojson", ".json"}:
        rows = _load_geojson(path)
    else:
        raise ValueError(f"Nieobsługiwany format gps-kataster: {path}")
    return GpsKatasterIndex(rows)


def apply_coordinate_template(
    meta: dict[str, Any],
    resolution: CoordinateResolution,
) -> None:
    """Inject a Jinja coordinate template for the resolved opening object."""

    row = resolution.row
    existing_coordinates = _dict(meta.get("coordinates"))
    coordinates: dict[str, Any] = {
        "gps_kataster_object_id": row.object_id,
        "lat": LAT_TEMPLATE,
        "lon": LON_TEMPLATE,
    }
    for key, value in existing_coordinates.items():
        if key not in coordinates and key != "gps_kataster":
            coordinates[key] = value
    meta["coordinates"] = coordinates


def render_meta_template(raw_text: str, index: GpsKatasterIndex | None) -> str:
    """Render Jinja placeholders in one `meta.yaml` text."""

    if "{{" not in raw_text and "{%" not in raw_text:
        return raw_text
    if index is None:
        raise GpsKatasterNoMatchError(
            "meta.yaml zawiera Jinja placeholdery współrzędnych; podaj "
            "--gps-kataster-best-measurements."
        )

    object_id = extract_template_object_id(raw_text)
    if object_id not in index.by_object_id:
        raise GpsKatasterNoMatchError(f"Brak object_id={object_id} w gps-kataster.")

    try:
        from jinja2 import StrictUndefined, Template
    except ImportError as exc:
        raise GpsKatasterCoordinateError(
            "Brak zależności jinja2; uruchom `pip install -r pipeline/requirements.txt`."
        ) from exc

    template = Template(raw_text, undefined=StrictUndefined)
    return template.render(
        gps_kataster={"objects": index.by_object_id},
        gps_kataster_object_id=object_id,
    )


def extract_template_object_id(raw_text: str) -> str:
    """Extract the opening object id used by coordinate Jinja placeholders."""

    match = OBJECT_ID_RE.search(raw_text)
    if not match:
        raise GpsKatasterNoMatchError(
            "Brak `coordinates.gps_kataster_object_id` dla Jinja placeholderów."
        )
    return match.group(1).strip()


def _load_csv(path: Path) -> list[BestMeasurementRow]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        return [_row_from_mapping(row) for row in csv.DictReader(csv_file)]


def _load_geojson(path: Path) -> list[BestMeasurementRow]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[BestMeasurementRow] = []
    for feature in payload.get("features", []):
        props = dict(feature.get("properties") or {})
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        if "lon" not in props and len(coords) >= 1:
            props["lon"] = coords[0]
        if "lat" not in props and len(coords) >= 2:
            props["lat"] = coords[1]
        rows.append(_row_from_mapping(props))
    return rows


def _row_from_mapping(data: dict[str, Any]) -> BestMeasurementRow:
    return BestMeasurementRow(
        object_id=_required_text(data, "object_id"),
        category=_required_text(data, "category"),
        name_local=_text(data.get("name_local")),
        cave_id=_text(data.get("cave_id")),
        measurement_id=_text(data.get("measurement_id")),
        lat=_required_float(data, "lat"),
        lon=_required_float(data, "lon"),
        x_1992=_text(data.get("x_1992")),
        y_1992=_text(data.get("y_1992")),
        source=_text(data.get("source")),
        source_ref=_text(data.get("source_ref")),
        nr_inwent=_text(data.get("nr_inwent")),
        pig_id=_normalise_external_id(data.get("pig_id")),
        tpn_globalid=_text(data.get("tpn_globalid")),
        verification_status=_text(data.get("verification_status")),
    )


def _group_by(rows: list[BestMeasurementRow], attr: str) -> dict[str, tuple[BestMeasurementRow, ...]]:
    grouped: dict[str, list[BestMeasurementRow]] = {}
    for row in rows:
        value = getattr(row, attr)
        if value:
            grouped.setdefault(value, []).append(row)
    return {key: tuple(value) for key, value in grouped.items()}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        text = _text(value)
        if text:
            return text
    return None


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _required_text(data: dict[str, Any], key: str) -> str:
    value = _text(data.get(key))
    if not value:
        raise ValueError(f"Brak pola {key} w gps-kataster best-measurements.")
    return value


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _required_float(data: dict[str, Any], key: str) -> float:
    value = _float_or_none(data.get(key))
    if value is None:
        raise ValueError(f"Brak liczbowego pola {key} w gps-kataster best-measurements.")
    return value


def _normalise_external_id(value: Any) -> str:
    text = _text(value)
    if text.isdigit():
        return str(int(text))
    return text


def _pig_id_from_dir_id(dir_id: str | None) -> str | None:
    if not dir_id:
        return None
    text = str(dir_id).strip().strip("'\"")
    if not text.isdigit():
        return None
    return str(int(text))


def _normalise_name(value: str) -> str:
    return " ".join(value.lower().replace("–", "-").split())


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Small-distance equirectangular approximation in meters."""

    mean_lat = math.radians((lat1 + lat2) / 2.0)
    dx = math.radians(lon2 - lon1) * math.cos(mean_lat) * 6_371_000.0
    dy = math.radians(lat2 - lat1) * 6_371_000.0
    return math.hypot(dx, dy)


def _ambiguous_message(candidates: list[BestMeasurementRow], matched_by: str) -> str:
    details = "; ".join(
        f"{row.object_id} ({row.name_local}, {row.lat:.8f}, {row.lon:.8f})"
        for row in candidates
    )
    return (
        f"Niejednoznaczne dopasowanie gps-kataster przez {matched_by}: {details}. "
        "Dodaj w meta.yaml `coordinates.gps_kataster_object_id` dla właściwego otworu."
    )
