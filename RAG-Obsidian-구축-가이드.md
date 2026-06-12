---
title: "RAG + Obsidian 위키 하이브리드 시스템 구축 가이드"
tags: [RAG, Obsidian, 구축가이드, 로컬LLM, 퍼블리싱]
created: 2026-06-11
type: guide
---

# RAG + Obsidian 위키 하이브리드 시스템 구축 가이드

> 이 문서는 "읽는 보고서"가 아니라 **따라 하면 구축되는 매뉴얼**이다.
> 모든 명령은 Windows 11 + PowerShell 기준이며, 코드블록은 그대로 복사해 실행할 수 있다.
> 독자 전제: Python을 다룰 줄 아는 Obsidian 사용자. 한국어 노트 중심, 네트워크 제약 환경 가능성 있음.

---

## 1. 개요

목표는 두 가지다.

1. **[[RAG|Retrieval-Augmented Generation]] 파이프라인**: 내 Obsidian vault를 검색해 근거 기반으로 답하는 로컬 질의응답 시스템
2. **위키 퍼블리싱**: 같은 vault에서 공개 노트만 골라 [[GitHub Pages]]로 자동 배포

### 추천 구성 (완전 로컬 무료)

| 단계 | 선택 | 이유 |
|---|---|---|
| 로더 | LlamaIndex `ObsidianReader` — **위키링크 그래프 추출 전용** | 위키링크·백링크 메타데이터 추출을 내장한 공식 로더. 단, 본문은 노트 1개당 1개가 아니라 **헤더 단위로 분할된 여러 Document**로 반환되므로("Documents are split by header within a markdown file" — [docs](https://developers.llamaindex.ai/python/framework-api-reference/readers/obsidian/)) 청킹용 본문은 원본 `.md`를 직접 읽는다 |
| [[청킹]] | **원본 노트 전문 기준** `MarkdownHeaderTextSplitter` + "짧은 노트=1청크" 하이브리드 | 헤더 기반 청킹이 고정·시맨틱 대비 5~10%p 우수 — 가장 가성비 좋은 단일 개선 ([Snowflake](https://www.snowflake.com/en/engineering-blog/impact-retrieval-chunking-finance-rag/)). 짧은 노트는 통째로 1청크 유지 |
| [[임베딩]] | `nlpai-lab/KURE-v1` (폴백: `BAAI/bge-m3`) | 한국어 검색 벤치마크(MTEB-ko-retrieval recall 0.687) 최상위, MIT 라이선스 ([KURE](https://github.com/nlpai-lab/KURE)) |
| [[벡터DB]] | [[Chroma]] | `pip install chromadb` 한 줄. 개인 vault 규모에 충분 |
| 키워드 검색 | [[BM25]] (`bm25s` + `kiwipiepy` 형태소 토크나이저) | [[하이브리드 검색]]은 실패 모드가 상보적이라 거의 항상 이득 ([ref](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026)) |
| 결합 | [[RRF]] (Reciprocal Rank Fusion) | 점수 정규화 없이 순위만으로 융합, 구현 10줄 |
| [[리랭킹]] | `BAAI/bge-reranker-v2-m3` | 로컬 무료 다국어 리랭커, bge-m3 기반 최대 8192 토큰 입력 지원 ([HF](https://huggingface.co/BAAI/bge-reranker-v2-m3)) |
| 그래프 활용 | **위키링크 1-hop 확장** | Obsidian이 이미 가진 `[[링크]]` 그래프를 쓰는 비용 0의 [[GraphRAG]] **지역(local) 질의 근사** (글로벌 요약 질의는 미커버 — 아래 배제 표 참조) |
| 생성 | [[Ollama]] + Qwen 2.5 | Windows 지원. Ollama는 MIT, Qwen2.5-7B는 Apache 2.0 (단, `qwen2.5:3b`는 Qwen Research License — 개인 사용은 가능하나 상업·재배포 전 라이선스 확인 필요). 일반적으로 권장되는 로컬 조합 |
| 평가 | [[RAGAS]] | faithfulness / answer relevancy / context precision·recall — 고급화 여부의 판단 도구 |
| 퍼블리싱 | [[obsidian-export]] → [[Quartz]] v4 → GitHub Actions → GitHub Pages | 비공개 노트 유출 차단 + 위키링크·백링크·그래프 뷰 지원 정적 사이트 |

### 채택하지 않은 것과 이유 (분석 결론)

| 항목 | 판정 | 이유 |
|---|---|---|
| [[GraphRAG]] / LightRAG | 보류 (트레이드오프 수용) | LLM으로 지식 그래프를 새로 추출하는 인덱싱 비용이 크다. **"이 주제와 연결된 노트는?" 같은 지역(local) 질의에 한해** Obsidian [[위키링크]] 그래프 1-hop 확장이 비용 0으로 근사한다. 단, GraphRAG의 커뮤니티 요약이 답하는 **글로벌 질의("내 노트 전체를 관통하는 주제는?")는 1-hop으로 대체되지 않는다** — 이를 포기하는 트레이드오프이며, 글로벌 요약 질의가 실제로 필요해지면 재검토 |
| 시맨틱 청킹 | 불필요 | 비용 대비 효과 의문(NAACL 2025에서 고정 200단어와 대등). 헤더 기반이 더 싸고 효과적 ([ref](https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide)) |
| Self-RAG / CRAG | 보류 | 자기비판 루프의 LLM 호출 비용을 개인 위키 질의응답에서 정당화하기 어려움 |
| [[Contextual Retrieval]], [[HyDE]]/multi-query, [[Qdrant]] 이전 | 조건부 보류 | Stage 4의 RAGAS 측정 결과가 트리거 조건을 만족할 때만 도입 — §10 부록 참조 |

### 로드맵

- Stage 0: vault 정비 (반나절)
- Stage 1: 최소 RAG (1~2일)
- Stage 2: 하이브리드 + 리랭킹 (1~2일)
- Stage 3: 위키링크 1-hop 확장 (1일)
- Stage 4: RAGAS 평가 (반나절)
- Stage 5: 퍼블리싱 (1일, Stage 1~4와 병렬 가능)
- 부록: 조건부 고급화

---

## 2. 아키텍처

```
┌────────────────────────── Obsidian Vault (.md + frontmatter + [[위키링크]]) ─────────────────────────┐
│                                                                                                      │
│  [인덱싱 — ingest.py]                                    [퍼블리싱 파이프라인]                         │
│                                                                                                      │
│  ObsidianReader ────────> graph.json (links/backlinks)   obsidian-export (.export-ignore로 필터링)    │
│  (위키링크 추출 전용)                                          │                                       │
│                                                              ▼                                       │
│  원본 .md 직접 읽기 ──> 위키링크 정규식 제거 ──> 청킹 ─┬─> chunks.json    Quartz v4 content/          │
│  (짧은 노트=1청크,                                    │                      │ git push               │
│   긴 노트=헤더 분할)                                  └─> KURE-v1 임베딩      ▼                        │
│                                                            └─> chroma_db GitHub Actions ──> GitHub Pages│
│                                                                                                      │
│  [질의 — ask_v3.py]                                                                                  │
│   ※ BM25 인덱스는 ingest 산출물이 아니라 ask 실행 시마다 chunks.json에서 재구축된다                      │
│     (시작이 느리면 bm25s의 save/load로 영속화 가능 — §6 참조)                                           │
│                                                                                                      │
│   질문 ─> 벡터 검색(chroma_db) ───┐                                                                   │
│        └> BM25 검색(kiwi 토큰화) ─┴> RRF 융합 ─> bge-reranker-v2-m3 ─> 위키링크 1-hop 확장             │
│                                                            └─> Ollama(Qwen 2.5) ─> 답                │
│                                                                (API 구성안: Claude/OpenAI — §9)       │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 사전 준비 (공통 환경)

- [ ] **Python 3.11** 설치 확인 (3.12 이상 금지 — 아래 참조)
- [ ] git 설치 확인 (Stage 5 퍼블리싱에 필요)
- [ ] 작업 폴더 + 가상환경 생성
- [ ] `requirements.txt` 작성 + 패키지 설치
- [ ] Ollama 설치 + 모델 다운로드

```powershell
# 1) Python 확인 (3.10 또는 3.11이어야 함 — 3.12 이상은 chromadb 설치 실패, 아래 주의 참조)
python --version

# 2) git 확인 (없으면: winget install Git.Git 후 새 터미널)
git --version

# 3) 작업 폴더 + 가상환경
mkdir C:\jh104\obsidian-rag
cd C:\jh104\obsidian-rag
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# 위 줄이 실행 정책 오류를 내면 먼저: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

> **Python 버전 주의 (Windows)**: `chromadb==0.6.3`이 의존하는 `chroma-hnswlib==0.7.6`은 **Windows용 사전 빌드 휠이 Python 3.11(cp311)까지만** 제공된다 ([PyPI 파일 목록](https://pypi.org/project/chroma-hnswlib/0.7.6/#files)). Python 3.12/3.13에서는 소스 빌드를 시도하다 MSVC 빌드 오류로 설치가 실패하므로 **Python 3.11을 사용**한다 (3.11이 따로 필요하면: `winget install Python.Python.3.11` 후 `py -3.11 -m venv .venv`).

`C:\jh104\obsidian-rag\requirements.txt` 로 저장. 아래는 **`pip install --dry-run`으로 의존성 해석이 충돌 없이 통과함을 확인한 버전 조합**이다 (2026-06-12, pip 25.x 기준 — 본인 환경의 코드 동작은 §5~§8의 각 완료 확인으로 검증할 것). 버전을 풀면 특히 ragas·langchain 계열에서 호환성이 깨진다 (§8 참조):

```
# RAG 파이프라인 (Stage 1~3)
llama-index-readers-obsidian==0.5.0
langchain-text-splitters==0.3.8
sentence-transformers==3.4.1
chromadb==0.6.3
bm25s==0.2.10
kiwipiepy==0.20.3
FlagEmbedding==1.3.4
ollama==0.4.7
# RAGAS 평가 (Stage 4) — §8 코드는 ragas 0.2.x의 EvaluationDataset API 기준
# 주의: ragas 0.1.x는 langchain-core<0.3을 요구해 위 langchain-* 0.3 계열과
#       같은 가상환경에 설치할 수 없다 (pip ResolutionImpossible)
ragas==0.2.15
langchain-ollama==0.2.2
langchain-huggingface==0.1.2
```

```powershell
# 4) 패키지 설치
pip install -r requirements.txt

# 5) Ollama 설치 + 모델 (생성용 LLM)
winget install Ollama.Ollama
ollama pull qwen2.5:7b      # RAM 16GB 미만이면: ollama pull qwen2.5:3b (단, 3b는 Qwen Research License 조건 확인)
```

**완료 확인**: 아래 명령이 모델 인사말을 출력하면 성공.

```powershell
ollama run qwen2.5:7b "안녕하세요라고만 답해"
```

> **네트워크 제약 환경 팁**: 임베딩·리랭커 모델은 최초 1회 Hugging Face에서 내려받아 캐시된다. 인터넷이 되는 곳에서 미리 받아두려면:
> ```powershell
> pip install -U "huggingface_hub[cli]"
> hf download nlpai-lab/KURE-v1
> hf download BAAI/bge-reranker-v2-m3
> # 이후 오프라인에서는:
> $env:HF_HUB_OFFLINE = "1"
> ```

---

## 4. Stage 0 — Vault 정비

- [ ] frontmatter 표준 키 5개를 노트 템플릿에 반영
- [ ] [[MOC]] 운영 원칙 합의(나 자신과)
- [ ] `check_vault.py`로 누락 노트 점검

### 4.1 frontmatter 표준 키

RAG의 메타데이터 필터링과 퍼블리싱 필터링에 공통으로 쓰이는 키를 통일한다. `type`·`tags`는 §5.1의 `ingest.py`가 Chroma metadata로 저장해 검색 필터(`where={"type": ...}`)에 실제로 쓰인다 — 예시는 §5.1 끝 참조. Obsidian의 `설정 → 핵심 플러그인 → 템플릿`에 아래 템플릿을 등록한다.

```yaml
---
tags: []
aliases: []
type: permanent   # MOC | permanent | literature
created: 2026-06-11
topic: ""
---
```

### 4.2 MOC 운영 원칙

- MOC는 미리 만들지 말고, 같은 주제 노트가 쌓이면 **자연 발생**시킨다 ([facedragons](https://facedragons.com/productivity/maps-of-content/))
- 한 MOC의 항목이 **25개를 초과하면 Sub-MOC로 분리**한다
- 폴더는 얕게(5~10개), 연결은 링크와 태그로 — PARA + Zettelkasten + MOC 하이브리드가 수렴된 베스트 프랙티스 ([studio-obsidian](https://studio-obsidian.com/obsidian-folder-structure/))
- frontmatter 질의는 Dataview로 시작하고, 느려지면 Datacore/Obsidian Bases를 검토 ([비교](https://obsidian.rocks/dataview-vs-datacore-vs-obsidian-bases/))

### 4.3 점검 스크립트

`C:\jh104\obsidian-rag\check_vault.py` 로 저장:

```python
# check_vault.py — frontmatter 표준 키 누락 점검
import re
from pathlib import Path

VAULT_PATH = r"C:\jh104\MyVault"   # <- 본인 vault 경로로 이 한 줄만 수정
REQUIRED_KEYS = ["tags", "type", "created"]

notes = list(Path(VAULT_PATH).rglob("*.md"))
missing = []
for p in notes:
    text = p.read_text(encoding="utf-8", errors="ignore")
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    fm = m.group(1) if m else ""
    absent = [k for k in REQUIRED_KEYS if not re.search(rf"^{k}\s*:", fm, re.M)]
    if absent:
        missing.append((str(p.relative_to(VAULT_PATH)), absent))

print(f"전체 노트 {len(notes)}개 중 표준 키 누락 {len(missing)}건")
for path, keys in missing[:30]:
    print(f"  {path}: {', '.join(keys)} 누락")
```

**완료 확인**:

```powershell
cd C:\jh104\obsidian-rag
.\.venv\Scripts\Activate.ps1
python check_vault.py
# 출력 예: "전체 노트 412개 중 표준 키 누락 0건"  <- 0건이면 통과 (당장 0이 아니어도 Stage 1 진행 가능)
```

---

## 5. Stage 1 — 최소 RAG (벡터 검색 + 로컬 LLM)

- [ ] `ingest.py` 작성·실행 → Chroma 인덱스 생성
- [ ] `ask_v1.py` 작성·실행 → 첫 질의응답 성공

### 5.1 인덱싱: `ingest.py`

**설계 메모 (중요)**: `ObsidianReader`는 노트 1개당 Document 1개를 반환하지 않는다. 내부적으로 MarkdownReader를 사용해 **마크다운 파일을 헤더 단위로 분할한 여러 Document**를 반환한다 (공식 문서: "Documents are split by header within a markdown file" — [docs](https://developers.llamaindex.ai/python/framework-api-reference/readers/obsidian/)). 이 분할 결과를 그대로 청크로 쓰면 "짧은 노트=1청크" 정책과 노트 단위 길이 판단을 적용할 수 없다. 그래서 이 가이드는 **ObsidianReader를 위키링크 그래프 추출에만 사용**하고, **청킹은 원본 `.md` 전문을 직접 읽어** "짧은 노트=통째로 1청크 / 긴 노트=헤더 분할" 정책을 적용한다.

**위키링크 전처리 메모**: Obsidian 노트의 `[[위키링크]]`·`[[링크|별칭]]`·`[[링크#헤더]]` 표기는 임베딩과 BM25 인덱싱에 그대로 노출되면 검색 품질에 노이즈가 된다. 청킹 전에 정규식으로 링크 텍스트만 남기고 괄호를 제거한다 (`[[프로젝트A|Project A]]` → `프로젝트A`).

`C:\jh104\obsidian-rag\ingest.py` 로 저장. **수정할 곳은 상단 두 줄뿐**이다.

```python
# ingest.py — vault 읽기 → 노트 단위 청킹 → 임베딩 → Chroma 저장 (+ chunks.json / graph.json 생성)
import json
import re
from pathlib import Path

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from llama_index.readers.obsidian import ObsidianReader
from sentence_transformers import SentenceTransformer

# ===== 이 두 줄만 본인 환경에 맞게 수정 =====
VAULT_PATH = r"C:\jh104\MyVault"          # Obsidian vault 경로
EMBED_MODEL = "nlpai-lab/KURE-v1"          # 느리거나 한영 혼용 노트가 많으면 "BAAI/bge-m3"
# ============================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "chroma_db")
MAX_CHARS = 1500   # 이 길이 이하 노트는 통째로 1청크 (짧은 노트가 많은 vault 기준값 — 본인 vault에 맞게 조정)
FM_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n?", re.S)   # frontmatter 제거용
FM_BLOCK_RE = re.compile(r"^---\r?\n(.*?)\r?\n---", re.S)  # frontmatter 추출용
# [[링크|별칭]] / [[링크#헤더]] / [[링크]] 모두 처리: 링크 텍스트(첫 번째 구성요소)만 남김
WIKI_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")

def strip_wikilinks(text: str) -> str:
    """[[위키링크]] 표기를 링크 텍스트만 남기고 제거한다. 임베딩·BM25 노이즈 방지용."""
    return WIKI_RE.sub(r"\1", text)

def parse_frontmatter(text: str) -> dict:
    """frontmatter에서 type/tags를 추출한다.
    tags는 인라인 배열(`tags: [a, b]`)과 블록 리스트(`tags:` 줄바꿈 후 `- 태그`,
    Obsidian Properties UI가 저장하는 형식) 둘 다 지원한다.
    Chroma metadata는 리스트를 지원하지 않으므로 tags는 쉼표 연결 문자열로 만든다."""
    m = FM_BLOCK_RE.match(text)
    if not m:
        return {}
    fm = m.group(1)
    out = {}
    tm = re.search(r"^type\s*:\s*(.+)$", fm, re.M)
    if tm:
        out["type"] = tm.group(1).split("#")[0].strip().strip("\"'")
    tg = re.search(r"^tags\s*:\s*\[(.*?)\]", fm, re.M)          # 인라인 배열: tags: [a, b]
    if tg:
        tags = [t.strip().strip("\"'") for t in tg.group(1).split(",")]
    else:                                                        # 블록 리스트: tags: 다음 줄부터 "- 태그"
        bl = re.search(r"^tags\s*:\s*\r?\n((?:[ \t]+-[ \t]*.+\r?\n?)+)", fm, re.M)
        tags = [t.strip().strip("\"'") for t in re.findall(r"-[ \t]*(.+)", bl.group(1))] if bl else []
    joined = ",".join(t for t in tags if t)
    if joined:
        out["tags"] = joined
    return out

# 1) 위키링크 그래프 — ObsidianReader 사용 (헤더 단위 Document를 반환하지만,
#    그래프 추출에는 metadata만 쓰므로 분할 여부와 무관하게 동작한다)
print("[1/4] vault 로드 (위키링크 그래프 추출용)...")
docs = ObsidianReader(VAULT_PATH).load_data()
print(f"      헤더 단위 Document {len(docs)}개 로드 (※ 노트 수가 아님)")

links: dict[str, list[str]] = {}
for d in docs:
    note = Path(str(d.metadata.get("file_name", "unknown"))).stem
    links.setdefault(note, [])
    for w in d.metadata.get("wikilinks", []) or []:
        target = str(w).split("|")[0].split("#")[0].strip()
        if target and target != note and target not in links[note]:
            links[note].append(target)

backlinks: dict[str, list[str]] = {}
for src, targets in links.items():
    for t in targets:
        backlinks.setdefault(t, []).append(src)

# 2) 청킹 — 원본 .md 전문을 직접 읽어 노트 단위로 판단
#    위키링크는 청킹 전에 strip_wikilinks()로 제거해 임베딩·BM25 노이즈를 막는다
print("[2/4] 노트 단위 청킹 (짧은 노트=1청크, 긴 노트=헤더 분할)...")
splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
    strip_headers=False,
)

note_files = [f for f in sorted(Path(VAULT_PATH).rglob("*.md"))
              if not any(part.startswith(".") for part in f.relative_to(VAULT_PATH).parts)]
chunks = []
for f in note_files:
    note = f.stem
    full = f.read_text(encoding="utf-8", errors="ignore")
    fm = parse_frontmatter(full)          # type/tags → Chroma metadata (필터 검색용, §4.1)
    raw = FM_RE.sub("", full, count=1).strip()
    if not raw:
        continue
    # 위키링크 정규식 전처리: [[링크|별칭]] → 링크텍스트, [[링크#헤더]] → 링크텍스트
    text = strip_wikilinks(raw)
    if len(text) <= MAX_CHARS:
        parts = [(text, "")]              # 짧은 노트: 통째로 1청크
    else:
        parts = []                        # 긴 노트: 헤더 단위 분할 + 섹션 경로 기록
        for p in splitter.split_text(text):
            section = " > ".join(v for _, v in sorted(p.metadata.items()) if v)
            parts.append((p.page_content, section))
    for body, section in parts:
        chunks.append({
            "id": f"chunk-{len(chunks)}",
            "note": note,
            "section": section,
            "type": fm.get("type", ""),
            "tags": fm.get("tags", ""),
            # 검색 품질을 위해 노트 제목·(헤더 분할된 경우) 섹션 경로를 청크 본문 앞에 주입
            "text": f"[노트: {note}]" + (f" [섹션: {section}]" if section else "") + "\n" + body,
        })

(BASE_DIR / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
(BASE_DIR / "graph.json").write_text(
    json.dumps({"links": links, "backlinks": backlinks}, ensure_ascii=False), encoding="utf-8")
print(f"      노트 {len(note_files)}개 → 청크 {len(chunks)}개, 그래프 노드 {len(links)}개")

print("[3/4] 임베딩 (최초 1회 모델 다운로드 약 2.3GB, 이후 캐시 사용)...")
model = SentenceTransformer(EMBED_MODEL)
embs = model.encode([c["text"] for c in chunks], batch_size=8,
                    show_progress_bar=True, normalize_embeddings=True)

print("[4/4] Chroma 저장...")
client = chromadb.PersistentClient(path=DB_PATH, settings=Settings(anonymized_telemetry=False))
try:
    client.delete_collection("vault")   # 재실행 시 기존 인덱스 교체
except Exception:
    pass
col = client.create_collection("vault", metadata={"hnsw:space": "cosine"})
for s in range(0, len(chunks), 1000):
    batch = chunks[s:s + 1000]
    col.add(
        ids=[c["id"] for c in batch],
        embeddings=embs[s:s + 1000].tolist(),
        documents=[c["text"] for c in batch],
        metadatas=[{"note": c["note"], "section": c["section"] or "-",
                    "type": c.get("type") or "-", "tags": c.get("tags") or "-"} for c in batch],
    )
print(f"완료: {col.count()}개 청크 인덱싱")
```

```powershell
python ingest.py
```

**완료 확인**: `[2/4]` 단계에서 `노트 N개 → 청크 M개`가 출력된다 (짧은 노트가 많은 vault라면 M이 N에 가깝고, 긴 노트가 많으면 M > N). 마지막 줄에 `완료: M개 청크 인덱싱` (M > 0)이 출력되고, `C:\jh104\obsidian-rag` 아래에 `chroma_db\`, `chunks.json`, `graph.json`이 생겨야 한다. `[1/4]`의 "헤더 단위 Document" 수는 노트 수보다 큰 것이 정상이다.

> **메타데이터 필터 예시**: §4.1의 frontmatter `type`/`tags`가 Chroma metadata로 저장되므로, 특정 노트 유형만 검색 대상으로 좁힐 수 있다. ask 스크립트의 `col.query(...)`에 `where` 한 줄만 추가하면 된다:
> ```python
> # 예: type: permanent 노트만 대상으로 벡터 검색
> res = col.query(query_embeddings=q_emb.tolist(), n_results=5, where={"type": "permanent"})
> ```
> tags는 쉼표 연결 문자열(예: `"RAG,Obsidian"`)로 저장된다 (Chroma metadata가 리스트를 지원하지 않기 때문). 태그 1개 단위의 필터 질의가 일상화되면 §10.3의 Qdrant 이전 트리거를 검토한다.

### 5.2 질의: `ask_v1.py`

```python
# ask_v1.py — Stage 1: 벡터 검색만으로 질의응답
from pathlib import Path

import chromadb
import ollama
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "nlpai-lab/KURE-v1"   # ingest.py와 반드시 동일해야 함
LLM_MODEL = "qwen2.5:7b"
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
```

**완료 확인**:

```powershell
python ask_v1.py
# 질문에 내 노트 내용을 근거로 한 한국어 답변 + "참고: <노트이름>"이 출력되면 통과
```

---

## 6. Stage 2 — 하이브리드 검색 + 리랭킹

- [ ] BM25(한국어 형태소 토큰화) 추가
- [ ] RRF 융합 추가
- [ ] bge-reranker-v2-m3 리랭킹 추가
- [ ] `ask_v2.py`로 Stage 1 대비 답변 비교

벡터 검색은 의미는 잘 잡지만 고유명사·정확한 키워드에 약하고, [[BM25]]는 그 반대다. 실패 모드가 상보적이라 둘을 [[RRF]]로 융합하면 거의 항상 이득이다. 융합 후보를 [[리랭킹]]으로 정밀 재정렬하면 상위 K개의 질이 한 번 더 올라간다.

> BM25 인덱스는 별도 파일로 저장하지 않고 **`ask_v2.py`/`ask_v3.py` 실행 시마다 `chunks.json`에서 재구축**한다 (개인 vault 수천 청크 규모에서 수 초). 시작 시간이 거슬리면 `bm25.save("bm25_index")` 후 `bm25s.BM25.load("bm25_index")`로 영속화할 수 있다.

`C:\jh104\obsidian-rag\ask_v2.py` 로 저장:

```python
# ask_v2.py — Stage 2: 벡터 + BM25 하이브리드(RRF) + 리랭킹
import json
from pathlib import Path

import bm25s
import chromadb
import ollama
from chromadb.config import Settings
from FlagEmbedding import FlagReranker
from kiwipiepy import Kiwi
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "nlpai-lab/KURE-v1"   # ingest.py와 동일해야 함
LLM_MODEL = "qwen2.5:7b"
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
```

**완료 확인**:

```powershell
python ask_v2.py
# 통과 기준 (카운트로 판정):
# 1) 노트에만 있는 고유명사(프로젝트명, 책 제목 등) 질문 5개를 만든다
# 2) ask_v1.py에 넣어 올바른 노트를 못 찾은 질문 N개를 추린다
# 3) 같은 N개를 ask_v2.py에 넣어 K개가 올바른 노트를 찾으면 기록
# → K >= ceil(N/2) 면 통과 (예: v1이 4개를 놓쳤으면 v2가 2개 이상 적중)
# → N = 0 (v1이 전부 적중)이면 질문을 더 어렵게 바꿔 1)부터 재시도
```

> 리랭커 모델(bge-reranker-v2-m3, 약 2.3GB)도 최초 1회 다운로드된다. 네트워크 제약 시 §3의 `hf download`로 미리 받아둘 것.

---

## 7. Stage 3 — 위키링크 1-hop 확장 (GraphRAG 지역 질의 근사)

- [ ] `ask_v3.py` 작성 (최종 질의 스크립트)
- [ ] 연결 노트가 보조 컨텍스트로 들어오는지 확인

Obsidian은 이미 `[[위키링크]]` 그래프를 갖고 있다. 검색으로 찾은 노트의 **링크·백링크 이웃 노트를 보조 컨텍스트로 추가**하면, LLM으로 그래프를 새로 추출하지 않고도 "연결된 맥락"을 공짜로 얻는다. `ingest.py`가 만든 `graph.json`을 그대로 쓴다.

> **이 근사의 한계**: 1-hop 확장이 커버하는 것은 "X와 연결된 맥락은?" 류의 **지역(local) 질의**다. [[GraphRAG]]의 커뮤니티 요약이 답하는 **글로벌 질의**("내 노트 전체를 관통하는 주제는?", "전체 vault의 핵심 클러스터는?")는 이 구성으로 대체되지 않는다. 그런 질의가 실제 워크플로에 필요해지면 그때 GraphRAG/LightRAG 도입을 재검토하라 — 그 전까지는 인덱싱 비용 0이 더 크다는 것이 분석 결론이다.

`C:\jh104\obsidian-rag\ask_v3.py` 로 저장 (이후 모든 단계에서 이 파일이 최종본):

```python
# ask_v3.py — 최종: 하이브리드 검색 + 리랭킹 + 위키링크 1-hop 확장
import json
from pathlib import Path

import bm25s
import chromadb
import ollama
from chromadb.config import Settings
from FlagEmbedding import FlagReranker
from kiwipiepy import Kiwi
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "nlpai-lab/KURE-v1"   # ingest.py와 동일해야 함
LLM_MODEL = "qwen2.5:7b"
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
```

**완료 확인**:

```powershell
python ask_v3.py
# "[사용된 청크]" 목록에 직접 검색된 노트 외에 그와 연결된 이웃 노트 이름이 함께 보이면 통과.
# (이웃이 안 보이면: graph.json을 열어 "links"가 비어 있지 않은지 확인 — 트러블슈팅 §14 참조)
```

---

## 8. Stage 4 — RAGAS 평가

- [ ] 평가셋 10~20문항 작성 (내 vault 내용 기반)
- [ ] `eval_rag.py` 실행, 4개 지표 기록
- [ ] 부록(§10)의 고급화 트리거 조건과 비교

[[RAGAS]]는 이후 "고급 기법을 더 넣을지"를 감으로 정하지 않게 해주는 **판단 도구**다. 4개 지표:

| 지표 | 의미 | 낮을 때 의심할 곳 |
|---|---|---|
| context_recall | 정답에 필요한 근거가 검색됐는가 | 검색(청킹·임베딩·하이브리드) |
| context_precision | 검색 결과 중 관련 청크 비율 | 리랭킹, TOP_K |
| faithfulness | 답이 검색 근거에 충실한가 | 프롬프트, 생성 LLM |
| answer_relevancy | 답이 질문에 적합한가 | 질문 이해 — 쿼리 변환 후보 |

평가용 패키지는 §3의 `requirements.txt`에 이미 포함되어 있다 (`ragas==0.2.15`, `langchain-ollama`, `langchain-huggingface`).

> **버전 주의**: 아래 코드는 **ragas 0.2.x의 `EvaluationDataset` API 기준**이다 (샘플 키: `user_input` / `response` / `retrieved_contexts` / `reference`). ragas 0.1.x의 `question/contexts/ground_truth` 스키마와는 호환되지 않으며, 0.1.x는 `langchain-core<0.3`을 요구하기 때문에 이 가이드의 langchain 0.3 계열과 **같은 가상환경에 설치 자체가 불가능**하다 (pip ResolutionImpossible — §3 requirements 주석 참조). `requirements.txt`의 버전 고정을 풀지 말 것.

`C:\jh104\obsidian-rag\eval_rag.py` 로 저장:

```python
# eval_rag.py — Stage 4: RAGAS 평가 (ragas==0.2.15, EvaluationDataset API 기준)
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama
from ragas import EvaluationDataset, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness

from ask_v3 import answer, id2chunk

# ===== 본인 vault 내용으로 10~20문항 작성 (아래는 형식 예시 — 반드시 교체) =====
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
```

**완료 확인**:

```powershell
python eval_rag.py
# 출력 예: {'faithfulness': 0.86, 'answer_relevancy': 0.79, 'context_precision': 0.83, 'context_recall': 0.74}
# 4개 지표 숫자가 출력되면 통과. 이 숫자를 기록해 둘 것 — §10 트리거 판단 기준이 된다.
```

> 평가자 LLM(여기서는 Qwen 2.5 7B)의 품질이 낮으면 지표가 불안정할 수 있다. 지표가 들쑥날쑥하면 **평가 단계만** API 모델로 돌리는 것이 가장 효율적인 API 사용처다 — `ChatOllama(...)` 자리에 §9의 API LLM을 끼우면 된다.

---

## 9. 로컬 무료 구성안 vs API 구성안

분석 결론: 사용자 조건(네트워크 제약 + 한국어 노트)에서는 **완전 로컬을 기본값으로 시작하는 것이 합리적**이다. 한국어 임베딩은 로컬 KURE-v1이 검증된 상위권 모델이므로, API를 쓴다면 먼저 **생성 단계만 교체하는 하이브리드**가 비용·프라이버시·품질의 균형이 좋다.

| | A. 완전 로컬 (본문 기준) | B. 하이브리드 (생성만 API) | C. 전체 API |
|---|---|---|---|
| 임베딩 | KURE-v1 (로컬) | KURE-v1 (로컬) | OpenAI `text-embedding-3-large` 등 |
| 리랭킹 | bge-reranker-v2-m3 (로컬) | bge-reranker-v2-m3 (로컬) | Cohere Rerank / Voyage rerank-2.5 |
| 생성 | Ollama Qwen 2.5 | **Claude / GPT API** | Claude / GPT API |
| 비용 | 0원 | 질의당 소액 | 질의당 + **재인덱싱마다** 임베딩 비용 |
| 오프라인 | 가능 | 생성만 온라인 필요 | 불가 |
| 노트 프라이버시 | 외부 전송 없음 | 검색된 청크만 전송 | 전체 노트가 임베딩 시 전송 |
| 적합한 경우 | 기본값 | 답변 품질·긴 종합이 아쉬울 때 | 로컬 GPU/RAM이 전혀 없을 때 |

### 9.1 구성안 B — 생성만 API로 교체 (권장 API 경로)

`ask_v3.py`의 `generate()` 함수 **하나만** 교체한다. Anthropic 예시:

```powershell
pip install anthropic
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # 본인 키
```

```python
# ask_v3.py 의 generate()를 아래로 교체 (상단에 import anthropic 추가)
import anthropic

api_client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수 사용

def generate(prompt: str) -> str:
    response = api_client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text")
```

OpenAI를 쓰려면 같은 자리에. 2026-06-11 현재 OpenAI 문서의 기본 경로는 Responses API이며, 복잡한 추론·코딩은 `gpt-5.5`, 비용·지연을 낮추려면 `gpt-5.4-mini`를 먼저 검토한다:

```python
# pip install openai ; $env:OPENAI_API_KEY = "sk-..."
from openai import OpenAI

oai = OpenAI()

def generate(prompt: str) -> str:
    res = oai.responses.create(model="gpt-5.5", input=prompt)
    return res.output_text
```

### 9.2 구성안 C — 임베딩까지 API

임베딩 모델을 바꾸면 **전체 재인덱싱이 필요**하고, 질의 시 임베딩도 같은 모델이어야 한다. `ingest.py`와 `ask_v3.py` 양쪽에서 임베딩 호출을 아래로 교체:

```python
# pip install openai ; $env:OPENAI_API_KEY = "sk-..."
from openai import OpenAI

oai = OpenAI()

def embed_api(texts: list[str]) -> list[list[float]]:
    res = oai.embeddings.create(model="text-embedding-3-large", input=texts)
    return [d.embedding for d in res.data]

# ingest.py: embs = model.encode(...) 대신
#   embs_list = embed_api([c["text"] for c in chunks])   # col.add(embeddings=embs_list[...]) 형태로 사용
# ask 스크립트: q_emb = embedder.encode(...) 대신
#   q_emb_list = embed_api([question])                   # col.query(query_embeddings=q_emb_list)
```

리랭킹까지 API로 가려면 `FlagReranker` 자리에 Cohere Rerank(`cohere.ClientV2().rerank(model="rerank-multilingual-v3.0", ...)`)를 끼운다. 단, 네트워크 제약 환경에서는 질의마다 외부 호출이 두 번 이상 발생하므로 구성안 B에서 멈추는 것을 권한다.

---

## 10. 부록 — 조건부 고급화 (RAGAS 측정 후에만)

Stage 4 지표가 아래 트리거를 만족할 때만 도입한다. 만족하지 않으면 **도입하지 않는 것이 결론**이다.

### 10.1 [[Contextual Retrieval]] — 트리거: `context_recall < 0.7`

청크마다 "이 청크가 문서 전체에서 어떤 맥락인지" LLM 요약을 앞에 붙여 인덱싱한다. Anthropic 측정으로 검색 실패율 -49%, 리랭킹 결합 시 -67% ([anthropic.com](https://www.anthropic.com/news/contextual-retrieval)). 비용: 인덱싱 시 **분할된 청크 수만큼 LLM 호출** (로컬 Ollama로 하면 무료, 시간만 소요).

`ingest.py`에 두 군데를 수정하면 된다. 먼저 상단 import 블록에 추가:

```python
# ingest.py 상단 import 블록에 추가
import ollama
```

함수를 청킹 루프 **위에** 추가:

```python
# Contextual Retrieval — 청크에 노트 전체 기준의 맥락 요약을 부착
def add_context(note_text: str, chunk_text: str) -> str:
    r = ollama.chat(model="qwen2.5:7b", messages=[{"role": "user", "content":
        f"<문서>\n{note_text[:4000]}\n</문서>\n위 문서에서 아래 청크의 위치와 맥락을 "
        f"한국어 1~2문장으로 설명하라. 설명만 출력하라.\n<청크>\n{chunk_text[:1500]}\n</청크>"}])
    # ollama SDK 0.4.x: ChatResponse 객체 — .message.content 로 접근
    return r.message.content.strip() + "\n" + chunk_text
```

그리고 청킹 루프의 `for body, section in parts:` 부분을 아래로 교체 — **헤더 분할로 잘린 청크(긴 노트)에만** 맥락을 부착한다 (짧은 노트=1청크는 이미 전체 맥락이므로 불필요).

> 아래 블록은 **단독 실행 불가** — `ingest.py`의 해당 위치(청킹 루프 안)에 붙여넣는 교체 코드다. `text`·`note`·`fm`은 루프의 기존 변수를 그대로 쓴다.

```python
    for body, section in parts:
        if section:                       # 헤더 분할된 청크에만 적용
            body = add_context(text, body)   # text = 해당 노트 전문 (루프 변수)
        chunks.append({
            "id": f"chunk-{len(chunks)}",
            "note": note,
            "section": section,
            "type": fm.get("type", ""),
            "tags": fm.get("tags", ""),
            "text": f"[노트: {note}]" + (f" [섹션: {section}]" if section else "") + "\n" + body,
        })
```

수정 후 `python ingest.py` 재실행 (전체 재인덱싱).

### 10.2 쿼리 변환 ([[HyDE]] / multi-query) — 트리거: `answer_relevancy < 0.7` 이고 질문 어휘와 노트 어휘가 자주 어긋날 때

질문을 LLM으로 가상 답변(HyDE)이나 3개의 변형 질문(multi-query)으로 바꿔 검색한다. `retrieve()` 앞단에 LLM 호출 1회가 추가되므로 응답 지연이 늘어난다.

### 10.3 [[Qdrant]] 이전 — 트리거: 청크 수만 개 이상 + `type:`/`tags:` 메타데이터 필터 질의가 일상화될 때

Chroma도 `where={"type": "permanent"}` 같은 동등 비교 필터를 지원하고(§5.1 예시 — `ingest.py`가 frontmatter의 `type`/`tags`를 metadata로 저장한다), 개인 vault 수천 청크 규모에서는 그것으로 충분하다. 다만 tags가 쉼표 연결 문자열이라 **태그 1개 단위 매칭·복합 payload 필터의 표현력은 Qdrant가 강하다**. 트리거 충족 시 `pip install qdrant-client` 후 `col.add/query`를 Qdrant API로 교체.

### 10.4 시간이 없을 때의 대체재

직접 파이프라인 대신 **Copilot for Obsidian(기본 무료, Ollama 네이티브) + Ollama** 조합으로 Stage 1 수준은 노코드로 가능하다. 단 KURE-v1 임베딩·위키링크 1-hop·RAGAS는 포기하게 된다. Smart Connections는 $20/월 전환, Khoj는 AGPL 셀프호스팅 옵션. (가격·무료 범위는 2026-06 기준이며 변경될 수 있다 — 도입 전 각 플러그인 공식 페이지·스토어 등록 정보에서 재확인할 것.)

---

## 11. 고급 RAG 확장

### 11.1 한국어 형태소 분석 (BM25 토크나이저)

이 가이드는 기본 안으로 **[[Kiwi]] (`kiwipiepy`)** 를 사용한다. Windows에서 `pip install kiwipiepy` 한 줄로 동작하며, 한국어 형태소 분석 정확도가 실용 수준이다.

```powershell
# 기본 안 (Windows 포함 모든 환경, 이미 requirements.txt에 포함)
pip install kiwipiepy
```

```python
from kiwipiepy import Kiwi
kiwi = Kiwi()
def tokenize(text: str) -> list[str]:
    return [t.form.lower() for t in kiwi.tokenize(text)]
```

**대안: Okt (KoNLPy)** — Java 기반이라 JDK 설치가 필요하지만, Windows에서 `pip install konlpy` 후 바로 쓸 수 있다. 품사 태깅이 더 정교하다.

```powershell
# JDK 설치 먼저 (없으면: winget install Microsoft.OpenJDK.21)
pip install konlpy
```

```python
from konlpy.tag import Okt
okt = Okt()
def tokenize(text: str) -> list[str]:
    return [t.lower() for t in okt.morphs(text)]
```

**MeCab은 Windows에서 사용 불가**: MeCab은 Linux/macOS 환경에서 바이너리와 한국어 사전(mecab-ko-dic)을 별도 빌드·설치해야 한다. Windows에서는 `pip install konlpy`만으로 MeCab이 동작하지 않으며, mecab-ko-msvc 또는 WSL을 경유한 별도 셋업이 필요하다. 이 가이드의 독자(Windows 11) 환경에서는 Kiwi 또는 Okt를 사용한다.

### 11.2 re-ranking 심화

`bge-reranker-v2-m3`은 로컬 무료 리랭커로 실용 수준이다. API 환경에서 더 높은 정확도가 필요하면 Cohere Rerank를 고려할 수 있다. Cross-Encoder 계열 리랭커의 MRR 향상 효과는 실험적으로 문서화되어 있다 ([ailog.fr Cross-Encoder 연구](https://ailog.fr/2024/10/05/rag-deep-dive-cross-encoders-reranking/)). 단, Cohere는 외부 API 호출이 발생하므로 §9의 구성안 C에서만 채택한다.

### 11.3 hybrid search 심화

BM25 + 벡터 하이브리드 검색은 실패 모드가 상보적이라 단독 검색 대비 검색 품질 개선이 일반적으로 보고된다 ([ref](https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026)). 구체적인 수치는 코퍼스·질의 유형·임베딩 모델에 따라 크게 달라지므로, RAGAS(`context_recall`, `context_precision`)로 본인 vault 기준 직접 측정하는 것이 가장 신뢰할 수 있는 판단 근거다.

---

## 12. Stage 5 — 퍼블리싱 (obsidian-export → Quartz → GitHub Pages)

- [ ] obsidian-export 설치, `.export-ignore`로 비공개 노트 차단
- [ ] Quartz v4 설치·로컬 미리보기
- [ ] GitHub Actions 배포 워크플로 작성 → Pages 공개

### 12.1 obsidian-export — 공개 노트만 추출

[[obsidian-export]](Rust CLI)는 vault를 일반 마크다운으로 변환하면서 제외 규칙을 적용해 **비공개 노트 유출을 차단**한다 ([참고](https://dev.to/defenderofbasic/host-your-obsidian-notebook-on-github-pages-for-free-8l1)).

```powershell
# 설치 방법 1: Rust가 있으면
cargo install obsidian-export
# 설치 방법 2: 미리 빌드된 바이너리
#   https://github.com/zoni/obsidian-export/releases 에서
#   x86_64-pc-windows-msvc .zip 다운로드 → 압축 해제 → 폴더를 PATH에 추가
```

vault 최상위에 `.export-ignore` 파일 생성 (gitignore 문법, **비공개 폴더를 모두 나열**):

```
일기/
private/
templates/
*.excalidraw.md
```

### 12.2 Quartz v4 설치

[[Quartz]] v4는 위키링크·백링크·그래프 뷰·검색을 지원하는 정적 사이트 생성기다 ([설치 가이드](https://notes.nicolevanderhoeven.com/How+to+publish+Obsidian+notes+with+Quartz+on+GitHub+Pages)). Node 20+ 필요.

```powershell
winget install OpenJS.NodeJS.LTS
cd C:\jh104
git clone https://github.com/jackyzha0/quartz.git
cd quartz
npm i
npx quartz create     # 프롬프트에서 "Empty Quartz" 선택
```

공개 노트를 내보내고 로컬 미리보기:

```powershell
obsidian-export "C:\jh104\MyVault" "C:\jh104\quartz\content"
npx quartz build --serve
# 브라우저에서 http://localhost:8080 접속 → 노트·위키링크·그래프 뷰가 보이면 통과
```

`quartz.config.ts`에서 `baseUrl`을 본인 주소로 수정:

```ts
baseUrl: "<깃허브ID>.github.io/quartz",
```

### 12.3 GitHub Actions 자동 배포

GitHub에 빈 저장소(예: `quartz`)를 만들고 연결한다:

```powershell
cd C:\jh104\quartz
git remote rm origin
git remote add origin https://github.com/<깃허브ID>/quartz.git
```

`C:\jh104\quartz\.github\workflows\deploy.yml` 생성 (Quartz 공식 워크플로):

```yaml
name: Deploy Quartz site to GitHub Pages
on:
  push:
    branches:
      - v4
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: "pages"
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
      - run: npx quartz build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: public
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

GitHub 저장소 `Settings → Pages → Source`를 **GitHub Actions**로 설정한 뒤 푸시:

```powershell
git add -A
git commit -m "publish vault"
git push origin v4
```

**완료 확인**: 저장소 Actions 탭에서 워크플로가 초록색으로 끝나고, `https://<깃허브ID>.github.io/quartz` 접속 시 사이트가 보이면 통과. 이후 갱신은 `obsidian-export` 재실행 → commit → push 3단계 (필요하면 이 3줄을 `publish.ps1`로 묶어둘 것).

> **프라이버시 최종 점검**: 배포된 사이트에서 비공개 폴더의 노트 제목을 검색해 **나오지 않는 것**을 반드시 확인한다.

---

## 13. GraphRAG 확장 (선택 — 글로벌 질의가 필요할 때)

현재 구성의 위키링크 1-hop은 지역(local) 질의만 커버한다. "내 노트 전체를 관통하는 주제는?" 같은 글로벌 질의가 실제로 필요해지면 아래를 검토한다.

> **버전 명시**: 아래 명령은 `graphrag==1.2.0` 기준이다 (`graphrag` 통합 콘솔 CLI는 0.9.0(2024-11)에서 도입된 것으로, **0.3.x에는 콘솔 명령이 없어** `python -m graphrag.index --root . --init` 방식이었다). graphrag는 버전 간 CLI 인터페이스가 자주 바뀌므로, 다른 버전을 쓸 경우 [공식 CHANGELOG](https://github.com/microsoft/graphrag/blob/main/CHANGELOG.md)에서 명령어를 재확인하라. 1.2.0의 요구 Python은 `>=3.10,<3.13`이므로 §3의 Python 3.11 환경이면 충족된다.

```powershell
pip install graphrag==1.2.0
mkdir C:\jh104\graphrag-project
cd C:\jh104\graphrag-project
# graphrag 1.x 기준 초기화 — settings.yaml / .env / prompts/ 생성
graphrag init --root .
# 생성된 .env 의 GRAPHRAG_API_KEY=<API_KEY> 에 본인 키 입력 후:
graphrag index --root .
graphrag query --root . --method local --query "RAG 파이프라인 구성요소는?"
```

인덱싱은 노트 수에 비례해 LLM 호출이 발생하므로 **비용과 시간 사전 확인 필수**다. 개인 vault 수백 노트 기준 API 비용이 수 달러 이상 발생할 수 있다.

---

## 14. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `.venv\Scripts\Activate.ps1` 실행 거부 | PowerShell 실행 정책 | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `pip install -r requirements.txt`가 chroma-hnswlib 빌드 오류로 실패 (`Microsoft Visual C++ 14.0 or greater is required` 등) | Python 3.12/3.13 사용 — `chroma-hnswlib==0.7.6`의 Windows 휠이 cp311(Python 3.11)까지만 제공되어 소스 빌드를 시도함 | Python 3.11로 가상환경 재생성: `winget install Python.Python.3.11` 후 `py -3.11 -m venv .venv` (§3 주의 참조) |
| 모델 다운로드 실패 / 타임아웃 | 네트워크 제약·프록시 | 프록시 설정 `$env:HTTPS_PROXY="http://프록시:포트"`, 또는 §3처럼 다른 망에서 `hf download` 후 캐시 복사(`%USERPROFILE%\.cache\huggingface`) + `$env:HF_HUB_OFFLINE="1"` |
| KURE-v1 임베딩이 너무 느림 | CPU 전용 환경 (모델 약 568M 파라미터) | `batch_size`를 4로 낮추기. 그래도 느리면 `EMBED_MODEL="BAAI/bge-m3"`로 교체 후 재인덱싱. **주의: KURE-v1의 하드웨어 요구·한영 혼용 성능은 공개 근거가 부족**하므로, 한영 혼용 노트가 많다면 두 모델을 RAGAS로 비교해 결정하라 |
| `ollama.chat` 연결 오류 | Ollama 서비스 미실행 | `ollama serve` 실행 또는 트레이 아이콘 확인. 메모리 부족이면 `qwen2.5:3b`로 교체 (Qwen Research License 조건 확인) |
| `graph.json`의 `links`가 전부 빈 배열 | ObsidianReader 버전이 위키링크 메타데이터 미지원 | `pip install -U llama-index-readers-obsidian` 후 `ingest.py` 재실행 |
| 노트 수보다 청크 수가 훨씬 많음 | 긴 노트가 많아 헤더 분할이 다수 발생 (정상 동작) | 문제 아님. 청크가 과하게 잘게 쪼개지면 `headers_to_split_on`에서 `"###"` 항목을 제거해 h3 분할을 끔 |
| Chroma `get_collection` 실패 | ingest 미실행 또는 경로 불일치 | `python ingest.py` 재실행, `chroma_db` 폴더 위치 확인 |
| 같은 제목 노트가 다른 폴더에 존재 | 노트명(stem) 기준 그래프 충돌 | 두 노트가 그래프에서 합쳐진다. Obsidian 관례상 노트 제목은 vault 전역에서 유일하게 유지하는 것을 권장 |
| 리랭킹 점수가 전부 비슷 | `compute_score`의 `max_length` **기본값**이 작아 입력이 잘림 (모델 bge-reranker-v2-m3 자체는 최대 8192 토큰 지원) | `reranker.compute_score(pairs, normalize=True, max_length=2048)`처럼 `max_length`를 명시하고, 그래도 잘리면 4096 등으로 상향 (메모리 사용량 증가 트레이드오프) |
| RAGAS 실행 시 import/스키마 오류 | 설치된 ragas가 §3 고정 버전(0.2.15)과 다름 — 0.1.x의 `question/contexts/ground_truth` 스키마와 0.2의 `EvaluationDataset` API는 비호환 | `pip install ragas==0.2.15` 로 복원 후 §8 코드 사용. ragas를 0.1.x로 **내리는 것은 불가** — `langchain-core<0.3` 요구로 이 가이드의 langchain 0.3 계열과 설치 충돌(ResolutionImpossible) |
| RAGAS 지표가 실행마다 크게 출렁임 | 평가자 LLM(7B) 한계 | 평가 횟수를 늘려 평균. 또는 평가 단계만 API LLM 사용 (§8 끝 참고) |
| Quartz 빌드 실패 `node: not found` | Node 미설치/구버전 | `winget install OpenJS.NodeJS.LTS` 후 새 터미널에서 `node --version` (20+) |
| Pages 404 | Pages 소스 미설정 | 저장소 `Settings → Pages → Source: GitHub Actions` 확인, `baseUrl` 재확인 |
| Windows에서 MeCab/KoNLPy MeCab이 동작하지 않음 | Windows용 MeCab은 바이너리·사전 별도 설치 필요 | Kiwi(`pip install kiwipiepy`) 또는 Okt(`pip install konlpy` + JDK) 사용 — §11.1 참조 |

---

## 15. 내가 다음에 할 일

1. - [ ] §3 사전 준비 실행 — git 확인, venv, `requirements.txt` 설치, Ollama (`ollama run qwen2.5:7b "안녕하세요라고만 답해"` 확인)
2. - [ ] (네트워크 제약 대비) `hf download nlpai-lab/KURE-v1` / `hf download BAAI/bge-reranker-v2-m3` 미리 실행
3. - [ ] Stage 0: frontmatter 템플릿 등록 + `check_vault.py` 실행
4. - [ ] Stage 1: `ingest.py` 실행 (`노트 N개 → 청크 M개` 확인) → `ask_v1.py`로 첫 질의 성공
5. - [ ] Stage 2~3: `ask_v2.py`, `ask_v3.py` 작성, 같은 질문 5개로 v1/v3 답변 비교
6. - [ ] Stage 4: 내 vault 기반 평가셋 10문항 작성 → `eval_rag.py` 실행, 지표 4개 기록
7. - [ ] 지표를 §10 트리거와 대조 — `context_recall < 0.7`이면 Contextual Retrieval 도입, 아니면 고급화 중단
8. - [ ] (병렬) Stage 5: `.export-ignore` 작성 → Quartz 로컬 미리보기 → GitHub Pages 배포 → 비공개 노트 미노출 검증
9. - [ ] 답변 품질이 아쉬우면 §9.1대로 `generate()`만 API(`claude-opus-4-8` 또는 `gpt-5.5`)로 교체해 비교
10. - [ ] [[MOC-RAG-Obsidian]] 허브 노트를 vault에 넣고, 새로 배운 개념을 하위 노트로 채워가기
11. - [ ] vault 업데이트 후 `python ingest.py` 재실행: 전체 재인덱싱이 기본 동작이다. 청크 수가 수만 개를 넘거나 API 임베딩(구성안 C)을 사용 중이라면 변경된 노트만 처리하는 증분 인덱싱 도입을 검토하라 (현재 `ingest.py`는 증분 처리를 지원하지 않음 — Chroma의 `col.upsert`로 구현 가능).

---

## 출처

- 청킹 비교: https://www.snowflake.com/en/engineering-blog/impact-retrieval-chunking-finance-rag/ , https://langcopilot.com/posts/2025-10-11-document-chunking-for-rag-practical-guide
- KURE-v1: https://github.com/nlpai-lab/KURE , https://huggingface.co/nlpai-lab/KURE-v1
- 하이브리드 검색: https://www.digitalapplied.com/blog/hybrid-search-bm25-vector-reranking-reference-2026
- Contextual Retrieval: https://www.anthropic.com/news/contextual-retrieval
- 리랭커: https://huggingface.co/BAAI/bge-reranker-v2-m3
- Cross-Encoder 리랭킹 연구: https://ailog.fr/2024/10/05/rag-deep-dive-cross-encoders-reranking/
- ObsidianReader (헤더 단위 분할 명시): https://developers.llamaindex.ai/python/framework-api-reference/readers/obsidian/
- BGE reranker fp16 주의: https://bge-model.com/tutorial/5_Reranking/5.2.html
- RAGAS 0.1→0.2 마이그레이션 (`EvaluationDataset` API): https://docs.ragas.io/en/latest/howtos/migrations/migrate_from_v01_to_v02/
- chroma-hnswlib 0.7.6 휠 목록 (Windows는 cp311까지): https://pypi.org/project/chroma-hnswlib/0.7.6/#files
- Qwen2.5 Ollama 라이선스 요약: https://ollama.com/library/qwen2.5
- Anthropic Claude 모델: https://docs.anthropic.com/en/docs/about-claude/models
- OpenAI 모델/Responses API/임베딩: https://developers.openai.com/api/docs/models , https://developers.openai.com/api/reference/resources/responses/methods/create , https://developers.openai.com/api/docs/guides/embeddings
- MOC 운영: https://facedragons.com/productivity/maps-of-content/ , https://studio-obsidian.com/obsidian-folder-structure/
- frontmatter 질의 도구: https://obsidian.rocks/dataview-vs-datacore-vs-obsidian-bases/
- Quartz 배포: https://notes.nicolevanderhoeven.com/How+to+publish+Obsidian+notes+with+Quartz+on+GitHub+Pages
- obsidian-export: https://dev.to/defenderofbasic/host-your-obsidian-notebook-on-github-pages-for-free-8l1
- graphrag CHANGELOG: https://github.com/microsoft/graphrag/blob/main/CHANGELOG.md
