#!/usr/bin/env python3
"""
cleanup_sources.py — Rimuove footnote Markdown e URL da deep.md
Formato reale footnote: [^2_1]: [https://...](https://...)
Uso: python cleanup_sources.py
     python cleanup_sources.py source/deep.md source/deep_clean.md
"""
import re, sys
from pathlib import Path


def clean_file(input_path: Path, output_path: Path):
    print(f"Leggo: {input_path} ({input_path.stat().st_size / 1024:.0f} KB)")
    text = input_path.read_text(encoding="utf-8")
    original_len = len(text)

    # 1. Definizioni footnote Markdown su riga intera
    #    [^2_1]: [https://example.com/...](https://example.com/...)
    text = re.sub(
        r'^\[\^\w+\]:\s+\[.*?\]\(.*?\)\s*$',
        '', text, flags=re.MULTILINE
    )

    # 2. Blocchi <span style="display:none">...</span>
    #    Contengono: [^2_17][^2_18][^2_19]...
    text = re.sub(
        r'<span[^>]*display\s*:\s*none[^>]*>.*?</span>',
        '', text, flags=re.DOTALL | re.IGNORECASE
    )

    # 3. Blocchi <div align="center">⁂</div> (separatori sezione)
    text = re.sub(
        r'<div[^>]*align\s*=\s*["\']?center["\']?[^>]*>.*?</div>',
        '', text, flags=re.DOTALL | re.IGNORECASE
    )

    # 4. Riferimenti inline a footnote: [^2_17] anche concatenati
    text = re.sub(r'(?:\[\^\w+\])+', '', text)

    # 5. Collassa righe vuote multiple (max 2 consecutive)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 6. Spazi bianchi di fine riga
    text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return original_len, len(text)


def main():
    if len(sys.argv) == 3:
        inp, out = Path(sys.argv[1]), Path(sys.argv[2])
    elif len(sys.argv) == 2:
        inp = Path(sys.argv[1])
        out = inp.parent / (inp.stem + "_clean" + inp.suffix)
    else:
        candidates = sorted(Path("source").glob("deep*.md"))
        if not candidates:
            print("Errore: nessun file deep*.md trovato in source/")
            sys.exit(1)
        inp = candidates[0]
        out = inp.parent / "deep_clean.md"

    if not inp.exists():
        print(f"Errore: file non trovato: {inp}")
        sys.exit(1)

    orig, clean = clean_file(inp, out)
    reduction  = (orig - clean) / orig * 100
    tok_orig   = orig  // 4
    tok_clean  = clean // 4
    tok_saved  = tok_orig - tok_clean
    cost_saved = tok_saved / 1_000_000 * 3 * 39

    print(f"\nRisultato:")
    print(f"  Originale : {orig:>10,} caratteri  (~{tok_orig:>8,} token)")
    print(f"  Pulito    : {clean:>10,} caratteri  (~{tok_clean:>8,} token)")
    print(f"  Riduzione : {reduction:>9.1f}%   (~{tok_saved:>8,} token risparmiati)")
    print(f"  Salvato in: {out}")
    print(f"  Risparmio stimato (Sonnet $3/M x 39 call): ${cost_saved:.2f}")


if __name__ == "__main__":
    main()
