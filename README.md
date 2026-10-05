 Medlemsrapportering og etterarbeid

Dette prosjektet håndterer datainnlesing, vasking, berikelse og analyse av menighetsdata og feillister fra Statsforvalteren for Mikaelkirken.

Systemet er bygget med **Polars 2.0** for høy ytelse og robust databehandling på tvers av menigheter og årganger.

---

## Prosjektstruktur

```text
medlemsrapportering/
├── config.json                        # Sentral sti- og filkonfigurasjon
├── pyproject.toml                     # Prosjektoppsett og avhengigheter (uv)
├── medlemsrapportering_data.py        # 📦 Kjernemotor (felles funksjon for datainnlesing)
├── medlemsrapportering-feil.py         # 🚀 Kjøring 1: Eksporterer feilliste for et gitt år
└── medlemsrapportering-til-statistikk.py # 🚀 Kjøring 2: Eksporterer totalt datagrunnlag
```

---

## Kjernefunksjonen: `lag_medlemsrapportering_data()`

Begge kjøringene benytter den delte motoren `lag_medlemsrapportering_data(ar=None)` i `medlemsrapportering_data.py`. Funksjonen fungerer som et felles fundament og utfører følgende oppgaver:

1. **Dynamisk år-deteksjon:**
   - Kalles den med et årstall (f.eks. `2025`), behandles kun dette året.
   - Kalles den uten parameter (`None`), skannes `grunnkatalog` automatisk etter alle mapper som følger mønsteret `Grunndata <ÅR>` (f.eks. 2020–2025).
2. **Robust fil- og menighetshåndtering:**
   - Leser menighetsfiler uavhengig av store/små bokstaver i filnavn (f.eks. `Oslo.xlsx`, `oslo.xlsx`).
   - Filtrerer strengt på de fem godkjente menighetene: **Bergen**, **Hamar**, **Oslo**, **Stavanger** og **Trondheim**.
3. **Datavask og typesikkerhet:**
   - Tvinger alle innleste kolonner til `String` umiddelbart for å unngå typekonflikter ved sammenslåing.
   - Standardiserer `Fødselsnummer` (11 siffer med ledende nuller) og `Postnummer` (4 siffer).
4. **Berikelse via `utilities`:**
   - Benytter `utilities.fnr_detaljer` for å beregne eksakt **`fodsels_dato`** (håndterer D-numre og århundreskifter 1800/1900/2000) og **`kjønn`** (Mann/Kvinne fra 9. siffer).
5. **Kobling mot Statsforvalterens feillister (LEFT JOIN):**
   - Kobler menighetsdataene mot `ugyldige <ar>.xlsx` på `["år", "Fødselsnummer"]`.
   - Dersom en feilliste mangler for et år (f.eks. før listen er mottatt fra Statsforvalteren), får medlemmene automatisk blanke felter i `Status` og `Tilleggsinfo`.
6. **Strukturert kolonneoppsett:**
   - `år` legges som **første kolonne** som `Int32`, etterfulgt av `Menighet`, eventuelle feilkolonner og vaskede persondata.

---

## Kjøringer (Bruk)

### 1. Generere feilliste (`medlemsrapportering-feil.py`)

Brukes når Statsforvalterens feilliste for et spesifikt år er mottatt og du kun vil sitte igjen med medlemmene som har avvik/feil.

- **Oppgave:** Henter data for det oppgitte året, fjerner alle godkjente medlemmer, og beholder kun rader der `Status` eller `Tilleggsinfo` inneholder en verdi.
- **Kjøring:**

  ```bash
  uv run medlemsrapportering-feil.py <ÅR>
  ```

  *Eksempel:*

  ```bash
  uv run medlemsrapportering-feil.py 2025
  ```
- **Resultat:** Lagres i mappen for feil definert i `config.json`:

  ```text
  <grunnkatalog>/Medlems statistikk/Feil/ugyldige_komplett_liste <ÅR>.xlsx
  ```
- Viser en oppsummering i terminalen over antall feil fordelt per menighet.

---

### 2. Generere fullstendig datagrunnlag (`medlemsrapportering-til-statistikk.py`)

Brukes for å eksportere det komplette medlemsgrunnlaget med utledet fødselsdato, kjønn og eventuelle feilmeldinger til én samlet Excel-fil.

#### Kjøring for alle år (anbefalt for totalstatistikk)

Dersom du utelater årstall, finner skriptet alle år som eksisterer i mappestrukturen og slår dem sammen i én fil:

```bash
uv run medlemsrapportering-til-statistikk.py
```

#### Kjøring for et enkeltår

Dersom du kun ønsker data for et spesifikt år:

```bash
uv run medlemsrapportering-til-statistikk.py 2025
```

- **Resultat:** Lagres direkte i grunnkatalogen:

  ```text
  <grunnkatalog>/til-medlems-statistikk.xlsx
  ```

---

## Konfigurasjon (`config.json`)

Stier og filnavnmønstre styres fra `config.json` i rotkatalogen:

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

## Forutsetninger og installasjon

Prosjektet administreres med [uv](https://github.com/astral-sh/uv).

1. Klon repoet:

   ```bash
   git clone https://github.com/samfunnet/medlemsrapportering.git
   cd medlemsrapportering
   ```

2. Installer avhengigheter (inkludert utilities-biblioteket):

   ```bash
   uv sync
   ```

   *(Eller manuelt: `uv add git+https://github.com/samfunnet/utilities`)*
