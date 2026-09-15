from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canon(value).encode('utf-8')).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _clean(value: Any) -> Any:
    sensitive = ('token', 'secret', 'password', 'authorization', 'cookie', 'session', 'api_key', 'private_key')
    if isinstance(value, Mapping):
        return {str(k): ('[REDACTED]' if any(term in str(k).lower() for term in sensitive) else _clean(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _norm_text(value: str) -> str:
    text = unicodedata.normalize('NFKC', str(value)).casefold().strip()
    text = re.sub(r'[^\w\s\-/,]', ' ', text, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', text).strip()


def _validate_coordinates(latitude: float | None, longitude: float | None) -> tuple[float | None, float | None]:
    if latitude is None and longitude is None:
        return None, None
    if latitude is None or longitude is None:
        raise ValueError('latitude and longitude must be provided together')
    lat, lon = float(latitude), float(longitude)
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('invalid coordinates')
    return lat, lon


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class Build175GeospatialIntelligenceService:
    BUILD = '175.0'
    SOURCE_PROFILES = [
        {
            'source_id': 'eu_gisco_address', 'title': 'Eurostat GISCO Address API', 'jurisdiction': 'EU',
            'category': 'authoritative_geocoder', 'access_mode': 'official_rest',
            'base_url': 'https://gisco-services.ec.europa.eu',
            'docs_url': 'https://gisco-services.ec.europa.eu/addressapi/docs/screen/home',
            'terms_url': 'https://ec.europa.eu/info/legal-notice_en',
            'capabilities': ['forward_geocoding', 'reverse_geocoding', 'pan_european_addresses'],
            'constraints': ['terms_review', 'rate_limit_observation', 'candidate_only']
        },
        {
            'source_id': 'eu_gisco_geodata', 'title': 'Eurostat GISCO Geodata and NUTS', 'jurisdiction': 'EU',
            'category': 'administrative_geodata', 'access_mode': 'official_download_api',
            'base_url': 'https://gisco-services.ec.europa.eu',
            'docs_url': 'https://ec.europa.eu/eurostat/web/gisco/geodata',
            'terms_url': 'https://ec.europa.eu/eurostat/about-us/policies/copyright',
            'capabilities': ['nuts_regions', 'countries', 'administrative_units', 'geometry_download'],
            'constraints': ['dataset_specific_download_rules', 'metadata_required']
        },
        {
            'source_id': 'de_bkg_geocoder', 'title': 'BKG Geocoding Services', 'jurisdiction': 'DE',
            'category': 'authoritative_geocoder', 'access_mode': 'official_key_or_guided',
            'base_url': 'https://sg.geodatenzentrum.de',
            'docs_url': 'https://gdz.bkg.bund.de/index.php/default/geocoderplus.html/',
            'terms_url': 'https://gdz.bkg.bund.de/index.php/default/nutzungsbedingungen',
            'capabilities': ['address_geocoding', 'geonames', 'postal_codes', 'batch_geocoding'],
            'constraints': ['credential_or_product_access', 'terms_review', 'no_embedded_key']
        },
        {
            'source_id': 'geonames_webservices', 'title': 'GeoNames Web Services', 'jurisdiction': 'GLOBAL',
            'category': 'placename_geocoder', 'access_mode': 'official_username',
            'base_url': 'https://api.geonames.org',
            'docs_url': 'https://www.geonames.org/export/web-services.html',
            'terms_url': 'https://www.geonames.org/export/',
            'capabilities': ['placename_search', 'postal_codes', 'reverse_geocoding', 'nearby_places'],
            'constraints': ['username_required', 'daily_credit_limits', 'attribution_required']
        },
        {
            'source_id': 'osm_nominatim_selfhosted', 'title': 'Nominatim (self-hosted or approved provider)', 'jurisdiction': 'GLOBAL',
            'category': 'open_geocoder', 'access_mode': 'self_hosted_or_approved_provider',
            'base_url': 'https://nominatim.openstreetmap.org',
            'docs_url': 'https://nominatim.org/release-docs/latest/api/Overview/',
            'terms_url': 'https://operations.osmfoundation.org/policies/nominatim/',
            'capabilities': ['forward_geocoding', 'reverse_geocoding', 'structured_search'],
            'constraints': ['public_instance_not_for_bulk', 'no_unbounded_autocomplete', 'identify_application', 'cache_results']
        },
        {
            'source_id': 'de_govdata_geodata', 'title': 'GovData Geospatial Datasets', 'jurisdiction': 'DE',
            'category': 'open_data_catalogue', 'access_mode': 'official_catalogue',
            'base_url': 'https://www.govdata.de',
            'docs_url': 'https://www.govdata.de/web/guest/hilfe',
            'terms_url': 'https://www.govdata.de/web/guest/lizenzen',
            'capabilities': ['dataset_discovery', 'administrative_data', 'geodata_resources'],
            'constraints': ['dataset_specific_licenses', 'resource_validation']
        },
    ]

    def __init__(self, db: Any, audit: Any, *, base_dir: str | Path, european_sources: Any, media_forensics: Any, actor: str = 'system'):
        self.db, self.audit, self.actor = db, audit, actor
        self.european_sources, self.media_forensics = european_sources, media_forensics
        self.base_dir = Path(base_dir)
        self.export_dir = self.base_dir / 'geospatial_175' / 'exports'
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def seed_geo_sources(self, *, confirmation: str) -> dict[str, Any]:
        if confirmation != 'GEO SOURCES 175 ERWEITERN':
            raise PermissionError('explicit geospatial source expansion approval required')
        for profile in self.SOURCE_PROFILES:
            payload = {**profile, 'status': 'DOCUMENTED'}
            self.db.execute(
                'INSERT OR REPLACE INTO geo_source_profiles_175 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (profile['source_id'], profile['title'], profile['jurisdiction'], profile['category'],
                 profile['access_mode'], profile['base_url'], profile['docs_url'], profile['terms_url'],
                 'DOCUMENTED', dumps(profile['capabilities']), dumps(profile['constraints']), now_ts(), _hash(payload))
            )
        return {'created': len(self.SOURCE_PROFILES), 'production_active': 0, 'review_required': True}

    def normalize_location(self, label: str, *, latitude: float | None = None, longitude: float | None = None,
                           country_code: str | None = None, admin_path: Sequence[str] | None = None,
                           uncertainty_meters: float = 1000.0, confidence: float = 0.5) -> dict[str, Any]:
        if not str(label).strip():
            raise ValueError('location label required')
        lat, lon = _validate_coordinates(latitude, longitude)
        if not 0 <= float(confidence) <= 1:
            raise ValueError('confidence must be between 0 and 1')
        if not 0 <= float(uncertainty_meters) <= 5_000_000:
            raise ValueError('invalid uncertainty radius')
        return {
            'label': str(label).strip(), 'normalized_label': _norm_text(label),
            'latitude': lat, 'longitude': lon, 'country_code': (country_code or '').upper() or None,
            'admin_path': [str(x).strip() for x in (admin_path or []) if str(x).strip()],
            'uncertainty_meters': float(uncertainty_meters), 'confidence': float(confidence)
        }

    def store_location(self, case_id: str, label: str, *, latitude: float | None = None, longitude: float | None = None,
                       uncertainty_meters: float = 1000.0, confidence: float = 0.5, location_type: str = 'candidate',
                       country_code: str | None = None, admin_path: Sequence[str] | None = None,
                       source_refs: Sequence[str] | None = None, provenance: Mapping[str, Any] | None = None,
                       sensitive_precision: bool = False, confirmation: str) -> dict[str, Any]:
        if confirmation != f'GEO 175 {case_id} ORT SPEICHERN':
            raise PermissionError('explicit location storage approval required')
        normalized = self.normalize_location(label, latitude=latitude, longitude=longitude, country_code=country_code,
                                             admin_path=admin_path, uncertainty_meters=uncertainty_meters, confidence=confidence)
        location_id = new_id('geo175')
        safe_provenance = _clean(dict(provenance or {}))
        payload = {**normalized, 'location_id': location_id, 'case_id': case_id, 'location_type': location_type,
                   'source_refs': list(source_refs or []), 'provenance': safe_provenance,
                   'sensitive_precision': bool(sensitive_precision), 'review_status': 'needs_review'}
        self.db.execute(
            'INSERT INTO geo_locations_175 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (location_id, case_id, normalized['label'], normalized['normalized_label'], normalized['latitude'],
             normalized['longitude'], normalized['uncertainty_meters'], normalized['confidence'], location_type,
             normalized['country_code'], dumps(normalized['admin_path']), dumps(list(source_refs or [])),
             dumps(safe_provenance), int(bool(sensitive_precision)), 'needs_review', now_ts(), _hash(payload))
        )
        self._event(case_id, 'location_stored', location_id, {'location_type': location_type, 'sensitive_precision': bool(sensitive_precision)})
        return {**payload, 'review_required': True, 'automatic_location_confirmation': False}

    def add_resolution_candidates(self, case_id: str, query_text: str, source_id: str,
                                  candidates: Sequence[Mapping[str, Any]], *, confirmation: str) -> dict[str, Any]:
        if confirmation != f'GEO 175 {case_id} KANDIDATEN SPEICHERN':
            raise PermissionError('explicit geocoding candidate approval required')
        source = self.db.one('SELECT * FROM geo_source_profiles_175 WHERE source_id=?', (source_id,))
        if not source:
            raise KeyError('unknown geospatial source')
        created = []
        for candidate in list(candidates)[:100]:
            lat, lon = _validate_coordinates(candidate.get('latitude'), candidate.get('longitude'))
            score = float(candidate.get('score', 0.0))
            if not 0 <= score <= 1:
                raise ValueError('candidate score must be between 0 and 1')
            uncertainty = float(candidate.get('uncertainty_meters', 1000.0))
            candidate_id = new_id('geocand175')
            safe = _clean(dict(candidate))
            evidence = _clean(dict(candidate.get('evidence') or {}))
            payload = {'candidate_id': candidate_id, 'case_id': case_id, 'query_text': query_text,
                       'source_id': source_id, 'candidate': safe, 'latitude': lat, 'longitude': lon,
                       'uncertainty_meters': uncertainty, 'score': score, 'evidence': evidence,
                       'review_status': 'needs_review'}
            self.db.execute(
                'INSERT INTO geo_resolution_candidates_175 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (candidate_id, case_id, query_text, source_id, dumps(safe), lat, lon, uncertainty, score,
                 dumps(evidence), 'needs_review', now_ts(), _hash(payload))
            )
            created.append(payload)
        return {'created': len(created), 'candidates': created, 'review_required': True, 'automatic_selection': False}

    def add_observation(self, case_id: str, location_id: str, *, entity_ref: str | None = None,
                        valid_from: str | None = None, valid_to: str | None = None, source_time: str | None = None,
                        source_refs: Sequence[str] | None = None, confidence: float = 0.5,
                        verification_status: str = 'unverified', details: Mapping[str, Any] | None = None,
                        confirmation: str) -> dict[str, Any]:
        if confirmation != f'GEO 175 {case_id} BEOBACHTUNG SPEICHERN':
            raise PermissionError('explicit geospatial observation approval required')
        if not self.db.one('SELECT 1 ok FROM geo_locations_175 WHERE location_id=? AND case_id=?', (location_id, case_id)):
            raise KeyError('location not found')
        if verification_status not in {'unverified', 'partially_verified', 'corroborated', 'disputed', 'rejected'}:
            raise ValueError('invalid verification status')
        if valid_from and valid_to and valid_from > valid_to:
            raise ValueError('invalid temporal interval')
        observation_id = new_id('geoobs175')
        payload = {'observation_id': observation_id, 'case_id': case_id, 'entity_ref': entity_ref,
                   'location_id': location_id, 'valid_from': valid_from, 'valid_to': valid_to,
                   'source_time': source_time, 'source_refs': list(source_refs or []), 'confidence': float(confidence),
                   'verification_status': verification_status, 'details': _clean(dict(details or {}))}
        self.db.execute(
            'INSERT INTO geo_observations_175 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (observation_id, case_id, entity_ref, location_id, valid_from, valid_to, now_ts(), source_time,
             dumps(list(source_refs or [])), float(confidence), verification_status,
             dumps(payload['details']), _hash(payload))
        )
        return {**payload, 'review_required': True}

    def estimate_route(self, case_id: str, origin_location_id: str, destination_location_id: str, *,
                       mode: str = 'straight_line', speed_kmh: float | None = None, confirmation: str) -> dict[str, Any]:
        if confirmation != f'GEO 175 {case_id} ROUTE SCHAETZEN':
            raise PermissionError('explicit route estimate approval required')
        origin = self.db.one('SELECT * FROM geo_locations_175 WHERE location_id=? AND case_id=?', (origin_location_id, case_id))
        destination = self.db.one('SELECT * FROM geo_locations_175 WHERE location_id=? AND case_id=?', (destination_location_id, case_id))
        if not origin or not destination or origin['latitude'] is None or destination['latitude'] is None:
            raise ValueError('both locations require coordinates')
        distance = _haversine(origin['latitude'], origin['longitude'], destination['latitude'], destination['longitude'])
        estimated = None
        assumptions = {'geodesic_distance_only': True, 'not_a_routing_engine': True}
        if speed_kmh is not None:
            if not 1 <= float(speed_kmh) <= 300:
                raise ValueError('invalid assumed speed')
            estimated = distance / (float(speed_kmh) * 1000 / 3600)
            assumptions['assumed_speed_kmh'] = float(speed_kmh)
        route_id = new_id('route175')
        payload = {'route_id': route_id, 'case_id': case_id, 'origin_location_id': origin_location_id,
                   'destination_location_id': destination_location_id, 'distance_meters': round(distance, 3),
                   'mode': mode, 'estimated_seconds': estimated, 'method': 'WGS84_haversine',
                   'assumptions': assumptions, 'review_status': 'needs_review'}
        self.db.execute(
            'INSERT INTO geo_route_estimates_175 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
            (route_id, case_id, origin_location_id, destination_location_id, payload['distance_meters'], mode,
             estimated, 'WGS84_haversine', dumps(assumptions), 'needs_review', now_ts(), _hash(payload))
        )
        return {**payload, 'review_required': True}

    def timeline(self, case_id: str, *, entity_ref: str | None = None) -> list[dict[str, Any]]:
        sql = '''SELECT o.*, l.label, l.latitude, l.longitude, l.uncertainty_meters, l.sensitive_precision
                 FROM geo_observations_175 o JOIN geo_locations_175 l ON l.location_id=o.location_id
                 WHERE o.case_id=?'''
        params: list[Any] = [case_id]
        if entity_ref:
            sql += ' AND o.entity_ref=?'; params.append(entity_ref)
        sql += " ORDER BY COALESCE(o.valid_from,o.observed_at), o.observed_at"
        return [dict(row) for row in self.db.all(sql, tuple(params))]

    def export_geojson(self, case_id: str, *, created_by: str, include_sensitive_precision: bool = False,
                       confirmation: str) -> dict[str, Any]:
        if confirmation != f'GEOJSON 175 {case_id} EXPORTIEREN':
            raise PermissionError('explicit GeoJSON export approval required')
        rows = self.db.all('SELECT * FROM geo_locations_175 WHERE case_id=? ORDER BY observed_at', (case_id,))
        features = []
        for row in rows:
            if row['latitude'] is None:
                continue
            lat, lon = float(row['latitude']), float(row['longitude'])
            precision = 'exact'
            if row['sensitive_precision'] and not include_sensitive_precision:
                lat, lon = round(lat, 2), round(lon, 2)
                precision = 'reduced_sensitive'
            features.append({'type': 'Feature', 'id': row['location_id'],
                             'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
                             'properties': {'label': row['label'], 'location_type': row['location_type'],
                                            'confidence': row['confidence'], 'uncertainty_meters': row['uncertainty_meters'],
                                            'review_status': row['review_status'], 'precision': precision}})
        collection = {'type': 'FeatureCollection', 'features': features,
                      'metadata': {'case_id': case_id, 'generated_at': now_ts(), 'review_required': True,
                                   'not_live_tracking': True, 'sensitive_precision_included': bool(include_sensitive_precision)}}
        path = self.export_dir / f'{case_id}_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.geojson'
        path.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding='utf-8')
        export_id = new_id('geoexport175')
        file_hash = _file_sha256(path)
        payload = {'export_id': export_id, 'case_id': case_id, 'file_path': str(path), 'feature_count': len(features),
                   'precision_policy': 'include_sensitive' if include_sensitive_precision else 'reduce_sensitive',
                   'created_by': created_by, 'file_sha256': file_hash}
        self.db.execute('INSERT INTO geo_exports_175 VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (export_id, case_id, 'geojson', str(path), len(features), payload['precision_policy'],
                         created_by, now_ts(), file_hash, _hash(payload)))
        return {**payload, 'review_required': True}

    def source_coverage(self) -> dict[str, Any]:
        base = int(self.media_forensics.source_coverage()['total_documented_sources'])
        geo = int(self.db.one('SELECT COUNT(*) n FROM geo_source_profiles_175')['n'])
        payload = {'previous_documented_sources': base, 'new_geospatial_sources': geo,
                   'total_documented_sources': base + geo, 'production_active_new': 0,
                   'operational_truth': 'documented sources are not automatically production ready'}
        return {**payload, 'payload_sha256': _hash(payload)}

    def case_summary(self, case_id: str) -> dict[str, Any]:
        locations = int(self.db.one('SELECT COUNT(*) n FROM geo_locations_175 WHERE case_id=?', (case_id,))['n'])
        observations = int(self.db.one('SELECT COUNT(*) n FROM geo_observations_175 WHERE case_id=?', (case_id,))['n'])
        return {'case_id': case_id, 'locations': locations, 'observations': observations,
                'opsec': {'no_live_tracking': True, 'public_or_authorized_sources_only': True,
                          'sensitive_precision_reduced_by_default': True, 'automatic_location_confirmation': False},
                'review_required': True}

    def _event(self, case_id: str | None, event_type: str, entity_ref: str | None, details: Mapping[str, Any]) -> None:
        safe = _clean(dict(details))
        payload = {'case_id': case_id, 'event_type': event_type, 'entity_ref': entity_ref, 'details': safe}
        self.db.execute('INSERT INTO geo_events_175 VALUES(?,?,?,?,?,?,?)',
                        (new_id('geoevent175'), case_id, event_type, entity_ref, dumps(safe), now_ts(), _hash(payload)))
