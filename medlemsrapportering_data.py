import json
from pathlib import Path
import re
import sys
import warnings
import polars as pl
from utilities import fnr_detaljer

warnings.filterwarnings("ignore", category=FutureWarning, module="polars")

KOLONNER = [
    "Medlemsnummer",
    "Etternavn",
    "Fornavn",
    "Adresse",
    "Postnummer",
    "Poststed",
    "Fødselsnummer",
]

GYLDIGE_MENIGHETER = {"bergen", "hamar", "oslo", "stavanger", "trondheim"}


def _finn_menighetsfiler(mappe: Path) -> list[tuple[Path, str]]:
    """Finner gyldige menighetsfiler uavhengig av store/små bokstaver."""
    funnet = []
    for f in mappe.glob("*.[xX][lL][sS][xX]"):
        if f.name.startswith("~$"):
            continue
        navn_lav = f.stem.lower()
        if navn_lav in GYLDIGE_MENIGHETER:
            funnet.append((f, navn_lav.capitalize()))
    return sorted(funnet, key=lambda x: x[1])


def _finn_menighetsmappe(grunnkatalog: Path, ar: int) -> Path | None:
    """Finner mappen 'Grunndata {ar}' uavhengig av casing."""
    for p in grunnkatalog.iterdir():
        if p.is_dir() and re.match(rf"(?i)^grunndata\s+{ar}$", p.name.strip()):
            return p
    return None


def _finn_alle_ar(grunnkatalog: Path) -> list[int]:
    """Finner alle årstall som har en 'Grunndata {ar}'-mappe."""
    funnede_ar = set()
    for p in grunnkatalog.iterdir():
        if p.is_dir():
            m = re.match(r"(?i)^grunndata\s+(\d{4})$", p.name.strip())
            if m:
                funnede_ar.add(int(m.group(1)))
    return sorted(funnede_ar)


def _les_menighetsfil(fil: Path, menighet: str, ar: int) -> pl.DataFrame:
    """Leser enkeltfil, standardiserer til String, og legger til Menighet og år."""
    df = pl.read_excel(fil)
    cols = df.columns[:7]
    return (
        df.select(cols)
        .rename(dict(zip(cols, KOLONNER)))
        .with_columns(
            pl.all().cast(pl.String).str.strip_chars(),
            pl.lit(menighet).alias("Menighet"),
            pl.lit(ar).cast(pl.Int32).alias("år"),
        )
        .with_columns(
            pl.col("Fødselsnummer").str.zfill(11),
            pl.col("Postnummer").str.zfill(4),
        )
    )


def lag_medlemsrapportering_data(
    ar: int | str | None = None, config_sti: Path | str | None = None
) -> pl.DataFrame:
    """
    Hovedfunksjon:
    - Dersom 'ar' er oppgitt: leser kun dette året.
    - Dersom 'ar' mangler (None): finner og leser alle tilgjengelige år.
    - Returnerer komplett Polars DataFrame med 'år' som første kolonne.
    """
    repo_katalog = Path(__file__).resolve().parent
    config_fil = Path(config_sti) if config_sti else (repo_katalog / "config.json")
    cfg = json.loads(config_fil.read_text(encoding="utf-8"))

    grunnkatalog = Path(cfg["grunnkatalog"])
    ugyldige_mappe = grunnkatalog / cfg["ugyldige_katalog"]

    # 1. Bestem hvilke år som skal behandles
    if ar is not None:
        aktuelle_ar = [int(ar)]
    else:
        aktuelle_ar = _finn_alle_ar(grunnkatalog)
        if not aktuelle_ar:
            raise FileNotFoundError(
                f"Ingen 'Grunndata <ÅR>'-mapper funnet i: {grunnkatalog}"
            )

    print(f"Behandler år: {aktuelle_ar}")

    # 2. Samle alle menighetsfiler for de aktuelle årene
    menighets_dfs = []
    for a in aktuelle_ar:
        mappe = _finn_menighetsmappe(grunnkatalog, a)
        if not mappe:
            print(f"⚠️ Fant ikke menighetsmappe for år {a}")
            continue

        filer = _finn_menighetsfiler(mappe)
        print(f"  [{a}] Laster inn {len(filer)} menigheter fra: {mappe.name} ...")
        for fil, menighet_navn in filer:
            menighets_dfs.append(_les_menighetsfil(fil, menighet_navn, a))

    if not menighets_dfs:
        raise FileNotFoundError("Ingen menighetsdata ble funnet for de valgte årene.")

    alle_data = pl.concat(menighets_dfs).with_columns(fnr_detaljer("Fødselsnummer"))
    print(f"Totalt {len(alle_data)} medlemsrader innlest på tvers av menigheter/år.")

    # 3. Les inn tilgjengelige feillister fra Statsforvalteren og tagg med 'år'
    ugyldige_dfs = []
    if ugyldige_mappe.exists():
        for a in aktuelle_ar:
            # Case-insensitivt søk etter ugyldige {ar}.xlsx
            funnet_ugyldig = next(
                (
                    f
                    for f in ugyldige_mappe.iterdir()
                    if f.is_file()
                    and re.match(rf"(?i)^ugyldige\s+{a}\.xlsx$", f.name.strip())
                ),
                None,
            )
            if funnet_ugyldig:
                u_df = pl.read_excel(funnet_ugyldig).with_columns(
                    pl.all().cast(pl.String).str.strip_chars()
                )
                fnr_kol = next(
                    (
                        c
                        for c in u_df.columns
                        if "fødselsnummer" in c.lower()
                        or c.lower() in ["fnr", "foedselsnummer"]
                    ),
                    "Fødselsnummer",
                )
                u_df = u_df.rename({fnr_kol: "Fødselsnummer"}).with_columns(
                    pl.col("Fødselsnummer").str.zfill(11),
                    pl.lit(a).cast(pl.Int32).alias("år"),
                )
                ugyldige_dfs.append(u_df)
            else:
                print(
                    f"  ℹ️ Ingen feilliste for {a} (ugyldige {a}.xlsx mangler). Settes til blanke feilfelter."
                )

    # 4. LEFT JOIN på både ['år', 'Fødselsnummer']
    if ugyldige_dfs:
        ugyldige_alle = pl.concat(ugyldige_dfs, how="diagonal_relaxed")
        feil_kolonner = [
            c
            for c in ugyldige_alle.columns
            if c not in alle_data.columns or c in ["år", "Fødselsnummer"]
        ]
        resultat = alle_data.join(
            ugyldige_alle.select(feil_kolonner), on=["år", "Fødselsnummer"], how="left"
        )
    else:
        # Hvis ingen feillister eksisterer i det hele tatt, opprett kolonnene som tomme
        resultat = alle_data.with_columns(
            pl.lit(None, dtype=pl.String).alias("Status"),
            pl.lit(None, dtype=pl.String).alias("Tilleggsinfo"),
        )

    # 5. Kolonnerekkefølge med 'år' helt først
    prioriterte = ["år", "Menighet", "Status", "Tilleggsinfo"]
    persondata = [
        "Medlemsnummer",
        "Etternavn",
        "Fornavn",
        "fodsels_dato",
        "kjønn",
        "Adresse",
        "Postnummer",
        "Poststed",
        "Fødselsnummer",
    ]
    rekkefolge = [c for c in prioriterte if c in resultat.columns]
    rekkefolge += [
        c for c in persondata if c in resultat.columns and c not in rekkefolge
    ]
    rekkefolge += [c for c in resultat.columns if c not in rekkefolge]

    return resultat.select(rekkefolge).sort(["år", "Menighet", "Etternavn", "Fornavn"])
