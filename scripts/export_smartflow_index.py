"""
Export the SmartFlow print archive to a single JSON file for cloud hosting.

Usage:
    python scripts/export_smartflow_index.py

Output:
    smartflow_index.json  (in project root)

Then upload that file to your S3 or Cloudflare R2 bucket (public read),
and set SMARTFLOW_INDEX_URL=https://your-bucket.../smartflow_index.json
in your Railway environment variables.
"""
import json
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.config import SMARTFLOW_XML_DIR
from app.smartflow import _parse_file

def main():
    xml_dir = SMARTFLOW_XML_DIR
    if not xml_dir or not os.path.isdir(xml_dir):
        print(f"ERROR: SMARTFLOW_XML_DIR not set or not found: {xml_dir!r}")
        print("Set SMARTFLOW_XML_DIR in your .env file and try again.")
        sys.exit(1)

    files = list(Path(xml_dir).rglob("*.xml"))
    print(f"Found {len(files)} XML files in {xml_dir}")

    articles = []
    for i, f in enumerate(files):
        if i % 1000 == 0:
            print(f"  Parsing {i}/{len(files)}...")
        article = _parse_file(str(f))
        if article:
            articles.append(article)

    articles.sort(key=lambda a: a.get("published-at", 0), reverse=True)
    print(f"Parsed {len(articles)} valid articles")

    out_path = Path(__file__).parent.parent / "smartflow_index.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"Written to {out_path} ({size_mb:.1f} MB)")
    print()
    print("Next steps:")
    print("  1. Upload smartflow_index.json to your S3 or Cloudflare R2 bucket")
    print("  2. Make the file publicly readable")
    print("  3. Copy the public URL")
    print("  4. Set SMARTFLOW_INDEX_URL=<url> in Railway environment variables")

if __name__ == "__main__":
    main()
