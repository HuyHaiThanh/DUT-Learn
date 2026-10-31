"""EX01 — Benchmark sơ bộ mô hình sinh (Ollama) và embedding trên máy thật.

Chạy: uv run --with requests --with sentence-transformers python evals/ex01/benchmark.py
Kết quả thô ghi vào evals/ex01/runs/<timestamp>/.
Câu hỏi và đoạn ngữ cảnh do nhóm dự án tự soạn (kiến thức CNTT phổ thông), chỉ dùng
để kiểm tra khả năng chạy, độ trễ và chất lượng tiếng Việt ban đầu; không phải tập đánh giá chính.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

OLLAMA = os.environ.get("DUT_LLM_BASE_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("DUT_LLM_MODEL", "qwen2.5:7b-instruct")
EMBED_MODEL = os.environ.get("DUT_EMBED_MODEL", "intfloat/multilingual-e5-small")
HERE = Path(__file__).parent

SYSTEM = (
    "Bạn là trợ giảng cho sinh viên công nghệ thông tin. Chỉ trả lời dựa trên các đoạn tài liệu "
    "được cung cấp, ghi số nguồn dạng [1], [2] sau mỗi ý. Nếu tài liệu không đủ để trả lời, nói rõ "
    "'Tài liệu hiện có không đủ căn cứ để trả lời' và không tự bịa. Trả lời bằng tiếng Việt, ngắn gọn."
)


def gpu_mem_used_mib() -> int | None:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], text=True
        )
        return int(out.strip().splitlines()[0])
    except Exception:
        return None


def ask(question: str, passages: list[str]) -> dict:
    ctx = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(passages))
    user = f"<tai_lieu>\n{ctx}\n</tai_lieu>\n\n<cau_hoi>{question}</cau_hoi>"
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        "stream": True,
        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096},
    }
    t0 = time.perf_counter()
    ttft = None
    parts: list[str] = []
    final: dict = {}
    with requests.post(f"{OLLAMA}/api/chat", json=body, stream=True, timeout=300) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            msg = json.loads(line)
            piece = msg.get("message", {}).get("content", "")
            if piece and ttft is None:
                ttft = time.perf_counter() - t0
            parts.append(piece)
            if msg.get("done"):
                final = msg
    total = time.perf_counter() - t0
    eval_count = final.get("eval_count", 0)
    eval_ns = final.get("eval_duration", 1)
    return {
        "answer": "".join(parts),
        "ttft_s": round(ttft or total, 3),
        "total_s": round(total, 3),
        "prompt_tokens": final.get("prompt_eval_count"),
        "output_tokens": eval_count,
        "gen_tok_per_s": round(eval_count / (eval_ns / 1e9), 1) if eval_count else None,
        "load_s": round(final.get("load_duration", 0) / 1e9, 3),
    }


def bench_embedding(texts: list[str]) -> dict:
    from sentence_transformers import SentenceTransformer

    t0 = time.perf_counter()
    model = SentenceTransformer(EMBED_MODEL)
    load = time.perf_counter() - t0
    passages = [f"passage: {t}" for t in texts] * 20
    t1 = time.perf_counter()
    vecs = model.encode(passages, batch_size=32, normalize_embeddings=True)
    enc = time.perf_counter() - t1
    q = model.encode(["query: Khóa chính trong cơ sở dữ liệu là gì?"], normalize_embeddings=True)
    sims = (vecs[: len(texts)] @ q[0]).tolist()
    return {
        "model": EMBED_MODEL,
        "device": str(model.device),
        "dim": int(vecs.shape[1]),
        "max_seq_length": model.max_seq_length,
        "load_s": round(load, 2),
        "passages": len(passages),
        "passages_per_s": round(len(passages) / enc, 1),
        "sanity_top_passage_index": int(max(range(len(sims)), key=lambda i: sims[i])),
        "sanity_scores": [round(s, 3) for s in sims],
    }


def main() -> None:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    run_dir = HERE / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    tags = requests.get(f"{OLLAMA}/api/tags", timeout=10).json()
    model_info = next((m for m in tags.get("models", []) if m["name"].startswith(MODEL)), None)
    env = {
        "python": sys.version,
        "platform": platform.platform(),
        "ollama_version": requests.get(f"{OLLAMA}/api/version", timeout=10).json(),
        "model": MODEL,
        "model_info": model_info,
        "gpu_mem_before_mib": gpu_mem_used_mib(),
    }

    results = []
    # Lần đầu đo cả thời gian nạp model (cold), sau đó warm.
    for i, c in enumerate(cases):
        r = ask(c["question"], c["passages"])
        r.update({"id": c["id"], "kind": c["kind"], "question": c["question"], "warm": i > 0})
        r["gpu_mem_mib"] = gpu_mem_used_mib()
        results.append(r)
        print(f"{c['id']}: ttft={r['ttft_s']}s total={r['total_s']}s tok/s={r['gen_tok_per_s']}")

    warm = sorted(x["total_s"] for x in results if x["warm"])
    summary = {
        "n": len(results),
        "cold_first_total_s": results[0]["total_s"],
        "cold_load_s": results[0]["load_s"],
        "warm_p50_total_s": warm[len(warm) // 2] if warm else None,
        "warm_p95_total_s": warm[min(len(warm) - 1, int(len(warm) * 0.95))] if warm else None,
        "warm_mean_tok_per_s": round(
            sum(x["gen_tok_per_s"] or 0 for x in results if x["warm"]) / max(1, len(warm)), 1
        ),
        "gpu_mem_peak_mib": max((x["gpu_mem_mib"] or 0) for x in results),
    }
    # Hai request đồng thời (Ollama mặc định có thể xếp hàng hoặc chạy song song).
    from concurrent.futures import ThreadPoolExecutor

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        conc = list(ex.map(lambda c: ask(c["question"], c["passages"]), cases[:2]))
    summary["concurrent_2"] = {
        "wall_s": round(time.perf_counter() - t0, 3),
        "each_total_s": [x["total_s"] for x in conc],
        "each_tok_per_s": [x["gen_tok_per_s"] for x in conc],
    }
    emb = bench_embedding([p for c in cases for p in c["passages"]][:20])

    (run_dir / "env.json").write_text(json.dumps(env, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "generation.jsonl").write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in results), encoding="utf-8"
    )
    (run_dir / "summary.json").write_text(
        json.dumps({"generation": summary, "embedding": emb}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"generation": summary, "embedding": emb}, ensure_ascii=False, indent=2))
    print(f"Saved to {run_dir}")


if __name__ == "__main__":
    main()
