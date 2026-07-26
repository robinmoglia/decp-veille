"""
Étape 1 — Explorer les données essentielles de la commande publique (DECP).

Objectif de ce script : télécharger le jeu consolidé une seule fois, puis
répondre à quatre questions avant d'écrire la moindre ligne de traitement.

  1. Qu'est-ce qu'il y a dedans ? (colonnes, types, volume)
  2. À quel point c'est sale ? (valeurs manquantes, doublons, aberrations)
  3. Est-ce que la donnée est fraîche ?
  4. Est-ce que l'information "date de renouvellement" est vraiment déductible ?

Lance-le, lis la sortie, et note tes observations dans le README.
C'est ça, le travail d'exploration — pas de coder vite.

Usage :
    pip install -r requirements.txt
    python 01_exploration.py
"""

from pathlib import Path
import urllib.request

import pandas as pd

# Identifiant stable de la ressource sur data.gouv.fr.
# L'URL /datasets/r/<id> renvoie toujours vers la dernière version publiée.
RESSOURCE_PARQUET = "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"
FICHIER_LOCAL = Path("data/decp.parquet")

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 60)


def telecharger_si_absent() -> Path:
    """Télécharge le parquet (~210 Mo) une seule fois."""
    FICHIER_LOCAL.parent.mkdir(exist_ok=True)
    if FICHIER_LOCAL.exists():
        taille = FICHIER_LOCAL.stat().st_size / 1e6
        print(f"Fichier déjà présent ({taille:.0f} Mo) — pas de retéléchargement.")
        return FICHIER_LOCAL

    print("Téléchargement en cours (~210 Mo, compte quelques minutes)...")

    def progression(blocs, taille_bloc, taille_totale):
        recu = blocs * taille_bloc / 1e6
        if taille_totale > 0:
            pct = min(100, recu / (taille_totale / 1e6) * 100)
            print(f"\r  {recu:.0f} Mo ({pct:.0f} %)", end="", flush=True)
        else:
            print(f"\r  {recu:.0f} Mo", end="", flush=True)

    # Fichier temporaire : si le téléchargement échoue, on ne garde pas
    # un fichier tronqué qui ferait planter la lecture au prochain lancement.
    temporaire = FICHIER_LOCAL.with_suffix(".parquet.partiel")
    urllib.request.urlretrieve(RESSOURCE_PARQUET, temporaire, reporthook=progression)
    temporaire.rename(FICHIER_LOCAL)
    print(f"\nTerminé : {FICHIER_LOCAL.stat().st_size / 1e6:.0f} Mo")
    return FICHIER_LOCAL


def titre(texte: str) -> None:
    print("\n" + "=" * 70)
    print(texte)
    print("=" * 70)


def main() -> None:
    chemin = telecharger_si_absent()
    df = pd.read_parquet(chemin)

    # ------------------------------------------------------------------
    titre("1. STRUCTURE")
    print(f"{len(df):,} lignes  x  {len(df.columns)} colonnes".replace(",", " "))
    print(f"Mémoire occupée : {df.memory_usage(deep=True).sum() / 1e9:.2f} Go")
    print("\nColonnes et types :")
    print(df.dtypes.to_string())

    print("\nAperçu de 3 lignes :")
    print(df.head(3).to_string())

    # ------------------------------------------------------------------
    titre("2. QUALITÉ — taux de valeurs manquantes par colonne")
    manquants = (df.isna().mean() * 100).sort_values(ascending=False)
    print(manquants.round(1).to_string())
    print(
        "\nÀ retenir : une colonne vide à plus de 60 % ne peut pas porter "
        "ta fonctionnalité principale. Choisis ton angle en fonction de ça."
    )

    # ------------------------------------------------------------------
    titre("3. FRAÎCHEUR")
    # Le jeu est annoncé comme quotidien : vérifie que c'est encore le cas.
    for col in ("datePublicationDonnees", "dateNotification"):
        if col in df.columns:
            dates = pd.to_datetime(df[col], errors="coerce")
            print(f"{col} : du {dates.min()} au {dates.max()}")
    print(
        "\nSi la date la plus récente a plusieurs semaines, la publication "
        "s'est peut-être interrompue. Vérifie sur la page data.gouv.fr avant "
        "de bâtir quoi que ce soit dessus."
    )

    # ------------------------------------------------------------------
    titre("4. MARCHÉS UNIQUES VS LIGNES")
    # Un marché apparaît sur plusieurs lignes : plusieurs titulaires,
    # et une ligne par modification (avenant).
    if "uid" in df.columns:
        print(f"Lignes            : {len(df):,}".replace(",", " "))
        print(f"Marchés uniques   : {df['uid'].nunique():,}".replace(",", " "))
        print(
            "\nC'est le piège n°1 du jeu de données : compter les lignes revient "
            "à surcompter les marchés. Pour l'état actuel de chaque marché, "
            "filtre sur donneesActuelles == True."
        )
    if "donneesActuelles" in df.columns:
        print("\nRépartition de donneesActuelles :")
        print(df["donneesActuelles"].value_counts(dropna=False).to_string())

    # ------------------------------------------------------------------
    titre("5. LE SIGNAL COMMERCIAL — échéances de marchés")
    # dureeRestanteMois est calculé en amont par le producteur des données.
    # C'est le cœur de ton produit : un marché qui se termine bientôt est
    # un marché qui va être remis en concurrence.
    colonnes_utiles = [
        c
        for c in ("uid", "objet", "acheteur_nom", "montant", "dureeMois", "dureeRestanteMois")
        if c in df.columns
    ]
    if "dureeRestanteMois" in df.columns:
        actuels = df[df["donneesActuelles"] == True] if "donneesActuelles" in df.columns else df
        restante = pd.to_numeric(actuels["dureeRestanteMois"], errors="coerce")
        bientot = actuels[(restante > 0) & (restante <= 12)]
        print(f"Marchés en cours se terminant dans les 12 mois : {len(bientot):,}".replace(",", " "))
        print("\nExemples :")
        print(bientot[colonnes_utiles].head(10).to_string())
        print(
            "\nVoilà ta valeur ajoutée : ces lignes sont invisibles pour une PME "
            "qui n'a pas d'outil, et chacune est une opportunité à préparer."
        )
    else:
        print(
            "Colonne dureeRestanteMois absente — recalcule-la toi-même à partir "
            "de dateNotification + dureeMois. C'est un bon exercice."
        )

    # ------------------------------------------------------------------
    titre("6. À QUOI RESSEMBLE LA SALETÉ")
    if "objet" in df.columns:
        print("15 objets de marché tirés au hasard :")
        for texte in df["objet"].dropna().sample(15, random_state=1):
            print("  -", str(texte)[:110])
        print(
            "\nRegarde bien : abréviations, fautes, MAJUSCULES, formulations "
            "administratives. Aucune règle fixe ne classera ça proprement. "
            "C'est exactement là que le LLM sert à quelque chose (étape 4)."
        )

    if "montant" in df.columns:
        montants = pd.to_numeric(df["montant"], errors="coerce")
        print("\nDistribution des montants :")
        print(montants.describe(percentiles=[0.5, 0.9, 0.99]).to_string())
        print(f"Montants nuls ou négatifs : {(montants <= 0).sum():,}".replace(",", " "))
        print("Les valeurs extrêmes sont des erreurs de saisie. À traiter à l'étape 2.")


if __name__ == "__main__":
    main()
