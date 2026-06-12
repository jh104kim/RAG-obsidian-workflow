---
title: "MOC - RAG + Obsidian 하이브리드 시스템"
tags: [MOC, RAG, Obsidian]
aliases: [RAG MOC, 옵시디언 RAG 지도]
type: MOC
created: 2026-06-11
topic: "RAG + Obsidian 위키 하이브리드"
---

# MOC — RAG + Obsidian 하이브리드 시스템

> 이 노트는 RAG + Obsidian 구축 프로젝트의 허브다.
> 운영 원칙: 항목이 25개를 넘는 묶음은 Sub-MOC로 분리한다.

## 시작점

- [[RAG-Obsidian-구축-가이드]] — 따라 하면 구축되는 메인 매뉴얼 (Stage 0~5 + 부록)
- [[TODO-비정형데이터-확장-로드맵]] — Phase 0~4 확장 계획 + 진행 로그 (진행 상태 SSOT)
- [[비정형데이터-DB화-기술선택]] — Text-to-SQL / RAG / GraphRAG 분기 기준, 평가 지표, 향상 기법

## 기초 개념

- [[RAG]] — 검색으로 찾은 근거를 LLM에 주입해 답하게 하는 패턴
- [[임베딩]] — 텍스트를 의미 벡터로 변환, 유사도 검색의 기반
- [[청킹]] — 노트를 검색 단위로 쪼개기. 헤더 기반 + "짧은 노트=1청크"가 결론
- [[벡터DB]] — 임베딩을 저장·검색하는 DB (Chroma, Qdrant, FAISS 등)
- [[BM25]] — 키워드 기반 고전 검색. 고유명사·정확 매칭에 강함
- [[위키링크]] — Obsidian의 `[[링크]]`. 이 프로젝트에서는 공짜 지식 그래프

## 검색 고도화 기법

- [[하이브리드 검색]] — 벡터 + BM25 결합. 실패 모드가 상보적이라 채택 1순위
- [[RRF]] — 점수 정규화 없이 순위만으로 검색 결과를 융합하는 방법
- [[리랭킹]] — 후보를 cross-encoder로 정밀 재정렬. 채택 2순위
- [[GraphRAG]] — LLM으로 지식 그래프를 추출하는 기법. 지역(local) 질의는 위키링크 1-hop으로 근사, 글로벌 요약 질의가 필요해지면 재검토(보류)
- [[Contextual Retrieval]] — 청크에 LLM 맥락 요약 부착. context_recall < 0.7일 때만 조건부 도입
- [[HyDE]] — 질문을 가상 답변으로 바꿔 검색. answer_relevancy 낮을 때만 조건부 도입

## 구성 요소 (도구)

- [[Chroma]] — 채택한 벡터DB. pip 한 줄, 개인 vault 규모에 충분
- [[Qdrant]] — 메타데이터 필터가 본격화되면 이전할 벡터DB 후보
- [[KURE-v1]] — 채택한 한국어 특화 임베딩 모델 (nlpai-lab, MIT)
- [[bge-m3]] — 다국어 임베딩 폴백. 한영 혼용·저사양 환경의 대안
- [[bge-reranker-v2-m3]] — 채택한 로컬 무료 리랭커 (max_length 명시 필요)
- [[bm25s]] — 채택한 BM25 파이썬 구현체
- [[Kiwi]] — 채택한 한국어 형태소 분석기(kiwipiepy). Windows에서 pip 한 줄로 동작
- [[Okt]] — KoNLPy 기반 대안 형태소 분석기. JDK 필요, Windows 지원
- [[MeCab]] — Linux/macOS용 고성능 형태소 분석기. Windows에서는 별도 설치 필요해 이 가이드에서 미채택
- [[ObsidianReader]] — LlamaIndex의 vault 로더. 위키링크·백링크 추출 내장
- [[Ollama]] — 로컬 LLM 실행기. 생성 단계 담당
- [[Qwen 2.5]] — 채택한 로컬 생성 모델 (RAM 부족 시 3b, 라이선스 조건 확인)

## 평가

- [[RAGAS]] — faithfulness / answer relevancy / context precision·recall. 고급화 도입 여부의 판단 도구
- [[평가셋]] — 내 vault 기반 질문·정답 10~20문항. 파이프라인 변경 전후 비교 기준

## Vault 운영

- [[MOC]] — 자연 발생시키고, 25개 초과 시 Sub-MOC 분리
- [[frontmatter]] — 표준 키: tags, aliases, type, created, topic
- [[Zettelkasten]] — 노트 하나 = 아이디어 하나 + 링크 연결
- [[PARA]] — 얕은 폴더 구조의 기준 틀
- [[Dataview]] — frontmatter 질의 도구 (느려지면 Datacore/Bases 검토)

## 퍼블리싱

- [[obsidian-export]] — 공개 노트만 추출하는 Rust CLI. 비공개 유출 차단 담당
- [[Quartz]] — 위키링크·백링크·그래프 뷰 지원 정적 사이트 생성기 (v4)
- [[GitHub Actions]] — push 시 자동 빌드·배포 워크플로
- [[GitHub Pages]] — 최종 호스팅

## API 확장 (선택)

- [[Claude API]] — 생성 단계만 교체하는 하이브리드 구성의 1안 (`claude-opus-4-8`)
- [[OpenAI API]] — 생성 단계는 Responses API(`gpt-5.5` 또는 저비용 `gpt-5.4-mini`), 전체 API 구성 시 임베딩은 text-embedding-3 계열 (재인덱싱 필요)
