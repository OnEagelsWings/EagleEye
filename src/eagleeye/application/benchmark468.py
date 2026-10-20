"""Reproducible *baseline*, not a measured EagleEye production search benchmark.

Synthetic deterministic 100-query goldset. Python standard library only.
Run: python tools/benchmark468.py --output benchmark468.json
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
import re
import sqlite3
import sys
import time
from pathlib import Path

def fixture(n=100):
    rows, questions = [], []
    for i in range(n):
        code = f"record{i:03d}"
        title = f"Public synthetic report {code} topic{i % 17} entity{i % 23}"
        rows.append((code, title))
        questions.append({"query_id": f"Q{i:03d}", "query": code, "relevant": [code]})
    return rows, questions

def metrics(rankings, questions):
    precision, recall, reciprocal, ndcg = [], [], [], []
    for q in questions:
        ranked = rankings[q["query_id"]]
        gold = set(q["relevant"])
        precision.append(len(gold.intersection(ranked[:10]))/10)
        recall.append(len(gold.intersection(ranked[:50]))/len(gold))
        positions=[i+1 for i,doc in enumerate(ranked[:10]) if doc in gold]
        reciprocal.append(1/min(positions) if positions else 0.0)
        dcg=sum((1/math.log2(i+2)) for i,doc in enumerate(ranked[:10]) if doc in gold)
        ideal=sum(1/math.log2(i+2) for i in range(min(10,len(gold))))
        ndcg.append(dcg/ideal if ideal else 0.0)
    return {"precision_at_10":sum(precision)/len(precision),"recall_at_50":sum(recall)/len(recall),
            "mrr_at_10":sum(reciprocal)/len(reciprocal),"ndcg_at_10":sum(ndcg)/len(ndcg)}

def benchmark():
    documents, gold=fixture()
    conn=sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE docs USING fts5(doc_id UNINDEXED, content)")
    conn.executemany("INSERT INTO docs(doc_id, content) VALUES (?,?)", documents)
    rankings={}
    durations=[]
    for q in gold:
        start=time.perf_counter_ns()
        rankings[q["query_id"]]=[row[0] for row in conn.execute(
            "SELECT doc_id FROM docs WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT 50",(q["query"],))]
        durations.append((time.perf_counter_ns()-start)/1e6)
    conn.close()
    durations.sort()
    fixture_bytes=json.dumps({"documents":documents,"gold":gold},sort_keys=True).encode()
    return {"name":"build468_synthetic_sqlite_fts5_baseline","not_product_search":True,
            "query_count":len(gold),"document_count":len(documents),
            "fixture_sha256":hashlib.sha256(fixture_bytes).hexdigest(),
            "runtime":{"python":sys.version.split()[0],"platform":platform.platform(),
                       "cpu":platform.processor() or "unknown"},
            "metrics":metrics(rankings,gold),
            "latency_ms":{"p50":durations[len(durations)//2],"p95":durations[math.ceil(.95*len(durations))-1]},
            "entity_resolution_f1":None,
            "limitations":["Synthetic unique-token lookup inflates recall and MRR",
                           "Not representative of multilingual OSINT or actual EagleEye pipeline",
                           "Precision@10 counts ten result slots even for single-answer queries",
                           "Entity-resolution measurement is N/A until ground-truth matcher exists"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default="benchmark468.json")
    args=parser.parse_args()
    result=benchmark()
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"report":args.output,"metrics":result["metrics"],"product_search":False}))
if __name__=="__main__":
    main()
