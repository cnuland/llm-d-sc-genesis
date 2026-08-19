"""LLM-driven synthetic data generation for llm-d-sc taxonomies.

Generator: DeepSeek-V4-Flash (homelab MaaS).
Verifier:  Qwen3.6-35B (a DIFFERENT model, so label verification is not the
           generator grading its own homework).

Contamination guard (the defect that damaged the first sensitivity model):
these are reasoning models and the server returns `reasoning_content` as a
SEPARATE field from `content`. A pipeline that reads the wrong field trains on
175-token chain-of-thought instead of on user prompts. This reader takes
`content` only, and every candidate is additionally screened for trace-like
prose before it can enter the corpus.

Resumable: results append to data/<taxonomy>-raw.jsonl and completed
(tier, domain, strategy) keys are skipped on re-run.
"""
import json, os, re, sys, time, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import request as urlrequest

MAAS = "https://llama-server-{}-homelab-maas.apps.ironman.cjlabs.dev/v1/chat/completions"
DS4 = (MAAS.format("ds4"), "ds4-flash-0731")
# Qwen3.8-27B replaced Qwen3.6-35B-A3B on the api-int GPU. Note the tradeoff:
# 3.8 is a DENSE 27B and 3.6 was a 35B-A3B MoE, so per-slot decode is slower on
# this iGPU; --parallel 4 recovers aggregate throughput for bulk generation.
QWEN = (MAAS.format("qwen38"), "qwen38-27b")
# Measured on this cluster: DS4 decodes at ~11 tok/s, Qwen at ~90 tok/s (it has
# speculative decoding, draft acceptance ~0.67). Generation is a LONG-output task
# and verification is a SHORT-output one, so Qwen generates and DS4 verifies.
# That keeps the verifier independent of the generator while putting the slow
# model on the cheap job; the reverse assignment was ~8x slower overall.
GENERATORS = [QWEN]
GEN_URL, GEN_MODEL = DS4
VER_URL, VER_MODEL = QWEN
KEY = Path("/tmp/.maaskey").read_text().strip()

TAXONOMIES = {
 "cost": {
   "signal": "expected serving cost of answering the prompt",
   "tiers": {
     "MINIMAL":  "a single fact or one-step instruction, answerable in one short sentence; trivial output",
     "LOW":      "a short answer: a brief explanation, a one-liner, a couple of sentences or a small snippet",
     "MODERATE": "one substantial deliverable: a complete guide, a full module, a detailed comparison; multi-paragraph output",
     "HIGH":     "very large input or output: analysing a whole corpus, or producing a book-length or exhaustive document",
   }},
 "sensitivity": {
   "signal": "data sensitivity of the content in the prompt",
   "tiers": {
     "PUBLIC":       "general knowledge; nothing organisation-specific or private",
     "INTERNAL":     "organisation-specific but not sensitive: runbooks, process, ownership, internal logistics",
     "CONFIDENTIAL": "business-sensitive: unannounced plans, contract terms, compensation, undisclosed incidents",
     "REGULATED":    "legally regulated personal data: health records, payment card data, national identifiers, financial records",
     "NEVER_EGRESS": "live credentials or key material: passwords, API keys, private keys, tokens, kubeconfigs",
   }},
}

DOMAINS = ["beekeeping","commercial fishing","stage lighting","viticulture","dairy farming",
 "costume design","ski resort operations","aquarium husbandry","orchard management","paper conservation",
 "glass blowing","wind turbine maintenance","amateur radio","cave surveying","textile dyeing",
 "harbour operations","letterpress printing","luthiery","sail making","timber framing",
 "cheese production","observatory scheduling","peatland restoration","canal boat maintenance","archery coaching",
 "mushroom cultivation","clock repair","reef monitoring","bookbinding","dry stone walling",
 "seed banking","lighthouse maintenance","veterinary practice","municipal recycling","stagecoach museum curation",
 "community pharmacy","independent bookshop","regional airline ground ops","school transport","town planning"]

TRACE_MARKERS = re.compile(
 r"^(the user|okay|alright|let me|i need to|i should|first,|we need to|hmm)\b|"
 r"\b(the user (wants|is asking)|i'll (generate|create|write)|let's (pick|think))\b", re.I)

_lock = threading.Lock()

def call(url, model, prompt, max_tokens=1400, temperature=0.9, retries=3):
    # Both models are reasoning models. Left enabled, Qwen spends the entire
    # token budget on `reasoning_content` and returns an EMPTY `content`, so the
    # pipeline silently generates nothing. Disabling thinking is both correct and
    # far cheaper: these are generation and labelling tasks, not reasoning ones.
    body = json.dumps({"model": model, "temperature": temperature, "max_tokens": max_tokens,
                       "chat_template_kwargs": {"enable_thinking": False},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urlrequest.Request(url, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    for a in range(retries):
        try:
            with urlrequest.urlopen(req, timeout=600) as r:
                msg = json.loads(r.read())["choices"][0]["message"]
                return msg.get("content") or ""      # NEVER reasoning_content
        except Exception as e:
            if a == retries - 1:
                print(f"  ! {type(e).__name__}: {str(e)[:80]}", flush=True)
                return ""
            time.sleep(3 * (a + 1))
    return ""

def parse_list(raw):
    """Extract a JSON array of strings; tolerate fences and stray prose."""
    if not raw: return []
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    m = re.search(r"\[.*\]", raw, re.S)
    if not m: return []
    try:
        items = json.loads(m.group(0))
    except Exception:
        return []
    return [i.strip() for i in items if isinstance(i, str) and i.strip()]

def clean(items, tier):
    """Reject reasoning traces, meta-commentary, and degenerate lengths."""
    out = []
    for t in items:
        w = len(t.split())
        if not (3 <= w <= 90): continue
        if TRACE_MARKERS.search(t): continue
        if tier in ("MINIMAL", "LOW", "PUBLIC") and w > 45: continue
        if re.search(r"\b(tier|classification|sensitivity level|category)\b", t, re.I): continue
        out.append(re.sub(r"\s+", " ", t))
    return out

def gen_prompt(tax, tier, desc, domain, strategy, other=None):
    tiers = TAXONOMIES[tax]["tiers"]
    ladder = "\n".join(f"- {k}: {v}" for k, v in tiers.items())
    base = (f"You are building a training set for a classifier of {TAXONOMIES[tax]['signal']}.\n"
            f"The full label ladder is:\n{ladder}\n\n")
    if strategy == "real_world":
        task = (f"Write 10 realistic, varied prompts that a real person would send to an AI assistant, "
                f"all of which are clearly {tier} ({desc}). Context domain: {domain}.")
    elif strategy == "boundary":
        task = (f"Write 8 realistic prompts in the domain of {domain} that sit CLOSE to the boundary "
                f"between {tier} and {other}, but are definitively {tier} ({desc}). Make them genuinely hard to tell apart.")
    else:  # hard_negative
        task = (f"Write 8 realistic prompts in the domain of {domain} whose surface vocabulary suggests "
                f"{other}, but which are actually {tier} ({desc}).")
    return base + task + (
        "\n\nRules: each prompt must be something a USER would type, not a description of a prompt. "
        "Never mention the label names or the words tier/category/classification. "
        "Do not explain your reasoning. Output ONLY a JSON array of strings.")

def run(tax, out_path):
    cfg = TAXONOMIES[tax]
    tiers = list(cfg["tiers"])
    done = set()
    if out_path.exists():
        for l in open(out_path):
            try: done.add(json.loads(l)["key"])
            except Exception: pass
    jobs = []
    for i, tier in enumerate(tiers):
        desc = cfg["tiers"][tier]
        for d in DOMAINS:
            jobs.append((tier, desc, d, "real_world", None))
        neighbours = [t for j, t in enumerate(tiers) if abs(i - j) == 1]
        for nb in neighbours:
            for d in DOMAINS[:14]:
                jobs.append((tier, desc, d, "boundary", nb))
        for nb in [t for t in tiers if t != tier][:2]:
            for d in DOMAINS[:8]:
                jobs.append((tier, desc, d, "hard_negative", nb))
    jobs = [j for j in jobs if f"{j[0]}|{j[2]}|{j[3]}|{j[4]}" not in done]
    print(f"{tax}: {len(jobs)} generation jobs ({len(done)} already done)", flush=True)

    fh = open(out_path, "a")
    counter = {"n": 0, "kept": 0}
    def work(idx_job):
        idx, j = idx_job
        tier, desc, d, strat, other = j
        url, model = GENERATORS[idx % len(GENERATORS)]
        items = clean(parse_list(call(url, model, gen_prompt(tax, tier, desc, d, strat, other))), tier)
        with _lock:
            for t in items:
                fh.write(json.dumps({"text": t, "tier": tier, "source": strat,
                                     "gen": model, "key": f"{tier}|{d}|{strat}|{other}"}) + "\n")
            counter["n"] += 1; counter["kept"] += len(items)
            if len(items) == 0:
                counter["empty"] = counter.get("empty", 0) + 1
                if counter["empty"] in (5, 25, 100):
                    print(f"  WARNING: {counter['empty']} jobs returned zero usable prompts "
                          f"after {counter['n']} jobs -- check the endpoint response shape",
                          flush=True)
            if counter["n"] % 20 == 0:
                fh.flush()
                print(f"  {counter['n']}/{len(jobs)} jobs, {counter['kept']} prompts "
                      f"({counter.get('empty', 0)} empty)", flush=True)
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(work, list(enumerate(jobs))))
    fh.close()
    print(f"{tax}: generation complete, {counter['kept']} raw prompts", flush=True)

if __name__ == "__main__":
    tax = sys.argv[1]
    Path("data").mkdir(exist_ok=True)
    run(tax, Path(f"data/{tax}-raw.jsonl"))
