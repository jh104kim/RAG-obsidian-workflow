---
title: "가이드 P1 — 비정형 데이터 파싱 → Obsidian Wiki화"
tags: [RAG, Obsidian, Docling, VLM, 비정형데이터, 구축가이드, P1]
created: 2026-06-12
type: guide
---

# 가이드 P1 — 비정형 데이터(엑셀/PDF/PPT/이미지) → Obsidian Wiki화

> 이 문서는 "읽는 보고서"가 아니라 **따라 하면 구축되는 매뉴얼**이다.
> 모든 명령은 Windows 11 + PowerShell 기준이고, 코드블록은 그대로 복사해 실행할 수 있다 (전 블록 `ast.parse` 구문 검증 완료).
> 독자 전제: Python을 다루는 Obsidian 사용자. 기존 RAG 시스템(`C:\jh104\obsidian-rag` — Chroma + KURE-v1 + bm25s + bge-reranker + [[Ollama]] qwen2.5:7b)이 이미 있고, 이 가이드는 그 **앞단**(비정형 파일 → 노트)을 추가한다.

---

## 1. 개요

목표: 엑셀·PDF·PPT·이미지를 파싱해 **[[frontmatter]] + [[위키링크]]가 달린 Obsidian 노트**로 자동 변환하고, 그 노트를 vault에 넣어 기존 `ingest.py`로 재인덱싱한다.

### 핵심 결정 (분석 결론 요약)

| 항목 | 결정 | 근거 |
|---|---|---|
| 파서 | **[[Docling]] 2.101.0 단독** | MIT 라이선스, PDF/PPTX/DOCX/XLSX/이미지 전 포맷, [[TableFormer]] ACCURATE 모드 기본, [[EasyOCR]] 한국어 지원, 완전 오프라인 구동 가능 ([docs](https://docling-project.github.io/docling/)) |
| [[VLM]] | **전면 도입 금지, 2단 적용** | ① 그림/차트만 Picture annotation(로컬), ② 빈 출력/실패 파일만 Ollama `qwen2.5vl:7b` 폴백. 전 페이지 VLM 파싱은 속도 편차가 너무 크다 — 같은 페이지가 SmolDocling 6.2초 vs Pixtral 309초 ([docling vision docs](https://docling-project.github.io/docling/usage/vision_models/)) |
| 엑셀 | **이원화** | 검색용은 Docling md, 질의(집계·필터)용은 [[openpyxl]] 병합셀 해제(unmerge/ffill) 후 [[DuckDB]] 적재. 병합셀 전처리 없이 적재하면 좌상단 셀 외엔 전부 빈 값이 된다 ([openpyxl docs](https://openpyxl.readthedocs.io/en/stable/editing_worksheets.html)) |
| [[위키링크]] | **규칙 매칭 1차 + LLM 2차** | 1차: 노트명+aliases 최장일치(한국어 조사 허용). 2차: `qwen2.5:7b`가 동의어·변형 표기만 보완. 사후 검수는 [Note Linker](https://github.com/AlexW00/obsidian-note-linker) 플러그인 |
| 노트 분할 | **길이 기준 하이브리드** | 기본 1문서 1노트, 장문 PDF만 허브+섹션 2계층(`parent: "[[허브]]"`). 임계값은 실측 과제(§11) |
| frontmatter 키 | title, source_file, source_type, parsed_by, parsed_date, tags, aliases, status | Obsidian 기본 속성(tags/aliases)과 호환 ([Obsidian properties](https://help.obsidian.md/properties)). 생성은 python-frontmatter 1.3.0 ([PyPI](https://pypi.org/project/python-frontmatter/)) |

### 채택하지 않은 것과 이유

| 항목 | 판정 | 이유 |
|---|---|---|
| VLM 전면 파싱 (모든 페이지) | 기각 | 페이지당 수초~수분의 속도 편차 + 로컬 GPU 부담. 일반 문서는 Docling 표준 파이프라인이 더 빠르고 안정적 |
| llama3.2-vision 폴백 | 기각 | 이미지 작업은 **영어만** 공식 지원 ([ollama library](https://ollama.com/library/llama3.2-vision)). 한국어 스캔/표는 `qwen2.5vl`이 강점 ([ollama library](https://ollama.com/library/qwen2.5vl)) |
| API VLM(Claude/GPT-4o) 기본 사용 | 보류 (선택적 3차) | 네트워크 제약 환경 + 비용. 품질이 절실한 그림 설명에 한해 §9 API 구성안으로 |
| 엑셀을 RAG 청크로만 처리 | 기각 | "합계 얼마?" 같은 집계 질의는 RAG가 못 푼다 → DuckDB 분리 적재 ([[비정형데이터-DB화-기술선택]] 분기 기준 참조) |

### 미리 알아둘 실측 미확정 3건 (§11에서 측정 방법 제시)

1. **GPU 사양별 처리 속도** — Docling OCR·VLM 폴백 속도는 GPU에 크게 의존. 본인 PC에서 샘플로 실측 필요.
2. **EasyOCR vs Tesseract kor 한국어 우열** — 일반론 근거가 없어 단정 불가. 보유 문서 샘플로 A/B 필요.
3. **노트 분할 임계값** — 본 가이드 기본값 8,000자는 출발점일 뿐, 검색 품질로 튜닝해야 함.

---

## 2. 아키텍처

```
[원본 파일: C:\jh104\obsidian-rag\inbox\  (xlsx / pdf / pptx / png ...)]
        │
        ▼
┌─ Stage 1. Docling 파싱 (parse_basic.py) ────────────────────────────┐
│  레이아웃 분석 + EasyOCR(ko,en) + TableFormer ACCURATE               │
│  └ (Stage 4-①) 그림/차트 → Picture annotation: 로컬 SmolVLM         │
└──────┬──────────────────────────────────────────────────────────────┘
       │ 출력 빈약? (페이지당 50자 미만 — 스캔본/이미지 PDF)
       ├─ 예 → (Stage 4-②) VLM 폴백: Ollama qwen2.5vl:7b 재변환
       ▼
[parsed\*.md]                      [엑셀 .xlsx — Stage 2 이원화]
       │                             ├ 검색용: Docling md (위 경로와 동일)
       │                             └ 질의용: openpyxl unmerge+fill
       │                                        → DuckDB (tables.duckdb)
       ▼
Stage 3. Wiki화 (wikify.py / wikify_llm.py)
  ① frontmatter 8키 부여 (python-frontmatter)
  ② [[위키링크]] 1차: vault 노트명+aliases 최장일치 (+한국어 조사 허용)
  ③ [[위키링크]] 2차: qwen2.5:7b가 동의어·변형 표기 제안 → 검증 후 적용
  ④ 장문(>임계값)은 허브+섹션 2계층 분할 (parent: "[[허브]]")
       ▼
[VAULT_PATH\parsed\*.md  ← vault에 들어감, status: draft]
       │
       ▼
Stage 5. 기존 RAG 연결: ingest.py 재인덱싱 → ask_v3.py로 질의 확인
(통합 실행: parse_to_wiki.py 한 방)
```

---

## 3. 사전 준비 (Stage 0)

- [ ] 기존 RAG venv 활성화 확인 (Python 3.11)
- [ ] P1 패키지 4종 설치 (docling / python-frontmatter / openpyxl / duckdb)
- [ ] Ollama VLM 모델 다운로드 (`qwen2.5vl:7b`)
- [ ] 작업 폴더(inbox/parsed) 생성
- [ ] (네트워크 제약 환경) Docling 모델 사전 다운로드

> **venv 전략 — 같은 venv 사용.**
> **검증: 기존 `requirements.txt` 11종 + `docling[easyocr]==2.101.0` + `python-frontmatter==1.3.0` + `openpyxl==3.1.5` + `duckdb==1.5.3` 조합을 `pip install --dry-run`으로 해석 — 충돌 없이 통과 (ResolutionImpossible 없음, exit 0; 2026-06-12, pip 25.3 / Linux Python 3.10 환경 실측. Windows Python 3.11에서는 휠 가용성만 다를 수 있고 의존성 그래프는 동일).** 별도 venv는 불필요하다.

```powershell
# 1) 기존 RAG venv 활성화 (이미 구축돼 있다는 전제 — 없으면 RAG-Obsidian-구축-가이드 §3 먼저)
cd C:\jh104\obsidian-rag
.\.venv\Scripts\Activate.ps1
python --version    # 3.11.x 확인

# 2) P1 패키지 설치
#    주의: docling 2.101.0 기본 설치의 OCR은 RapidOCR이다.
#    EasyOCR을 쓰려면 [easyocr] 엑스트라가 반드시 필요 (METADATA 실측 확인:
#    docling==2.101.0 → docling-slim[standard], easyocr는 extra == 'easyocr')
pip install "docling[easyocr]==2.101.0" python-frontmatter==1.3.0 openpyxl==3.1.5 duckdb==1.5.3

# 3) Ollama VLM 모델 (qwen2.5vl 7b = 6.0GB — https://ollama.com/library/qwen2.5vl)
ollama pull qwen2.5vl:7b
ollama list          # qwen2.5:7b(기존) + qwen2.5vl:7b 둘 다 보여야 함

# 4) 작업 폴더
mkdir C:\jh104\obsidian-rag\inbox    # 변환할 원본 파일을 여기 넣는다
mkdir C:\jh104\obsidian-rag\parsed   # Docling 출력(md)이 쌓이는 곳
```

### 오프라인(네트워크 제약) 준비 — 온라인 가능한 시점에 1회 실행

Docling은 기본적으로 첫 실행 때 레이아웃·TableFormer 모델을 HuggingFace에서 받는다. 미리 받아두면 완전 오프라인 구동이 가능하다 ([installation docs](https://docling-project.github.io/docling/installation/), [advanced options](https://docling-project.github.io/docling/usage/advanced_options/)):

```powershell
# 모델 일괄 프리페치 (기본 위치: 사용자 홈 아래 .cache\docling\models)
docling-tools models download

# 이후 세션에서 환경변수로 모델 경로 고정 (현재 세션 + 영구 등록)
$env:DOCLING_ARTIFACTS_PATH = "$env:USERPROFILE\.cache\docling\models"
[Environment]::SetEnvironmentVariable("DOCLING_ARTIFACTS_PATH", "$env:USERPROFILE\.cache\docling\models", "User")
```

> **EasyOCR 한국어 모델 주의**: EasyOCR은 자체 모델(`ko` 감지·인식기)을 첫 OCR 실행 때 `~\.EasyOCR\`에 내려받는다. 오프라인 PC로 옮길 땐 온라인 PC에서 Stage 1을 한 번 실행한 뒤 `%USERPROFILE%\.EasyOCR` 폴더째 복사한다.
> **원격 호출 정책**: Docling은 외부 서비스 호출을 기본 차단하고 `enable_remote_services=True`로만 옵트인한다 — localhost Ollama 호출(Stage 4-②)에도 이 플래그가 필요하다 (단, localhost라 데이터는 PC 밖으로 안 나간다).

**완료 확인**:

```powershell
python -c "import docling, frontmatter, openpyxl, duckdb, easyocr; print('P1 패키지 OK')"
```

---

## 4. Stage 1 — Docling 기본 파싱 (전 포맷 → Markdown)

- [ ] `parse_basic.py` 저장
- [ ] 샘플 파일 2~3개를 `inbox\`에 넣고 실행
- [ ] `parsed\*.md` 출력 육안 확인 (표가 마크다운 표로 나오는지)

`C:\jh104\obsidian-rag\parse_basic.py` 로 저장:

```python
# parse_basic.py — Docling 일괄 변환: inbox의 PDF/PPTX/DOCX/XLSX/이미지 → parsed/*.md
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    PdfPipelineOptions,
    TableFormerMode,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)

INBOX = Path(r"C:\jh104\obsidian-rag\inbox")     # 원본 파일을 넣는 폴더
PARSED = Path(r"C:\jh104\obsidian-rag\parsed")   # 변환된 md가 쌓이는 폴더
EXTS = {".pdf", ".pptx", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}

pdf_opts = PdfPipelineOptions()
pdf_opts.do_ocr = True
pdf_opts.ocr_options = EasyOcrOptions(lang=["ko", "en"])          # 한국어+영어 OCR
pdf_opts.do_table_structure = True
pdf_opts.table_structure_options.mode = TableFormerMode.ACCURATE  # 기본값이지만 명시 [S1]
# 표의 열이 어긋나거나 잘못 병합되면 아래 한 줄을 켠다 [S5]
# pdf_opts.table_structure_options.do_cell_matching = False

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts),
        InputFormat.IMAGE: ImageFormatOption(pipeline_options=pdf_opts),
    }
)


def parse_file(src):
    result = converter.convert(src)
    md = result.document.export_to_markdown()
    return md, result.document.num_pages()


if __name__ == "__main__":
    PARSED.mkdir(parents=True, exist_ok=True)
    for src in sorted(INBOX.iterdir()):
        if src.suffix.lower() not in EXTS:
            continue
        try:
            md, pages = parse_file(src)
        except Exception as e:
            print("FAIL {}: {}".format(src.name, e))
            continue
        out = PARSED / (src.stem + ".md")
        out.write_text("<!-- source: {} -->\n\n".format(src.name) + md, encoding="utf-8")
        print("OK {} -> {} ({}p, {}자)".format(src.name, out.name, pages, len(md)))
```

설계 메모:

- PPTX/DOCX/XLSX는 포맷 옵션 없이도 Docling 기본 백엔드가 처리한다. PDF·이미지에만 OCR/표 옵션을 명시했다.
- 출력 첫 줄의 `<!-- source: 원본파일명 -->` 주석은 Stage 3에서 frontmatter의 `source_file`로 옮겨진다.
- 이미지에 `PdfFormatOption`을 쓰면 2.101.0에서 DeprecationWarning이 나온다(소스 확인) — 그래서 `ImageFormatOption`을 사용.

```powershell
cd C:\jh104\obsidian-rag
python parse_basic.py
```

**완료 확인**: `parsed\` 안에 파일별 `.md`가 생겼고, ① 한국어 본문이 깨지지 않았으며 ② 표가 `| 셀 | 셀 |` 마크다운 표로 나오는지 2~3개 열어 확인한다. 스캔 PDF가 거의 빈 출력이면 정상 — Stage 4-②에서 폴백 처리한다.

---

## 5. Stage 2 — 엑셀 이원화 (검색용 md + 질의용 DuckDB)

- [ ] `excel_to_duckdb.py` 저장 후 실행
- [ ] `tables.duckdb`에 테이블 생성 확인
- [ ] 샘플 SQL 질의 1개 실행

검색용 md는 Stage 1이 이미 만들었다. 여기서는 **질의용** 경로를 만든다. 핵심은 병합셀 전처리: [[openpyxl]]에서 병합 범위는 좌상단 셀에만 값이 있으므로(`merged_cells.ranges`), 해제 후 범위 전체에 값을 채워야 집계가 가능하다 ([openpyxl docs](https://openpyxl.readthedocs.io/en/stable/editing_worksheets.html)).

`C:\jh104\obsidian-rag\excel_to_duckdb.py` 로 저장:

```python
# excel_to_duckdb.py — 질의용 적재: 병합셀 해제(unmerge)+값 채움 후 DuckDB 테이블 생성
import re
from pathlib import Path

import duckdb
import openpyxl

INBOX = Path(r"C:\jh104\obsidian-rag\inbox")
CLEAN_DIR = Path(r"C:\jh104\obsidian-rag\parsed\_clean_xlsx")   # 정리본 보관
DB_PATH = Path(r"C:\jh104\obsidian-rag\tables.duckdb")


def unmerge_and_fill(src, dst):
    """병합셀은 좌상단 셀에만 값이 남는다 — 해제 후 범위 전체에 값을 복사한다."""
    wb = openpyxl.load_workbook(src)
    for ws in wb.worksheets:
        for rng in list(ws.merged_cells.ranges):    # 순회 중 변경되므로 복사본으로
            value = ws.cell(rng.min_row, rng.min_col).value
            ws.unmerge_cells(str(rng))
            for row in ws.iter_rows(min_row=rng.min_row, max_row=rng.max_row,
                                    min_col=rng.min_col, max_col=rng.max_col):
                for cell in row:
                    cell.value = value
    wb.save(dst)


def table_name_for(path):
    name = re.sub(r"\W+", "_", path.stem).strip("_").lower()
    return name or "t_unnamed"


def load_to_duckdb(xlsx, table):
    con = duckdb.connect(str(DB_PATH))
    con.execute("INSTALL excel; LOAD excel;")       # 확장 설치는 최초 1회만 네트워크 필요
    path_sql = str(xlsx).replace("'", "''")
    con.execute(
        'CREATE OR REPLACE TABLE "{}" AS '
        "SELECT * FROM read_xlsx('{}', header = true, all_varchar = true, "
        "ignore_errors = true, stop_at_empty = false)".format(table, path_sql)
    )
    n = con.execute('SELECT count(*) FROM "{}"'.format(table)).fetchone()[0]
    con.close()
    return n


if __name__ == "__main__":
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    for src in sorted(INBOX.glob("*.xlsx")):
        clean = CLEAN_DIR / src.name
        unmerge_and_fill(src, clean)
        n = load_to_duckdb(clean, table_name_for(src))
        print('OK {} -> 테이블 "{}" ({}행)'.format(src.name, table_name_for(src), n))
```

`read_xlsx` 주요 옵션 ([DuckDB excel 확장](https://duckdb.org/docs/current/core_extensions/excel.html)): `sheet=`(시트 지정), `range=`(셀 범위), `header=`, `all_varchar=`(타입 추론 끄기 — 지저분한 시트에 안전), `ignore_errors=`, `stop_at_empty=`(빈 행에서 중단 여부). **`.xls`(구형)는 미지원** — Excel에서 `.xlsx`로 다시 저장 후 투입.

```powershell
python excel_to_duckdb.py
```

**완료 확인**:

```powershell
python -c 'import duckdb; con = duckdb.connect(r"C:\jh104\obsidian-rag\tables.duckdb"); print(con.execute("SHOW TABLES").fetchall())'
```

샘플 질의 (테이블명은 본인 파일명에 맞게):

```sql
-- duckdb CLI 또는 python에서: 헤더가 1행이 아니면 range='A3:H100' 식으로 조정
SELECT * FROM "내파일명" LIMIT 5;
SELECT 부서, count(*) FROM "내파일명" GROUP BY 부서;
```

> 헤더가 여러 줄이거나 표가 시트 중간에 시작하면 `read_xlsx(..., range = 'A3:H200', header = true)`로 범위를 지정하는 편이 정리본 수정보다 빠르다.

---

## 6. Stage 3 — Wiki화 (frontmatter + 위키링크 + 장문 분할)

- [ ] `wikify.py` 저장, `VAULT_PATH`를 본인 경로로 수정
- [ ] 실행 후 vault의 `parsed\` 폴더에 노트 생성 확인
- [ ] Obsidian에서 frontmatter 속성·링크 렌더링 확인
- [ ] (선택) `wikify_llm.py`로 2차 링크 보완
- [ ] Obsidian 플러그인으로 사후 검수

### 6.1 1차 — 규칙 매칭 (`wikify.py`)

원리: vault의 **노트 파일명 + frontmatter `aliases`**를 용어 사전으로 만들고, 본문에서 **최장일치**로 치환한다. 한국어는 "Docling은/RAG를"처럼 조사가 붙으므로, 용어 뒤 조사를 허용하되 링크 안에는 넣지 않는다(`[[Docling]]은`). frontmatter 속성 값의 위키링크는 **반드시 따옴표**가 필요하며(`parent: "[[허브]]"` — [Obsidian properties](https://help.obsidian.md/properties)), python-frontmatter의 YAML 직렬화가 자동으로 따옴표를 붙여준다(기능 테스트로 확인: `parent: '[[허브]]'` 출력).

`C:\jh104\obsidian-rag\wikify.py` 로 저장:

```python
# wikify.py — 파싱된 md에 frontmatter + [[위키링크]]를 달아 vault용 노트로 변환
import datetime
import re
from pathlib import Path

import frontmatter

VAULT_PATH = Path(r"C:\jh104\MyVault")              # TODO: 본인 vault 경로로 수정
PARSED_DIR = Path(r"C:\jh104\obsidian-rag\parsed")  # Stage 1 출력 폴더
PARSED_SUBDIR = "parsed"        # vault 안에서 변환 노트가 들어갈 하위 폴더명
SPLIT_THRESHOLD = 8000          # 글자 수 분할 임계값 — ※ 실측 미확정(§11 참조)
MAX_LINKS_PER_TERM = 1          # 같은 용어는 노트당 1회만 링크 (링크 도배 방지)

# 용어 바로 뒤에 붙어도 매칭으로 인정할 한국어 조사
JOSA = "(?:으로|에서|부터|까지|처럼|보다|에게|한테|마다|조차|밖에|은|는|이|가|을|를|과|와|의|도|만|에|로)"


def build_term_map(vault):
    """vault의 노트 파일명 + frontmatter aliases → 링크 대상 노트명 매핑."""
    terms = {}
    for md in vault.rglob("*.md"):
        name = md.stem
        terms.setdefault(name, name)
        try:
            post = frontmatter.load(md)
        except Exception:
            continue        # frontmatter가 깨진 노트는 파일명만 등록
        aliases = post.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        for a in aliases:
            a = str(a).strip()
            if a:
                terms.setdefault(a, name)
    return terms


def link_terms(text, terms):
    """1차 규칙 매칭: 최장일치 + 조사 허용. 코드블록·기존 링크·URL은 건드리지 않는다."""
    protected = []

    def _protect(m):
        protected.append(m.group(0))
        return "\x00{}\x00".format(len(protected) - 1)

    text = re.sub(
        r"```[\s\S]*?```|\[\[[^\]]*\]\]|`[^`\n]*`|https?://\S+",
        _protect, text,
    )

    for term in sorted(terms, key=len, reverse=True):   # 긴 용어부터 = 최장일치
        if len(term) < 2:
            continue
        target = terms[term]
        pattern = re.compile(
            r"(?<![\w가-힣])" + re.escape(term) + r"(?=" + JOSA + r"?(?![\w가-힣]))"
        )
        count = 0

        def _repl(m):
            nonlocal count
            if count >= MAX_LINKS_PER_TERM:
                return m.group(0)
            count += 1
            t = m.group(0)
            return "[[{}]]".format(t) if t == target else "[[{}|{}]]".format(target, t)

        new_text = pattern.sub(_repl, text)
        if new_text != text:
            # 방금 만든 링크 안에서 더 짧은 용어가 다시 매칭되지 않도록 즉시 보호
            text = re.sub(r"\[\[[^\]]*\]\]", _protect, new_text)

    return re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], text)


def sanitize_filename(name):
    """Windows·Obsidian에서 못 쓰는 문자 제거 + 길이 제한."""
    name = re.sub(r'[\\/:*?"<>|\[\]#^]', " ", name)
    return re.sub(r"\s+", " ", name).strip()[:80]


def split_long_note(md_text, base_name):
    """(노트명, 본문, 추가메타) 리스트 반환. 임계값 이하면 1문서 1노트."""
    if len(md_text) <= SPLIT_THRESHOLD:
        return [(base_name, md_text, {})]
    parts = re.split(r"(?m)^(?=## )", md_text)
    if len(parts) < 3:              # 나눌 H2 섹션이 1개 이하면 그대로 둔다
        return [(base_name, md_text, {})]
    intro, sections = parts[0], parts[1:]
    notes, toc = [], []
    for i, sec in enumerate(sections, 1):
        heading = sec.splitlines()[0].lstrip("#").strip() or "섹션"
        name = sanitize_filename("{} - {:02d} {}".format(base_name, i, heading))
        notes.append((name, sec, {"parent": "[[{}]]".format(base_name)}))
        toc.append("- [[{}]]".format(name))
    hub_body = intro.rstrip() + "\n\n## 섹션 목차\n" + "\n".join(toc) + "\n"
    return [(base_name, hub_body, {})] + notes


def make_note(body, src_name, title, extra_meta):
    """frontmatter 표준 키 8종 + 추가 메타(parent 등)."""
    meta = {
        "title": title,
        "source_file": src_name,
        "source_type": Path(src_name).suffix.lstrip(".").lower() or "md",
        "parsed_by": "docling-2.101.0",
        "parsed_date": datetime.date.today().isoformat(),
        "tags": ["auto-parsed", "P1"],
        "aliases": [],
        "status": "draft",          # 사람 검수 후 reviewed로 바꾼다
    }
    meta.update(extra_meta)
    post = frontmatter.Post(body, **meta)
    return frontmatter.dumps(post)  # "[[..]]" 값은 YAML 직렬화 시 자동으로 따옴표 처리


def wikify_file(parsed_md, out_dir, terms):
    raw = parsed_md.read_text(encoding="utf-8")
    m = re.match(r"<!--\s*source:\s*(.+?)\s*-->\s*", raw)
    src_name = m.group(1) if m else parsed_md.name
    if m:
        raw = raw[m.end():]
    base = sanitize_filename(Path(src_name).stem)
    local_terms = {t: n for t, n in terms.items() if n != base}  # 자기 자신 링크 방지
    written = []
    for name, body, extra in split_long_note(raw, base):
        note = make_note(link_terms(body, local_terms), src_name, name, extra)
        out_path = out_dir / (name + ".md")
        out_path.write_text(note, encoding="utf-8")
        written.append(out_path)
    return written


if __name__ == "__main__":
    out_dir = VAULT_PATH / PARSED_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    terms = build_term_map(VAULT_PATH)
    print("용어 사전: {}개 (노트명+aliases)".format(len(terms)))
    for f in sorted(PARSED_DIR.glob("*.md")):
        for p in wikify_file(f, out_dir, terms):
            print("vault <-", p.name)
```

```powershell
python wikify.py
```

**완료 확인** (기능 테스트로 검증된 동작):

1. vault의 `parsed\` 폴더에 노트가 생겼다.
2. Obsidian에서 노트를 열면 frontmatter 속성 8종이 Properties 패널에 보인다.
3. 본문에 `[[기존노트명]]은` 형태로 링크가 걸렸고, 코드블록·URL 안은 안 건드렸다.
4. 장문 PDF는 허브 노트(섹션 목차) + `문서명 - 01 ...` 섹션 노트로 나뉘었고, 섹션 노트 frontmatter에 `parent: '[[허브명]]'`이 **따옴표로 감싸여** 있다.

### 6.2 2차 — LLM 보완 (`wikify_llm.py`)

규칙 매칭은 표기가 정확히 같아야 잡는다. "벡터 데이터베이스"라고 쓴 본문을 `[[벡터DB]]`로 잇는 건 LLM 몫이다. 제안은 반드시 **검증 후** 적용한다(제목이 vault에 실재 + 표현이 본문에 실재 + 미링크).

`C:\jh104\obsidian-rag\wikify_llm.py` 로 저장:

```python
# wikify_llm.py — 2차 보완: 규칙 매칭이 놓친 동의어·변형 표기를 qwen2.5:7b가 제안
import json
import re

import frontmatter
import ollama

from wikify import PARSED_SUBDIR, VAULT_PATH, build_term_map

PROMPT = """다음은 Obsidian 노트 본문과 vault에 존재하는 노트 제목 목록이다.
본문에 등장하는 표현 중, 노트 제목과 같은 개념을 가리키지만 표기가 달라서
아직 [[링크]]가 안 된 것을 찾아라. 반드시 JSON 배열로만 답하라.
형식: [{{"본문표현": "...", "노트제목": "..."}}] / 찾은 것이 없으면 []

[노트 제목 목록]
{titles}

[본문]
{body}
"""


def suggest_links(body, titles):
    resp = ollama.chat(
        model="qwen2.5:7b",
        messages=[{
            "role": "user",
            "content": PROMPT.format(titles="\n".join(titles), body=body[:4000]),
        }],
        options={"temperature": 0},
    )
    raw = resp["message"]["content"]
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return []
    try:
        out = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return out if isinstance(out, list) else []


def apply_suggestions(body, suggestions, titles):
    """LLM 제안을 검증 후 적용: 제목이 실재 + 표현이 본문에 존재 + 미링크일 때만."""
    applied = 0
    for s in suggestions:
        if not isinstance(s, dict):
            continue
        phrase = str(s.get("본문표현", "")).strip()
        title = str(s.get("노트제목", "")).strip()
        if not phrase or title not in titles or phrase not in body:
            continue
        if "[[" + phrase in body or "|" + phrase + "]]" in body:
            continue        # 이미 링크된 표현은 건너뛴다
        link = "[[{}]]".format(title) if phrase == title else "[[{}|{}]]".format(title, phrase)
        body = body.replace(phrase, link, 1)
        applied += 1
    return body, applied


if __name__ == "__main__":
    out_dir = VAULT_PATH / PARSED_SUBDIR
    titles = sorted(set(build_term_map(VAULT_PATH).values()))
    for md in sorted(out_dir.glob("*.md")):
        post = frontmatter.load(md)
        new_body, n = apply_suggestions(
            post.content, suggest_links(post.content, titles), set(titles)
        )
        if n:
            post.content = new_body
            md.write_text(frontmatter.dumps(post), encoding="utf-8")
            print("{}: 링크 {}개 추가".format(md.name, n))
```

```powershell
# Ollama 데몬이 떠 있어야 한다 (ollama serve 또는 트레이 앱)
python wikify_llm.py
```

알려진 한계(명시): 본문이 4,000자로 잘려 들어가므로 장문 뒷부분의 동의어는 못 잡는다(분할 노트면 대부분 커버). 또 `str.replace` 기반이라 드물게 의도치 않은 위치를 바꿀 수 있다 — 그래서 `status: draft`로 두고 사람이 검수한다.

### 6.3 사후 검수 (Obsidian 플러그인)

- [Note Linker](https://github.com/AlexW00/obsidian-note-linker): vault 전체를 스캔해 미링크 후보를 보여주고 클릭으로 일괄 링크 — 자동화가 놓친 것 검수용.
- [Various Complements](https://github.com/tadashi-aikawa/obsidian-various-complements-plugin): 이후 수동 편집 시 노트명 자동완성.

**완료 확인**: Obsidian graph view에서 새 노트들이 기존 노트와 엣지로 연결돼 보이면 성공. 고아 노트(연결 0)가 많으면 aliases를 보강하고 `wikify.py`를 다시 돌린다(같은 이름 노트는 덮어씀).

---

## 7. Stage 4 — VLM 2단 적용 (전면 도입 금지)

- [ ] (①) 그림 많은 PDF에 Picture annotation 테스트
- [ ] (②) `vlm_fallback.py` 저장, 스캔 PDF 1개로 폴백 테스트

### 7.1 ① 그림/차트 설명 — Picture annotation (로컬)

문서 전체는 표준 파이프라인으로 두고, **그림 요소에만** 로컬 VLM 설명을 단다 ([vision docs](https://docling-project.github.io/docling/usage/vision_models/)). 기본 제공 프리셋 `smolvlm_picture_description`(SmolVLM-256M, 로컬 실행)을 쓴다.

`C:\jh104\obsidian-rag\parse_with_pictures.py` 로 저장:

```python
# parse_with_pictures.py — Stage 4-①: 그림/차트 설명(Picture annotation, 로컬 SmolVLM)
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    PdfPipelineOptions,
    TableFormerMode,
    smolvlm_picture_description,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.document import PictureDescriptionData

pdf_opts = PdfPipelineOptions()
pdf_opts.do_ocr = True
pdf_opts.ocr_options = EasyOcrOptions(lang=["ko", "en"])
pdf_opts.do_table_structure = True
pdf_opts.table_structure_options.mode = TableFormerMode.ACCURATE
pdf_opts.do_picture_description = True                              # 그림마다 설명 생성
pdf_opts.picture_description_options = smolvlm_picture_description  # 로컬 SmolVLM-256M
pdf_opts.images_scale = 2.0
pdf_opts.generate_picture_images = True

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts)}
)


def picture_section(doc):
    """그림 설명 annotation을 노트 끝에 붙일 섹션 문자열로 정리."""
    lines = []
    for i, pic in enumerate(doc.pictures, 1):
        for ann in pic.annotations:
            if isinstance(ann, PictureDescriptionData):
                lines.append("- 그림 {}: {}".format(i, ann.text))
    if not lines:
        return ""
    return "\n\n## 그림 설명 (자동 생성)\n" + "\n".join(lines) + "\n"


if __name__ == "__main__":
    src = Path(r"C:\jh104\obsidian-rag\inbox\sample.pdf")   # TODO: 그림 있는 PDF로 테스트
    result = converter.convert(src)
    md = result.document.export_to_markdown() + picture_section(result.document)
    print(md[-1500:])
```

솔직한 한계: SmolVLM-256M은 소형 모델이라 설명이 **영어 위주에 단순**하다. 한국어 설명 품질이 필요하면 두 가지 대안 — ⓐ `picture_description_options`를 `PictureDescriptionApiOptions`로 바꿔 **localhost Ollama의 qwen2.5vl:7b**를 쓰거나(여전히 로컬 — §9의 코드에서 url만 `http://localhost:11434/v1/chat/completions`, model만 `qwen2.5vl:7b`로 교체), ⓑ 외부 API(§9). 또한 inline VLM 실행에는 `transformers`/`accelerate`가 필요한데 기존 RAG venv에 이미 들어있다(dry-run 해석 결과에 포함 확인).

> 만족스러우면 `parse_basic.py`의 옵션 블록에 `do_picture_description` 3줄을 그대로 합쳐 상시 적용해도 된다 (그림 없는 문서엔 오버헤드 없음).

### 7.2 ② 빈 출력/실패 파일만 VLM 폴백 (Ollama qwen2.5vl:7b)

스캔본·이미지 PDF는 표준 파이프라인 출력이 거의 비는데, 이런 파일만 [[VLM]] 전체 파싱으로 재변환한다. Docling의 `VlmPipeline`은 OpenAI 호환 원격 엔드포인트를 지원하고, Ollama가 바로 그 형식이다 ([vision docs](https://docling-project.github.io/docling/usage/vision_models/)). `qwen2.5vl`은 스캔 폼/표 구조화가 강점으로 명시된 모델이다 ([ollama library](https://ollama.com/library/qwen2.5vl)).

`C:\jh104\obsidian-rag\vlm_fallback.py` 로 저장:

```python
# vlm_fallback.py — Stage 4-②: Docling 출력이 빈약한 PDF만 Ollama qwen2.5vl:7b로 재변환
import re
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmPipelineOptions
from docling.datamodel.pipeline_options_vlm_model import ApiVlmOptions, ResponseFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline

INBOX = Path(r"C:\jh104\obsidian-rag\inbox")
PARSED = Path(r"C:\jh104\obsidian-rag\parsed")
MIN_CHARS_PER_PAGE = 50     # 휴리스틱: 페이지당 이 글자 수 미만이면 "빈 출력"으로 간주


def needs_fallback(md_text, num_pages):
    return len(md_text.strip()) < MIN_CHARS_PER_PAGE * max(num_pages, 1)


def make_vlm_converter():
    opts = VlmPipelineOptions(enable_remote_services=True)  # 원격 호출 옵트인 — localhost Ollama에도 필요
    opts.vlm_options = ApiVlmOptions(
        url="http://localhost:11434/v1/chat/completions",   # Ollama의 OpenAI 호환 엔드포인트
        params={"model": "qwen2.5vl:7b"},
        prompt="이 페이지 전체를 마크다운으로 정확히 전사하라. 표는 마크다운 표로, 제목 계층은 #으로 표현하라.",
        timeout=600,        # 페이지당 수십 초~수 분 (GPU 사양 의존 — §11 실측 과제)
        scale=2.0,
        response_format=ResponseFormat.MARKDOWN,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=opts)
        }
    )


def reparse_with_vlm(src):
    result = make_vlm_converter().convert(src)
    return result.document.export_to_markdown()


if __name__ == "__main__":
    for md_file in sorted(PARSED.glob("*.md")):
        body = re.sub(r"<!--.*?-->", "", md_file.read_text(encoding="utf-8"), flags=re.S)
        if not needs_fallback(body, 1):
            continue
        src = next(INBOX.glob(md_file.stem + ".pdf"), None)
        if src is None:
            continue
        print("VLM 재변환:", src.name)
        md = reparse_with_vlm(src)
        md_file.write_text("<!-- source: {} -->\n\n".format(src.name) + md, encoding="utf-8")
        print("done: {} ({}자)".format(md_file.name, len(md)))
```

설계 메모:

- 폴백 단위는 **파일**이다. 일부 페이지만 스캔본인 혼합 PDF는 `converter.convert(src, page_range=(시작, 끝))`으로 범위를 지정해 수동 처리한다(페이지 자동 판별은 P1 범위 밖).
- 2.101.0에서 `ApiVlmOptions` 사용 시 `DeprecationWarning`(VlmConvertOptions 권장)이 출력되지만 **동작에는 문제 없다** — VlmPipeline 소스에 레거시 경로가 그대로 살아 있음을 확인했다. 문서화된 안정 API라 그대로 쓴다.

**완료 확인**: 스캔 PDF 1개를 `inbox\`에 넣고 Stage 1 → `vlm_fallback.py` 순서로 실행. `parsed\해당파일.md`가 수십 자 미만 → 수천 자 마크다운으로 바뀌면 성공. 첫 실행은 모델 로드로 오래 걸린다.

---

## 8. Stage 5 — 통합 파이프라인 + 기존 RAG 재인덱싱

- [ ] `parse_to_wiki.py` 저장 후 전체 파이프라인 1회 실행
- [ ] `ingest.py` 재인덱싱
- [ ] `ask_v3.py`로 새 문서 내용 질의 → 답에 새 노트가 인용되는지 확인

### 8.1 통합 실행 스크립트

`C:\jh104\obsidian-rag\parse_to_wiki.py` 로 저장 (로드맵 P1의 `parse_to_wiki.py` 항목이 이 파일):

```python
# parse_to_wiki.py — P1 통합 파이프라인: inbox → Docling → (빈 출력이면 VLM 폴백) → Wiki 노트 → vault
from parse_basic import EXTS, INBOX, PARSED, parse_file
from vlm_fallback import needs_fallback, reparse_with_vlm
from wikify import PARSED_SUBDIR, VAULT_PATH, build_term_map, wikify_file


def main():
    PARSED.mkdir(parents=True, exist_ok=True)
    out_dir = VAULT_PATH / PARSED_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Docling 1차 변환 + 빈 출력 시 VLM 폴백 (PDF만)
    for src in sorted(INBOX.iterdir()):
        if src.suffix.lower() not in EXTS:
            continue
        out_md = PARSED / (src.stem + ".md")
        if out_md.exists():
            continue        # 이미 변환됨 — 다시 변환하려면 parsed/에서 해당 md 삭제
        try:
            md, pages = parse_file(src)
        except Exception as e:
            print("FAIL(docling) {}: {}".format(src.name, e))
            md, pages = "", 1
        if needs_fallback(md, pages) and src.suffix.lower() == ".pdf":
            print("빈 출력 → VLM 폴백:", src.name)
            try:
                md = reparse_with_vlm(src)
            except Exception as e:
                print("FAIL(vlm) {}: {}".format(src.name, e))
        if not md.strip():
            print("SKIP(빈 결과):", src.name)
            continue
        out_md.write_text("<!-- source: {} -->\n\n".format(src.name) + md, encoding="utf-8")
        print("parsed:", out_md.name)

    # 2) Wiki화: frontmatter + 위키링크 + 장문 분할 → vault에 기록
    terms = build_term_map(VAULT_PATH)
    print("용어 사전: {}개".format(len(terms)))
    for f in sorted(PARSED.glob("*.md")):
        for p in wikify_file(f, out_dir, terms):
            print("vault <-", p.name)

    print("완료. 다음 단계: 엑셀은 excel_to_duckdb.py, 재인덱싱은 ingest.py")


if __name__ == "__main__":
    main()
```

### 8.2 vault 투입 → 재인덱싱 → 질의 확인

변환 노트는 `VAULT_PATH\parsed\`에 들어가므로 기존 `ingest.py`(vault 전체 인덱싱)가 그대로 잡는다:

```powershell
cd C:\jh104\obsidian-rag
.\.venv\Scripts\Activate.ps1

# 전체 파이프라인 (엑셀 질의용 적재는 별도)
python parse_to_wiki.py
python excel_to_duckdb.py

# 기존 RAG 재인덱싱 (chunks.json + chroma_db 갱신)
python ingest.py

# 새 문서 내용으로 질의 — 답의 출처에 새 노트가 인용되면 연결 완료
python ask_v3.py "방금 넣은 PDF의 핵심 내용 관련 질문"
```

**완료 확인 (전체 파이프라인의 정의된 "끝")**:

1. `ingest.py` 출력의 노트/청크 수가 투입 문서만큼 늘었다.
2. `ask_v3.py` 답변의 근거(citation)에 `parsed\` 노트가 등장한다.
3. 엑셀 수치 질문은 RAG가 아니라 DuckDB SQL(§5)로 답이 나온다 — 이 분기 기준은 [[비정형데이터-DB화-기술선택]] 참조.

> 운용 메모: 이후엔 새 파일을 `inbox\`에 넣고 `python parse_to_wiki.py && python ingest.py`만 반복하면 된다. 변환 캐시는 `parsed\*.md` 존재 여부로 판단하므로 재변환하려면 해당 md를 지운다.

---

## 9. API 구성안 (선택적 3차 — 품질 최우선일 때만)

로컬 2단으로 부족한 **그림/차트 설명**에 한해 외부 API VLM을 쓴다. 전제: 네트워크 가능 + 문서 외부 전송 허용(보안 검토 필수). Docling은 `enable_remote_services=True` 옵트인 없이는 어떤 외부 호출도 하지 않는다.

```powershell
# 환경변수로 키 주입 (코드에 키를 적지 말 것)
$env:OPENAI_API_KEY = "sk-..."
```

`C:\jh104\obsidian-rag\api_picture_description.py` 로 저장:

```python
# api_picture_description.py — 선택적 3차: 그림 설명만 외부 API VLM으로 (품질 최우선일 때)
import os

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    PictureDescriptionApiOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

pdf_opts = PdfPipelineOptions()
pdf_opts.enable_remote_services = True      # 외부 API 호출은 명시적 옵트인 [S5]
pdf_opts.do_picture_description = True
pdf_opts.picture_description_options = PictureDescriptionApiOptions(
    url="https://api.openai.com/v1/chat/completions",
    params={"model": "gpt-4o-mini"},
    headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
    prompt="이 그림/차트를 한국어로 3문장 이내로 설명하라. 수치가 보이면 수치를 포함하라.",
    timeout=90,
)

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts)}
)
```

- `converter`를 §7.1의 `picture_section()`과 조합해 쓰면 된다 (그림 설명 추출 로직은 동일).
- 품질 순 추천: `gpt-4o` > `gpt-4o-mini`(비용 효율). Claude를 쓰려면 OpenAI 호환 엔드포인트 사용 가능 여부를 Anthropic 문서에서 확인 후 `url`/`headers`만 교체한다 — 미확인 상태로 단정하지 않는다.
- VLM 폴백(§7.2)도 같은 방식으로 `ApiVlmOptions`의 `url`/`params`/`headers`만 API로 바꾸면 되지만, **문서 전체가 외부로 나가므로** 그림 설명보다 보안 민감도가 훨씬 높다.

---

## 10. 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `EasyOcrOptions` 지정했는데 `easyocr` import 오류 | docling 2.101.0 기본 설치는 RapidOCR만 포함 | `pip install "docling[easyocr]==2.101.0"` (엑스트라 필수 — §3) |
| 한국어 OCR이 깨짐/누락 | `lang`에 `ko` 누락 또는 EasyOCR 모델 미다운로드 | `EasyOcrOptions(lang=["ko", "en"])` 확인, 온라인에서 1회 실행해 `~\.EasyOCR` 모델 생성. 그래도 나쁘면 §11 A/B(Tesseract `kor`)로 비교 |
| 표 열이 어긋나거나 셀이 엉뚱하게 병합됨 | TableFormer 셀 매칭 실패 | `pdf_opts.table_structure_options.do_cell_matching = False` 주석 해제 ([advanced options](https://docling-project.github.io/docling/usage/advanced_options/)) |
| `DeprecationWarning: Using legacy VLM options ...` | 2.101.0이 `VlmConvertOptions` 신 API를 권장 | 무시 가능 — 레거시 경로 동작 확인됨(§7.2). 차후 docling 업그레이드 시 마이그레이션 |
| VLM 폴백이 `ConnectionError` | Ollama 데몬 미실행 | `ollama serve` 실행 후 `ollama list`로 확인. `enable_remote_services=True`도 확인 |
| VLM 폴백이 매우 느림 | 7B VLM + CPU 폴백 | GPU/VRAM 확인(모델 6.0GB). 페이지 많으면 `page_range`로 나눠 실행. §11 실측 과제 |
| `INSTALL excel` 실패 (오프라인) | DuckDB 확장 다운로드 불가 | 온라인 PC에서 같은 DuckDB 버전으로 `INSTALL excel` 후 `%USERPROFILE%\.duckdb\extensions` 폴더 복사 |
| `.xls` 파일이 안 읽힘 | DuckDB excel 확장은 `.xls` 미지원 | Excel에서 `.xlsx`로 다른 이름 저장 ([docs](https://duckdb.org/docs/current/core_extensions/excel.html)) |
| 엑셀 집계 결과가 비거나 중복 | 병합셀 미처리 원본을 직접 적재 | 반드시 `unmerge_and_fill` 거친 정리본 적재 (§5) |
| frontmatter의 `parent` 링크가 그래프에 안 잡힘 | 속성 값 위키링크에 따옴표 누락 | `parent: "[[허브]]"` 형식이어야 함 ([Obsidian properties](https://help.obsidian.md/properties)). 본 가이드 코드는 자동 처리 |
| 위키링크가 과하게/엉뚱하게 걸림 | 짧은 노트명(2자)·일반명사 노트명 | `MAX_LINKS_PER_TERM` 유지, 문제 용어는 `build_term_map` 결과에서 제외(예: `terms.pop("회의", None)`), Note Linker로 검수 |
| `wikify.py`가 vault의 템플릿/일일노트까지 사전에 넣음 | `rglob("*.md")` 전체 스캔 | `build_term_map`에서 템플릿 폴더 스킵 조건 추가 (예: `if "templates" in md.parts: continue`) |
| 첫 Docling 실행이 모델 다운로드로 멈춘 듯 보임 | HF 다운로드 (수 GB) | 정상. 오프라인 PC는 §3 `docling-tools models download` + `DOCLING_ARTIFACTS_PATH` 선행 |

---

## 11. 실측 과제 3건 (미확정 — 측정 방법)

| # | 과제 | 측정 방법 | 기록처 |
|---|---|---|---|
| 1 | GPU 사양별 처리 속도 | 대표 문서 5개(일반 PDF, 스캔 PDF, 표 위주, PPT, 이미지)로 Stage 1·Stage 4-② 소요 시간을 `Measure-Command { python parse_basic.py }`로 측정 | 로드맵 진행 로그에 수치로 |
| 2 | EasyOCR vs Tesseract `kor` 한국어 우열 | 같은 스캔 샘플 3개를 `EasyOcrOptions(lang=["ko","en"])` vs `TesseractCliOcrOptions(lang=["kor","eng"])`(Tesseract 별도 설치 필요)로 변환해 오인식 글자 수 비교. 일반론 근거가 없어 **본인 문서로만 판정 가능** | 〃 |
| 3 | 노트 분할 임계값 (`SPLIT_THRESHOLD=8000`) | 장문 PDF 1개를 4000/8000/16000으로 바꿔 wikify→ingest 후, 골든셋(P0)의 해당 문서 질문으로 Hit@5 비교 | 〃 + 확정값을 `wikify.py`에 반영 |

---

## 12. 내가 다음에 할 일

- [ ] §3 사전 준비 실행 (패키지 설치 + `qwen2.5vl:7b` pull + inbox/parsed 폴더)
- [ ] `wikify.py`의 `VAULT_PATH`를 **본인 PC의 실제 vault 경로**로 수정 (CLAUDE.md 규칙: `C:\jh104\MyVault` 가정 금지)
- [ ] 보유 샘플 파일 5개로 Stage 1 파서 PoC (로드맵 P1 체크박스: "Docling vs VLM 직접 파싱 비교" — Stage 1 출력과 Stage 4-② VLM 출력을 같은 파일로 비교)
- [ ] 엑셀 1개로 Stage 2 실행 → DuckDB 테이블 + 샘플 SQL 확인 (로드맵: "표 데이터 분리 적재 결정 — 스키마 초안")
- [ ] Stage 3~5 실행 → `ask_v3.py` 인용 확인 (로드맵: "`parse_to_wiki.py` 구현" + "vault 재인덱싱" 체크)
- [ ] §11 실측 3건 측정 → 결과를 로드맵 진행 로그에 수치로 기록
- [ ] 로드맵 `TODO-비정형데이터-확장-로드맵.md`의 P1 체크박스 갱신 + 진행 로그 1줄 append
- [ ] (다음 Phase) P2 리트리벌 향상 리서치: `/research-report ...` (로드맵 P2 참조)
