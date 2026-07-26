# Veille sur la commande publique

Outil de détection d'opportunités commerciales pour les PME, à partir des données
ouvertes des marchés publics français.

> Ce README est ta vitrine. Un recruteur y passera 90 secondes. Remplis les
> sections marquées `À COMPLÉTER` au fur et à mesure — surtout les chiffres.

## Le problème

Une PME qui veut vendre à des acheteurs publics ne sait pas qui achète sa
prestation, à quel prix, ni quand les contrats en cours seront remis en
concurrence. L'information est publique et obligatoire, mais elle est diluée
dans un fichier de plus de 2 Go que personne n'ouvre.

## Ce que fait l'outil

`À COMPLÉTER quand la v1 tourne.`

## Source des données

- Jeu consolidé : [DECP consolidées, format tabulaire](https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire) — Parquet (~210 Mo) et CSV (~2,2 Go), mise à jour annoncée quotidienne
- Licence Ouverte 2.0 : réutilisation libre, y compris commerciale, avec mention de la source
- API tabulaire pour interroger sans base de données : `https://tabular-api.data.gouv.fr/api/resources/22847056-61df-452d-837d-8b8ceadbfc52/data/`
- Fichier bonus : `probabilites-naf-cpv.csv` donne, pour un code NAF d'entreprise, les codes CPV de marchés les plus probables. C'est ce qui permettra de dire à une PME « voici les marchés qui te correspondent » à partir de son seul SIRET.

### Pièges connus (vérifiés avant de commencer)

- Un marché occupe **plusieurs lignes** : une par titulaire et une par modification (avenant). Compter les lignes revient à surcompter. Identifiant global : `uid`.
- `donneesActuelles == True` isole la dernière version de chaque marché.
- `modification_id == 0` correspond à l'attribution initiale.
- La colonne `dureeRestanteMois` porte le signal commercial central : un marché qui se termine bientôt sera remis en concurrence.

## Étapes

- [ ] **1. Explorer** — `01_exploration.py`. Comprendre le contenu, mesurer la saleté.
- [ ] **2. Nettoyer et structurer** — schéma PostgreSQL, chargement, requêtes SQL.
- [ ] **3. Automatiser** — mise à jour quotidienne via GitHub Actions.
- [ ] **4. Enrichir** — classification des objets de marché par LLM, précision mesurée.
- [ ] **5. Restituer** — application Streamlit + alerte hebdomadaire.

## Ce que j'ai appris

**Exploration du 23/07/2026 (jeu du 23/07).**

- **Volume** : 3 141 176 lignes, 58 colonnes, ~8,7 Go en mémoire. Pour 1 738 976 marchés uniques → environ 1,8 ligne par marché (plusieurs titulaires et avenants).
- **Fraîcheur confirmée** : données jusqu'au jour même. Le flux quotidien fonctionne.
- **État courant** : `donneesActuelles == True` isole 1 993 256 lignes ; 1 115 697 sont d'anciennes versions et 32 223 sont à `None`.
- **Signal produit** : 240 810 marchés en cours se terminent dans les 12 mois → cœur de la fonctionnalité d'alerte.
- **Défauts de qualité identifiés (à corriger à l'étape 2)** :
  - fausses dates `1899-12-31` = cases vides mal exportées, à convertir en `NaT` ;
  - montants : max à 1e11 € (aberrant), 64 408 valeurs ≤ 0, médiane réaliste à 165 590 € ;
  - colonnes vides à >70 % (`idAccordCadre` 90 %, `origineFrance/UE` 89 %, `tauxAvance` 81 %, `marcheInnovant` 72 %) → écartées de la table principale.
- **Colonnes solides à garder** : `uid`, `objet`, `montant`, `codeCPV`, `dureeMois`, `dureeRestanteMois`, `dateNotification`, `acheteur_nom`, `acheteur_departement_code`, `titulaire_nom`, `titulaire_categorie` (PME/ETI/GE — utile plus tard), `donneesActuelles`.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
python 01_exploration.py
```
