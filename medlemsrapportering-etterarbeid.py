import argparse
import json
from pathlib import Path
import polars as pl

# De 7 faste kolonnene i posisjon 0 til 6 fra grunndata-filene
KOLONNER_GRUNNDATA = [
    "Medlemsnummer",
    "Etternavn",
    "Fornavn",
    "Adresse",
    "Postnummer",
    "Poststed",
    "Fødselsnummer",
]


def vask_tekst(col_name: str, lengde: int | None = None) -> pl.Expr:
    """Renser tekst fra Excel: fjerner flyttallsdesimaler (.0), mellomrom,

    og fyller inn ledende nuller (hvis lengde er oppgitt).
    """
    expr = pl.col(col_name).cast(pl.String).str.replace(r"\.0$", "").str.strip_chars()
    if lengde:
        expr = expr.str.zfill(lengde)
    return expr


def les_menighetsfil(fil: Path) -> pl.DataFrame:
    """Leser én menighetsfil, tar de 7 første kolonnene uansett navn,

    døper dem om og vasker fødselsnummer og postnummer.
    """
    df = pl.read_excel(fil)

    if df.width < 7:
        raise ValueError(
            f"Filen {fil.name} har bare {df.width} kolonner, forventet minst 7!"
        )

    # 1. Kutt til de 7 første kolonnene og overskriv navnene etter fast rekkefølge
    df = df[:, :7]
    df.columns = KOLONNER_GRUNNDATA

    # 2. Vask felter og legg til menighetsnavn fra filnavnet (f.eks. "Trondheim")
    return df.filter(
        pl.col("Fødselsnummer").is_not_null() & (pl.col("Fødselsnummer") != "")
    ).with_columns(
        vask_tekst("Fødselsnummer", 11),
        vask_tekst("Postnummer", 4),
        vask_tekst("Medlemsnummer"),
        pl.lit(fil.stem).alias("Menighet"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Finner alle ugyldige medlemmer for et gitt år."
    )
    parser.add_argument("ar", type=int, help="Rapporteringsår (f.eks. 2025)")
    args = parser.parse_args()

    # 1. Hent stier fra config.json
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)

    base = Path(cfg["grunnkatalog"])
    menighet_mappe = base / cfg["menigheter_undermappe"].format(ar=args.ar)
    ugyldig_mappe = base / cfg["ugyldige_katalog"].format(ar=args.ar)
    ugyldig_fil = ugyldig_mappe / cfg["ugyldige_medlemmer_filnavn"].format(ar=args.ar)
    utdata_fil = ugyldig_mappe / cfg["ugyldige_medlemmer_filnavn_komplett"].format(
        ar=args.ar
    )

    # 2. Finn menighetsfilene
    filer = [
        f
        for f in menighet_mappe.glob("*.xlsx")
        if not f.name.startswith("~$") and f.resolve() != ugyldig_fil.resolve()
    ]
    if not filer:
        raise FileNotFoundError(f"Ingen menighetsfiler funnet i {menighet_mappe}")

    print(f"Laster inn {len(filer)} menigheter fra: {menighet_mappe.name} ...")

    # 3. Les alle menigheter og slå sammen vertikalt
    samlet = pl.concat([les_menighetsfil(f) for f in sorted(filer)], how="vertical")
    print(f"Totalt {len(samlet)} medlemmer innlest fra menighetene.")

    # 4. Les Statsforvalterens ugyldige-liste (Fødselsnummer, Status, Tilleggsinfo)
    print(f"Leser ugyldige fra: {ugyldig_fil.name} ...")
    ugyldige = (
        pl.read_excel(ugyldig_fil)
        .filter(pl.col("Fødselsnummer").is_not_null() & (pl.col("Fødselsnummer") != ""))
        .with_columns(vask_tekst("Fødselsnummer", 11))
    )

    # 5. INNER JOIN på Fødselsnummer (kun treff beholdes)
    feilliste = samlet.join(ugyldige, on="Fødselsnummer", how="inner")

    # 6. Sorter kolonnene logisk for etterarbeid (Menighet og feilårsak først)
    kolonne_rekkefolge = [
        "Menighet",
        "Status",
        "Tilleggsinfo",
        "Fødselsnummer",
        "Etternavn",
        "Fornavn",
        "Adresse",
        "Postnummer",
        "Poststed",
        "Medlemsnummer",
    ]
    aktive_kolonner = [c for c in kolonne_rekkefolge if c in feilliste.columns]
    resten = [c for c in feilliste.columns if c not in aktive_kolonner]
    feilliste = feilliste.select(aktive_kolonner + resten)

    # 7. Lagre ferdig fil
    ugyldig_mappe.mkdir(parents=True, exist_ok=True)
    feilliste.write_excel(utdata_fil)

    print(f"\n✅ FERDIG: Lagret {len(feilliste)} feil til:")
    print(f"   {utdata_fil}\n")

    # Skriv ut oversikt over feil per menighet
    # print(feilliste)
    print("Feil fordelt per menighet:")
    print(feilliste["Menighet"].value_counts(sort=True))


if __name__ == "__main__":
    main()
