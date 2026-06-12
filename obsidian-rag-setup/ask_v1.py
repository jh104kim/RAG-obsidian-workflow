# ask_v1.py — Stage 1: 벡터 검색만으로 질의응답 (가이드 §5.2)
from pathlib import Path

import chromadb
import ollama
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# ===== 사용자 수정 지점 =====
EMBED_MODEL = "nlpai-lab/KURE-v1"   # ingest.py와 반드시 동일해야 함
LLM_MODEL = "qwen2.5:7b"
# ===========================
TOP_K = 5
BASE_DIR = Path(__file__).resolve().parent

embedder = SentenceTransformer(EMBED_MODEL)
col = chromadb.PersistentClient(
    path=str(BASE_DIR / "chroma_db"),
    settings=Settings(anonymized_telemetry=False),
).get_collection("vault")

def answer(question: str) -> str:
    q_emb = embedder.encode([question], normalize_embeddings=True)
    res = col.query(query_embeddings=q_emb.tolist(), n_results=TOP_K)
    context = "\n\n---\n\n".join(res["documents"][0])
    prompt = (
        "당신은 내 Obsidian 노트를 검색해 답하는 비서다.\n"
        "아래 노트 발췌만 근거로 한국어로 답하라. 발췌에 근거가 없으면 모른다고 답하라.\n"
        "답변 끝에 '참고:' 뒤에 참고한 노트 이름을 나열하라.\n\n"
        f"[노트 발췌]\n{context}\n\n[질문]\n{question}"
    )
    # ollama Python SDK 0.4.x: chat()은 ChatResponse 객체를 반환한다
    # 0.4.x는 ChatResponse 객체 반환 — 딕셔너리 접근도 동작하나 공식 문서 스타일인 속성 접근(.message.content)을 쓴다
    resp = ollama.chat(model=LLM_MODEL, messages=[{"role": "user", "content": prompt}])
    return resp.message.content

if __name__ == "__main__":
    while True:
        q = input("\n질문 (종료: 빈 입력): ").strip()
        if not q:
            break
        print(answer(q))
