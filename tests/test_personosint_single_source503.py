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
