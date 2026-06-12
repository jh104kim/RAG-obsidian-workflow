# check_vault.py — frontmatter 표준 키 누락 점검 (가이드 §4.3)
import re
from pathlib import Path

# ===== 사용자 수정 지점 =====
VAULT_PATH = r"C:\jh104\MyVault"   # TODO: 본인 경로로 수정 (Obsidian vault 경로)
# ===========================
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
