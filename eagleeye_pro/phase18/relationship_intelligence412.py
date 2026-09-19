from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any

BUILD = '412.0'
POLICY_ID = 'phase18.relationship-intelligence-graph.v412'
ENTITY_KEYS = ('structured_entities', 'entities')
RELATION_KEYS = ('structured_relationships', 'relationships')


def _canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str)


def _sha(v: Any) -> str:
    return hashlib.sha256(_canon(v).encode()).hexdigest()


def _norm(v: Any) -> str:
    return ' '.join(str(v or '').split())


class RelationshipIntelligence412:
    """Provenance-first relationship graph over explicitly structured search results.

    This layer never creates an entity or relationship from text co-occurrence.  Only
    caller/importer supplied structured provenance is admitted.  Unknown endpoints
    remain unresolved candidates for analyst/entity-resolution review.
    """

    def __init__(self, db, audit, *, search408, temporal411, actor='local-analyst'):
        self.db = db
        self.audit = audit
        self.search408 = search408
        self.temporal411 = temporal411
        self.actor = actor

    @staticmethod
    def _pick_list(prov: dict, keys: tuple[str, ...]) -> list[dict]:
        for key in keys:
            value = prov.get(key)
            if isinstance(value, list):
                return [dict(x) for x in value if isinstance(x, dict)]
        return []

    def graph(self, search_id: str) -> dict:
        sess = self.search408.session(search_id)
        results = self.search408.merged_results(search_id)
        nodes: dict[str, dict] = {}
        edge_assertions: dict[tuple[str, str, str], list[dict]] = {}
        malformed: list[dict] = []
        unstructured: list[str] = []

        # Pass 1: explicit entities only.
        for result in results:
            prov = dict(result.get('provenance') or {})
            entities = self._pick_list(prov, ENTITY_KEYS)
            relationships = self._pick_list(prov, RELATION_KEYS)
            if not entities and not relationships:
                unstructured.append(result['result_id'])
            for raw in entities:
                eid = _norm(raw.get('entity_id'))
                etype = _norm(raw.get('entity_type') or raw.get('type'))
                label = _norm(raw.get('label') or raw.get('name'))
                if not eid or not etype or not label:
                    malformed.append({'result_id': result['result_id'], 'kind': 'entity', 'reason': 'entity_id_type_label_required'})
                    continue
                observation = {
                    'result_id': result['result_id'], 'source_id': result['source_id'],
                    'canonical_ref': result.get('canonical_ref', ''),
                    'provenance_class': prov.get('provenance_class', ''),
                }
                node = nodes.setdefault(eid, {
                    'entity_id': eid, 'entity_type': etype, 'label': label,
                    'aliases': set(), 'observations': [], 'entity_resolution_performed': False,
                })
                if node['entity_type'] != etype:
                    node.setdefault('type_conflicts', set()).update({node['entity_type'], etype})
                if node['label'] != label:
                    node['aliases'].add(label)
                node['observations'].append(observation)

        # Pass 2: explicit relationships whose endpoints are declared entities.
        for result in results:
            prov = dict(result.get('provenance') or {})
            for raw in self._pick_list(prov, RELATION_KEYS):
                subject = _norm(raw.get('subject_id'))
                predicate = _norm(raw.get('predicate') or raw.get('relationship_type'))
                obj = _norm(raw.get('object_id'))
                if not subject or not predicate or not obj:
                    malformed.append({'result_id': result['result_id'], 'kind': 'relationship', 'reason': 'subject_predicate_object_required'})
                    continue
                if subject not in nodes or obj not in nodes:
                    malformed.append({
                        'result_id': result['result_id'], 'kind': 'relationship',
                        'reason': 'unresolved_endpoint', 'subject_id': subject,
                        'predicate': predicate, 'object_id': obj,
                    })
                    continue
                assertion = {
                    'result_id': result['result_id'], 'source_id': result['source_id'],
                    'canonical_ref': result.get('canonical_ref', ''),
                    'assertion_ref': _norm(raw.get('assertion_ref')),
                    'valid_from': _norm(raw.get('valid_from')),
                    'valid_to': _norm(raw.get('valid_to')),
                    'basis': 'explicit_structured_provenance',
                }
                edge_assertions.setdefault((subject, predicate, obj), []).append(assertion)

        out_nodes = []
        for eid, node in sorted(nodes.items()):
            item = dict(node)
            item['aliases'] = sorted(item['aliases'])
            if 'type_conflicts' in item:
                item['type_conflicts'] = sorted(item['type_conflicts'])
            item['observations'] = sorted(item['observations'], key=lambda x: (x['source_id'], x['result_id']))
            item['node_hash'] = _sha({k: item[k] for k in item if k != 'node_hash'})
            out_nodes.append(item)

        edges = []
        for (subject, predicate, obj), assertions in sorted(edge_assertions.items()):
            assertions = sorted(assertions, key=lambda x: (x['source_id'], x['result_id'], x['canonical_ref']))
            edge = {
                'subject_id': subject, 'predicate': predicate, 'object_id': obj,
                'assertions': assertions, 'independent_source_ids': sorted({x['source_id'] for x in assertions}),
                'assertion_count': len(assertions), 'relationship_inferred': False,
                'truth_determined': False, 'automatic_evidence_promotion': False,
            }
            edge['edge_hash'] = _sha(edge)
            edges.append(edge)

        graph = {
            'build': BUILD, 'search_id': search_id, 'case_id': sess['case_id'],
            'nodes': out_nodes, 'edges': edges,
            'node_count': len(out_nodes), 'edge_count': len(edges),
            'malformed_or_unresolved': malformed,
            'unstructured_result_ids': sorted(unstructured),
            'text_cooccurrence_relationships': False,
            'entity_resolution_performed': False,
            'relationship_inference_performed': False,
            'truth_determined': False, 'network_execution': False,
            'automatic_go': False, 'automatic_evidence_promotion': False,
        }
        graph['graph_hash'] = _sha(graph)
        return graph

    def neighborhood(self, search_id: str, entity_id: str) -> dict:
        entity_id = _norm(entity_id)
        graph = self.graph(search_id)
        if entity_id not in {n['entity_id'] for n in graph['nodes']}:
            raise KeyError('entity not present in explicit graph')
        edges = [e for e in graph['edges'] if e['subject_id'] == entity_id or e['object_id'] == entity_id]
        neighbor_ids = sorted({e['object_id'] if e['subject_id'] == entity_id else e['subject_id'] for e in edges})
        nodes = [n for n in graph['nodes'] if n['entity_id'] == entity_id or n['entity_id'] in neighbor_ids]
        return {
            'build': BUILD, 'search_id': search_id, 'entity_id': entity_id,
            'nodes': nodes, 'edges': edges, 'neighbor_ids': neighbor_ids,
            'relationship_inference_performed': False, 'truth_determined': False,
        }

    def paths(self, search_id: str, start_entity_id: str, end_entity_id: str, max_depth: int = 4) -> dict:
        start, end = _norm(start_entity_id), _norm(end_entity_id)
        depth = max(1, min(int(max_depth), 6))
        graph = self.graph(search_id)
        ids = {n['entity_id'] for n in graph['nodes']}
        if start not in ids or end not in ids:
            raise KeyError('path endpoint not present in explicit graph')
        adjacency: dict[str, list[tuple[str, dict]]] = {x: [] for x in ids}
        for edge in graph['edges']:
            adjacency[edge['subject_id']].append((edge['object_id'], edge))
            adjacency[edge['object_id']].append((edge['subject_id'], edge))
        found = []
        q = deque([(start, [start], [])])
        while q and len(found) < 50:
            current, node_path, edge_path = q.popleft()
            if len(edge_path) >= depth:
                continue
            for nxt, edge in adjacency.get(current, []):
                if nxt in node_path:
                    continue
                np = node_path + [nxt]
                ep = edge_path + [edge['edge_hash']]
                if nxt == end:
                    found.append({'entity_path': np, 'edge_hashes': ep, 'explicit_edge_count': len(ep)})
                else:
                    q.append((nxt, np, ep))
        return {
            'build': BUILD, 'search_id': search_id, 'start_entity_id': start,
            'end_entity_id': end, 'max_depth': depth, 'paths': found,
            'path_count': len(found), 'derived_only_from_explicit_edges': True,
            'relationship_inference_performed': False, 'truth_determined': False,
        }

    def verify_integrity(self):
        s=self.status()
        forbidden=('truth_determined','execution_authority','automatic_evidence_promotion','network_execution','automatic_go')
        violations=[k for k in forbidden if s.get(k) is True]
        return {'build': BUILD, 'valid': not violations, 'violations': violations, 'contract':'static_capability_integrity'}

    def status(self) -> dict:
        return {
            'build': BUILD, 'policy': POLICY_ID, 'relationship_intelligence_graph': True,
            'explicit_structured_entities_only': True,
            'explicit_structured_relationships_only': True,
            'text_cooccurrence_relationships': False,
            'unresolved_endpoints_fail_closed': True,
            'provenance_preserved': True, 'entity_resolution_performed': False,
            'relationship_inference_performed': False, 'truth_determined': False,
            'network_execution': False, 'execution_authority': False,
            'automatic_go': False, 'automatic_evidence_promotion': False,
        }
