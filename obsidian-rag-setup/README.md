# obsidian-rag-setup — 실행 순서

`RAG-Obsidian-구축-가이드.md`에서 추출한 실행 파일 패키지. 모든 명령은 Windows 11 + PowerShell 기준.

> **다른 PC / 다른 vault에서 사용할 때**: 이 패키지는 vault 경로에 의존하지 않는다.
> ① 폴더를 그 PC의 원하는 위치로 복사하고 ② `ingest.py`·`check_vault.py` 상단 `VAULT_PATH`만 **그 PC의 실제 vault 경로**로 바꾸면 끝.
> (아래 표의 `C:\jh104\obsidian-rag`는 가이드 기본값일 뿐, 다른 경로도 무방)

## 실행 순서

| 순서 | 명령 | 완료 확인 (가이드 체크 기준) |
|---|---|---|
| 1 | 이 폴더 전체를 `C:\jh104\obsidian-rag` 로 복사 | 폴더에 requirements.txt, *.py 존재 |
| 2 | `cd C:\jh104\obsidian-rag` → `.\setup.ps1` | 단계별 `[OK]` 출력 후, `ollama run qwen2.5:7b "안녕하세요라고만 답해"` 가 인사말 출력 (§3) |
| 3 | `ingest.py`·`check_vault.py` 상단 `VAULT_PATH`를 본인 vault 경로로 수정 | — |
| 4 | (선택) `python check_vault.py` | `표준 키 누락 0건` 이면 통과. 0이 아니어도 다음 진행 가능 (§4.3) |
| 5 | `python ingest.py` | `노트 N개 → 청크 M개` 출력, 마지막 줄 `완료: M개 청크 인덱싱` (M > 0), 폴더에 `chroma_db\`·`chunks.json`·`graph.json` 생성 (§5.1) |
| 6 | `python ask_v3.py` | 노트 근거 한국어 답변 + `참고:` 출력. `[사용된 청크]`에 직접 검색된 노트 외 연결 이웃 노트가 함께 보이면 통과 (§7) |
| 7 | `goldenset.json`의 빈 문항을 본인 vault 기반으로 채움 → `python evaluate.py` | 유형별/전체 Hit@k·MRR·nDCG@k 표 + 실패 질문 id 출력, `eval_results\` 에 결과 JSON 저장 (LLM 불필요) |
| 8 | (선택) `python evaluate.py --ragas` | faithfulness / answer_relevancy / context_precision / context_recall 4개 숫자 출력 → 기록 (§8). 기존 `eval_rag.py` 단독 실행도 가능 |

## 골든셋 평가 (goldenset.json + evaluate.py)

**goldenset.json 작성 요령** (30문항 틀 — 유형별 첫 항목이 작성 예시, 작성 후 `EXAMPLE-` 문항은 삭제):

| 유형 | 문항 수 | 의도 |
|---|---|---|
| fact | 10 | 단일 노트의 사실 조회 |
| summary | 8 | 한 주제의 요약/설명 |
| keyword | 6 | 고유명사·정확 매칭 — BM25 강점 검증 |
| multihop | 6 | 2개 이상 노트 연결 — 위키링크 확장 검증 |

- `expected_notes`: 정답 근거가 들어있는 노트의 **파일명(확장자 제외)** 리스트. 리트리벌 적중 판정 기준이므로 정확히 적을 것 (multihop은 2개 이상).
- `ground_truth`: 정답 문장 — `--ragas` 측정에만 사용. 비워두면 해당 문항은 RAGAS에서 제외.
- question이 빈 문항과 `EXAMPLE-` 문항은 측정에서 자동 제외(건수 보고됨).

**실행**:

- `python evaluate.py` — 리트리벌 지표만 (Hit@k/MRR/nDCG@k, LLM 불필요). 실패 질문(Hit=0) id 목록이 P3 진입 판단 자료.
- `python evaluate.py --hop` — 위키링크 1-hop 확장 포함 판정 (확장 효과 A/B 비교).
- `python evaluate.py --ragas` — 답변 생성 후 RAGAS 4지표 추가 (Ollama 필요).
- 결과는 매회 `eval_results\YYYY-MM-DD_HHMM.json`으로 저장 — 인덱싱/설정 변경 전후 비교에 사용.

## 단계별 비교용 (선택)

- `ask_v1.py` (벡터 검색만) / `ask_v2.py` (하이브리드+리랭킹) — v1이 놓친 고유명사 질문 N개 중 v2가 ceil(N/2)개 이상 적중하면 Stage 2 통과 (§6).

## 평가 후 고급화 판단 (§10)

- `context_recall < 0.7` → `ingest.py` 상단 `USE_CONTEXTUAL_RETRIEVAL = True`로 바꾸고 재인덱싱 (Contextual Retrieval, §10.1)
- 트리거 미충족 → 고급화 도입하지 않음 (가이드 결론)

## 기타 파일

- `publishing\export-ignore.example` — vault 최상위에 `.export-ignore`로 복사 (Stage 5 비공개 노트 차단, §12.1)
- `publishing\deploy.yml` — Quartz 저장소의 `.github\workflows\deploy.yml` 로 복사 (§12.3)
