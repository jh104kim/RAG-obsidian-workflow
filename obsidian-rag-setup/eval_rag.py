# eval_rag.py — Stage 4: RAGAS 평가 (ragas==0.2.15, EvaluationDataset API 기준) (가이드 §8)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from ask_v3 import answer, id2chunk

# ===== 사용자 수정 지점: 본인 vault 내용으로 10~20문항 작성 (아래는 형식 예시 — 반드시 교체) =====
# TODO: 본인 vault 기반 평가셋으로 수정
EVAL_SET = [
    {"question": "내 노트에서 RAG의 핵심 구성요소는 무엇이라고 정리했나?",
     "ground_truth": "검색(retrieval)과 생성(generation). 벡터 검색으로 관련 문서를 찾아 LLM에 컨텍스트로 제공한다."},
    {"question": "Zettelkasten 노트 작성 원칙으로 무엇을 적어뒀나?",
     "ground_truth": "노트 하나에 아이디어 하나, 내 언어로 다시 쓰기, 다른 노트와 링크로 연결하기."},
]
# ===========================================================================

samples = []
for item in EVAL_SET:
    # answer()가 (답변, 사용된 청크 id 리스트)를 반환하므로 검색은 문항당 1회만 수행된다
    ans, used = answer(item["question"])
    samples.append({
        "user_input": item["question"],
        "response": ans,
        "retrieved_contexts": [id2chunk[cid]["text"] for cid in used],
        "reference": item["ground_truth"],
    })

result = evaluate(
    EvaluationDataset.from_list(samples),
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=LangchainLLMWrapper(ChatOllama(model="qwen2.5:7b", temperature=0)),
    embeddings=LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name="nlpai-lab/KURE-v1")),
)
print(result)
