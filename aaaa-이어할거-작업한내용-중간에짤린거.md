비정형 데이터를 현재의 기준으로 정리하는 방법을 알려줘. 비정형 엑셀, 그림, 테이블, ppt, pdf등 db화로 text to sql or 파싱 or RAG or graph DB 어떤 상황에 어떤걸 사용해야하나? 그리고 쿼리 정확도 평가 방법 및 최근 기법으로 향상하는 거 까지 아이디어 있으면 같이 검토해서 알려줘

4시간 전

로드된 도구, 웹 검색됨, 코드 검색됨
로드된 도구, 웹 검색됨, 코드 검색됨
비정형 데이터 → DB화 기술 선택과 평가/향상 기법을 정리합니다. (BIRD 리더보드 등 2026년 6월 현재 기준 확인함)

1. 기술 선택: 핵심 기준 2가지
① 데이터 성격 ② 질문 유형으로 결정합니다.

상황	선택	이유
수치 집계·필터·정렬 질문 ("작년 매출 합계는?")	파싱 → 정형 DB + Text-to-SQL	집계는 LLM이 아니라 SQL이 해야 정확
의미 검색·요약 질문 ("계약서에서 위약금 조항은?")	파싱 → 청킹 → RAG	정답이 텍스트 안에 있음
엔티티 간 관계·다단계 추론 ("A사와 거래한 회사들의 공통 협력사는?")	Graph DB (GraphRAG)	벡터 검색은 2-hop 이상 관계를 못 따라감
둘 다 섞임 (실무 대부분)	하이브리드 + 라우터	질문을 LLM이 분류해 SQL/RAG/Graph로 분기
핵심: 이 4개는 경쟁 관계가 아니라, 파싱이 공통 전처리이고 나머지는 질문 유형별 분기입니다.

2. 파일 형식별 파싱 전략
형식	권장 도구	처리 방향
비정형 엑셀 (병합셀, 다중 헤더)	openpyxl + LLM 정규화, 또는 Docling	표 구조 복원 → tidy 형태(1행=1레코드)로 펴서 RDB 적재
PDF (디지털)	Docling (IBM, 레이아웃·표 인식), MinerU	표는 → DB, 본문은 → RAG 청크로 분리
PDF (스캔/이미지)	OCR(PaddleOCR 등) 또는 VLM 직접 파싱 (GPT-4o/Claude에 이미지로 투입)	최근엔 OCR보다 VLM 파싱이 표 복원 정확도 높음
PPT	python-pptx로 텍스트/표 추출 + 슬라이드 이미지를 VLM 캡셔닝	슬라이드는 시각 정보가 핵심이라 텍스트만 뽑으면 손실 큼
그림/차트	ColPali/ColQwen 계열 (페이지를 이미지 그대로 임베딩)	파싱 자체를 생략하는 멀티모달 RAG. 파싱 실패 위험 제거
Docling: 문서 레이아웃·표를 구조화된 JSON/Markdown으로 추출하는 오픈소스 파서
ColPali: 문서 페이지 이미지를 직접 벡터화해 텍스트 추출 없이 검색하는 모델
3. 쿼리 정확도 평가 방법
Text-to-SQL:

지표	의미
EX (Execution Accuracy)	생성 SQL 실행 결과가 정답 결과와 일치하는지. 표준 지표
EM (Exact Match)	SQL 문자열 일치. 같은 답도 다른 SQL이 가능해 잘 안 씀
Test-suite accuracy	여러 DB 인스턴스에서 실행해 우연한 일치 제거
벤치마크 현실 (2026.6 BIRD 기준): 테스트 1위 ~82% vs 인간 93%. 멀티턴 상호작용 평가(BIRD-Interact)에선 최고 모델도 ~16%. → Text-to-SQL은 아직 100% 신뢰 불가, 검증 루프가 필수라는 뜻.

RAG: 이미 가이드에 있는 RAGAS 4지표(faithfulness, answer relevancy, context precision/recall) + 검색 단계는 Hit@k, MRR, nDCG로 분리 측정. nDCG: 상위 랭킹에 정답 문서가 있을수록 높은 점수를 주는 검색 품질 지표

공통: 평가셋이 없으면 LLM으로 합성 Q&A 생성(RAGAS testset generator) → LLM-as-judge로 채점 → 사람이 샘플 검수.

4. 최근 정확도 향상 기법
Text-to-SQL:

후보 다중 생성 + 선택: SQL을 N개 생성, 실행 결과로 다수결/선택 (CHASE-SQL, XiYan-SQL 방식). 가장 효과 큼
Schema linking: 전체 스키마 대신 질문 관련 테이블·컬럼만 추려 프롬프트에 투입
실행 기반 self-correction: SQL 실행 → 에러/빈 결과면 에러 메시지를 보고 재생성
시맨틱 레이어: 컬럼별 설명·용어 사전·대표값을 메타데이터로 제공. 실무에서 체감 효과 최대
Agentic 멀티턴: 모호한 질문은 되묻기. 2026년 벤치마크 트렌드가 단발 생성 → 상호작용 평가로 이동 중
RAG:

하이브리드 검색(BM25+벡터) + 리랭커 — 이미 사용자 가이드에 반영됨
Query rewriting/decomposition: 질문을 검색 친화적으로 재작성하거나 하위 질문 분해
Agentic RAG: 검색 결과가 부족하면 스스로 재검색 판단
GraphRAG: 청크에서 엔티티·관계 추출 → 그래프 구축 + 커뮤니티 요약으로 "전체 조망형 질문"("이 문서들의 주요 테마는?") 대응. 단, 구축 비용(LLM 호출)이 커서 관계형 질문이 실제로 많을 때만
5. 추천 아키텍처 (검토 의견)
지금 진행 중인 Obsidian RAG와 결합한다면:

파일 입수 → Docling 파싱 → ① 표 → SQLite/DuckDB
                          ② 본문 → Chroma (기존 RAG)
                          ③ 이미지·차트 → VLM 캡션 후 ②에 합류
질문 → LLM 라우터 → SQL 경로(집계) / RAG 경로(의미) → 답변 + 출처
GraphDB는 1단계에서 빼는 걸 권합니다. 관계형 질문 빈도가 확인된 후 추가해도 늦지 않고, 유지비가 큽니다. 평가는 질문 30~50개 골든셋부터 만들고 EX(SQL)·RAGAS(RAG)를 경로별로 따로 측정하는 게 순서입니다.

원하시면 이 내용을 리서치 폴더에 노트(md)로 저장하거나, /research-report용 주제로 확장해 드릴 수 있습니다.

4시간 전
리서치 폴더 노트에 "적절한 이름"으로 저장해주고, /research-report용 주제로 확장해서, 실제 비정형 데이터를 옵시디언 wiki화와 같이 위 rag 구축 및 리트리벌 정확도 향상을 위한 조사 및 추후 graph db 연계 및 옵시디언의 wiki graph 스킬을 이용하는 것까지 확장할 수 있도록 todo  리스트 및 진행 중 저장할 수 있도록 해줘. claude md가 필요하면 반영해줘

4시간 전

도구 9개 사용함, 3개의 파일 생성됨, 2개 파일 읽음
도구 9개 사용함, 3개의 파일 생성됨, 2개 파일 읽음
MOC에 새 노트 링크를 추가합니다.


파일 수정됨, 파일 읽음
파일 수정됨, 파일 읽음
완료했습니다. 3개 파일 생성 + MOC 갱신:

비정형데이터-DB화-기술선택.md — 이전 답변을 위키링크 달린 Obsidian 노트로 저장
TODO-비정형데이터-확장-로드맵.md — Phase 0~4 체크박스 TODO + Phase별 /research-report 명령(복붙용) + append-only 진행 로그. 이 파일이 진행 상태의 단일 출처(SSOT)
CLAUDE.md — Claude Code가 세션 시작 시 로드맵을 읽고, 체크박스·진행 로그를 갱신하며, Phase 가이드는 가이드-P{N}-*.md로 저장(기존 가이드 덮어쓰기 방지)하도록 규칙 반영
참고: 기존 MOC에 "GraphRAG는 위키링크 1-hop으로 대체(불필요 판정)" 기록이 있어, 로드맵에서도 P3(GraphRAG)는 실패 사례 확인 시에만 진입하는 조건부로, P4(위키링크 그래프 활용)를 본명으로 설계했습니다.


C:\jh104\리서치\비정형데이터-DB화-기술선택.md
문서 

C:\jh104\리서치\TODO-비정형데이터-확장-로드맵.md
문서 

C:\jh104\리서치\CLAUDE.md
문서 
4시간 전
그럼 phase 0부터 진행하면 되나?

4시간 전

사고 과정
사고 과정
네, Phase 0부터가 맞습니다. 단, 항목별로 실행 위치가 다릅니다:

P0 항목	어디서	비고
① critic 라운드 2 심사	여기서 바로 가능	.claude/agents/critic.md 기준을 읽어 가이드를 심사하고, 수정 필요 시 writer 규칙대로 고칠 수 있음
② RAG 실제 구축	본인 PC (Claude Code)	Ollama·venv·모델 다운로드가 본인 환경에서 돌아야 함. 저는 격리 환경이라 대신 실행 불가
③ 골든셋 30문항 작성	여기서 가능 (틀 제공)	단, 질문·정답은 본인 vault 내용 기반이라 최종 작성은 직접
권장 순서: ① 심사를 지금 여기서 끝내고 → ②는 Claude Code에서 "이어서 해줘"로 진행 (CLAUDE.md가 로드맵을 읽고 안내함) → ③은 구축 직후.

①번 critic 심사를 지금 바로 시작할까요? 완료되면 로드맵 체크박스와 진행 로그도 갱신해 두겠습니다.

4시간 전
진행하자

4시간 전

도구 4개 사용함, 파일 읽음, 에이전트 실행됨
도구 4개 사용함, 파일 읽음, 에이전트 실행됨
Critic 라운드 2 결과: REVISION NEEDED (치명 3 / 보통 2 / 사소 4)

치명 지적 — 모두 실제 설치 테스트로 확인됨:

requirements.txt 설치 불가 — ragas 0.1.21(langchain-core<0.3)과 langchain 계열(≥0.3)이 충돌해 pip install 즉시 실패
Python 3.12/3.13에서 chromadb 0.6.3 설치 실패 — chroma-hnswlib Windows 휠이 cp311까지만 존재
§13 graphrag init 명령이 고정 버전(0.3.6)에 존재하지 않음 — 실제는 python -m graphrag.index 방식
→ writer 수정 후 critic 라운드 3 재심사로 넘어갑니다.


도구 2개 사용함, 파일 읽음, 에이전트 실행됨
도구 2개 사용함, 파일 읽음, 에이전트 실행됨
Writer 수정 완료 — 변경점: [라운드 2] 지적 9건 전부 반영

ragas 0.2.15로 통일 (pip dry-run으로 충돌 해소 실측), eval_rag.py를 새 EvaluationDataset API로 교체
Python 3.11 핀 명시 (3.12+ 금지 사유·트러블슈팅 추가)
graphrag 1.2.0으로 상향 (콘솔 CLI 존재 실측 확인)
frontmatter type/tags → Chroma metadata 저장 코드 추가 (필터 예시 포함)
MOC GraphRAG 모순 해소 + 사소 4건 반영
→ critic 라운드 3 재심사 진행 중...


로드된 도구, 에이전트 실행됨
로드된 도구, 에이전트 실행됨
You've hit your session limit · resets 12:50pm (Asia/Seoul)

critic 라운드 3 재심사를 다시 실행합니다 (직전 시도는 세션 한도로 중단됨).


4개 파일 수정됨, 2개의 패턴 검색됨, 에이전트 실행됨
4개 파일 수정됨, 2개의 패턴 검색됨, 에이전트 실행됨
검증 통과. 가이드에 반영합니다.


2개 파일 수정됨, 명령 2개 실행함, 파일 읽음
2개 파일 수정됨, 명령 2개 실행함, 파일 읽음
마운트 동기화 지연으로 보입니다. 잠시 후 재시도합니다.


명령 3개 실행함, 파일 읽음
명령 3개 실행함, 파일 읽음
수정 확인 완료. 로드맵을 갱신합니다.


도구 3개 사용함, 2개 파일 수정됨, 파일 읽음
도구 3개 사용함, 2개 파일 수정됨, 파일 읽음
P0-① 완료 — 최종 판정: APPROVED (라운드 3, 치명 0건)

요약:

라운드 2: REVISION NEEDED (치명 3: requirements 충돌·Python 3.12 설치 실패·graphrag CLI 오류) → writer가 9건 전부 반영, 실측 검증 포함
라운드 3: APPROVED. 잔여 지적 3건(ollama 허위 오류 주장, 블록 리스트 tags 미지원, graphrag CLI 도입 시점)도 추가 반영 완료 — 코드 수정분은 기능 테스트 통과
로드맵 체크박스·진행 로그 갱신됨
다음 할 일 (P0-②): 본인 PC에서 cd C:\jh104\리서치 && claude 실행 후 "이어서 해줘" — CLAUDE.md가 로드맵을 읽고 RAG 실제 구축(가이드 §3 사전 준비)부터 안내합니다. 구축이 끝나면 P0-③ 골든셋 작성은 여기서 틀을 도와드릴 수 있습니다.


C:\jh104\리서치\RAG-Obsidian-구축-가이드.md
문서 

C:\jh104\리서치\TODO-비정형데이터-확장-로드맵.md
문서 
4시간 전
다음 할 일 (P0-②): 본인 PC에서 cd C:\jh104\리서치 && claude 실행 후 "이어서 해줘" — CLAUDE.md가 로드맵을 읽고 RAG 실제 구축(가이드 §3 사전 준비)부터 안내합니다. 구축이 끝나면 P0-③ 골든셋 작성은 여기서 틀을 도와드릴 수 있습니다.

위 po 2 진행하자


사고 과정
사고 과정
P0-②를 여기서 가능한 데까지 진행합니다. 실제 실행(venv·Ollama·인덱싱)은 본인 PC 몫이지만, 가이드에서 실행 파일들을 추출해 바로 돌릴 수 있는 코드 패키지로 만들어 두면 PC에서는 복사+실행만 하면 됩니다.


도구 7개 사용함, 2개 파일 수정됨, 에이전트 실행됨
도구 7개 사용함, 2개 파일 수정됨, 에이전트 실행됨
P0-② 준비 완료 — 여기서 가능한 부분은 끝났습니다. 리서치\obsidian-rag-setup\ 폴더에 실행 패키지 11개 파일을 만들었습니다 (py 6개 전부 구문 검증 통과).

이제 본인 PC에서 할 일 (순서대로, README에도 있음):

obsidian-rag-setup 폴더를 C:\jh104\obsidian-rag로 복사
PowerShell에서 .\setup.ps1 실행 — Python 3.11 확인·venv·패키지 설치·Ollama 모델 pull까지 자동
ingest.py 상단 VAULT_PATH를 본인 vault 경로로 수정 → python ingest.py
python ask_v3.py로 질의 테스트
참고: §10.1 Contextual Retrieval은 USE_CONTEXTUAL_RETRIEVAL = False 플래그로 꺼둔 상태입니다 (가이드 기준 — RAGAS context_recall < 0.7일 때만 켜는 조건부 기법).

구축이 끝나면 알려주세요. P0-③ 골든셋 30문항 틀 작성으로 넘어가겠습니다.


C:\jh104\리서치\obsidian-rag-setup\README.md
문서 

C:\jh104\리서치\obsidian-rag-setup\setup.ps1
 

C:\jh104\리서치\obsidian-rag-setup\ingest.py
 
지금 진행하는거는 다른 옵시디언 발루트가 있는데서 사용할 예정임. 지금까지 작업 및 todo list 및 관련 docs 업데이트하고 푸시해줘


도구 2개 사용함, 명령 실행함, 파일 읽음
도구 2개 사용함, 명령 실행함, 파일 읽음
Next, SETUP.md updates:


6개 파일 수정됨
6개 파일 수정됨
문서 업데이트 완료. 푸시 준비로 .gitignore를 만들어 둡니다.


파일 생성됨, 도구 사용함
파일 생성됨, 도구 사용함
업데이트 완료. 반영 내용:

SETUP.md — 현재 상태 표 갱신(critic APPROVED, 코드 패키지 완료), 파일 구조에 신규 파일 추가, "별도 PC의 다른 vault에서 운용" 주의 명시
CLAUDE.md — vault 경로를 가정하지 말고 사용자에게 확인하라는 규칙 추가
obsidian-rag-setup/README.md — 다른 vault에서 쓸 때 VAULT_PATH만 바꾸면 된다는 안내 추가
로드맵 — 체크박스·진행 로그 갱신
.gitignore — 신규 생성 (로컬 설정·RAG 산출물 제외)
푸시는 본인 PC에서 아래를 실행해 주세요 (이 폴더는 아직 git 저장소가 아니고, 제 환경엔 GitHub 인증이 없습니다):

powershell
cd C:\jh104\리서치
git init -b main
git add -A
git commit -m "RAG+Obsidian: 가이드 critic APPROVED, 실행 패키지(obsidian-rag-setup), P0~P4 로드맵"

# GitHub에서 빈 리포(private 권장)를 만든 뒤:
git remote add origin https://github.com/<계정>/<리포명>.git
git push -u origin main
운용 PC에서는 git clone 후 obsidian-rag-setup\README.md 순서대로 실행하면 됩니다.

https://github.com/jh104kim/RAG-obsidian-workflow.git 에 푸시 진행해줘


명령 4개 실행함
명령 4개 실행함
확인 결과: 저장소(jh104kim/RAG-obsidian-workflow)는 비어 있는 상태로 준비돼 있지만, 이 격리 환경에는 GitHub 인증 수단(토큰·SSH 키)이 없어 푸시가 불가능합니다. 계정 인증 정보를 제가 다루는 것도 안전 규칙상 할 수 없는 부분이라, 푸시만 본인 PC에서 실행해 주세요. 파일은 모두 준비된 상태라 아래를 그대로 붙여넣으면 끝납니다:

powershell
cd C:\jh104\리서치
git init -b main
git add -A
git commit -m "RAG+Obsidian: 가이드 critic APPROVED, 실행 패키지(obsidian-rag-setup), P0~P4 로드맵"
git remote add origin https://github.com/jh104kim/RAG-obsidian-workflow.git
git push -u origin main
푸시 시 Git Credential Manager가 브라우저로 GitHub 로그인 창을 띄울 겁니다 — 한 번 로그인하면 이후엔 자동입니다.

운용 PC에서는:

powershell
git clone https://github.com/jh104kim/RAG-obsidian-workflow.git C:\jh104\리서치
후 obsidian-rag-setup\README.md 순서대로 (setup.ps1 → VAULT_PATH 수정 → ingest.py → ask_v3.py) 진행하면 됩니다.

푸시 진행완료힘. 추가 진행할 작업 알려줘


파일 수정됨
파일 수정됨
다음으로 어떤 작업을 진행할까요?
P0-③ 골든셋 틀 (권장)
P0-③ 골든셋 틀 작업을 시작합니다.


도구 3개 사용함, 2개 파일 수정됨, 에이전트 실행됨
도구 3개 사용함, 2개 파일 수정됨, 에이전트 실행됨
P0-③ 골든셋 틀 완성.

goldenset.json — 30문항 틀 (fact 10 / summary 8 / keyword 6 / multihop 6). 유형별 첫 항목에 작성 예시 포함 (EXAMPLE- 표시, 작성 후 삭제)
evaluate.py — ask_v3의 리트리벌 파이프라인을 그대로 import해 Hit@k·MRR·nDCG 측정. --hop(위키링크 확장 A/B), --ragas(4지표) 플래그. 결과는 eval_results\에 이력 저장, Hit=0 실패 질문 목록이 P3(GraphRAG) 진입 판단 자료
README·로드맵 갱신 완료. 구문/JSON 검증 통과
새 파일들이 푸시 이후에 생겼으니 PC에서 한 번 더:

powershell
cd C:\jh104\리서치
git add -A && git commit -m "골든셋 틀(goldenset.json)+evaluate.py 추가" && git push
이제 남은 건 운용 PC에서 구축 → 골든셋 채우기 → python evaluate.py 베이스라인 측정입니다. 그게 끝나면 P1 리서치(비정형→Wiki화)로 넘어가면 되고, 원하면 P1 리서치는 구축과 무관하니 지금 미리 돌려둘 수도 있습니다.


C:\jh104\리서치\obsidian-rag-setup\goldenset.json
코드 

C:\jh104\리서치\obsidian-rag-setup\evaluate.py
 

C:\jh104\리서치\obsidian-rag-setup\README.md
문서 
진행하자.


사고 과정
사고 과정
P1 리서치 파이프라인(researcher → analyst → writer → critic)을 실행합니다.


도구 9개 사용함, 2개 파일 읽음, 에이전트 2개 실행됨
도구 9개 사용함, 2개 파일 읽음, 에이전트 2개 실행됨

Added task: P1 researcher 조사

결과

Added task: P1 analyst 분석

결과

Added task: P1 writer 가이드 작성

결과

Added task: P1 critic 심사 루프

결과

researcher.md 읽음

analyst.md 읽음

Updated task

결과

P1 researcher 웹 조사
31단계


Completed task

결과

Started task

결과

P1 analyst 의사결정 분석

Completed task

결과

Started task

결과
완료
researcher(소스 20개)·analyst(의사결정 표) 완료. 핵심 결론: Docling 단독 파서 + 그림/실패 페이지만 로컬 VLM(qwen2.5vl) 2단 + 엑셀은 md/DuckDB 이원화 + 위키링크는 규칙 매칭+LLM 병행 (한국어 조사 문제가 핵심 구현 포인트). 이제 writer가 가이드 초안을 작성합니다 (~5분).


P1 writer 가이드 작성
P1 writer 가이드 작성
You've hit your session limit · resets 5:50pm (Asia/Seoul)

문제가 발생했습니다
메시지를 다시 보내 보세요. 계속 발생하면 저희가 조사할 수 있도록 피드백을 공유해 주세요.

You've hit your session limit · resets 5:50pm (Asia/Seoul)
이전 메시지부터 대화를 다시 시작할 수 있습니다.

