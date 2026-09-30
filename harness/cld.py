# -*- coding: utf-8 -*-
"""closed-loop-dev 하네스 진입점 — 표준 라이브러리만 쓴다(Python 3.11+).

사용 예:
    python .cld/harness/cld.py status
    python .cld/harness/cld.py prompt build P2 --out prompt.txt
    python .cld/harness/cld.py handover check
    python .cld/harness/cld.py gates run --out <스크래치>
    python .cld/harness/cld.py patch spec.json --check
    python .cld/harness/cld.py tree <rev> --out <스크래치>/tree
    python .cld/harness/cld.py verify scope <base> <head>

하위 명령의 자세한 인자는 ``python cld.py <명령> --help`` 로 본다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cldlib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
