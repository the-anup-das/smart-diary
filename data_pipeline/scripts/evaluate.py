"""Evaluation Benchmarking Script.
Loads the fine-tuned LoRA models and evaluates them against the test_dataset.jsonl holdout set.
Supports single-model evaluation and a --compare mode for head-to-head results.
"""

import argparse
import os
import json
import re
import time
from rich.console import Console
from rich.table import Table
from rich.progress import track
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template
from json_repair import repair_json
from pydantic import ValidationError

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from schemas.feedback_schema import FeedbackReportSchema

console = Console()

MODEL_MAP = {
    "qwen": "unsloth/Qwen2.5-3B-Instruct",
    "phi": "unsloth/Phi-3.5-mini-instruct",
    "llama": "unsloth/Llama-3.2-3B-Instruct"
}

CHAT_TEMPLATE_MAP = {
    "qwen": "chatml",
    "phi": "phi-3",
    "llama": "llama-3.1",
}


def load_test_dataset():
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "output", "test_dataset.jsonl")
    if not os.path.exists(dataset_path):
        console.print("[bold red]Test dataset not found at output/test_dataset.jsonl[/bold red]")
        sys.exit(1)
        
    data = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data


def extract_system_entry(sharegpt_item):
    """Extracts the exact system prompt from the ShareGPT formatted test sample."""
    for msg in sharegpt_item.get("conversations", []):
        if msg.get("from") == "system":
            return msg.get("value")
    return ""


def extract_user_entry(sharegpt_item):
    """Extracts the human's entry from the ShareGPT formatted test sample."""
    for msg in sharegpt_item.get("conversations", []):
        if msg.get("from") == "human":
            return msg.get("value")
    return ""


def extract_ground_truth(sharegpt_item):
    """Extracts the teacher's ground truth JSON from the ShareGPT test sample."""
    for msg in sharegpt_item.get("conversations", []):
        if msg.get("from") == "gpt":
            text = msg.get("value", "")
            # Extract JSON after </thought> tag
            if "</thought>" in text:
                json_part = text.split("</thought>")[-1].strip()
            else:
                json_part = text.strip()
            try:
                return json.loads(repair_json(json_part))
            except Exception:
                return None
    return None


def extract_json_from_output(raw_output: str) -> str:
    """Extracts the JSON portion from a model's raw output which may contain <thought> blocks."""
    # Case 1: Model followed training format with <thought>...</thought>{json}
    if "</thought>" in raw_output:
        json_part = raw_output.split("</thought>")[-1].strip()
    else:
        json_part = raw_output.strip()
    
    # Case 2: Find the first { to last } in case there's preamble text
    first_brace = json_part.find("{")
    last_brace = json_part.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_part = json_part[first_brace:last_brace + 1]
    
    return json_part


def evaluate_model(model_key: str, test_data: list, limit: int, is_base: bool = False) -> dict:
    """Evaluate a single model (either zero-shot base or fine-tuned LoRA) and return detailed results."""
    base_model_name = MODEL_MAP[model_key]
    display_name = f"{model_key}_base" if is_base else f"{model_key}_ft"
    lora_path = os.path.join(os.path.dirname(__file__), "..", "output", f"lora_{model_key}")
    
    if not is_base and not os.path.exists(lora_path):
        console.print(f"[bold red]LoRA adapter not found at {lora_path}. Skipping {display_name}.[/bold red]")
        return None

    console.print(f"\nLoading [bold cyan]{display_name.upper()}[/bold cyan]...")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model_name,
        max_seq_length=4096,
        load_in_4bit=True,
    )
    
    if not is_base:
        model.load_adapter(lora_path)
        
    FastLanguageModel.for_inference(model)
    
    # Apply the correct chat template for this model
    tokenizer = get_chat_template(tokenizer, chat_template=CHAT_TEMPLATE_MAP[model_key])

    samples = test_data[:limit]
    
    results = {
        "model": display_name,
        "total": len(samples),
        "valid_json": 0,
        "valid_schema": 0,
        "field_accuracy": {},  # Per-field presence tracking
        "avg_latency_ms": 0,
        "failures": [],       # Store failure details for debugging
    }

    # Track which top-level fields are present across all samples
    expected_fields = list(FeedbackReportSchema.model_fields.keys())
    field_hits = {f: 0 for f in expected_fields}
    total_latency = 0

    console.print(f"Evaluating {len(samples)} test samples for [bold cyan]{display_name.upper()}[/bold cyan]...")
    
    for idx, item in enumerate(track(samples, description=f"Benchmarking {model_key.upper()}...")):
        user_input = extract_user_entry(item)
        system_input = extract_system_entry(item)
        if not user_input or not system_input:
            continue
        
        messages = [
            {"role": "system", "content": system_input},
            {"role": "user", "content": user_input}
        ]
        
        prompt = tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
        
        inputs = tokenizer([prompt], return_tensors="pt").to("cuda")
        
        start_time = time.time()
        outputs = model.generate(**inputs, max_new_tokens=2048, use_cache=True)
        latency = (time.time() - start_time) * 1000
        total_latency += latency
        
        # Decode only the NEW tokens (skip the input prompt tokens)
        input_length = inputs["input_ids"].shape[1]
        new_tokens = outputs[0][input_length:]
        response_text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        
        json_str = extract_json_from_output(response_text)
        
        try:
            parsed = json.loads(repair_json(json_str))
            results["valid_json"] += 1
            
            # Track per-field presence
            for field in expected_fields:
                if field in parsed:
                    field_hits[field] += 1
            
            FeedbackReportSchema.model_validate(parsed)
            results["valid_schema"] += 1
        except json.JSONDecodeError as e:
            results["failures"].append({
                "sample": idx, "stage": "json_parse", 
                "error": str(e)[:100], "raw": json_str[:200]
            })
        except ValidationError as e:
            results["valid_json"] += 1  # JSON was valid, schema failed
            # Count field hits even on schema failure
            try:
                parsed_anyway = json.loads(repair_json(json_str))
                for field in expected_fields:
                    if field in parsed_anyway:
                        field_hits[field] += 1
            except Exception:
                pass
            results["failures"].append({
                "sample": idx, "stage": "schema_validation", 
                "error": str(e.errors()[0])[:150] if e.errors() else str(e)[:150]
            })
        except Exception as e:
            results["failures"].append({
                "sample": idx, "stage": "unknown", "error": str(e)[:100]
            })

    results["avg_latency_ms"] = total_latency / max(1, len(samples))
    results["field_accuracy"] = {
        f: round((hits / max(1, results["valid_json"])) * 100, 1) 
        for f, hits in field_hits.items()
    }
    
    # Cleanup GPU memory for next model
    del model, tokenizer
    import torch
    torch.cuda.empty_cache()
    
    return results


def print_single_results(results: dict):
    """Print a detailed results table for a single model."""
    table = Table(title=f"Evaluation: {results['model'].upper()}", border_style="bright_blue")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Score", style="bold bright_white")
    
    json_acc = (results["valid_json"] / results["total"]) * 100
    schema_acc = (results["valid_schema"] / results["total"]) * 100
    
    table.add_row("Total Evaluated", str(results["total"]))
    table.add_row("JSON Parse Rate", f"{json_acc:.1f}%")
    table.add_row("Strict Schema Rate", f"{schema_acc:.1f}%")
    table.add_row("Avg Latency", f"{results['avg_latency_ms']:.0f}ms")
    
    console.print("\n", table)

    # Per-field breakdown
    field_table = Table(title="Per-Field Presence Rate", border_style="dim")
    field_table.add_column("Field", style="cyan")
    field_table.add_column("Hit Rate", style="white")
    for field, rate in results["field_accuracy"].items():
        style = "green" if rate >= 95 else "yellow" if rate >= 80 else "red"
        field_table.add_row(field, f"[{style}]{rate}%[/{style}]")
    console.print(field_table)


def print_comparison(all_results: list):
    """Print a head-to-head comparison table."""
    table = Table(title="🏆 Model Comparison (Head-to-Head)", border_style="bright_green")
    table.add_column("Metric", style="bold cyan")
    for r in all_results:
        table.add_column(r["model"].upper(), style="bold bright_white")

    metrics = [
        ("Total Evaluated", lambda r: str(r["total"])),
        ("JSON Parse Rate", lambda r: f"{(r['valid_json'] / r['total']) * 100:.1f}%"),
        ("Strict Schema Rate", lambda r: f"{(r['valid_schema'] / r['total']) * 100:.1f}%"),
        ("Avg Latency", lambda r: f"{r['avg_latency_ms']:.0f}ms"),
    ]
    
    for label, fn in metrics:
        table.add_row(label, *[fn(r) for r in all_results])
    
    console.print("\n", table)
    
    # Determine winner
    best = max(all_results, key=lambda r: r["valid_schema"])
    console.print(f"\n[bold green]🏆 Winner: {best['model'].upper()} with {(best['valid_schema']/best['total'])*100:.1f}% strict schema accuracy![/bold green]")


def save_results(all_results: list):
    """Save evaluation results to disk for the dashboard."""
    output_path = os.path.join(os.path.dirname(__file__), "..", "output", "eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        # Strip raw failure text for cleaner storage
        clean = []
        for r in all_results:
            c = dict(r)
            c["failures"] = len(r["failures"])  # Just store count
            clean.append(c)
        json.dump(clean, f, indent=2)
    console.print(f"[dim]Results saved to {output_path}[/dim]")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Fine-Tuned SLM")
    parser.add_argument("--model", type=str, choices=["qwen", "phi", "llama"], help="Single model to evaluate")
    parser.add_argument("--compare", action="store_true", help="Evaluate all 3 models head-to-head")
    parser.add_argument("--include-base", action="store_true", help="Include zero-shot base models to measure fine-tuning improvement")
    parser.add_argument("--limit", type=int, default=50, help="Max test samples to evaluate per model")
    args = parser.parse_args()

    if not args.model and not args.compare:
        console.print("[bold red]Specify --model <name> or --compare to evaluate.[/bold red]")
        sys.exit(1)

    test_data = load_test_dataset()

    if args.compare:
        console.print("[bold bright_white]Running full comparison...[/bold bright_white]")
        all_results = []
        for model_key in ["qwen", "phi", "llama"]:
            if args.include_base:
                res_base = evaluate_model(model_key, test_data, args.limit, is_base=True)
                if res_base:
                    print_single_results(res_base)
                    all_results.append(res_base)
                    
            res_ft = evaluate_model(model_key, test_data, args.limit, is_base=False)
            if res_ft:
                print_single_results(res_ft)
                all_results.append(res_ft)
        
        if len(all_results) > 1:
            print_comparison(all_results)
            save_results(all_results)
    else:
        if args.include_base:
            res_base = evaluate_model(args.model, test_data, args.limit, is_base=True)
            if res_base:
                print_single_results(res_base)
                
        res_ft = evaluate_model(args.model, test_data, args.limit, is_base=False)
        if res_ft:
            print_single_results(res_ft)
            
        # Collect valid results for comparison/saving
        valid_results = [r for r in [res_base if args.include_base else None, res_ft] if r is not None]
        if len(valid_results) > 1:
            print_comparison(valid_results)
        if valid_results:
            save_results(valid_results)


if __name__ == "__main__":
    main()
