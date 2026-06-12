---
title: "확장 로드맵 — 비정형 데이터 → Obsidian Wiki + RAG + Graph"
created: 2026-06-12
updated: 2026-06-12
tags: [TODO, 로드맵, RAG, GraphRAG, Obsidian]
---

# 확장 로드맵 + TODO

> **이 파일이 프로젝트 진행 상태의 단일 출처(SSOT)다.**
> 규칙: 작업 시작/완료 시 체크박스 갱신 + 하단 [진행 로그]에 한 줄 추가. 세션이 끊겨도 이 파일만 읽으면 이어서 진행 가능.

## 전체 그림

```
P1. 비정형 데이터 파싱 → Obsidian Wiki화
        ↓ (노트가 쌓이면)
P2. RAG 구축 + 리트리벌 정확도 향상 (← 현재 가이드의 본 구축 포함)
        ↓ (관계형 질문 필요성 확인되면)
P3. Graph DB 연계 (GraphRAG)
        ↓
P4. Obsidian Wiki Graph 활용 (링크 그래프 = 지식 그래프)
```

배경 지식: [[비정형데이터-DB화-기술선택]] | 기존 가이드: [[RAG-Obsidian-구축-가이드]]

---

## Phase 0 — 기존 잔여 작업

- [x] RAG-Obsidian-구축-가이드.md critic 심사 (라운드 2: REVISION→수정 반영, 라운드 3: **APPROVED**, 2026-06-12)
- [ ] 가이드 Stage 0~5 따라 RAG 시스템 실제 구축 (`C:\jh104\obsidian-rag`)
  - [x] 실행 코드 패키지 추출 완료 → `리서치\obsidian-rag-setup\` (py 6개 구문 검증 통과, setup.ps1·README 포함)
  - [ ] 운용 PC(별도 vault 환경)에서: `obsidian-rag-setup` 복사 → `setup.ps1` → **VAULT_PATH를 그 PC의 실제 vault 경로로** 수정 → `ingest.py` → `ask_v3.py`
- [ ] 골든셋 질문 30개 작성 + RAGAS 베이스라인 측정
  - [x] 틀 완성: `goldenset.json`(30문항, fact/summary/keyword/multihop) + `evaluate.py`(Hit@k·MRR·nDCG, `--hop`·`--ragas` 플래그) (2026-06-12)
  - [ ] 운용 PC에서: 빈 문항을 본인 vault 기반으로 채우고 `python evaluate.py`로 베이스라인 측정 → 결과를 진행 로그에 기록

## Phase 1 — 비정형 데이터 → Obsidian Wiki화

목표: 엑셀·PDF·PPT·이미지를 파싱해 frontmatter + `[[위키링크]]` 달린 Obsidian 노트로 자동 변환.

- [ ] 리서치 실행:
  ```
  /research-report 비정형 데이터(비정형 엑셀, PDF, PPT, 이미지)를 Docling·VLM으로 파싱해 Obsidian 위키 노트(frontmatter+위키링크 자동 생성)로 변환하는 파이프라인 구축
  ```
- [ ] 산출 가이드를 `가이드-P1-비정형파싱-Wiki화.md`로 저장 (기존 가이드 덮어쓰기 금지)
- [ ] 파서 선정 PoC: Docling vs VLM 직접 파싱 — 보유 샘플 파일 5개로 비교
- [ ] 표 데이터 분리 적재 결정: SQLite/DuckDB 스키마 초안
- [ ] `parse_to_wiki.py` 구현: 파일 → 노트(.md) + 표(.db)
- [ ] 변환된 노트를 vault에 넣고 `ingest.py` 재인덱싱

## Phase 2 — RAG 리트리벌 정확도 향상

목표: 골든셋 기준 리트리벌 지표(Hit@5, nDCG)와 RAGAS 점수 개선.

- [ ] 리서치 실행:
  ```
  /research-report Obsidian RAG 리트리벌 정확도 향상 — 쿼리 재작성·분해, 하이브리드 가중치 튜닝, 리랭커 비교, Agentic RAG, RAGAS 골든셋 평가 루프 구축
  ```
- [ ] 산출 가이드를 `가이드-P2-리트리벌-향상.md`로 저장
- [ ] 평가 루프 자동화: `evaluate.py` (골든셋 → Hit@k/MRR/nDCG + RAGAS 일괄 측정)
- [ ] 기법별 A/B 측정 (각 1개씩 켜고 측정, 결과는 진행 로그에 기록):
  - [ ] 쿼리 재작성 (query rewriting)
  - [ ] 하이브리드 가중치(BM25:벡터) 튜닝
  - [ ] 리랭커 교체 비교 (bge-reranker-v2-m3 vs 대안)
  - [ ] 청킹 전략 변경 (크기/오버랩/헤더 기준)
- [ ] 베이스라인 대비 개선폭 정리 → [[비정형데이터-DB화-기술선택]]에 결과 추가

## Phase 3 — Graph DB 연계 (GraphRAG)

진입 조건: 골든셋에서 관계형·전체 조망형 질문의 실패 사례가 확인될 때.

- [ ] 실패 질문 유형 수집 (P2 평가에서 RAG가 틀린 멀티홉 질문 목록화)
- [ ] 리서치 실행:
  ```
  /research-report 로컬 RAG에 GraphRAG 연계 — 노트에서 엔티티·관계 추출, 경량 그래프 저장소(NetworkX/Kuzu vs Neo4j) 비교, 커뮤니티 요약, 라우터로 RAG/Graph 분기
  ```
- [ ] 산출 가이드를 `가이드-P3-GraphRAG-연계.md`로 저장
- [ ] 그래프 저장소 선정 (로컬 우선: NetworkX/Kuzu → 필요 시 Neo4j)
- [ ] `build_graph.py` 구현 + 라우터(질문 분류 → SQL/RAG/Graph) 추가
- [ ] 멀티홉 질문 골든셋으로 RAG vs GraphRAG 정확도 비교

## Phase 4 — Obsidian Wiki Graph 활용

핵심 아이디어: **Obsidian의 `[[링크]]` 그래프 자체가 공짜 지식 그래프다** (LLM 추출 비용 0).
노트=노드, 위키링크=엣지로 변환해 P3 그래프의 시드/보강으로 사용.

- [ ] 리서치 실행:
  ```
  /research-report Obsidian vault의 위키링크·백링크·태그 그래프를 추출해 GraphRAG 지식 그래프로 변환·활용 — 그래프 기반 리트리벌(이웃 노트 확장), graph view 시각화 연계
  ```
- [ ] 산출 가이드를 `가이드-P4-WikiGraph-활용.md`로 저장
- [ ] vault 링크 그래프 추출 스크립트 (`extract_wikigraph.py`: md 파싱 → 엣지 리스트)
- [ ] 검색 결과에 "링크된 이웃 노트 확장" 추가 → 정확도 변화 측정
- [ ] (선택) P3 LLM 추출 그래프와 위키링크 그래프 병합 실험

---

## 산출물 파일명 규칙

| Phase | 가이드 파일 | 코드 위치 |
|---|---|---|
| P1 | `가이드-P1-비정형파싱-Wiki화.md` | `C:\jh104\obsidian-rag\` |
| P2 | `가이드-P2-리트리벌-향상.md` | 〃 |
| P3 | `가이드-P3-GraphRAG-연계.md` | 〃 |
| P4 | `가이드-P4-WikiGraph-활용.md` | 〃 |

> `/research-report` 기본 동작은 `RAG-Obsidian-구축-가이드.md` 덮어쓰기이므로, **실행 후 반드시 위 이름으로 저장하도록 지시할 것** (CLAUDE.md에 규칙 반영됨).

## 진행 로그 (append-only)

> 형식: `- YYYY-MM-DD | Phase | 한 일 | 다음 할 일`

- 2026-06-12 | 준비 | 로드맵·기술선택 노트·CLAUDE.md 생성 | P0: critic 라운드 2 심사부터
- 2026-06-12 | 준비 | critic 라운드 2 지적 9건 가이드·MOC 반영 (ragas 0.2.15 통일·pip dry-run 검증, Python 3.11 핀, graphrag 1.2.0 CLI 교정, frontmatter→Chroma metadata 필터) | P0: critic 라운드 3 재심사 또는 §3 사전 준비 실행
- 2026-06-12 | P0 | critic 라운드 3 **APPROVED** (치명 0). 잔여 지적 3건 추가 반영: ollama 0.4.x 허위 오류 주장 3곳 교정·트러블슈팅 행 삭제, parse_frontmatter 블록 리스트 tags 지원(기능 테스트 통과), graphrag CLI 도입 시점 0.9.0으로 교정 | P0: 가이드 따라 RAG 실제 구축 (본인 PC에서 Claude Code로 "이어서 해줘")
- 2026-06-12 | P0 | 실행 코드 패키지 추출 (`obsidian-rag-setup\`: requirements·setup.ps1·ingest·ask_v1~v3·eval_rag·README, §10.1은 USE_CONTEXTUAL_RETRIEVAL 플래그로 게이트) | P0: PC에서 setup.ps1 실행 → ingest → ask_v3 동작 확인 → 골든셋 작성
- 2026-06-12 | P0 | 운용 환경 확정: 별도 PC의 다른 Obsidian vault에서 사용 — SETUP·CLAUDE.md·README에 VAULT_PATH 주의 반영, git 푸시 준비 | P0: 운용 PC에서 git clone/pull 후 setup.ps1 실행
- 2026-06-12 | P0 | GitHub 푸시 완료 (jh104kim/RAG-obsidian-workflow) | P0: 운용 PC 구축 / P0-③ 골든셋 틀 / P1 리서치 중 선택
- 2026-06-12 | P0 | 골든셋 틀 완성 — goldenset.json(30문항 틀+유형별 예시) + evaluate.py(ask_v3 import 재사용, Hit@k/MRR/nDCG·--hop·--ragas, eval_results 이력 저장), README 갱신 | P0: 운용 PC에서 구축 + 골든셋 채우기 + 베이스라인 측정. 이후 P1 리서치
