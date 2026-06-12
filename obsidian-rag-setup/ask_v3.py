# ask_v3.py — 최종: 하이브리드 검색 + 리랭킹 + 위키링크 1-hop 확장 (가이드 §7)
import json
from pathlib import Path

import bm25s
import chromadb
import ollama
from chromadb.config import Settings
from FlagEmbedding import FlagReranker
from kiwipiepy import Kiwi
from sentence_transformers import SentenceTransformer

# ===== 사용자 수정 지점 =====
EMBED_MODEL = "nlpai-lab/KURE-v1"   # ingest.py와 동일해야 함
LLM_MODEL = "qwen2.5:7b"
# ===========================
TOP_K_EACH = 20    # 벡터/BM25 각각 가져올 후보 수
TOP_K_FINAL = 5    # 리랭킹 후 최종 사용할 청크 수
MAX_HOP_EXTRA = 4  # 1-hop 확장으로 추가할 청크 수 상한
BASE_DIR = Path(__file__).resolve().parent

chunks = json.loads((BASE_DIR / "chunks.json").read_text(encoding="utf-8"))
graph = json.loads((BASE_DIR / "graph.json").read_text(encoding="utf-8"))
id2chunk = {c["id"]: c for c in chunks}
ids = [c["id"] for c in chunks]
note2chunks: dict[str, list[str]] = {}
for c in chunks:
    note2chunks.setdefault(c["note"], []).append(c["id"])

kiwi = Kiwi()
def tokenize(text: str) -> list[str]:
    return [t.form.lower() for t in kiwi.tokenize(text)]

print("BM25 인덱스 구축 중...")
bm25 = bm25s.BM25()
bm25.index([tokenize(c["text"]) for c in chunks])

embedder = SentenceTransformer(EMBED_MODEL)
col = chromadb.PersistentClient(
    path=str(BASE_DIR / "chroma_db"),
    settings=Settings(anonymized_telemetry=False),
).get_collection("vault")
# Windows/CPU 기본값은 fp32. CUDA GPU가 있으면 use_fp16=True로 바꿔 속도를 높일 수 있다.
reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=False)

def rrf(rank_lists: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranks in rank_lists:
        for r, cid in enumerate(ranks):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + r + 1)
    return sorted(scores, key=scores.get, reverse=True)

def retrieve(question: str) -> tuple[list[str], list[str]]:
    """(리랭킹 통과 핵심 청크, 1-hop 보조 청크) 반환"""
    q_emb = embedder.encode([question], normalize_embeddings=True)
    vec_ids = col.query(query_embeddings=q_emb.tolist(),
                        n_results=min(TOP_K_EACH, len(chunks)))["ids"][0]
    idx, _ = bm25.retrieve([tokenize(question)], k=min(TOP_K_EACH, len(chunks)))
    bm_ids = [ids[i] for i in idx[0]]
    fused = rrf([vec_ids, bm_ids])[:TOP_K_EACH]

    # 리랭킹 — 모델은 8192 토큰까지 지원. compute_score의 max_length 기본값이 작아 명시 필요
    pairs = [[question, id2chunk[cid]["text"]] for cid in fused]
    scores = reranker.compute_score(pairs, normalize=True, max_length=2048)
    if not isinstance(scores, list):
        scores = [scores]
    ranked = sorted(zip(fused, scores), key=lambda x: x[1], reverse=True)
    top = [cid for cid, _ in ranked[:TOP_K_FINAL]]

    # 위키링크/백링크 1-hop 확장 — 비용 0의 GraphRAG 지역 질의 근사
    seen, extra = set(top), []
    for note in {id2chunk[cid]["note"] for cid in top}:
        for nb in graph["links"].get(note, []) + graph["backlinks"].get(note, []):
            for cid in note2chunks.get(nb, [])[:1]:   # 이웃 노트는 첫 청크만
                if cid not in seen:
                    extra.append(cid)
                    seen.add(cid)
            if len(extra) >= MAX_HOP_EXTRA:
                break
        if len(extra) >= MAX_HOP_EXTRA:
            break
    return top, extra

def generate(prompt: str) -> str:
    """생성 단계. API 구성안으로 바꾸려면 이 함수만 교체하면 된다 (§9 참조)."""
    # ollama SDK 0.4.x: chat()은 ChatResponse 객체 반환 — resp.message.content 로 접근
    resp = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    return resp.message.content

def answer(question: str) -> tuple[str, list[str]]:
    top, extra = retrieve(question)
    context = "\n\n---\n\n".join(id2chunk[cid]["text"] for cid in top)
    hop = "\n\n---\n\n".join(id2chunk[cid]["text"] for cid in extra)
    prompt = (
        "당신은 내 Obsidian 노트를 검색해 답하는 비서다.\n"
        "아래 노트 발췌만 근거로 한국어로 답하라. 발췌에 근거가 없으면 모른다고 답하라.\n"
        "답변 끝에 '참고:' 뒤에 참고한 노트 이름을 나열하라.\n\n"
        f"[핵심 발췌]\n{context}\n\n"
        + (f"[연결된 노트 발췌(보조)]\n{hop}\n\n" if hop else "")
        + f"[질문]\n{question}"
    )
    return generate(prompt), top + extra

if __name__ == "__main__":
    while True:
        q = input("\n질문 (종료: 빈 입력): ").strip()
        if not q:
            break
        text, used = answer(q)
        print(text)
        print("\n[사용된 청크]", ", ".join(id2chunk[cid]["note"] for cid in used))
