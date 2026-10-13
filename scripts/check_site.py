#!/usr/bin/env python3
"""
check_site.py — pemeriksa ringan untuk repo statis (HTML/CSS/JS/dokumentasi).

Dipakai oleh CI di repo yang tidak punya langkah build, mis:
  axryzure-hystori-cosmic, web-memperingati-maulid-nabi,
  belajar-coding-dasar, termux-linux-distro-guide

Yang diperiksa:
  • HTML : <title> terisi, meta viewport ada, atribut lang ada,
           dan semua src/href lokal menunjuk file yang benar-benar ada.
  • MD   : semua tautan/gambar relatif ada; tingkat heading tidak melompat.
  • JS   : sintaks valid (memakai `node --check`, mendukung ESM).

Jalankan manual: python3 scripts/check_site.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".github"}

errors: list[str] = []
warnings: list[str] = []


def err(m: str) -> None:
    errors.append(m)


def warn(m: str) -> None:
    warnings.append(m)


def iter_files(suffixes: tuple[str, ...]):
    for path in sorted(ROOT.rglob("*")):
        # hanya folder di dalam repo yang dilewati (bukan nama folder induk)
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


# ---------------------------------------------------------------- HTML
def check_html(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")

    if not re.search(r"<title>\s*\S", text, re.I):
        err(f"{rel(path)}: <title> kosong atau hilang")
    if not re.search(r'<meta[^>]+name=["\']viewport["\']', text, re.I):
        err(f"{rel(path)}: meta viewport hilang (tampilan rusak di HP)")
    if not re.search(r"<html[^>]+lang=", text, re.I):
        err(f"{rel(path)}: atribut lang pada <html> hilang")

    for attr, value in re.findall(r'\b(src|href)=["\']([^"\']+)["\']', text, re.I):
        v = value.strip()
        if v.startswith(("http://", "https://", "//", "data:", "mailto:", "tel:", "#", "javascript:")):
            continue
        target = (path.parent / v.split("#")[0].split("?")[0]).resolve()
        if not target.exists():
            err(f"{rel(path)}: {attr} menunjuk file yang tidak ada → {value}")


# ---------------------------------------------------------------- MD
def check_md(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")

    for target in re.findall(r"!?\[[^\]]*\]\(([^)\s]+)\)", text):
        if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
            continue
        clean = target.split("#")[0].split("?")[0]
        if not clean:
            continue
        if not (path.parent / clean).exists():
            err(f"{rel(path)}: tautan/gambar relatif tidak ditemukan → {target}")

    level_sebelumnya = 0
    for nomor, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^(#{1,6})\s+\S", line)
        if not m:
            continue
        level = len(m.group(1))
        if level_sebelumnya and level > level_sebelumnya + 1:
            warn(f"{rel(path)}:{nomor}: tingkat heading melompat (H{level_sebelumnya} → H{level})")
        level_sebelumnya = level


# ---------------------------------------------------------------- JS
def check_js(path: Path) -> None:
    res = subprocess.run(
        ["node", "--check", str(path)], capture_output=True, text=True
    )
    if res.returncode == 0:
        return

    # coba sebagai ES module (file .js dengan import/export)
    if "import" in res.stderr or "export" in res.stderr or "Unexpected token 'export'" in res.stderr:
        with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as tmp:
            tmp.write(path.read_text(encoding="utf-8", errors="replace"))
            tmp_path = tmp.name
        res2 = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
        Path(tmp_path).unlink(missing_ok=True)
        if res2.returncode == 0:
            return
        res = res2

    baris = (res.stderr or "").strip().splitlines()
    kandidat = [l.strip() for l in baris if re.search(r"\b\w*Error\b", l)]
    ringkas = kandidat[-1] if kandidat else (baris[0] if baris else "tidak diketahui")
    err(f"{rel(path)}: sintaks JavaScript tidak valid → {ringkas}")


def main() -> int:
    for p in iter_files((".html",)):
        check_html(p)
    for p in iter_files((".md",)):
        check_md(p)
    for p in iter_files((".js", ".mjs")):
        check_js(p)

    print("=" * 60)
    print(f"Pemeriksaan repo statis — {ROOT.name}")
    print("=" * 60)
    for w in warnings:
        print(f"  [peringatan] {w}")
    for e in errors:
        print(f"  [GAGAL]      {e}")
    if errors:
        print(f"\n  ❌ {len(errors)} masalah harus diperbaiki.")
        return 1
    print(f"\n  ✅ Semua pemeriksaan lulus ({len(warnings)} peringatan).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
