"""Schritt 503: Namensabgleich und Quellfamilien gibt es nur noch einmal (in PersonOSINT); die Fallakte nutzt sie."""
import random

from eagleeye.application.intel492 import entitymatch  # lädt PersonOSINT (installiert oder Ordner neben src)
from eagleeye.application.intel492 import lineage as ee_lineage
from personosint import lineage as po_lineage
from personosint import namematch


def test_case_file_uses_the_single_name_matcher():
    assert entitymatch.compare_names is namematch.compare_names
    assert entitymatch._compare is namematch.compare_prepared and entitymatch._Prepared is namematch.Prepared
    assert entitymatch.REASONS is namematch.REASONS
    # Regel aus der Fallakte gilt jetzt auch in PersonOSINT: Initialen oder Rechtsform allein sind kein Anker.
    assert namematch.compare_names("A. B.", "Anna Berg")[0] < namematch.THRESHOLD
    assert namematch.compare_names("Müller GmbH", "Meier GmbH")[0] < namematch.THRESHOLD
    assert namematch.is_candidate("K. Hoffmann", "Karin Hoffmann")[0]
    assert namematch.is_candidate("Владимир Иванов", "Vladimir Ivanov")[0]


def test_source_family_definition_is_shared():
    assert ee_lineage.shingles is po_lineage.shingles
    assert (ee_lineage.LEVELS, ee_lineage.MIN_WORDS, ee_lineage.SHINGLE) == (po_lineage.LEVELS, po_lineage.MIN_WORDS, po_lineage.SHINGLE)


def _documents():
    rng = random.Random(503)
    vocab = [f"wort{i}" for i in range(4000)]
    texts = [" ".join(rng.choice(vocab) for _ in range(250)) for _ in range(6)]
    docs = []
    for i, base in enumerate(texts):
        for copy in range(i % 3 + 1):              # 1–3 Übernahmen je Ursprung, leicht verändert
            words = base.split()
            for k in rng.sample(range(len(words)), 5 * copy):
                words[k] = rng.choice(vocab)
            docs.append({"id": f"d{i}-{copy}", "document_id": f"d{i}-{copy}", "title": f"Text {i}", "text": " ".join(words)})
    docs.append({"id": "kurz", "document_id": "kurz", "title": "zu kurz", "text": "nur wenige Wörter"})
    return docs


def test_exact_and_minhash_families_agree():
    docs = _documents()
    exact = po_lineage.source_families(docs)
    estimated = ee_lineage.source_families(docs)
    groups = lambda result, key: sorted(sorted(m[key] for m in f["members"]) for f in result["families"])  # noqa: E731
    assert groups(exact, "id") == groups(estimated, "document_id")
    assert exact["independent_origins"] == estimated["independent_origins"] == 6
    assert exact["duplicate_documents"] == estimated["duplicate_documents"]


def _random_case_graph(rng, n, p):
    ents = [{"id": f"e{i}", "label": f"N{i:03d}", "kind": rng.choice(["person", "organization"])} for i in range(n)]
    rels = [{"source_id": f"e{i}", "target_id": f"e{j}", "predicate": "kennt",
             "state": rng.choice(["supported", "hypothesis", "disputed", "rejected"]),
             "sources": [{"review_state": "reviewed"}] * rng.randint(0, 3)}
            for i in range(n) for j in range(i + 1, n) if rng.random() < p]
    return {"entities": ents, "relations": rels}


def test_network_analysis_is_one_core_and_matches_networkx():
    import networkx as nx
    from networkx.algorithms import community

    from eagleeye.application.intel492 import network
    from personosint import graph as po_graph

    rng = random.Random(503)
    for _ in range(60):
        graph = _random_case_graph(rng, rng.randint(3, 30), rng.uniform(0.05, 0.3))
        g = network.build_graph(graph)
        if not g.number_of_edges():
            continue
        for _, _, data in g.edges(data=True):
            data["distance"] = 1 / data["weight"]
        edges = [(str(r["source_id"]), str(r["target_id"]), network.relation_weight(r)) for r in graph["relations"]]
        ours = po_graph.weighted_betweenness(list(g.nodes), edges)
        theirs = nx.betweenness_centrality(g, weight="distance", normalized=True)
        assert all(abs(ours[k] - theirs[k]) < 1e-9 for k in theirs)
        groups = po_graph.louvain(list(g.nodes), [e for e in edges if e[2] > 0])
        assert community.modularity(g, groups, weight="weight") >= community.modularity(
            g, community.louvain_communities(g, weight="weight", seed=492), weight="weight") - 0.05
        a, b = rng.sample(list(g.nodes), 2)
        steps = network.path_between(graph, a, b)
        try:
            expected = nx.shortest_path_length(g, a, b, weight="distance")
        except nx.NetworkXNoPath:
            assert steps == []
        else:
            assert abs(sum(1 / s["weight"] for s in steps) - expected) < 1e-9
        result = network.analyse(graph)
        assert result["components"] == nx.number_connected_components(g) and result["truth_determined"] is False


def test_case_file_network_page_uses_the_shared_core(monkeypatch):
    from eagleeye.application.intel492 import network
    from personosint import network as po_network

    calls = []
    original = po_network.analyse_weighted
    monkeypatch.setattr(po_network, "analyse_weighted", lambda *a, **k: calls.append(1) or original(*a, **k))
    graph = {"entities": [{"id": "a", "label": "A", "kind": "person"}, {"id": "b", "label": "B", "kind": "person"},
                          {"id": "c", "label": "C", "kind": "organization"}],
             "relations": [{"source_id": "a", "target_id": "c", "predicate": "arbeitet bei", "state": "supported", "sources": []},
                           {"source_id": "b", "target_id": "c", "predicate": "arbeitet bei", "state": "hypothesis", "sources": []}]}
    result = network.analyse(graph)
    assert calls and result["central"][0]["label"] == "C" and result["bridges"][0]["label"] == "C"
