# setup.ps1 — 가이드 §3 사전 준비 자동화 (Windows 11 + PowerShell)
# 실행 위치: 이 폴더(권장: C:\jh104\obsidian-rag)에서 실행
# 실행 정책 오류가 나면 먼저: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# ---------- 1) Python 3.11 확인 (3.12 이상 금지 — chroma-hnswlib Windows 휠이 cp311까지만 제공) ----------
$pyVersion = $null
try { $pyVersion = & py -3.11 --version 2>$null } catch {}
if (-not $pyVersion) {
    Write-Host "[실패] Python 3.11을 찾을 수 없습니다." -ForegroundColor Red
    Write-Host "       설치 후 다시 실행하세요:  winget install Python.Python.3.11" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Python 3.11 확인: $pyVersion" -ForegroundColor Green

# ---------- 2) 가상환경 생성 + 활성화 ----------
if (-not (Test-Path ".\.venv")) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "[실패] venv 생성 실패" -ForegroundColor Red; exit 1 }
    Write-Host "[OK] 가상환경(.venv) 생성" -ForegroundColor Green
} else {
    Write-Host "[OK] 가상환경(.venv) 이미 존재 — 재사용" -ForegroundColor Green
}
try {
    . .\.venv\Scripts\Activate.ps1
    Write-Host "[OK] 가상환경 활성화" -ForegroundColor Green
} catch {
    Write-Host "[실패] 가상환경 활성화 실패. 실행 정책 확인:" -ForegroundColor Red
    Write-Host "       Set-ExecutionPolicy -Scope CurrentUser RemoteSigned" -ForegroundColor Yellow
    exit 1
}

# ---------- 3) 패키지 설치 ----------
Write-Host "`npip install -r requirements.txt 실행 중... (수 분 소요)" -ForegroundColor Cyan
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[실패] 패키지 설치 실패." -ForegroundColor Red
    Write-Host "       chroma-hnswlib 빌드 오류라면 Python 3.12+ 사용이 원인 — 가이드 §14 참조" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] requirements.txt 설치 완료" -ForegroundColor Green

# ---------- 4) Ollama 확인 + 생성용 LLM 다운로드 ----------
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "[실패] Ollama가 설치되어 있지 않습니다." -ForegroundColor Red
    Write-Host "       설치 후 다시 실행하세요:  winget install Ollama.Ollama" -ForegroundColor Yellow
    exit 1
}
Write-Host "[OK] Ollama 설치 확인" -ForegroundColor Green
Write-Host "qwen2.5:7b 모델 다운로드 중... (최초 1회, 약 4.7GB)" -ForegroundColor Cyan
ollama pull qwen2.5:7b
# RAM 16GB 미만이면 위 줄 대신: ollama pull qwen2.5:3b  (단, 3b는 Qwen Research License 조건 확인)
if ($LASTEXITCODE -ne 0) {
    Write-Host "[실패] 모델 다운로드 실패. Ollama 서비스 실행 여부 확인 (ollama serve)" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] qwen2.5:7b 준비 완료" -ForegroundColor Green

# ---------- 5) (선택) 네트워크 제약 환경 대비 — 임베딩·리랭커 모델 사전 다운로드 ----------
# 인터넷이 되는 곳에서 미리 받아 캐시해 두려면 아래 주석을 해제:
# pip install -U "huggingface_hub[cli]"
# hf download nlpai-lab/KURE-v1
# hf download BAAI/bge-reranker-v2-m3
# 이후 오프라인에서는:  $env:HF_HUB_OFFLINE = "1"

Write-Host "`n===== 사전 준비 완료 =====" -ForegroundColor Green
Write-Host "최종 확인:  ollama run qwen2.5:7b `"안녕하세요라고만 답해`"  → 인사말이 나오면 §3 통과"
Write-Host "다음 단계: ingest.py 상단 VAULT_PATH 수정 후  python ingest.py"
