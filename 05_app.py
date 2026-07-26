"""
Étape 5 — L'interface : Observatoire des marchés publics à venir.

Une application web qui laisse une PME saisir son secteur et sa zone, et voir
les marchés publics qui vont être remis en concurrence dans les 12 mois.

Elle lit en priorité data/opportunites.parquet (produit par 04_maj.py).
Si ce fichier n'existe pas, elle retombe sur data/decp_propre.parquet (étape 2)
et calcule les opportunités elle-même.

Lancement (ce n'est PAS "python 05_app.py", mais) :
    pip install streamlit
    streamlit run 05_app.py

Une page web s'ouvre toute seule dans ton navigateur.
"""

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

FICHIER_OPPORTUNITES = Path("data/opportunites.parquet")
FICHIER_PROPRE = Path("data/decp_propre.parquet")

st.set_page_config(page_title="Marchés publics à venir", page_icon="📄", layout="wide")


@st.cache_data
def charger() -> pd.DataFrame:
    """Charge les opportunités. Le cache évite de relire le fichier à chaque clic."""
    if FICHIER_OPPORTUNITES.exists():
        df = pd.read_parquet(FICHIER_OPPORTUNITES)
    elif FICHIER_PROPRE.exists():
        df = duckdb.connect().execute(
            f"""
            SELECT uid, objet, montant, codeCPV, nature, dureeRestanteMois,
                   dateNotification, acheteur_nom, acheteur_departement_nom,
                   acheteur_region_nom, titulaire_categorie
            FROM read_parquet('{FICHIER_PROPRE.as_posix()}')
            WHERE dureeRestanteMois > 0 AND dureeRestanteMois <= 12
            """
        ).df()
    else:
        return pd.DataFrame()
    return df


def date_maj() -> str | None:
    fichier = Path("data/derniere_maj.json")
    if fichier.exists():
        return json.loads(fichier.read_text(encoding="utf-8")).get("date_maj")
    return None


# --- Chargement ------------------------------------------------------------
df = charger()

st.title("📄 Marchés publics à venir")
st.caption(
    "Les marchés en cours qui seront remis en concurrence dans les 12 mois — "
    "autant d'opportunités à préparer pour une PME."
)

if df.empty:
    st.error(
        "Aucune donnée trouvée. Lance d'abord `python 04_maj.py` "
        "(ou `02_nettoyage.py`) pour générer les fichiers dans data/."
    )
    st.stop()

maj = date_maj()
if maj:
    st.caption(f"Dernière mise à jour des données : {maj}")

# --- Barre latérale : les filtres -----------------------------------------
st.sidebar.header("Filtres")

secteur = st.sidebar.text_input(
    "Mot-clé du secteur (dans l'objet du marché)",
    placeholder="nettoyage, informatique, formation...",
)

departements = ["Tous"] + sorted(
    d for d in df["acheteur_departement_nom"].dropna().unique()
)
departement = st.sidebar.selectbox("Département de l'acheteur", departements)

mois_max = st.sidebar.slider("Expire dans (mois) au maximum", 1, 12, 12)

montant_min = st.sidebar.number_input("Montant minimum (€)", value=0, step=10000)

# --- Application des filtres -----------------------------------------------
resultat = df.copy()
if secteur.strip():
    resultat = resultat[
        resultat["objet"].str.contains(secteur.strip(), case=False, na=False)
    ]
if departement != "Tous":
    resultat = resultat[resultat["acheteur_departement_nom"] == departement]
resultat = resultat[resultat["dureeRestanteMois"] <= mois_max]
if montant_min > 0:
    resultat = resultat[resultat["montant"] >= montant_min]

# --- Indicateurs clés ------------------------------------------------------
col1, col2, col3 = st.columns(3)
col1.metric("Marchés trouvés", f"{len(resultat):,}".replace(",", " "))
enjeu = resultat["montant"].sum()
col2.metric("Enjeu total", f"{enjeu / 1e6:,.0f} M€".replace(",", " "))
mediane = resultat["montant"].median()
col3.metric(
    "Montant médian",
    f"{mediane:,.0f} €".replace(",", " ") if pd.notna(mediane) else "—",
)

# --- Graphique : opportunités par département ------------------------------
if departement == "Tous" and not resultat.empty:
    st.subheader("Répartition par département")
    par_dep = (
        resultat["acheteur_departement_nom"].value_counts().head(15).sort_values()
    )
    st.bar_chart(par_dep)

# --- Tableau détaillé ------------------------------------------------------
st.subheader("Détail des marchés")
affichage = resultat.sort_values("dureeRestanteMois")[
    [
        "dureeRestanteMois", "objet", "acheteur_nom",
        "acheteur_departement_nom", "montant", "nature",
    ]
].rename(
    columns={
        "dureeRestanteMois": "Mois restants",
        "objet": "Objet du marché",
        "acheteur_nom": "Acheteur",
        "acheteur_departement_nom": "Département",
        "montant": "Montant (€)",
        "nature": "Nature",
    }
)
st.dataframe(affichage, use_container_width=True, hide_index=True)

# --- Export ----------------------------------------------------------------
st.download_button(
    "⬇️ Télécharger ces résultats (CSV)",
    resultat.to_csv(index=False).encode("utf-8"),
    file_name="opportunites_filtrees.csv",
    mime="text/csv",
)
