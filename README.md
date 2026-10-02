### `README.md`

```markdown
# Medlemsrapportering – Mikaelkirken

Automatiseringsverktøy for årlig medlemsrapportering og kontroll mot Statsforvalteren. Prosjektet er bygget i Python med **Polars** og administreres med **uv**.

---

## 📋 Forutsetninger

1. **Linux** med [uv](https://docs.astral.sh/uv/) installert:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
1. Tilgang til servermountet spesifisert i `config.json` (f.eks. `/mnt/server/...`).

Ingen manuell opprettelse av virtuelt miljø (`venv`) eller `pip install` er nødvendig. `uv` håndterer alle avhengigheter automatisk.

---

## ⚙️ Konfigurasjon (`config.json`)

Skriptene styres av `config.json` i rotmappen. Her defineres filbanene, der `{ar}` automatisk erstattes med året du sender inn via terminalen:

```json
{
  "grunnkatalog": "/mnt/server/system-ssd/mount/Mikaelkirken/IKT/Medlemsregisteret/Statstilskudd",
  "menigheter_undermappe": "Grunndata {ar}",
  "ugyldige_katalog": "Medlems statistikk/Feil",
  "ugyldige_medlemmer_filnavn": "ugyldige {ar}.xlsx",
  "ugyldige_medlemmer_filnavn_komplett": "ugyldige_komplett_liste {ar}.xlsx"
}
```

---

## 🚀 Hovedrutine: Etterarbeid (`medlemsrapportering-etterarbeid.py`)

Dette skriptet kjøres **etter** at Statsforvalteren har behandlet medlemslisten og returnert filen over ugyldige medlemmer (f.eks. `ugyldige 2025.xlsx`).

### Hva skriptet gjør

1. **Leser alle menighetsfiler** i mappen `Grunndata {ar}` (Trondheim, Bergen, Stavanger, Hamar, Oslo, osv.).
2. **Standardiserer kolonner etter fast posisjon:** Kolonnenavnene i menighetenes Excel-filer kan variere, men skriptet tvinger alltid de 7 første kolonnene til:
   * `[0] Medlemsnummer`, `[1] Etternavn`, `[2] Fornavn`, `[3] Adresse`, `[4] Postnummer`, `[5] Poststed`, `[6] Fødselsnummer`
3. **Vasker data automatisk:**
   * **Fødselsnummer:** Fylles ut til 11 siffer med ledende nuller (zfill) dersom Excel har lagret det numerisk.
   * **Postnummer:** Sikres til 4 siffer (slik at f.eks. `0955` Oslo ikke blir til `955`).
4. **Legger til menighet:** Navnet på menigheten hentes automatisk fra filnavnet (f.eks. `Trondheim.xlsx` → `Trondheim`).
5. **Kjører ren INNER JOIN:** Matcher menighetsdataene mot Statsforvalterens feilliste på `Fødselsnummer`. Kun rader med feil beholdes.
6. **Eksporterer beriket feilliste:** Lagrer en ny Excel-fil der `Menighet`, `Status` og `Tilleggsinfo` er plassert først.

---

### Slik kjører du skriptet

Åpne terminalen i rotmappen til repoet og kjør:

```bash
uv run medlemsrapportering-etterarbeid.py <ÅR>
```

#### Eksempel

```bash
uv run medlemsrapportering-etterarbeid.py 2025
```

#### Forventet terminalutdata

```text
Laster inn 5 menigheter fra: Grunndata 2025 ...
Totalt 1450 medlemmer innlest fra menighetene.
Leser ugyldige fra: ugyldige 2025.xlsx ...

✅ FERDIG: Lagret 38 feil til:
   /mnt/.../Medlems statistikk/Feil/ugyldige_komplett_liste 2025.xlsx

Feil fordelt per menighet:
shape: (5, 2)
┌───────────┬───────┐
│ Menighet  ┆ count │
│ ---       ┆ ---   │
│ str       ┆ u32   │
╞═══════════╪═══════╡
│ Oslo      ┆ 18    │
│ Trondheim ┆ 9     │
│ Bergen    ┆ 6     │
│ Stavanger ┆ 3     │
│ Hamar     ┆ 2     │
└───────────┴───────┘
```

Resultatfilen `ugyldige_komplett_liste 2025.xlsx` er nå klar til å distribueres til menighetene eller saksbehandles videre.

---

## 🔮 Kommende funksjoner og skript

Flere rutiner legges til etter hvert:

* **`medlemsrapportering-statsforvalteren.py`**:
  Rutine som kjøres *før* innsending. Den leser alle menighetenes grunndatafiler, sjekker for eventuelle duplikater mellom menighetene, og genererer den samlede Excel-filen som skal rapporteres til Statsforvalteren.

---

## 🔒 Personvern og GDPR

* Prosjektet behandler medlemslister og fødselsnumre (særlige kategorier av personopplysninger etter GDPR art. 9).
* `.gitignore` er konfigurert slik at **ingen Excel-filer (`*.xlsx`) skal commites til Git**.
* Alle data skal til enhver tid leses fra og skrives til de sikrede serverkatalogene spesifisert i `config.json`.
