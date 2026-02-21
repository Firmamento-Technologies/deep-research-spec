#!/usr/bin/env python3
"""
compress_deep.py — Compressione semantica di deep.md tramite Claude Sonnet
Mantiene il 100% delle informazioni architetturali, elimina ripetizioni e ridondanze.
Uso: python compress_deep.py
"""
import os, sys, time
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

MODEL       = "anthropic/claude-sonnet-4-5"
CHUNK_SIZE  = 80_000   # caratteri per chunk (~20K token)
OUTPUT_FILE = Path("source/deep_compressed.md")

SYSTEM_PROMPT = """Sei un esperto di architettura software con il compito di comprimere
semanticamente un documento tecnico. Il documento è la trascrizione di una conversazione
di design per un sistema AI multi-agente chiamato Deep Research System (DRS).

REGOLE ASSOLUTE:
1. NON perdere nessuna decisione architetturale, formula, struttura dati, o specifica tecnica
2. NON perdere nessun nome di agente, parametro, soglia numerica, o nome di modello LLM
3. NON perdere nessuna integrazione critica aggiunta nelle analisi (CSS formula, Error Handling Matrix, Budget Controller, Testing Framework, Security Layer, Style Calibration Gate, ecc.)
4. ELIMINA: domande e risposte conversazionali ridondanti, ripetizioni dello stesso concetto, frasi introduttive ("Ottima domanda", "Perfetto", "Hai ragione"), riassunti di cose già dette, meta-commenti sul processo ("ora scrivo il prompt", "ho abbastanza materiale")
5. CONSOLIDA: se lo stesso concetto viene spiegato 3 volte in punti diversi della conversazione, tienilo UNA volta nella sua versione più completa
6. OUTPUT: prosa tecnica densa e strutturata, senza fronzoli conversazionali
7. FORMATO: mantieni i titoli Markdown esistenti come riferimenti strutturali

L'obiettivo è ridurre del 60-70% la lunghezza mantenendo il 100% del valore informativo
per un developer che deve implementare il sistema."""

USER_TEMPLATE = """Comprimi semanticamente questo estratto del documento Deep Research System.
Segui le regole del sistema. Restituisci SOLO il contenuto compresso, senza commenti.

--- ESTRATTO ---
{chunk}
--- FINE ESTRATTO ---"""

def split_into_chunks(text: str, chunk_size: int) -> list[str]:
    """Divide il testo in chunk rispettando i confini di paragrafo."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Cerca il boundary più vicino (fine paragrafo)
        boundary = text.rfind("\n\n", start, end)
        if boundary == -1 or boundary <= start:
            boundary = text.rfind("\n", start, end)
        if boundary == -1 or boundary <= start:
            boundary = end
        chunks.append(text[start:boundary])
        start = boundary
    return [c.strip() for c in chunks if c.strip()]

def compress_chunk(chunk: str, idx: int, total: int) -> str:
    """Comprime un singolo chunk con retry."""
    for attempt in range(3):
        try:
            print(f"  Chunk {idx}/{total} ({len(chunk):,} car) — tentativo {attempt+1}...")
            resp = client.chat.completions.create(
                model=MODEL,
                max_tokens=16000,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": USER_TEMPLATE.format(chunk=chunk)},
                ],
            )
            result = resp.choices[0].message.content.strip()
            ratio = (1 - len(result)/len(chunk)) * 100
            print(f"  ✅ {len(chunk):,} → {len(result):,} car  ({ratio:.0f}% riduzione)")
            return result
        except Exception as e:
            print(f"  ⚠️  Errore: {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
    print(f"  ❌ Chunk {idx} fallito dopo 3 tentativi — uso originale")
    return chunk

def main():
    inp = Path("source/deep.md")
    if not inp.exists():
        print(f"Errore: {inp} non trovato")
        sys.exit(1)

    print(f"Leggo {inp} ({inp.stat().st_size/1024:.0f} KB)...")
    text = inp.read_text(encoding="utf-8")
    orig_len = len(text)

    chunks = split_into_chunks(text, CHUNK_SIZE)
    print(f"Diviso in {len(chunks)} chunk da ~{CHUNK_SIZE:,} car\n")

    # Stima costo
    est_input_tokens  = orig_len // 4
    est_output_tokens = est_input_tokens * 0.35  # stima 65% riduzione
    est_cost = (est_input_tokens / 1e6 * 3) + (est_output_tokens / 1e6 * 15)
    print(f"Stima costo operazione: ${est_cost:.2f}\n")

    compressed_parts = []
    for i, chunk in enumerate(chunks, 1):
        part = compress_chunk(chunk, i, len(chunks))
        compressed_parts.append(part)
        # Salvataggio incrementale ogni 3 chunk (checkpoint)
        if i % 3 == 0:
            partial = "\n\n".join(compressed_parts)
            Path("source/deep_compressed_partial.md").write_text(partial, encoding="utf-8")
            print(f"  💾 Checkpoint salvato ({i}/{len(chunks)} chunk)\n")

    final_text = "\n\n".join(compressed_parts)
    OUTPUT_FILE.write_text(final_text, encoding="utf-8")

    final_len = len(final_text)
    reduction = (orig_len - final_len) / orig_len * 100
    tok_saved = (orig_len - final_len) // 4
    saving_per_call = tok_saved / 1e6 * 3
    saving_total = saving_per_call * 36

    print(f"\n{'='*50}")
    print(f"COMPRESSIONE COMPLETATA")
    print(f"{'='*50}")
    print(f"  Originale   : {orig_len:>10,} car  (~{orig_len//4:>8,} token)")
    print(f"  Compresso   : {final_len:>10,} car  (~{final_len//4:>8,} token)")
    print(f"  Riduzione   : {reduction:>9.1f}%")
    print(f"  Salvato in  : {OUTPUT_FILE}")
    print(f"\n  Risparmio per chiamata generate_specs: ${saving_per_call:.3f}")
    print(f"  Risparmio totale (36 file)            : ${saving_total:.2f}")
    print(f"\n  Prossimo passo:")
    print(f"  Aggiorna generate_specs.py per usare deep_compressed.md")
    print(f"  sed -i 's/deep\\.md/deep_compressed.md/g' generate_specs.py")

if __name__ == "__main__":
    main()
