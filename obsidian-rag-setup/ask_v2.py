# ask_v2.py — Stage 2: 벡터 + BM25 하이브리드(RRF) + 리랭킹 (가이드 §6)
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
BASE_DIR = Path(__file__).resolve().parent

chunks = json.loads((BASE_DIR / "chunks.json").read_text(encoding="utf-8"))
id2chunk = {c["id"]: c for c in chunks}
ids = [c["id"] for c in chunks]

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

def retrieve(question: str) -> list[str]:
    # 1) 벡터 검색
    q_emb = embedder.encode([question], normalize_embeddings=True)
    vec_ids = col.query(query_embeddings=q_emb.tolist(),
                        n_results=min(TOP_K_EACH, len(chunks)))["ids"][0]
    # 2) BM25 검색
    idx, _ = bm25.retrieve([tokenize(question)], k=min(TOP_K_EACH, len(chunks)))
    bm_ids = [ids[i] for i in idx[0]]
    # 3) RRF 융합
    fused = rrf([vec_ids, bm_ids])[:TOP_K_EACH]
    # 4) 리랭킹 — 모델(bge-reranker-v2-m3)은 최대 8192 토큰을 지원하지만,
    #    compute_score의 max_length "기본값"이 작아 긴 청크가 잘릴 수 있으므로 명시한다
    pairs = [[question, id2chunk[cid]["text"]] for cid in fused]
    scores = reranker.compute_score(pairs, normalize=True, max_length=2048)
    if not isinstance(scores, list):
        scores = [scores]
    ranked = sorted(zip(fused, scores), key=lambda x: x[1], reverse=True)
    return [cid for cid, _ in ranked[:TOP_K_FINAL]]

def answer(question: str) -> str:
    top = retrieve(question)
    context = "\n\n---\n\n".join(id2chunk[cid]["text"] for cid in top)
    prompt = (
        "당신은 내 Obsidian 노트를 검색해 답하는 비서다.\n"
        "아래 노트 발췌만 근거로 한국어로 답하라. 발췌에 근거가 없으면 모른다고 답하라.\n"
        "답변 끝에 '참고:' 뒤에 참고한 노트 이름을 나열하라.\n\n"
        f"[노트 발췌]\n{context}\n\n[질문]\n{question}"
    )
    # ollama SDK 0.4.x: ChatResponse 객체 반환 — 속성 접근 스타일 사용
    resp = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    return resp.message.content

if __name__ == "__main__":
    while True:
        q = input("\n질문 (종료: 빈 입력): ").strip()
        if not q:
            break
        print(answer(q))
