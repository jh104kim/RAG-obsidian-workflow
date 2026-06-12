# 프로젝트: RAG + Obsidian 하이브리드 (비정형 데이터 확장)

Obsidian vault 기반 로컬 한국어 RAG 시스템을 구축하고, 비정형 데이터(엑셀/PDF/PPT/이미지) → Wiki화 → 리트리벌 향상 → GraphRAG → Wiki Graph 활용으로 단계 확장하는 프로젝트.

## 세션 시작 시 반드시 할 일

1. `TODO-비정형데이터-확장-로드맵.md`를 읽고 현재 Phase와 미완료 체크박스를 파악한다. **이 파일이 진행 상태의 단일 출처다.**
2. 사용자가 "이어서 해줘"라고 하면 진행 로그의 마지막 줄 "다음 할 일"부터 시작한다.

## 작업 규칙

- 작업을 시작/완료할 때마다 로드맵의 체크박스(`- [ ]` → `- [x]`)를 갱신한다.
- 의미 있는 작업 단위가 끝날 때마다 로드맵 하단 [진행 로그]에 한 줄 append한다 (형식: `- 날짜 | Phase | 한 일 | 다음 할 일`). 세션이 중간에 끊겨도 복구 가능해야 한다.
- 실험 결과(평가 점수, A/B 비교)는 진행 로그에 수치로 남긴다.

## /research-report 산출물 규칙 (중요)

- 커맨드 기본 동작은 `RAG-Obsidian-구축-가이드.md` 덮어쓰기다. **Phase 확장 주제로 실행할 때는 기존 파일을 덮어쓰지 말고** 로드맵의 [산출물 파일명 규칙] 표에 따라 `가이드-P{N}-*.md`로 저장한다.
- MOC 노트는 새로 만들지 말고 `MOC-RAG-Obsidian.md`에 새 가이드 링크를 추가한다.

## 파일 맵

| 파일 | 역할 |
|---|---|
| `TODO-비정형데이터-확장-로드맵.md` | Phase별 TODO + 진행 로그 (SSOT) |
| `비정형데이터-DB화-기술선택.md` | 기술 선택 근거 노트 (Text-to-SQL/RAG/GraphRAG 분기 기준, 평가 지표, 향상 기법) |
| `RAG-Obsidian-구축-가이드.md` | 기본 RAG 구축 매뉴얼 (Stage 0~5) |
| `MOC-RAG-Obsidian.md` | Obsidian 허브 노트 |
| `SETUP.md` | 새 PC 셋업 가이드 |
| `.claude/agents/*.md` | researcher/analyst/writer/critic 에이전트 |
| `C:\jh104\obsidian-rag\` | RAG 시스템 코드 작업 폴더 |

## 환경 메모

- **RAG 운용 환경**: 이 리서치 폴더가 아닌 별도 PC의 다른 Obsidian vault에서 사용 예정. vault 경로를 `C:\jh104\MyVault`로 가정하지 말 것 — `VAULT_PATH`는 사용자에게 확인 후 설정.
- 실행 코드 패키지: `obsidian-rag-setup\` (가이드에서 추출, 구문 검증 완료). 구축 작업 시 이 패키지를 출발점으로 사용.
- 기본 모델: sonnet (`.claude/settings.local.json`)
- 한국어 우선. 임베딩 기본값 `nlpai-lab/KURE-v1`, 생성 LLM 기본값 Ollama `qwen2.5:7b`
- 답변은 간결하게, 표·체크리스트 위주. 코딩 용어는 한 줄 부가 설명.
