from __future__ import annotations

import json

from vietnamese_legal_parser import parse_structure

TEXT = """\
Chương I
QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
1. Văn bản này quy định về ví dụ sử dụng parser.
a) Điểm thứ nhất;
b) Điểm thứ hai.
"""

result = parse_structure(TEXT, include_diagnostics=True)
print(json.dumps(result, ensure_ascii=False, indent=2))
