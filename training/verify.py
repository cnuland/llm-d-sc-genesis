"""Cross-model label verification and dataset assembly.

The generator (DeepSeek-V4-Flash) proposed both the prompt and its label. A
generator grading its own output is not evidence, so every candidate is
re-labelled by a DIFFERENT model (Qwen3.6-35B) with no knowledge of the proposed
label. Rows where the two models disagree are DROPPED: they are either genuinely
ambiguous or mislabelled, and both are poison for a triplet loss that treats the
label as ground truth.

Also enforces: dedup, per-tier balance, and a hard leakage check against the
hand-authored held-out evaluation set.
"""
import json, re, sys, threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.argv = [sys.argv[0], sys.argv[1]]
exec(open("sdg_llm.py").read().replace('if __name__ == "__main__":', 'if False:'))

tax = sys.argv[1]
tiers = list(TAXONOMIES[tax]["tiers"])
norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

rows, seen = [], set()
for line in open(f"data/{tax}-raw.jsonl"):
    try: r = json.loads(line)
    except Exception: continue
    k = norm(r["text"])
    if k in seen or not k: continue
    seen.add(k); rows.append(r)
print(f"{tax}: {len(rows)} unique raw rows  {dict(Counter(r['tier'] for r in rows))}")

ev = {norm(json.loads(l)["text"]) for l in open(f"../evals/datasets/{tax}-heldout.jsonl") if l.strip()}
before = len(rows)
rows = [r for r in rows if norm(r["text"]) not in ev]
print(f"  leakage check: dropped {before - len(rows)} rows matching held-out prompts")

ladder = "\n".join(f"- {k}: {v}" for k, v in TAXONOMIES[tax]["tiers"].items())
BATCH = 12
# Group by generating model so each batch is verified wholly by the other model.
rows.sort(key=lambda r: r.get("gen", ""))
batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
verdicts, lock, done = {}, threading.Lock(), {"n": 0}

def verify(idx_batch):
    idx, batch = idx_batch
    # Verify with a DIFFERENT model than the one that generated the row. Rows
    # are grouped by generator upstream, so this picks the opposite endpoint.
    # Generation runs on Qwen, so verification runs on DS4: the label is always
    # confirmed by a model that did not propose it.
    gen = batch[0].get("gen", "")
    url, model = (QWEN if "ds4" in gen else DS4)
    listing = "\n".join(f"{i+1}. {r['text'][:300]}" for i, r in enumerate(batch))
    prompt = (f"Classify each prompt by {TAXONOMIES[tax]['signal']}.\nLabels:\n{ladder}\n\n"
              f"Prompts:\n{listing}\n\nOutput ONLY a JSON array of {len(batch)} label strings, "
              f"in order, each one of: {', '.join(tiers)}. No explanation.")
    out = parse_list(call(url, model, prompt, max_tokens=900, temperature=0.0))
    with lock:
        if len(out) == len(batch):
            for r, lab in zip(batch, out):
                lab = lab.strip().upper()
                if lab in tiers: verdicts[norm(r["text"])] = lab
        done["n"] += 1
        if done["n"] % 25 == 0: print(f"  verified {done['n']}/{len(batches)} batches", flush=True)

with ThreadPoolExecutor(max_workers=5) as ex:
    list(ex.map(verify, list(enumerate(batches))))

agree = [r for r in rows if verdicts.get(norm(r["text"])) == r["tier"]]
unver = [r for r in rows if norm(r["text"]) not in verdicts]
disagree_rate = 1 - len(agree) / max(1, len(rows) - len(unver))
print(f"  cross-model: {len(agree)} agreed, {len(rows)-len(unver)-len(agree)} disagreed "
      f"({disagree_rate:.1%}), {len(unver)} unverified (dropped)")

by_tier = defaultdict(list)
for r in agree: by_tier[r["tier"]].append(r)
cap = min(len(v) for v in by_tier.values()) if len(by_tier) == len(tiers) else 0
if cap == 0:
    print(f"  FAIL: a tier has no verified rows: {[(t, len(by_tier[t])) for t in tiers]}")
    sys.exit(1)
RNG = __import__("random").Random(20260818)
balanced = []
for t in tiers:
    RNG.shuffle(by_tier[t]); balanced += by_tier[t][:cap]
RNG.shuffle(balanced)

out = Path(f"data/{tax}-train.jsonl")
with open(out, "w") as f:
    for r in balanced:
        f.write(json.dumps({"text": r["text"], "tier": r["tier"], "source": r["source"]}) + "\n")
print(f"{tax}: {len(balanced)} verified balanced examples ({cap}/tier) -> {out}")
print(f"  sources {dict(Counter(r['source'] for r in balanced))}")
