"""Test full pipeline: hbk_parser -> indexer -> search."""

import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
from indexer import HbkIndexer

workbench_root = Path(os.environ.get("WORKBENCH_ROOT", Path(__file__).resolve().parents[2]))
db_path = workbench_root / "generated" / "help-index" / "help-index.db"
hbk_dir = Path(os.environ.get("HBK_DIR", r"C:\Program Files (x86)\1cv8t"))
hbk_candidates = sorted(hbk_dir.glob("**/*_ru.hbk"))
if not hbk_candidates:
    raise FileNotFoundError(f"No *_ru.hbk files found under {hbk_dir}. Set HBK_DIR to a local 1C platform bin directory.")
hbk_path = hbk_candidates[0]

indexer = HbkIndexer(db_path)
count = indexer.index_hbk(hbk_path)
print("Indexed: %d topics" % count)
print("Stats: %s" % indexer.stats())

# Search tests
for q in ["запуск", "1С", "конфигурация", "интерфейс", "установка"]:
    results = indexer.search(q, limit=3)
    print("\nSearch '%s': %d results" % (q, len(results)))
    for r in results:
        print("  [%s] %s (cat=%s) rank=%.4f" % (r["topic_id"], r["title"], r["category"], r["rank"]))

# Get tree
tree = indexer.get_tree(0)
print("\nTree roots: %d" % len(tree))
for r in tree[:5]:
    print("  [%s] %s / %s" % (r["topic_id"], r["title_ru"], r["html_path"]))

# Get specific topic
topic = indexer.get_topic(1)
print("\nTopic 1: %s" % topic)

indexer.close()
print("\nDONE")
