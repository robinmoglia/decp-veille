"""
Étape 4 — Mise à jour automatique.

Ce script fait, d'un seul coup, ce que tu as appris aux étapes 1 à 3 :
  1. retélécharge le fichier officiel le plus récent ;
  2. le nettoie (mêmes règles que 02_nettoyage.py) ;
  3. en extrait les opportunités : marchés en cours expirant dans les 12 mois ;
  4. écrit un petit fichier frais + un résumé daté.

Il est conçu pour tourner tout seul, chaque nuit, via GitHub Actions.
Il est "idempotent" : le relancer dix fois donne le même résultat propre.

Usage manuel :
    python 04_maj.py
"""

from __future__ import annotations

import json
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# --- mêmes réglages que l'étape 2 -----------------------------------------
RESSOURCE_PARQUET = "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"
DOSSIER = Path("data")
FICHIER_BRUT = DOSSIER / "decp.parquet"

COLONNES_GARDEES = [
    "uid", "objet", "montant", "codeCPV", "nature", "procedure",
    "dureeMois", "dureeRestanteMois", "offresRecues", "dateNotification",
    "acheteur_nom", "acheteur_categorie", "acheteur_departement_code",
    "acheteur_departement_nom", "acheteur_region_nom",
    "titulaire_nom", "titulaire_categorie", "titulaire_departement_nom",
    "donneesActuelles",
]
# Colonnes légères pour le fichier "opportunités" que lira l'appli.
COLONNES_OPPORTUNITES = [
    "uid", "objet", "montant", "codeCPV", "nature", "dureeRestanteMois",
    "dateNotification", "acheteur_nom", "acheteur_departement_nom",
    "acheteur_region_nom", "titulaire_categorie",
]
MONTANT_MIN, MONTANT_MAX = 1, 1_000_000_000
FAUSSES_DATES = {"1899-12-31", "1900-01-01", "1970-01-01"}

# Regroupement des natures de marché. Clé = version sans accent et en
# minuscules ; valeur = libellé propre affiché. Tout ce qui n'est pas
# reconnu garde sa forme d'origine (juste re-capitalisée).
NATURES_PROPRES = {
    "marche": "Marché",
    "accord-cadre": "Accord-cadre",
    "accord cadre": "Accord-cadre",
    "marche subsequent": "Marché subséquent",
    "marche de partenariat": "Marché de partenariat",
    "marche de defense ou de securite": "Marché de défense ou de sécurité",
    "concession de service public": "Concession de service public",
}


def sans_accent(texte: str) -> str:
    """Enlève les accents : 'Marché' et 'MARCHE' deviennent comparables."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def telecharger() -> None:
    DOSSIER.mkdir(exist_ok=True)
    print("Téléchargement du fichier officiel du jour...")
    temporaire = FICHIER_BRUT.with_suffix(".parquet.partiel")
    urllib.request.urlretrieve(RESSOURCE_PARQUET, temporaire)
    temporaire.rename(FICHIER_BRUT)
    print(f"  {FICHIER_BRUT.stat().st_size / 1e6:.0f} Mo récupérés")


def nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["donneesActuelles"] == True].copy()
    df = df.drop_duplicates(subset="uid", keep="first")
    df = df[[c for c in COLONNES_GARDEES if c in df.columns]].copy()

    # dates
    df["dateNotification"] = df["dateNotification"].astype(str).str.slice(0, 10)
    df.loc[df["dateNotification"].isin(FAUSSES_DATES), "dateNotification"] = None
    df["dateNotification"] = pd.to_datetime(df["dateNotification"], errors="coerce")

    # montants
    df["montant"] = pd.to_numeric(df["montant"], errors="coerce")
    df.loc[(df["montant"] < MONTANT_MIN) | (df["montant"] > MONTANT_MAX), "montant"] = None

    # objet : espaces + balises HTML résiduelles (<br />, etc.)
    df["objet"] = (
        df["objet"].astype(str)
        .str.replace(r"<[^>]+>", " ", regex=True)   # retire le HTML
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # nature : regrouper les orthographes (MARCHE / marché / Marché -> Marché)
    cle = df["nature"].astype(str).str.strip().str.lower().map(sans_accent)
    df["nature"] = cle.map(NATURES_PROPRES).fillna(cle.str.capitalize())
    return df


def main() -> None:
    telecharger()

    df = pd.read_parquet(FICHIER_BRUT)
    total_brut = len(df)
    propre = nettoyer(df)

    # Fichier propre complet (reste en local, trop gros pour le versionner).
    propre.to_parquet(DOSSIER / "decp_propre.parquet", index=False)

    # Fichier léger des opportunités : c'est lui que lira l'appli.
    restante = pd.to_numeric(propre["dureeRestanteMois"], errors="coerce")
    opportunites = propre[(restante > 0) & (restante <= 12)][
        [c for c in COLONNES_OPPORTUNITES if c in propre.columns]
    ].copy()
    opportunites.to_parquet(DOSSIER / "opportunites.parquet", index=False)

    # Résumé daté : la preuve que la mise à jour a bien eu lieu.
    resume = {
        "date_maj": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "lignes_brutes": int(total_brut),
        "marches_propres": int(len(propre)),
        "opportunites_12_mois": int(len(opportunites)),
        "date_marche_plus_recent": (
            propre["dateNotification"].max().strftime("%Y-%m-%d")
            if propre["dateNotification"].notna().any() else None
        ),
    }
    (DOSSIER / "derniere_maj.json").write_text(
        json.dumps(resume, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\nMise à jour terminée :")
    for cle, valeur in resume.items():
        print(f"  {cle} : {valeur}")


if __name__ == "__main__":
    main()
