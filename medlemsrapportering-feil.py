import json
from pathlib import Path
import sys
import polars as pl
from medlemsrapportering_data import lag_medlemsrapportering_data

ar = sys.argv[1]

# Hent utfil-sti fra config
cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
utfil = (
    Path(cfg["grunnkatalog"])
    / cfg["ugyldige_katalog"]
    / cfg["ugyldige_medlemmer_filnavn_komplett"].format(ar=ar)
)

# Hent data og filtrer helvektorisert over begge feltene i én operasjon
feil_df = lag_medlemsrapportering_data(ar).filter(
    pl.any_horizontal(
        pl.col("Status", "Tilleggsinfo").fill_null("").str.strip_chars() != ""
    )
)

# Eksporter
feil_df.write_excel(utfil)

print(f"\n✅ FERDIG: Lagret {len(feil_df)} feil til:\n   {utfil}")
print("\nFeil fordelt per menighet:")
print(feil_df["Menighet"].value_counts().sort("count", descending=True))
