---
title: "프로젝트 셋업 가이드 — 다른 PC에서 바로 시작하기"
created: 2026-06-12
tags: [셋업, 가이드, RAG, Obsidian]
---

# RAG + Obsidian 하이브리드 프로젝트 — 셋업 가이드

> 이 문서 하나로 새 PC에서 프로젝트를 처음부터 재현할 수 있다.

---

## 1. 이 프로젝트가 뭔가

**목표 2가지**:
1. 내 Obsidian vault를 검색해 한국어로 답하는 **로컬 RAG 질의응답 시스템** 구축
2. 같은 vault에서 공개 노트만 골라 **GitHub Pages로 자동 배포**

**파이프라인 구조**:
- Claude Code의 `/research-report` 커맨드를 실행하면 4개 에이전트(Researcher → Analyst → Writer → Critic)가 순서대로 작동해 핸즈온 구축 가이드를 자동 생성한다.
- 생성된 가이드를 따라 RAG 시스템을 직접 구축한다.

---

## 2. 이 폴더의 파일 구조

```
C:\jh104\리서치\
│
├── SETUP.md                        ← 지금 읽는 이 파일
├── CLAUDE.md                       ← Claude Code 프로젝트 메모리 (작업 규칙·진행 이어가기)
├── TODO-비정형데이터-확장-로드맵.md  ← Phase 0~4 TODO + 진행 로그 (진행 상태 SSOT)
├── RAG-Obsidian-구축-가이드.md      ← 핵심: RAG 시스템 구축 매뉴얼 (Stage 0~5, critic APPROVED)
├── MOC-RAG-Obsidian.md             ← Obsidian 허브 노트 (개념 링크 지도)
├── 비정형데이터-DB화-기술선택.md     ← Text-to-SQL/RAG/GraphRAG 분기·평가·향상 기법 노트
│
├── obsidian-rag-setup\             ← 가이드에서 추출한 실행 코드 패키지 (복사해서 바로 실행)
│   ├── README.md / setup.ps1 / requirements.txt
│   ├── ingest.py / ask_v1~v3.py / eval_rag.py / check_vault.py
│   └── publishing\
│
└── .claude/
    ├── commands/
    │   └── research-report.md      ← /research-report 슬래시 커맨드 정의
    └── agents/
        ├── researcher.md           ← 웹 조사 에이전트
        ├── analyst.md              ← 분석·비교표 에이전트
        ├── writer.md               ← 가이드 초안 작성 에이전트
        └── critic.md               ← 심사·검증 에이전트
```

### 파일별 용도

| 파일 | 용도 | 건드릴 일 |
|---|---|---|
| `RAG-Obsidian-구축-가이드.md` | 실제 구축 매뉴얼. 이 파일만 보고 시스템을 만든다 | 없음 (읽기만) |
| `MOC-RAG-Obsidian.md` | Obsidian vault에 넣으면 허브 노트로 동작 | 없음 |
| `.claude/commands/research-report.md` | `/research-report` 실행 시 파이프라인 흐름 정의 | 커스터마이징 원할 때만 |
| `.claude/agents/*.md` | 각 에이전트의 역할·지시 정의 | 커스터마이징 원할 때만 |

---

## 3. 새 PC 셋업 (순서대로)

### 3-1. 필수 소프트웨어 설치

```powershell
# Python 3.11 이상
# https://www.python.org/downloads/ 에서 설치
python --version   # 3.11.x 이상이어야 함

# Git
winget install Git.Git
git --version

# Ollama (로컬 LLM 서버)
winget install Ollama.Ollama

# Node.js 20+ (퍼블리싱 할 때만 필요)
winget install OpenJS.NodeJS.LTS
```

### 3-2. 이 프로젝트 폴더 복사

USB, OneDrive, GitHub 등으로 아래 폴더 전체를 새 PC의 동일 경로에 복사한다:

```
C:\jh104\리서치\
```

> 경로를 바꾸고 싶으면 `RAG-Obsidian-구축-가이드.md` 내 `C:\jh104\obsidian-rag` 경로도 함께 수정한다.

### 3-3. Claude Code 설치

```powershell
# Node.js가 설치된 상태에서
npm install -g @anthropic-ai/claude-code

# 설치 확인
claude --version
```

### 3-4. Claude Code 실행

```powershell
cd C:\jh104\리서치
claude
```

Claude Code가 자동으로 `.claude/` 폴더를 인식하고 에이전트·커맨드를 로드한다.

---

## 4. 파이프라인 재실행 방법 (`/research-report`)

> 가이드를 새로 생성하거나 주제를 바꿔 실행하고 싶을 때 사용한다.
> 기존 `RAG-Obsidian-구축-가이드.md`가 있으면 덮어쓴다.

Claude Code 내에서:

```
/research-report
```

또는 다른 주제로:

```
/research-report LangGraph + Obsidian 워크플로 자동화 구축
```

**파이프라인 소요 시간**: 약 15~30분 (웹 조사 → 분석 → 초안 → 검증 루프)

**자동으로 생성되는 파일**:
- `RAG-Obsidian-구축-가이드.md`
- `MOC-RAG-Obsidian.md`

---

## 5. RAG 시스템 실제 구축 (빠른 시작)

> **더 빠른 방법**: `obsidian-rag-setup\` 폴더를 작업 위치로 복사하고 그 안의 `README.md` 순서대로 실행하면
> 아래 5-1~5-4가 `setup.ps1` 한 번으로 끝난다. 아래는 수동 절차 참고용.
> 자세한 내용은 `RAG-Obsidian-구축-가이드.md` 참조.

### 5-1. 작업 폴더 생성

```powershell
mkdir C:\jh104\obsidian-rag
cd C:\jh104\obsidian-rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# 오류 시: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 5-2. 패키지 설치

`C:\jh104\obsidian-rag\requirements.txt` 생성 후 붙여넣기:

```
llama-index-readers-obsidian==0.5.0
langchain-text-splitters==0.3.8
sentence-transformers==3.4.1
chromadb==0.6.3
bm25s==0.2.10
kiwipiepy==0.20.3
FlagEmbedding==1.3.4
ollama==0.4.7
ragas==0.1.21
datasets==3.2.0
langchain-ollama==0.2.2
langchain-huggingface==0.1.2
```

```powershell
pip install -r requirements.txt
```

### 5-3. Ollama 모델 다운로드

```powershell
ollama pull qwen2.5:7b   # 약 4.7GB, 최초 1회
ollama run qwen2.5:7b "안녕하세요라고만 답해"   # 동작 확인
```

### 5-4. 임베딩 모델 미리 받기 (네트워크 제약 환경)

```powershell
pip install -U "huggingface_hub[cli]"
hf download nlpai-lab/KURE-v1
hf download BAAI/bge-reranker-v2-m3
# 이후 오프라인 환경에서: $env:HF_HUB_OFFLINE = "1"
```

### 5-5. vault 인덱싱

`ingest.py` 상단의 `VAULT_PATH`를 본인 vault 경로로 수정 후:

```powershell
python ingest.py
# 완료: N개 청크 인덱싱 출력되면 성공
```

### 5-6. 질의응답 실행

```powershell
python ask_v3.py
# 질문: 내 프로젝트 A의 목표가 뭐였지?
```

---

## 6. 현재 프로젝트 상태 (2026-06-12 기준)

| 항목 | 상태 |
|---|---|
| 리서치 파이프라인 설정 | 완료 |
| RAG 구축 가이드 생성 | 완료 |
| Critic 최종 APPROVED | **완료** (라운드 3, 치명 0건 — requirements·Python 3.11·graphrag CLI 등 실측 검증) |
| MOC 허브 노트 | 완료 |
| 실행 코드 패키지 추출 | **완료** (`obsidian-rag-setup\`, py 6개 구문 검증 통과) |
| RAG 시스템 실제 구축 | 미착수 — `obsidian-rag-setup\README.md` 순서대로 실행 |
| 확장 로드맵 (P0~P4) | `TODO-비정형데이터-확장-로드맵.md` 참조 (진행 상태 SSOT) |

> **운용 환경 주의**: RAG 시스템은 이 폴더가 아닌 **별도 PC의 다른 Obsidian vault**에서 사용할 예정.
> 코드는 vault 경로에 의존하지 않으며, `ingest.py`·`check_vault.py` 상단 `VAULT_PATH`만 해당 PC의 실제 vault 경로로 수정하면 된다.

---

## 7. 주요 선택 사항 요약

### 임베딩 모델 선택

| 모델 | 조건 | 명령 |
|---|---|---|
| `nlpai-lab/KURE-v1` | **기본값** (한국어 특화) | `EMBED_MODEL = "nlpai-lab/KURE-v1"` |
| `BAAI/bge-m3` | GPU 있거나 한영 혼용 노트 많을 때 | `EMBED_MODEL = "BAAI/bge-m3"` |
| `Qwen/Qwen3-Embedding-8B` | VRAM 8GB+, 최고 성능 원할 때 | `EMBED_MODEL = "Qwen/Qwen3-Embedding-8B"` |

### 생성 LLM 선택

| 구성 | 조건 | 변경 위치 |
|---|---|---|
| Ollama qwen2.5:7b | **기본값** (완전 로컬 무료) | 변경 불필요 |
| Claude API | 답변 품질 개선 원할 때 | `ask_v3.py`의 `generate()` 함수만 교체 |
| OpenAI GPT-4o | 동일 | `ask_v3.py`의 `generate()` 함수만 교체 |

---

## 8. 자주 겪는 문제

| 증상 | 해결 |
|---|---|
| `.venv\Scripts\Activate.ps1` 오류 | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| 모델 다운로드 타임아웃 | `$env:HF_ENDPOINT = "https://hf-mirror.com"` |
| `ollama.chat` 연결 오류 | `ollama serve` 실행 후 재시도 |
| Chroma `get_collection` 실패 | `python ingest.py` 재실행 |
| Windows에서 MeCab 오류 | Kiwi(`kiwipiepy`) 또는 Okt(`konlpy`) 사용. MeCab은 Windows 미지원 |
| claude 명령어 없음 | `npm install -g @anthropic-ai/claude-code` 재설치 |

---

## 9. 참고 파일 경로 요약

| 역할 | 경로 |
|---|---|
| 이 셋업 가이드 | `C:\jh104\리서치\SETUP.md` |
| RAG 구축 매뉴얼 | `C:\jh104\리서치\RAG-Obsidian-구축-가이드.md` |
| Obsidian 허브 노트 | `C:\jh104\리서치\MOC-RAG-Obsidian.md` |
| RAG 시스템 작업 폴더 | `C:\jh104\obsidian-rag\` (직접 생성 필요) |
| Obsidian vault | `C:\jh104\MyVault\` (본인 경로로 수정) |
