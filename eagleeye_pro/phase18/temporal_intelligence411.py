from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

BUILD = '411.0'
POLICY_ID = 'phase18.temporal-intelligence.v411'
_DATE_RE = re.compile(r'(?<!\d)(20\d{2}|19\d{2})(?:-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?)?(?!\d)')


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


def _parse_isoish(value: str):
    value = str(value or '').strip()
    if not value:
        return None
    # Explicit temporal values only; no natural-language date guessing.
    try:
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        dt = datetime.fromisoformat(value)
        return {'value': dt.date().isoformat(), 'precision': 'day', 'raw': value}
    except Exception:
        pass
    m = _DATE_RE.fullmatch(value)
    if not m:
        return None
    y, mo, d = m.groups()
    if d:
        return {'value': f'{y}-{mo}-{d}', 'precision': 'day', 'raw': value}
    if mo:
        return {'value': f'{y}-{mo}', 'precision': 'month', 'raw': value}
    return {'value': y, 'precision': 'year', 'raw': value}


class TemporalIntelligence411:
    """Read-only temporal analysis over provenance-bound federated search results.

    The layer surfaces explicit chronology, temporal coverage and conflicts. It does
    not infer causality, determine truth, execute searches, or promote evidence.
    """
    EXPLICIT_FIELDS = ('event_date', 'published_at', 'observed_at', 'retrieved_at')

    def __init__(self, db, audit, *, search408, quality409, actor='local-analyst'):
        self.db = db
        self.audit = audit
        self.search408 = search408
        self.quality409 = quality409
        self.actor = actor

    def _candidates(self, search_id: str):
        rows = []
        for result in self.search408.merged_results(search_id):
            prov = dict(result.get('provenance') or {})
            explicit = []
            for field in self.EXPLICIT_FIELDS:
                parsed = _parse_isoish(prov.get(field))
                if parsed:
                    explicit.append({'field': field, **parsed, 'basis': 'explicit_provenance'})
            # Text dates are surfaced only as candidates and never used as authoritative dates.
            text = f"{result.get('title','')} {result.get('snippet','')}"
            text_dates = []
            for m in _DATE_RE.finditer(text):
                raw = m.group(0)
                parsed = _parse_isoish(raw)
                if parsed and parsed['value'] not in {x['value'] for x in explicit}:
                    text_dates.append({**parsed, 'field': 'text_mention', 'basis': 'text_candidate'})
            rows.append({
                'result_id': result['result_id'],
                'source_id': result['source_id'],
                'canonical_ref': result.get('canonical_ref',''),
                'title': result.get('title',''),
                'explicit_dates': explicit,
                'text_date_candidates': text_dates,
            })
        return rows

    def timeline(self, search_id: str):
        sess = self.search408.session(search_id)
        candidates = self._candidates(search_id)
        events = []
        for row in candidates:
            for d in row['explicit_dates']:
                events.append({
                    'result_id': row['result_id'], 'source_id': row['source_id'],
                    'canonical_ref': row['canonical_ref'], 'title': row['title'],
                    'temporal_value': d['value'], 'precision': d['precision'],
                    'temporal_field': d['field'], 'basis': d['basis'],
                })
        events.sort(key=lambda x: (x['temporal_value'], x['source_id'], x['result_id']))
        undated = [r['result_id'] for r in candidates if not r['explicit_dates']]
        out = {
            'build': BUILD, 'search_id': search_id, 'case_id': sess['case_id'],
            'events': events, 'undated_result_ids': undated,
            'text_date_candidates': [
                {'result_id': r['result_id'], 'source_id': r['source_id'], 'dates': r['text_date_candidates']}
                for r in candidates if r['text_date_candidates']
            ],
            'explicit_temporal_events': len(events),
            'undated_results': len(undated),
            'truth_determined': False, 'causality_inferred': False,
            'evidence_promoted': False, 'network_execution': False,
        }
        out['timeline_hash'] = _sha(out)
        return out

    def conflicts(self, search_id: str):
        timeline = self.timeline(search_id)
        grouped = {}
        for e in timeline['events']:
            # Retrieval time describes collection, not the event itself. Compare the
            # same semantic temporal field across similar result titles only.
            if e['temporal_field'] == 'retrieved_at':
                continue
            title_key = ' '.join(e['title'].strip().casefold().split())
            key = (title_key or e['canonical_ref'].strip().casefold(), e['temporal_field'])
            grouped.setdefault(key, []).append(e)
        conflicts = []
        for (object_key, temporal_field), rows in grouped.items():
            values = sorted({r['temporal_value'] for r in rows})
            if len(values) <= 1:
                continue
            sources = sorted({r['source_id'] for r in rows})
            conflicts.append({
                'object_key': object_key, 'temporal_field': temporal_field,
                'temporal_values': values, 'source_ids': sources,
                'result_ids': sorted({r['result_id'] for r in rows}),
                'classification': 'temporal_disagreement_requires_review',
                'automatic_resolution': False,
            })
        return {
            'build': BUILD, 'search_id': search_id, 'conflicts': conflicts,
            'conflict_count': len(conflicts), 'automatic_resolution': False,
            'truth_determined': False, 'causality_inferred': False,
        }

    def coverage(self, search_id: str):
        timeline = self.timeline(search_id)
        quality = self.quality409.assess(search_id)
        results = self.search408.merged_results(search_id)
        dated_results = len({e['result_id'] for e in timeline['events']})
        ratio = round(dated_results / len(results), 6) if results else 0.0
        gaps = []
        if not results:
            gaps.append('no_results_imported')
        elif ratio < 0.5:
            gaps.append('low_explicit_temporal_coverage')
        if timeline['text_date_candidates']:
            gaps.append('unverified_text_date_candidates_present')
        return {
            'build': BUILD, 'search_id': search_id, 'results': len(results),
            'dated_results': dated_results, 'explicit_temporal_coverage_ratio': ratio,
            'retrieval_coverage_gaps': quality['gaps'], 'temporal_gaps': gaps,
            'sufficient_for_temporal_analysis': bool(results) and ratio >= 0.5,
            'truth_determined': False, 'causality_inferred': False,
            'network_execution': False,
        }

    def status(self):
        return {
            'build': BUILD, 'policy': POLICY_ID, 'temporal_intelligence': True,
            'explicit_provenance_dates': True, 'text_dates_candidate_only': True,
            'temporal_conflict_detection': True, 'coverage_analysis': True,
            'automatic_conflict_resolution': False, 'truth_determined': False,
            'causality_inferred': False, 'execution_authority': False,
            'automatic_go': False, 'automatic_evidence_promotion': False,
            'network_execution': False,
        }
