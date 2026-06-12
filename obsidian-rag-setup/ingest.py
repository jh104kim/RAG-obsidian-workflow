# ingest.py — vault 읽기 → 노트 단위 청킹 → 임베딩 → Chroma 저장 (+ chunks.json / graph.json 생성)
# 가이드 §5.1 기준. §10.1 Contextual Retrieval 교체 코드는 USE_CONTEXTUAL_RETRIEVAL 플래그로 반영
# (가이드 §10 트리거: RAGAS context_recall < 0.7일 때만 True로 변경 후 전체 재인덱싱)
import json
import re
from pathlib import Path

import chromadb
import ollama  # §10.1 Contextual Retrieval용 (USE_CONTEXTUAL_RETRIEVAL=True일 때 사용)
from chromadb.config import Settings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from llama_index.readers.obsidian import ObsidianReader
from sentence_transformers import SentenceTransformer

# ===== 사용자 수정 지점 (이 블록만 본인 환경에 맞게 수정) =====
VAULT_PATH = r"C:\jh104\MyVault"          # TODO: 본인 경로로 수정 (Obsidian vault 경로)
EMBED_MODEL = "nlpai-lab/KURE-v1"          # 느리거나 한영 혼용 노트가 많으면 "BAAI/bge-m3"
USE_CONTEXTUAL_RETRIEVAL = False           # §10.1 — RAGAS context_recall < 0.7일 때만 True (Ollama 실행 필요)
# ==============================================================

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

# §10.1 Contextual Retrieval — 청크에 노트 전체 기준의 맥락 요약을 부착
def add_context(note_text: str, chunk_text: str) -> str:
    r = ollama.chat(model="qwen2.5:7b", messages=[{"role": "user", "content":
        f"<문서>\n{note_text[:4000]}\n</문서>\n위 문서에서 아래 청크의 위치와 맥락을 "
        f"한국어 1~2문장으로 설명하라. 설명만 출력하라.\n<청크>\n{chunk_text[:1500]}\n</청크>"}])
    # ollama SDK 0.4.x: ChatResponse 객체 — .message.content 로 접근
    return r.message.content.strip() + "\n" + chunk_text

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
        if USE_CONTEXTUAL_RETRIEVAL and section:   # §10.1: 헤더 분할된 청크에만 맥락 부착
            body = add_context(text, body)         # text = 해당 노트 전문 (루프 변수)
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
