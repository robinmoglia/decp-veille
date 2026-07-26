"""
Étape 2 — Nettoyer les DECP et produire une table propre et exploitable.

Ce que fait ce script, en partant des constats de l'exploration :
  - ne garder qu'une ligne par marché (la version courante) ;
  - ne conserver que les colonnes solides ;
  - réparer les fausses dates (1899-12-31 → vide) ;
  - écarter les montants aberrants (<= 0 ou démesurés) ;
  - livrer un fichier propre + un récapitulatif des corrections.

Ce récapitulatif est exactement le livrable qu'attend un client freelance :
« voici ce qui était cassé, voici ce que j'ai corrigé, voici le fichier propre ».
Garde-le, il te sert de preuve de compétence.

Usage :
    python 02_nettoyage.py
"""

from pathlib import Path

import pandas as pd

FICHIER_BRUT = Path("data/decp.parquet")
DOSSIER_SORTIE = Path("data")

# Colonnes retenues à l'étape d'exploration (les >70 % vides sont exclues).
COLONNES_GARDEES = [
    "uid",
    "objet",
    "montant",
    "codeCPV",
    "nature",
    "procedure",
    "dureeMois",
    "dureeRestanteMois",
    "offresRecues",
    "dateNotification",
    "acheteur_nom",
    "acheteur_categorie",
    "acheteur_departement_code",
    "acheteur_departement_nom",
    "acheteur_region_nom",
    "titulaire_nom",
    "titulaire_categorie",
    "titulaire_departement_nom",
    "donneesActuelles",
]

# Bornes de plausibilité pour un montant de marché public.
# En dessous : erreur ou marché vide. Au-dessus : erreur de saisie
# (le 99e centile observé est à ~35 M€, donc 1 Md€ est une borne large et sûre).
MONTANT_MIN = 1
MONTANT_MAX = 1_000_000_000

# Les exports Excel écrivent parfois une date vide comme le "jour zéro".
FAUSSES_DATES = {"1899-12-31", "1900-01-01", "1970-01-01"}


def journal(rapport: list[str], texte: str) -> None:
    """Affiche à l'écran et mémorise pour le récapitulatif final."""
    print(texte)
    rapport.append(texte)


def main() -> None:
    rapport: list[str] = []
    DOSSIER_SORTIE.mkdir(exist_ok=True)

    if not FICHIER_BRUT.exists():
        raise SystemExit(
            "data/decp.parquet introuvable. Lance d'abord : python 01_exploration.py"
        )

    df = pd.read_parquet(FICHIER_BRUT)
    lignes_depart = len(df)
    journal(rapport, f"Lignes au départ : {lignes_depart:,}".replace(",", " "))

    # 1) Ne garder que la version courante de chaque marché ---------------
    avant = len(df)
    df = df[df["donneesActuelles"] == True].copy()
    journal(
        rapport,
        f"1. Versions courantes seulement : -{avant - len(df):,} lignes "
        f"(anciennes versions et avenants dépassés)".replace(",", " "),
    )

    # 2) Garder une seule ligne par marché --------------------------------
    # Un marché à plusieurs titulaires reste sur plusieurs lignes ; pour la
    # table d'analyse "un marché = une ligne", on garde la première.
    avant = len(df)
    df = df.drop_duplicates(subset="uid", keep="first")
    journal(
        rapport,
        f"2. Une ligne par marché (uid) : -{avant - len(df):,} lignes doublons"
        .replace(",", " "),
    )

    # 3) Ne conserver que les colonnes solides ----------------------------
    colonnes = [c for c in COLONNES_GARDEES if c in df.columns]
    df = df[colonnes].copy()
    journal(
        rapport,
        f"3. Colonnes conservées : {len(colonnes)} sur 58 "
        "(les colonnes vides à plus de 70 % sont écartées)",
    )

    # 4) Réparer les dates ------------------------------------------------
    df["dateNotification"] = df["dateNotification"].astype(str).str.slice(0, 10)
    fausses = df["dateNotification"].isin(FAUSSES_DATES).sum()
    df.loc[df["dateNotification"].isin(FAUSSES_DATES), "dateNotification"] = None
    df["dateNotification"] = pd.to_datetime(df["dateNotification"], errors="coerce")
    journal(
        rapport,
        f"4. Dates réparées : {fausses:,} fausses dates (1899, etc.) mises à vide"
        .replace(",", " "),
    )

    # 5) Nettoyer les montants -------------------------------------------
    df["montant"] = pd.to_numeric(df["montant"], errors="coerce")
    hors_bornes = ((df["montant"] < MONTANT_MIN) | (df["montant"] > MONTANT_MAX)).sum()
    df.loc[
        (df["montant"] < MONTANT_MIN) | (df["montant"] > MONTANT_MAX), "montant"
    ] = None
    journal(
        rapport,
        f"5. Montants aberrants mis à vide : {hors_bornes:,} "
        f"(hors de [{MONTANT_MIN} €, {MONTANT_MAX:,} €])".replace(",", " "),
    )

    # 6) Normaliser l'objet (nettoyage léger, sans reformuler) ------------
    df["objet"] = (
        df["objet"].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    )

    # ---------------------------------------------------------------------
    journal(rapport, "")
    journal(rapport, f"Lignes à l'arrivée : {len(df):,}".replace(",", " "))
    journal(
        rapport,
        f"Réduction totale : {lignes_depart:,} → {len(df):,} "
        f"({100 * len(df) / lignes_depart:.0f} % conservé)".replace(",", " "),
    )

    # Écriture des fichiers ----------------------------------------------
    sortie_parquet = DOSSIER_SORTIE / "decp_propre.parquet"
    sortie_csv = DOSSIER_SORTIE / "decp_propre.csv"
    df.to_parquet(sortie_parquet, index=False)
    df.to_csv(sortie_csv, index=False, encoding="utf-8")
    journal(rapport, "")
    journal(rapport, f"Fichier propre écrit : {sortie_parquet}")
    journal(rapport, f"Version CSV (ouvrable dans Excel) : {sortie_csv}")

    # Récapitulatif des corrections (le livrable "client") ----------------
    rapport_fichier = DOSSIER_SORTIE / "rapport_nettoyage.txt"
    rapport_fichier.write_text(
        "RÉCAPITULATIF DU NETTOYAGE — données de la commande publique\n"
        "============================================================\n\n"
        + "\n".join(rapport)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nRécapitulatif enregistré : {rapport_fichier}")


if __name__ == "__main__":
    main()
