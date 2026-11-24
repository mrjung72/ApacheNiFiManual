"""HTML 문서의 텍스트 노드를 영어→한국어로 번역해 _ko.html을 생성합니다.

- 코드/스크립트/스타일 등 번역 제외 태그는 원문 유지
- 번역은 Argos Translate(오프라인) 사용 — 외부 API 불필요
- 이미 *_ko.html이 있으면 스킵 (--force로 강제)

사용 예:
    python translate_html.py docs/html/overview.html
    python translate_html.py docs/html/ --all
"""
import argparse
import os
import re
import sys
import time

from bs4 import BeautifulSoup, NavigableString, Comment, Doctype

import argostranslate.package
import argostranslate.translate

# 번역하지 않고 원문을 유지할 태그
SKIP_TAGS = {
    "script", "style", "code", "pre", "kbd", "samp", "var",
    "math", "svg", "noscript", "template",
}
# 태그는 유지하되 내용만 번역
ALPHA_RE = re.compile(r"[A-Za-z]")

_cache = {}
_stats = {"nodes": 0, "chars": 0}


def tr(text: str) -> str:
    """문자열 번역 (캐시 적용)."""
    key = text
    if key in _cache:
        return _cache[key]
    # 공백/기호만 있거나 알파벳이 거의 없으면 번역 생략
    letters = len(ALPHA_RE.findall(text))
    if letters < 3 or letters / max(len(text), 1) < 0.3:
        _cache[key] = text
        return text
    # 너무 긴 텍스트는 문장 단위로 나눠 번역
    if len(text) > 1500:
        parts = re.split(r"(?<=[.!?])\s+", text)
        out = " ".join(tr(p) if len(p) > 20 else p for p in parts)
    else:
        try:
            out = argostranslate.translate.translate(text, "en", "ko")
        except Exception:
            out = text
    _cache[key] = out
    _stats["nodes"] += 1
    _stats["chars"] += len(text)
    return out


def translate_file(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang") == "en":
        html_tag["lang"] = "ko"

    for node in list(soup.find_all(string=True)):
        if isinstance(node, (Comment, Doctype)):
            continue
        parent = node.parent
        if parent is None or parent.name in SKIP_TAGS:
            continue
        text = str(node)
        if not text.strip():
            continue
        # 태그 내부 공백 구조 유지를 위해 앞뒤 공백을 분리해 번역
        stripped = text.strip()
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        translated = tr(stripped)
        if translated != stripped:
            node.replace_with(lead + translated + trail)

    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(str(soup))
    print(f"완료: {dst} (번역 노드 {_stats['nodes']:,}개, "
          f"{_stats['chars']:,}자)", flush=True)


def main():
    ap = argparse.ArgumentParser(description="HTML 영어→한국어 번역")
    ap.add_argument("path", help="HTML 파일 또는 디렉토리")
    ap.add_argument("--all", action="store_true", help="디렉토리 내 전체 *.html")
    ap.add_argument("--force", action="store_true", help="기존 _ko.html 덮어쓰기")
    args = ap.parse_args()

    if os.path.isdir(args.path):
        files = sorted(
            os.path.join(args.path, f)
            for f in os.listdir(args.path) if f.endswith(".html")
            and not f.endswith("_ko.html")
        )
    else:
        files = [args.path]

    for src in files:
        dst = src[:-5] + "_ko.html"
        if os.path.exists(dst) and not args.force:
            print(f"스킵(이미 존재): {dst}", flush=True)
            continue
        _stats.update(nodes=0, chars=0)
        _cache.clear()
        t0 = time.time()
        translate_file(src, dst)
        print(f"  소요 {time.time() - t0:.0f}초", flush=True)


if __name__ == "__main__":
    main()
