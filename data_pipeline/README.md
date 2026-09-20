# Distilling a small model for Save & Reflect

This folder produces a small language model (SLM) that runs the app's journal analysis locally,
on a NAS CPU or a home GPU, with quality checked against the same golden set the cloud model is
scored on. Everything hangs off one contract, `backend/ai_contracts/analysis.py`: the schema and
the system prompt that production sends, that the teacher labels with, that the student trains
on and that the evaluator uses.

```mermaid
flowchart LR
    subgraph gen["1. Generate (run.py)"]
        W["Writer"] --> R["Reviewer"]
        R -->|approved| A["Analyzer (teacher)"]
        R -->|critique| E["Editor"] --> R
        A --> V["Validator: schema + rules"]
        V -->|errors fed back| A
        V --> J["Judge (different model)"]
        J -->|critique, one repair| A
        J -->|pass| D[("dataset_raw.jsonl")]
        J -.->|sample| J2["Second opinion"]
    end
    D --> S["2. build_splits: dedup, stratify"] --> T["3. finetune (Unsloth QLoRA)"]
    T --> G[("GGUF + merged fp16")]
    G --> Serve["4. llama-server / vLLM"]
    Serve --> Ev["5. evaluate: golden + held-out"]
    Ev -.->|gate| Serve
```

## Setup

```bash
python -m venv data_pipeline/.venv && data_pipeline/.venv/Scripts/activate   # or source .../bin/activate
pip install -r data_pipeline/requirements.txt
cp data_pipeline/.env.example data_pipeline/.env    # add LLM_API_KEY; never commit it
```

Run every command from the repository root. The app's root `.env` is loaded first, so the
Google keys used by the judge overflow are picked up from there.

## Models and roles

| Role | Default | Why |
|---|---|---|
| Writer, reviewer, editor | `Qwen/Qwen3-30B-A3B-Instruct-2507` on `LLM_BASE_URL` | fast, good prose |
| Analyzer (teacher) | one fixed model, `ANALYZER_MODEL` | labels keep a single calibration; chosen on the golden set |
| Judge | `Ternary-Bonsai-2-27B` on `LLM_BASE_URL`, then LM Studio, then Gemini 3.6 Flash | a different family grades the labels; hosts rotate on rate limits or outages |
| Second opinion | Cerebras `gpt-oss-120b` (optional) | re-judges 10% of passes and 25% of fails, logs disagreements |

Every role can live on its own server (`<ROLE>_BASE_URL`, `<ROLE>_API_KEY`, `<ROLE>_MODEL`).
Judges are a list: `base_url|key|model[|extra_json]` entries separated by `;`, where `key` is
`env:NAME` or a literal, and `extra_json` holds per-host request parameters (Gemini 3.x needs
`{"reasoning_effort": "low", "max_tokens": 800}`). Rotate writers by listing several models in
`WRITER_MODELS`; rotate hosts for the judge, never the analyzer.

## 1. Generate

```bash
python -m data_pipeline.run --count 1 --dry-run          # one sample end to end, printed, nothing written
python -m data_pipeline.run --count 5 --concurrency 2    # smoke run
python -m data_pipeline.run --count 1500 --concurrency auto
streamlit run data_pipeline/dashboard.py                 # outcomes, judge scores, lessons, samples
```

What happens per sample: a seeded diversity profile (persona, emotion, topic, style, length, an
edge case for 30% of samples, a custom persona instruction for 15%); the writer drafts, the
reviewer approves or the editor revises (three rounds at most); the analyzer labels the entry with
the production prompt; the validator checks the schema and the business rules and feeds errors
back for a retry; the judge scores grounding, safety, CBT quality, schema semantics and persona
adherence and either passes, sends one repair request to the analyzer with its critique, or
discards. Rejection reasons go to `output/lessons.json` and steer later writers and analyzers;
they never enter the training records.

Outputs: `output/dataset_raw.jsonl` (entry, analysis, meta with models, judge scores, prompt
version), `logs/telemetry.jsonl` (fixed keys), `output/judge_disagreements.jsonl`. Resume by
running the same command again; the run stops itself after eight consecutive crashes.

Edge cases: acute crisis vs figurative venting, compulsive stimulation, brain fog with stated
minutes, brain builders, decisions, high and low rumination, a no-signals control, messy grammar,
and a two-topic split.

## 2. Build the splits

```bash
python -m data_pipeline.scripts.build_splits --seed 3407 --test-ratio 0.1
```

Drops exact and near duplicates (5-word shingles, Jaccard 0.8, within a stratum), splits
stratified on (edge case, safety flag), writes `training_dataset.jsonl` and `test_dataset.jsonl`
as ShareGPT conversations whose system turn is the production prompt, plus
`splits_manifest.json` with hashes, counts and settings.

## 3. Fine-tune (NVIDIA GPU, Linux or WSL)

```bash
pip install -r data_pipeline/requirements-gpu.txt
python data_pipeline/scripts/finetune.py --model qwen --epochs 2 --export adapter,merged,gguf --quant q4_k_m,q8_0
```

QLoRA with Unsloth on `Qwen2.5-3B-Instruct` (`--model llama` or `phi` for the alternatives):
loss on the assistant turn only, a 5% validation split with early stopping, cosine schedule,
rank 32. Exports the adapter, a merged fp16 checkpoint for vLLM and GGUF files for llama.cpp, and
writes `output/lora_<model>/manifest.json` with the dataset hash, prompt version, hyperparameters,
package versions and eval loss.

## 4. Serve

```bash
./data_pipeline/scripts/serve_llama.sh --gpu                       # llama.cpp, any GGUF under output/
docker compose --profile local-ai up -d                           # llama.cpp on CPU, in the stack
docker compose --profile local-ai-gpu up -d                       # llama.cpp with CUDA
docker compose --profile local-ai-vllm up -d                      # vLLM on the merged export
python data_pipeline/scripts/smoke_endpoint.py --base-url http://localhost:8080/v1 --model smart-diary-slm
```

The backend sends a JSON-schema response format; llama.cpp and vLLM enforce it with a grammar,
LM Studio and Ollama honour it too, and the router downgrades to JSON mode with repair when a
server rejects it. In the app, pick Cloud or Local in Settings, enter the server URL and model
name, test the connection, and optionally keep the cloud model as a fallback.

## 5. Evaluate

```bash
# the served model, exactly as production calls it
python data_pipeline/scripts/evaluate.py --backend endpoint --base-url http://localhost:8080/v1 --model smart-diary-slm --dataset both --gate
# teacher candidates on the golden set
python data_pipeline/scripts/evaluate.py --backend endpoint --base-url $LLM_BASE_URL --api-key-env LLM_API_KEY --model Qwen/Qwen3-30B-A3B-Instruct-2507 --dataset golden --label teacher-qwen
python data_pipeline/scripts/evaluate.py --backend endpoint --base-url $LLM_BASE_URL --api-key-env LLM_API_KEY --model Ternary-Bonsai-2-27B --dataset golden --label teacher-bonsai
# local weights on the training box
python data_pipeline/scripts/evaluate.py --backend unsloth --model qwen --base --dataset golden      # zero-shot baseline
python data_pipeline/scripts/evaluate.py --backend unsloth --model qwen --dataset both --gate
# which judge to trust
python -m data_pipeline.eval.judge_calibration --limit 8
```

`eval/golden_set.jsonl` holds 40 hand-written entries with expected values: the safety flag,
mood range, rumination level, top topic, stimulation and brain-rot loads, builders, decision flag,
grammar. `eval/thresholds.json` is the gate (`--gate` exits 1 when missed): schema validity 98%,
rules 95%, distress recall 95% and precision 80%, mood MAE 1.0, rumination and top-topic
accuracy 70%, load MAEs 0.5. Results append to `output/eval_results.json`, so teacher candidates,
the base model, the fine-tuned weights and the served GGUF sit in one file.

The judge calibration sends correct analyses and deliberately corrupted copies (flipped safety
flag, topic weights not summing to one, invented minutes, wrong rumination level, two micro
actions, contradictory mood) to each judge candidate and reports pass rate on the correct ones
and fail rate on each corruption.

## Order of operations for a new dataset

1. `--dry-run`, then `--count 5`, read the samples.
2. Score the teacher candidates on the golden set; set `ANALYZER_MODEL` to the winner.
3. Run the judge calibration; put the winner first in `JUDGE_ENDPOINTS`.
4. Full run, `build_splits`, `finetune`, `evaluate --gate` on the weights and again on the served GGUF.

## Tests

```bash
data_pipeline/.venv/Scripts/python.exe -m pytest data_pipeline/tests -q      # pipeline, no network
cd backend && uv run --no-sync --with pytest python -m pytest tests -q      # contract, router, app
```
