"""Fine-tune all-MiniLM-L6-v2 for an llm-d-sc taxonomy.

Same recipe as the reference complexity model: BatchAllTripletLoss with
GROUP_BY_LABEL batch sampling, so each batch contains multiple examples per
label and every valid (anchor, positive, negative) triplet inside the batch
contributes. The output is an embedding model, not a classification head: the
taxonomy stays in anchors.json and can be changed without retraining.
"""
import json, sys, logging
from pathlib import Path
from datasets import Dataset
from sentence_transformers import SentenceTransformer, losses
from sentence_transformers.trainer import SentenceTransformerTrainer
from sentence_transformers.training_args import SentenceTransformerTrainingArguments, BatchSamplers

logging.basicConfig(level=logging.WARNING)

which = sys.argv[1]
epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 12
labels = json.load(open(f"../classifiers/{which}.json"))["labels"]
L2I = {l: i for i, l in enumerate(labels)}

rows = [json.loads(l) for l in open(f"data/{which}-train.jsonl") if l.strip()]
ds = Dataset.from_dict({
    "sentence": [r["text"] for r in rows],
    "label": [L2I[r["tier"]] for r in rows],
})
print(f"{which}: {len(ds)} examples, {len(labels)} labels, {epochs} epochs")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="mps")
loss = losses.BatchAllTripletLoss(model)
out = Path(f"models/{which}")

args = SentenceTransformerTrainingArguments(
    output_dir=str(out),
    num_train_epochs=epochs,
    per_device_train_batch_size=64,
    learning_rate=2e-5,
    warmup_ratio=0.1,
    weight_decay=0.01,
    seed=42,
    logging_steps=50,
    save_strategy="no",
    report_to="none",
    batch_sampler=BatchSamplers.GROUP_BY_LABEL,
)
SentenceTransformerTrainer(model=model, args=args, train_dataset=ds, loss=loss).train()
out.mkdir(parents=True, exist_ok=True)
model.save(str(out))
print("saved ->", out)
