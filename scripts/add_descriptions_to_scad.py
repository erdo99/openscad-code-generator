#!/usr/bin/env python3
"""
Tüm .scad dosyalarının en üstüne, dosya adından türetilmiş bir açıklama yorumu ekler.
Kullanım: python scripts/add_descriptions_to_scad.py [klasör_yolu]
Örnek:   python scripts/add_descriptions_to_scad.py data/files
"""
from pathlib import Path
import re
import sys


def description_from_filename(name: str) -> str:
    """Örnek: 136975448_hollow_cube.scad -> hollow cube"""
    # .scad kaldır
    base = name.replace(".scad", "").strip()
    # Baştaki sayı ve alt çizgiyi kaldır (123456_ veya 123456789_)
    base = re.sub(r"^\d+_", "", base)
    # Alt çizgileri boşluğa çevir
    base = base.replace("_", " ")
    # Birden fazla boşluğu tek yap
    base = re.sub(r"\s+", " ", base).strip()
    return base or "OpenSCAD shape"


def hints_from_code(code: str) -> list[str]:
    """Koddan kısa ipuçları (RAG için ek bağlam)."""
    hints = []
    code_lower = code.lower()
    if "cube(" in code_lower or "cube [" in code_lower:
        hints.append("cube")
    if "sphere(" in code_lower:
        hints.append("sphere")
    if "cylinder(" in code_lower or "cylinder [" in code_lower:
        hints.append("cylinder")
    if "difference()" in code_lower:
        hints.append("difference/cutout")
    if "union()" in code_lower:
        hints.append("union")
    if "intersection()" in code_lower:
        hints.append("intersection")
    if "translate(" in code_lower:
        hints.append("translate")
    if "rotate(" in code_lower or "rotate_extrude" in code_lower:
        hints.append("rotate")
    if "linear_extrude" in code_lower:
        hints.append("linear_extrude")
    if "rotate_extrude" in code_lower:
        hints.append("rotate_extrude")
    if "resize(" in code_lower or "resize [" in code_lower:
        hints.append("resize")
    if "hull()" in code_lower:
        hints.append("hull")
    if "minkowski()" in code_lower:
        hints.append("minkowski")
    if "scale(" in code_lower:
        hints.append("scale")
    return hints


def build_description(filename: str, code: str) -> str:
    """Dosya adı + koddan açıklama metni üretir."""
    desc = description_from_filename(filename)
    hints = hints_from_code(code)
    if hints:
        desc += " (" + ", ".join(hints[:4]) + ")"
    return desc


def has_description_line(lines: list[str]) -> bool:
    """İlk satırlarda '// Description:' veya '//Description:' var mı?"""
    for line in lines[:3]:
        if re.match(r"\s*//\s*Description\s*:", line, re.I):
            return True
    return False


def replace_or_prepend_description(content: str, new_description: str) -> str:
    """Mevcut // Description: satırını günceller veya en başa yeni satır ekler."""
    lines = content.splitlines()
    new_line = f"// Description: {new_description}"

    if has_description_line(lines):
        out = []
        replaced = False
        for line in lines:
            if not replaced and re.match(r"\s*//\s*Description\s*:", line, re.I):
                out.append(new_line)
                replaced = True
            else:
                out.append(line)
        return "\n".join(out) + ("\n" if content.endswith("\n") else "")
    else:
        if lines and lines[0].strip().startswith("#!"):
            # Shebang varsa onun hemen altına ekle
            return lines[0] + "\n" + new_line + "\n" + "\n".join(lines[1:]) + ("\n" if content.endswith("\n") else "")
        return new_line + "\n" + content


def process_folder(folder: Path) -> tuple[int, int]:
    """Klasördeki tüm .scad dosyalarını işler. (işlenen, atlanan) döner."""
    processed = 0
    skipped = 0
    for path in sorted(folder.rglob("*.scad")):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"  [skip read] {path.name}: {e}")
            skipped += 1
            continue
        desc = build_description(path.name, content)
        new_content = replace_or_prepend_description(content, desc)
        if new_content != content:
            try:
                path.write_text(new_content, encoding="utf-8")
                print(f"  + {path.name}")
                processed += 1
            except Exception as e:
                print(f"  [skip write] {path.name}: {e}")
                skipped += 1
        else:
            skipped += 1
    return processed, skipped


def main():
    if len(sys.argv) > 1:
        folder = Path(sys.argv[1])
    else:
        folder = Path(__file__).resolve().parent.parent / "data" / "files"

    if not folder.is_dir():
        print(f"Klasör bulunamadı: {folder}")
        print("Kullanım: python scripts/add_descriptions_to_scad.py <klasör_yolu>")
        print("Örnek:   python scripts/add_descriptions_to_scad.py data/files")
        sys.exit(1)

    print(f"İşleniyor: {folder}")
    processed, skipped = process_folder(folder)
    print(f"Tamamlandı: {processed} dosyaya yorum eklendi/güncellendi, {skipped} atlandı.")


if __name__ == "__main__":
    main()
