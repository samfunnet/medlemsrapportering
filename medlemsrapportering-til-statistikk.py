import json
from pathlib import Path
import sys
from medlemsrapportering_data import lag_medlemsrapportering_data

# Valgfritt årstall fra kommandolinjen
ar = sys.argv[1] if len(sys.argv) > 1 else None

# Hent grunnkatalog og definer utfil
cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
utfil = Path(cfg["grunnkatalog"]) / "til-medlems-statistikk.xlsx"

# Hent data (for spesifikt år eller alle tilgjengelige år)
df = lag_medlemsrapportering_data(ar)
df.select(
    [
        "år",
        "Menighet",
        "Status",
        "Tilleggsinfo",
        "fodsels_dato",
        "kjønn",
        "Postnummer",
    ]
).write_excel(utfil)

beskrivelse = (
    f"år {ar}"
    if ar
    else f"alle år ({df['år'].n_unique()} år: {sorted(df['år'].unique().to_list())})"
)
print(f"\n✅ FERDIG: Lagret {len(df)} rader for {beskrivelse} til:\n   {utfil}")
