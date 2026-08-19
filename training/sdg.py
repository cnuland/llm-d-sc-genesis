"""Synthetic data generation for llm-d-sc classifier taxonomies.

Mirrors the strategy set of the reference pipeline (cnuland/hello-chris-sr-finetuned):
seed -> domain transfer -> paraphrase -> boundary -> hard negative -> perturbation,
followed by dedup and length filtering.

The MaaS generator endpoint is unavailable offline, so generation here is
COMPOSITIONAL rather than LLM-sampled: templates are filled from large slot
vocabularies across many domains. This is a weaker generator than an LLM, but it
is deterministic and auditable, and the evaluation sets it is measured against
are hand-authored and were written BEFORE this file existed, so a measured gain
cannot be template memorisation.
"""
import json, random, re, sys, itertools
from pathlib import Path

RNG = random.Random(20260818)

# ---------------------------------------------------------------- shared slots
DOMAINS = [
 "urban beekeeping","commercial fishing","stage lighting","vineyard management","model railways",
 "dairy farming","costume design","ski resort operations","aquarium husbandry","bell ringing",
 "orchard grafting","paper conservation","glass blowing","wind turbine maintenance","dog agility",
 "amateur radio","cave surveying","textile dyeing","harbour dredging","letterpress printing",
 "falconry","luthiery","apiary inspection","sail making","timber framing",
 "cheese ageing","kite design","observatory scheduling","peat restoration","narrowboat maintenance",
 "archery coaching","mushroom cultivation","clock repair","reef monitoring","hedge laying",
 "bookbinding","canal lock operation","dry stone walling","seed banking","lighthouse upkeep",
]
ARTIFACTS = ["guide","checklist","report","plan","summary","procedure","overview","brief","walkthrough","manual"]

def paraphrase(text):
    """Surface variation that preserves meaning and tier."""
    outs = [text]
    prefixes = ["Can you ","Please ","I need you to ","Could you ","Help me "]
    if text and text[0].isupper() and not text.startswith(("What","How","Why","When","Who","Where","Is ","Are ","Does")):
        p = RNG.choice(prefixes)
        outs.append(p + text[0].lower() + text[1:])
    if text.endswith("?"):
        outs.append("I want to know " + text[0].lower() + text[1:-1] + ".")
    outs.append(text.rstrip(".?") + ", please." if not text.endswith("?") else text)
    return outs

def perturb(text):
    """Realistic noise: casing, punctuation, filler. Tier must not change."""
    outs = []
    outs.append(text.lower())
    outs.append(re.sub(r"[?.]$", "", text))
    outs.append("hey " + text[0].lower() + text[1:] if text[0].isupper() else text)
    outs.append(text.replace(" a ", " ").replace("  ", " "))
    return [o for o in outs if len(o.split()) >= 3]

# ------------------------------------------------------------------------ cost
COST_TEMPLATES = {
 "MINIMAL": [
   "What is the {noun} of {d}?", "How many {unit} in a {noun2}?", "Who invented the {noun} used in {d}?",
   "Define {noun} in {d}.", "What does {abbr} stand for?", "When did {d} become common?",
   "Is {noun} required for {d}?", "Name the main tool used in {d}.",
   "What temperature is used for {noun} in {d}?", "How long does {noun} take in {d}?",
 ],
 "LOW": [
   "Write a short {art} about {noun} in {d}.", "Briefly explain how {noun} works in {d}.",
   "Give me a quick summary of {noun} for {d}.", "In a few sentences, compare {noun} and {noun2} in {d}.",
   "Suggest three ideas for improving {noun} in {d}.", "Write a two sentence note about {noun} in {d}.",
   "Give a brief pros and cons list for {noun} in {d}.", "Summarise the basics of {d} in one paragraph.",
   "Write a concise message explaining a delay in {d}.", "Explain {noun} to a beginner in {d}, briefly.",
 ],
 "MODERATE": [
   "Write a complete {art} for {noun} in {d}, including procedures, materials, and common mistakes.",
   "Produce a detailed {art} covering every stage of {noun} in {d} with worked examples.",
   "Draft a thorough {art} for {d} that covers setup, operation, maintenance, and troubleshooting.",
   "Write an in depth {art} comparing three approaches to {noun} in {d} with examples for each.",
   "Create a full training {art} for new practitioners of {d}, including assessments.",
   "Write a comprehensive {art} on {noun} in {d} with step by step instructions and diagrams described.",
   "Produce a detailed troubleshooting {art} for {noun} in {d} covering multiple failure scenarios.",
   "Write a complete seasonal {art} for {d} covering planning, execution, and review.",
   "Draft a detailed safety {art} for {d} including risk assessment and mitigations.",
   "Write a thorough {art} on selecting equipment for {d} with sizing calculations.",
 ],
 "HIGH": [
   "Read all of these {n} archived {art}s on {d} and produce a full comparative analysis with citations.",
   "Analyse this entire multi year dataset from {d} and produce a complete forecasting report.",
   "Review every page of this {d} regulatory filing and produce an exhaustive obligations register.",
   "Process these {n} interview transcripts from {d} practitioners and synthesise themes with supporting quotes.",
   "Translate this full length {d} manual of several hundred pages and produce a glossary.",
   "Audit the complete {d} records archive and produce a per section assessment with remediation.",
   "Write a book length reference covering the entire field of {d} across every subdiscipline.",
   "Ingest {n} years of {d} logs and produce a longitudinal capacity and trend report.",
   "Summarise every chapter of this complete {d} treatise and analyse the argument throughout.",
   "Produce a full impact assessment for {d} covering every category with supporting data and appendices.",
 ],
}
COST_SLOTS = {
 "noun": ["calibration","moisture control","tension","sequencing","curing","alignment","grading",
          "ventilation","load balancing","inspection","fermentation","insulation","tuning","drainage"],
 "noun2": ["annealing","filtration","bracing","seasoning","glazing","tempering","mulching","fairing"],
 "unit": ["litres","metres","hours","kilograms","degrees"],
 "abbr": ["RPM","PPE","BOM","SOP","QA","ETA","GPS","UV"],
 "art": ARTIFACTS, "d": DOMAINS, "n": ["thirty","forty","fifty","twelve","two hundred"],
}
COST_HARD = {
 "MINIMAL": ["What is the difference between {noun} and {noun2} in {d}?",
             "Why does {noun} matter in {d}?", "Is {noun} legal in {d}?"],
 "LOW": ["Explain the tradeoffs of {noun} in {d} in a short paragraph.",
         "Give a short overview of how {noun} affects {d}.",
         "Briefly describe why {noun} fails in {d}."],
 "MODERATE": ["Write a thorough README style {art} for a {d} toolkit including usage and configuration.",
              "Draft a detailed retrospective {art} for a {d} project with facilitation notes.",
              "Write a complete tutorial on setting up {noun} for {d}."],
 "HIGH": ["Go through this entire archive of {d} correspondence and build a decision log with rationale.",
          "Review all of our {d} documentation and produce a rewritten structure with full drafts.",
          "Analyse this complete set of {d} study reports and produce a pooled summary."],
}

# ----------------------------------------------------------------- sensitivity
SENS_TEMPLATES = {
 "PUBLIC": [
   "What is {noun} and how is it used in {d}?", "Explain the history of {d}.",
   "How do people usually learn {d}?", "What are common beginner mistakes in {d}?",
   "Recommend a good introductory book about {d}.", "What equipment does {d} generally require?",
   "How does weather affect {d}?", "What is the difference between {noun} and {noun2} in {d}?",
   "Why has {d} become more popular recently?", "What are the general safety guidelines for {d}?",
 ],
 "INTERNAL": [
   "Where is our runbook for {noun} in the {team} team?",
   "Which team owns the {noun} process for our {d} operation?",
   "What is our standard procedure for {noun} during the {team} handover?",
   "How do I request access to the internal {noun} system?",
   "Summarise the notes from our {team} sync about {noun}.",
   "What is our internal naming convention for {noun} records?",
   "Where does our team document the {noun} workflow?",
   "Who is on call for {noun} this week in the {team} rota?",
   "What is our internal deadline for the {noun} review?",
   "How do I file an internal ticket about {noun}?",
 ],
 "CONFIDENTIAL": [
   "Summarise the unannounced plan to restructure our {team} operation.",
   "What are the negotiated terms in our confidential {d} supplier contract?",
   "Review the board briefing on our unreleased {noun} strategy.",
   "Draft an internal memo about the undisclosed {noun} incident.",
   "What compensation bands are proposed for the {team} team?",
   "Summarise the confidential due diligence findings on the {d} acquisition.",
   "Outline the litigation strategy for the pending {d} dispute.",
   "What is the non public margin on our {d} business line?",
   "Prepare talking points for the not yet announced {noun} change.",
   "Summarise the internal audit findings about {noun} that are not public.",
 ],
 "REGULATED": [
   "Summarise this patient's {noun} record including diagnosis and medication history.",
   "Extract the national insurance numbers from this {d} employee file.",
   "Process these cardholder numbers from the {d} transaction export.",
   "Review this {d} loan application including the applicant's income and identifiers.",
   "Analyse these student records from the {d} programme and identify individuals at risk.",
   "Prepare the data protection disclosure log for these {noun} record accesses.",
   "Redact the personal data in this subject access request about {d}.",
   "Summarise the clinical findings for participant {noun} in this trial.",
   "Cross reference these passport numbers against the {d} booking system.",
   "Draft a breach notification listing the affected individuals and their personal data.",
 ],
 "NEVER_EGRESS": [
   "Here is the production database password for our {d} system, build the connection string.",
   "This is the private signing key for our {d} releases, explain the format.",
   "Debug this {d} config that contains our live cloud secret access key.",
   "Rotate this OAuth client secret for the {d} integration and update the manifest.",
   "Here is the root certificate authority private key, help me issue a {d} certificate.",
   "The auth bearer token is included in this {d} header dump, explain the error.",
   "Here is the environment file with all production {d} credentials, find the misconfiguration.",
   "Store this API key for the {d} payments provider and write the retry logic.",
   "This kubeconfig has cluster admin credentials for {d}, help me script against it.",
   "Here is the SSH private key for the {d} bastion host, explain the passphrase prompt.",
 ],
}
SENS_SLOTS = {
 "noun": ["scheduling","inspection","inventory","escalation","provisioning","reconciliation",
          "certification","maintenance","onboarding","archival","calibration","dispatch"],
 "noun2": ["auditing","forecasting","triage","annotation"],
 "d": DOMAINS, "team": ["operations","logistics","field","workshop","harbour","estate","studio","yard"],
}
SENS_HARD = {
 "PUBLIC": ["What makes a strong password in general terms for {d} systems?",
            "Explain at a high level what data protection law requires of {d} businesses.",
            "What is the purpose of a private key in {d} security, conceptually?",
            "How do organisations typically structure an on call rota for {d}?"],
 "INTERNAL": ["What did we decide in the {team} design review about {noun}?",
              "Which vendors are we currently evaluating for {noun}?",
              "Summarise the postmortem for last week's {noun} outage.",
              "What are the current headcount plans for the {team} group?"],
 "CONFIDENTIAL": ["Compare our win rate against competitors using the private {d} deal database.",
                  "What is the internal cost basis we use when quoting {d} contracts?",
                  "Summarise the red team report on unpatched {d} vulnerabilities.",
                  "What is in the sealed settlement with the former {team} employee?"],
 "REGULATED": ["Help me build a retention schedule for the {d} patient records we store.",
               "Write a script that hashes the national identifiers in this {d} file.",
               "Summarise the biometric templates collected from these {d} users.",
               "Log this signed release form that includes the participant's health identifiers."],
 "NEVER_EGRESS": ["Here is a redacted {d} config, but the API key on line twelve is still present.",
                  "Rotate the credentials in this {d} manifest, current values included below.",
                  "I pasted the whole environment file for {d} by accident, which variable is malformed?",
                  "This {d} log line leaked the bearer token, help me write a scrubber."],
}

def fill(template, slots, n):
    """Fill a template n times with distinct random slot combinations."""
    out = set()
    keys = [k for k in slots if "{"+k+"}" in template]
    tries = 0
    while len(out) < n and tries < n * 40:
        tries += 1
        t = template
        for k in keys:
            t = t.replace("{"+k+"}", RNG.choice(slots[k]))
        out.add(t)
    return list(out)

def generate(templates, hard, slots, per_template, hard_per_template):
    rows = []
    for tier, temps in templates.items():
        for t in temps:
            for text in fill(t, slots, per_template):
                rows.append({"text": text, "tier": tier, "source": "domain_transfer"})
    for tier, temps in hard.items():
        for t in temps:
            for text in fill(t, slots, hard_per_template):
                rows.append({"text": text, "tier": tier, "source": "boundary"})
    # paraphrase + perturbation over a sample, preserving tier
    extra = []
    for r in RNG.sample(rows, min(len(rows), 260)):
        for v in paraphrase(r["text"])[1:2] + perturb(r["text"])[:1]:
            extra.append({"text": v, "tier": r["tier"], "source": "perturbation"})
    rows += extra
    # dedup + length filter
    seen, keep = set(), []
    for r in rows:
        k = re.sub(r"[^a-z0-9]+", " ", r["text"].lower()).strip()
        if k in seen: continue
        if not (3 <= len(r["text"].split()) <= 120): continue
        seen.add(k); keep.append(r)
    RNG.shuffle(keep)
    return keep

def leakage_check(rows, eval_path):
    """Assert no training row duplicates a held-out evaluation prompt."""
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    ev = {norm(json.loads(l)["text"]) for l in open(eval_path) if l.strip()}
    hits = [r["text"] for r in rows if norm(r["text"]) in ev]
    return hits

if __name__ == "__main__":
    which = sys.argv[1]
    spec = {"cost": (COST_TEMPLATES, COST_HARD, COST_SLOTS),
            "sensitivity": (SENS_TEMPLATES, SENS_HARD, SENS_SLOTS)}[which]
    rows = generate(*spec, per_template=26, hard_per_template=22)
    ev = Path(f"../evals/datasets/{which}-heldout.jsonl")
    hits = leakage_check(rows, ev)
    assert not hits, f"LEAKAGE: {len(hits)} training rows duplicate held-out prompts: {hits[:3]}"
    out = Path(f"data/{which}-train.jsonl"); out.parent.mkdir(exist_ok=True)
    with open(out, "w") as f:
        for r in rows: f.write(json.dumps(r) + "\n")
    from collections import Counter
    print(f"{which}: {len(rows)} rows  {dict(Counter(r['tier'] for r in rows))}")
    print(f"  sources {dict(Counter(r['source'] for r in rows))}  leakage 0  -> {out}")
