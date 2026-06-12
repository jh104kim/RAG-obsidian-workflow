# evaluate.py — goldenset.json 일괄 측정: 리트리벌 지표(Hit@k / MRR / nDCG@k) + 선택적 RAGAS 4지표
#
# 리트리벌 파이프라인은 ask_v3.py의 retrieve()를 import해 그대로 재사용한다
# (하이브리드 검색(벡터+BM25) + RRF + bge-reranker 리랭킹 + 위키링크 1-hop 확장).
# 따라서 ingest.py 산출물(chroma 컬렉션 "vault", chunks.json의 note/text 키, graph.json)과
# 자동으로 정합 — 별도 복제 코드 없음.
#
# 사용법:
#   python evaluate.py            # 리트리벌 지표만 (LLM 불필요, 기본)
#   python evaluate.py --hop      # 위키링크 1-hop 확장 청크까지 적중 판정에 포함 (확장 효과 A/B 비교용)
#   python evaluate.py --ragas    # ask_v3.answer()로 답변 생성 후 RAGAS 4지표 추가 (Ollama 실행 필요)
#
# 결과는 eval_results/YYYY-MM-DD_HHMM.json 으로 저장된다 (A/B 비교 이력용).
import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TYPE_ORDER = ["fact", "summary", "keyword", "multihop"]


def retrieval_metrics(ranked_notes: list[str], expected: list[str], cutoff: int) -> dict:
    """ranked_notes: 검색 순서대로의 노트명(중복 제거 후). expected: 정답 근거 노트명 리스트.
    이진 관련도(노트명 일치=1) 기준 Hit@cutoff / MRR / nDCG@cutoff."""
    exp = set(expected)
    ranked = ranked_notes[:cutoff]
    hit = 1.0 if any(n in exp for n in ranked) else 0.0
    mrr = 0.0
    for i, n in enumerate(ranked):
        if n in exp:
            mrr = 1.0 / (i + 1)
            break
    dcg = sum(1.0 / math.log2(i + 2) for i, n in enumerate(ranked) if n in exp)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(exp), cutoff)))
    return {"hit": hit, "mrr": mrr, "ndcg": (dcg / idcg) if idcg else 0.0}


def dedup_notes(chunk_ids: list[str], id2chunk: dict) -> list[str]:
    """청크 id 리스트 → 순서를 유지한 노트명 리스트 (같은 노트의 청크 여러 개는 1번만)."""
    notes = []
    for cid in chunk_ids:
        n = id2chunk[cid]["note"]
        if n not in notes:
            notes.append(n)
    return notes


def fmt_row(label: str, n: int, hit: float, mrr: float, ndcg: float) -> str:
    return f"{label:<10} {n:>4}   {hit:>6.3f}  {mrr:>6.3f}  {ndcg:>6.3f}"


def main():
    ap = argparse.ArgumentParser(description="goldenset.json 기반 RAG 평가")
    ap.add_argument("--hop", action="store_true",
                    help="위키링크 1-hop 확장 청크까지 적중 판정에 포함 (기본: 리랭킹 통과 핵심 청크만)")
    ap.add_argument("--ragas", action="store_true",
                    help="답변 생성 후 RAGAS 4지표(faithfulness/answer_relevancy/context_precision/context_recall) 측정")
    args = ap.parse_args()

    # ---- 골든셋 로드 및 측정 대상 선별 ----
    gs_path = BASE_DIR / "goldenset.json"
    gs = json.loads(gs_path.read_text(encoding="utf-8"))
    k = int(gs.get("k", 5))
    questions = gs.get("questions", [])

    examples = [q for q in questions if q.get("id", "").startswith("EXAMPLE-")]
    empties = [q for q in questions if not q.get("id", "").startswith("EXAMPLE-")
               and not q.get("question", "").strip()]
    targets = [q for q in questions if not q.get("id", "").startswith("EXAMPLE-")
               and q.get("question", "").strip()]
    no_expected = [q["id"] for q in targets if not q.get("expected_notes")]

    print(f"골든셋 {len(questions)}문항 | 측정 대상 {len(targets)}문항 "
          f"(건너뜀: EXAMPLE {len(examples)}건, 질문 미작성 {len(empties)}건)")
    if no_expected:
        print(f"[경고] expected_notes가 비어 리트리벌 판정 불가 → 리트리벌 집계에서 제외: {', '.join(no_expected)}")
    if not targets:
        print("측정할 문항이 없습니다. goldenset.json의 question을 채운 뒤 다시 실행하세요.")
        sys.exit(0)

    # ---- ask_v3 로드 (BM25 구축·임베더·리랭커 로딩에 수 분 걸릴 수 있음) ----
    print("ask_v3 파이프라인 로드 중 (임베더/리랭커/BM25)...")
    import ask_v3  # 재사용: retrieve(), answer(), id2chunk — ingest.py 산출물과 정합 보장

    # 골든셋 k를 retrieve()의 최종 청크 수에 반영 (ask_v3.retrieve는 모듈 전역 TOP_K_FINAL을 참조)
    ask_v3.TOP_K_FINAL = k
    ask_v3.TOP_K_EACH = max(ask_v3.TOP_K_EACH, k)
    cutoff = k + ask_v3.MAX_HOP_EXTRA if args.hop else k  # hop 포함 시 확장 청크도 판정 범위에 넣음

    # ---- 리트리벌 측정 ----
    per_q = []
    for q in targets:
        top, extra = ask_v3.retrieve(q["question"])
        used = top + extra if args.hop else top
        ranked_notes = dedup_notes(used, ask_v3.id2chunk)
        row = {"id": q["id"], "type": q.get("type", "?"), "question": q["question"],
               "expected_notes": q.get("expected_notes", []), "retrieved_notes": ranked_notes,
               "top_chunk_ids": top, "hop_chunk_ids": extra}
        if q.get("expected_notes"):
            row.update(retrieval_metrics(ranked_notes, q["expected_notes"], cutoff))
        per_q.append(row)

    scored = [r for r in per_q if "hit" in r]

    def agg(rows):
        n = len(rows)
        return (n,
                sum(r["hit"] for r in rows) / n,
                sum(r["mrr"] for r in rows) / n,
                sum(r["ndcg"] for r in rows) / n) if n else (0, 0.0, 0.0, 0.0)

    mode = f"핵심 {k}청크 + 1-hop 확장 (cutoff={cutoff})" if args.hop else f"핵심 {k}청크 (이웃 확장 제외)"
    print(f"\n=== 리트리벌 지표 — {mode} ===")
    header = f"{'유형':<10} {'문항':>4}   Hit@{cutoff:<3} MRR     nDCG@{cutoff}"
    print(header)
    print("-" * len(header))
    type_summary = {}
    seen_types = [t for t in TYPE_ORDER if any(r["type"] == t for r in scored)]
    seen_types += sorted({r["type"] for r in scored} - set(TYPE_ORDER))
    for t in seen_types:
        n, h, m, nd = agg([r for r in scored if r["type"] == t])
        type_summary[t] = {"n": n, "hit": h, "mrr": m, "ndcg": nd}
        print(fmt_row(t, n, h, m, nd))
    n, h, m, nd = agg(scored)
    overall = {"n": n, "hit": h, "mrr": m, "ndcg": nd}
    print("-" * len(header))
    print(fmt_row("전체", n, h, m, nd))

    failed = [r["id"] for r in scored if r["hit"] == 0.0]
    print(f"\n실패 질문 (Hit=0, P3 진입 조건 판단용): {len(failed)}건"
          + (f" — {', '.join(failed)}" if failed else ""))

    # ---- RAGAS (선택) — eval_rag.py와 동일한 방식 (ragas==0.2.15 EvaluationDataset API) ----
    ragas_summary = None
    if args.ragas:
        ragas_targets = [q for q in targets if q.get("ground_truth", "").strip()]
        skipped_gt = len(targets) - len(ragas_targets)
        print(f"\n=== RAGAS 측정 — {len(ragas_targets)}문항 "
              f"(ground_truth 미작성으로 건너뜀 {skipped_gt}건) ===")
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_ollama import ChatOllama
        from ragas import EvaluationDataset, evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (answer_relevancy, context_precision,
                                   context_recall, faithfulness)

        samples = []
        for q in ragas_targets:
            ans, used = ask_v3.answer(q["question"])  # (답변, 사용 청크 id) — 검색+생성 1회
            samples.append({
                "user_input": q["question"],
                "response": ans,
                "retrieved_contexts": [ask_v3.id2chunk[cid]["text"] for cid in used],
                "reference": q["ground_truth"],
            })
        result = evaluate(
            EvaluationDataset.from_list(samples),
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=LangchainLLMWrapper(ChatOllama(model=ask_v3.LLM_MODEL, temperature=0)),
            embeddings=LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=ask_v3.EMBED_MODEL)),
        )
        print(result)
        try:
            df = result.to_pandas()
            ragas_summary = {c: float(df[c].mean()) for c in
                             ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
                             if c in df.columns}
        except Exception:
            ragas_summary = {"repr": str(result)}

    # ---- 결과 저장 (A/B 비교 이력) ----
    out_dir = BASE_DIR / "eval_results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / (datetime.now().strftime("%Y-%m-%d_%H%M") + ".json")
    out = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "goldenset_version": gs.get("version", ""),
        "config": {"k": k, "cutoff": cutoff, "hop": args.hop, "ragas": args.ragas,
                   "embed_model": ask_v3.EMBED_MODEL},
        "counts": {"total": len(questions), "measured": len(targets),
                   "skipped_example": len(examples), "skipped_empty_question": len(empties),
                   "no_expected_notes": no_expected},
        "retrieval": {"by_type": type_summary, "overall": overall, "failed_ids": failed},
        "ragas": ragas_summary,
        "per_question": per_q,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
