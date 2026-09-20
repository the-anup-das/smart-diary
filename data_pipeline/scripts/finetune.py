"""
QLoRA fine-tune of a 3B-class instruct model on the ShareGPT training file, with Unsloth.

Runs on a Linux or WSL machine with an NVIDIA GPU (16 GB is enough for the 3B models at 4-bit;
Gemma 4 E2B needs about 10 GB and the latest unsloth and transformers).
Loss is computed on the assistant turn only, a held-out validation split drives early stopping,
and the run writes a manifest that ties the adapter to the exact dataset and prompt version.

    pip install -r requirements-gpu.txt
    python scripts/finetune.py --model qwen --epochs 2 --export adapter,merged,gguf --quant q4_k_m,q8_0
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE.parent / "output"
REPO_ROOT = HERE.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASE_MODELS = {
    "qwen": "unsloth/Qwen2.5-3B-Instruct",
    "llama": "unsloth/Llama-3.2-3B-Instruct",
    "phi": "unsloth/Phi-3.5-mini-instruct",
    "gemma4": "unsloth/gemma-4-E2B-it",   # 2.3B effective parameters, Apache 2.0, native system role, thinking switchable
}
CHAT_TEMPLATES = {"qwen": "qwen-2.5", "llama": "llama-3.1", "phi": "phi-3", "gemma4": "gemma-4"}
# The markers train_on_responses_only needs to mask everything but the assistant turn.
RESPONSE_MARKERS = {
    "qwen": ("<|im_start|>user\n", "<|im_start|>assistant\n"),
    "llama": ("<|start_header_id|>user<|end_header_id|>\n\n", "<|start_header_id|>assistant<|end_header_id|>\n\n"),
    "phi": ("<|user|>\n", "<|assistant|>\n"),
    "gemma4": ("<|turn>user\n", "<|turn>model\n"),
}
# Gemma 4 is multimodal and reasons before answering: it loads through FastModel with the vision
# and audio layers frozen, and every training text is rendered with thinking off, the way the
# student is served. Its tokenizer adds <bos> itself, so the rendered text must not carry one.
MULTIMODAL = {"gemma4"}
THINKING_SWITCH = {"gemma4"}


def render_chat(tokenizer, conversation: list[dict], family: str, add_generation_prompt: bool = False) -> str:
    kwargs = {"enable_thinking": False} if family in THINKING_SWITCH else {}
    text = tokenizer.apply_chat_template(conversation, tokenize=False, add_generation_prompt=add_generation_prompt, **kwargs)
    if family in MULTIMODAL and text.startswith("<bos>"):
        text = text[len("<bos>"):]
    return text


def load_student(model_name: str, family: str, max_seq_length: int):
    """The base or adapter for a family, 4-bit, ready for LoRA or inference."""
    if family in MULTIMODAL:
        from unsloth import FastModel

        model, tokenizer = FastModel.from_pretrained(model_name=model_name, max_seq_length=max_seq_length, dtype=None, load_in_4bit=True, full_finetuning=False)
        return FastModel, model, tokenizer
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(model_name=model_name, max_seq_length=max_seq_length, dtype=None, load_in_4bit=True)
    return FastLanguageModel, model, tokenizer


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return None


def package_versions() -> dict:
    versions = {}
    for name in ("torch", "transformers", "trl", "peft", "unsloth", "datasets", "bitsandbytes"):
        try:
            versions[name] = __import__(name).__version__
        except Exception:  # noqa: BLE001
            versions[name] = None
    return versions


def sft_config(**kwargs):
    """Build SFTConfig across TRL versions: the sequence-length key was renamed in TRL 0.20."""
    from trl import SFTConfig

    params = inspect.signature(SFTConfig.__init__).parameters
    if "max_length" in params and "max_seq_length" in kwargs:
        kwargs["max_length"] = kwargs.pop("max_seq_length")
    elif "max_seq_length" in params and "max_length" in kwargs:
        kwargs["max_seq_length"] = kwargs.pop("max_length")
    for key in list(kwargs):
        if key not in params:
            kwargs.pop(key)
    return SFTConfig(**kwargs)


def main() -> None:
    parser = argparse.ArgumentParser(description="QLoRA fine-tune with Unsloth")
    parser.add_argument("--model", choices=BASE_MODELS, default="qwen")
    parser.add_argument("--data", type=Path, default=OUTPUT_DIR / "training_dataset.jsonl")
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--r", type=int, default=32)
    parser.add_argument("--alpha", type=int, default=32)
    parser.add_argument("--dropout", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=4096)
    parser.add_argument("--val-ratio", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=3407)
    parser.add_argument("--export", default="adapter,merged,gguf", help="comma-separated: adapter, merged, gguf")
    parser.add_argument("--quant", default="q4_k_m,q8_0", help="GGUF quantisations, comma-separated")
    parser.add_argument("--resume", action="store_true", help="resume from the last checkpoint in the output dir")
    parser.add_argument("--patience", type=int, default=3, help="early-stopping patience in evaluation rounds")
    args = parser.parse_args()

    if not args.data.exists():
        raise SystemExit(f"{args.data} not found; run python -m data_pipeline.scripts.build_splits first")

    import torch
    from datasets import load_dataset
    from transformers import EarlyStoppingCallback
    from trl import SFTTrainer
    from unsloth.chat_templates import get_chat_template, standardize_sharegpt, train_on_responses_only

    from data_pipeline.contracts import PROMPT_VERSION  # noqa: E402

    base = BASE_MODELS[args.model]
    out_dir = OUTPUT_DIR / f"lora_{args.model}"
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    print(f"base {base} | data {args.data} | out {out_dir}")

    loader, model, tokenizer = load_student(base, args.model, args.max_seq_length)
    if args.model in MULTIMODAL:
        model = loader.get_peft_model(
            model, finetune_vision_layers=False, finetune_language_layers=True, finetune_attention_modules=True, finetune_mlp_modules=True,
            r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none", use_gradient_checkpointing="unsloth", random_state=args.seed,
        )
    else:
        model = loader.get_peft_model(
            model, r=args.r, lora_alpha=args.alpha, lora_dropout=args.dropout, bias="none",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            use_gradient_checkpointing="unsloth", random_state=args.seed,
        )
    tokenizer = get_chat_template(tokenizer, chat_template=CHAT_TEMPLATES[args.model])

    dataset = load_dataset("json", data_files=str(args.data), split="train")
    dataset = standardize_sharegpt(dataset)
    dataset = dataset.map(lambda batch: {"text": [render_chat(tokenizer, c, args.model) for c in batch["conversations"]]}, batched=True)
    dataset = dataset.shuffle(seed=args.seed)
    split = dataset.train_test_split(test_size=args.val_ratio, seed=args.seed)
    train_ds, val_ds = split["train"], split["test"]
    steps_per_epoch = max(1, len(train_ds) // (args.batch_size * args.grad_accum))
    eval_every = max(1, steps_per_epoch // 10)
    print(f"train {len(train_ds)} | val {len(val_ds)} | {steps_per_epoch} steps per epoch | eval every {eval_every}")

    config = sft_config(
        output_dir=str(out_dir), per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum, num_train_epochs=args.epochs, learning_rate=args.lr,
        warmup_ratio=0.05, lr_scheduler_type="cosine", weight_decay=0.01, optim="adamw_8bit",
        logging_steps=5, eval_strategy="steps", eval_steps=eval_every, save_strategy="steps", save_steps=eval_every,
        save_total_limit=3, load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
        fp16=not torch.cuda.is_bf16_supported(), bf16=torch.cuda.is_bf16_supported(), seed=args.seed, report_to="none",
        dataset_text_field="text", max_seq_length=args.max_seq_length, dataset_num_proc=2, packing=False,
    )
    trainer = SFTTrainer(
        model=model, processing_class=tokenizer, train_dataset=train_ds, eval_dataset=val_ds, args=config,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=args.patience)],
    )
    instruction_part, response_part = RESPONSE_MARKERS[args.model]
    trainer = train_on_responses_only(trainer, instruction_part=instruction_part, response_part=response_part)

    result = trainer.train(resume_from_checkpoint=args.resume or None)
    metrics = trainer.evaluate()
    print("final eval:", metrics)

    exports = {e.strip() for e in args.export.split(",") if e.strip()}
    if "adapter" in exports:
        model.save_pretrained(str(out_dir))
        tokenizer.save_pretrained(str(out_dir))
    merged_dir = OUTPUT_DIR / f"model_{args.model}_merged"
    if "merged" in exports:
        model.save_pretrained_merged(str(merged_dir), tokenizer, save_method="merged_16bit")
    gguf_dir = OUTPUT_DIR / f"model_{args.model}_gguf"
    if "gguf" in exports:
        quants = [q.strip() for q in args.quant.split(",") if q.strip()]
        model.save_pretrained_gguf(str(gguf_dir), tokenizer, quantization_method=quants)

    splits_manifest = OUTPUT_DIR / "splits_manifest.json"
    manifest = {
        "base_model": base, "family": args.model, "chat_template": CHAT_TEMPLATES[args.model],
        "prompt_version": PROMPT_VERSION,
        "dataset": {"path": str(args.data), "sha256": sha256_file(args.data), "rows": len(dataset), "train_rows": len(train_ds), "val_rows": len(val_ds)},
        "splits_manifest": json.loads(splits_manifest.read_text(encoding="utf-8")) if splits_manifest.exists() else None,
        "hyperparameters": {k: v for k, v in vars(args).items() if k not in ("data",)},
        "train_loss": getattr(result, "training_loss", None), "eval": metrics,
        "exports": sorted(exports), "gguf_dir": str(gguf_dir) if "gguf" in exports else None, "merged_dir": str(merged_dir) if "merged" in exports else None,
        "git_commit": git_commit(), "packages": package_versions(), "platform": platform.platform(), "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "wall_time_s": round(time.time() - started), "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"done in {manifest['wall_time_s']}s; manifest at {out_dir / 'manifest.json'}")
    if "gguf" in exports:
        print(f"serve it: ./scripts/serve_llama.sh {gguf_dir}/<file>.gguf   or   docker compose --profile local-ai up -d (LOCAL_LLM_GGUF=model_{args.model}_gguf/<file>.gguf)")
    if args.model in THINKING_SWITCH:
        print("this family reasons before answering unless told not to: the serve script and the compose profiles pass enable_thinking=false to the chat template")


if __name__ == "__main__":
    main()
