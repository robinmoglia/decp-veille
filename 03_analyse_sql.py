"""
Étape 3 — Interroger les données propres en SQL (avec DuckDB).

DuckDB permet d'écrire du vrai SQL directement sur ton fichier parquet, sans
installer de serveur de base de données. Le langage est le même que PostgreSQL :
ce que tu apprends ici se réutilise tel quel quand on branchera la vraie base.

Chaque requête ci-dessous répond à une question qu'une PME se pose vraiment.
Lis-les, modifie-les, casse-les : c'est comme ça qu'on apprend le SQL.

Usage :
    pip install duckdb
    python 03_analyse_sql.py
"""

from pathlib import Path

import duckdb

FICHIER = "data/decp_propre.parquet"


def titre(texte: str) -> None:
    print("\n" + "=" * 70)
    print(texte)
    print("=" * 70)


def main() -> None:
    if not Path(FICHIER).exists():
        raise SystemExit("data/decp_propre.parquet introuvable. Lance d'abord 02_nettoyage.py")

    con = duckdb.connect()
    # On expose le parquet sous le nom de table "marches" pour écrire du SQL lisible.
    con.execute(f"CREATE VIEW marches AS SELECT * FROM read_parquet('{FICHIER}')")

    # 1 -------------------------------------------------------------------
    titre("1. Combien de marchés, pour quel montant total ?")
    print(
        con.execute(
            """
            SELECT
                COUNT(*)                         AS nb_marches,
                ROUND(SUM(montant) / 1e9, 1)     AS total_milliards_eur,
                ROUND(MEDIAN(montant))           AS montant_median_eur
            FROM marches
            """
        ).df().to_string(index=False)
    )

    # 2 -------------------------------------------------------------------
    titre("2. Les 15 plus gros acheteurs publics (en montant cumulé)")
    print(
        con.execute(
            """
            SELECT
                acheteur_nom,
                COUNT(*)                         AS nb_marches,
                ROUND(SUM(montant) / 1e6)        AS total_millions_eur
            FROM marches
            WHERE acheteur_nom IS NOT NULL
            GROUP BY acheteur_nom
            ORDER BY total_millions_eur DESC
            LIMIT 15
            """
        ).df().to_string(index=False)
    )

    # 3 -------------------------------------------------------------------
    titre("3. Nature des marchés (travaux, fournitures, services...)")
    print(
        con.execute(
            """
            SELECT
                nature,
                COUNT(*)                         AS nb_marches,
                ROUND(MEDIAN(montant))           AS montant_median_eur
            FROM marches
            GROUP BY nature
            ORDER BY nb_marches DESC
            """
        ).df().to_string(index=False)
    )

    # 4 -------------------------------------------------------------------
    titre("4. Part des marchés remportés par des PME")
    print(
        con.execute(
            """
            SELECT
                titulaire_categorie,
                COUNT(*)                                       AS nb_marches,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pourcentage
            FROM marches
            WHERE titulaire_categorie IS NOT NULL
            GROUP BY titulaire_categorie
            ORDER BY nb_marches DESC
            """
        ).df().to_string(index=False)
    )

    # 5 -------------------------------------------------------------------
    titre("5. LE SIGNAL PRODUIT — marchés qui expirent dans les 12 mois")
    # C'est la requête qui vaut de l'argent : chaque ligne est un marché
    # bientôt remis en concurrence, donc une opportunité pour une PME.
    print(
        con.execute(
            """
            SELECT
                COUNT(*)                         AS nb_marches_a_venir,
                ROUND(SUM(montant) / 1e9, 1)     AS enjeu_milliards_eur
            FROM marches
            WHERE dureeRestanteMois > 0
              AND dureeRestanteMois <= 12
            """
        ).df().to_string(index=False)
    )

    # 6 -------------------------------------------------------------------
    titre("6. Exemple concret : marchés de nettoyage/propreté expirant bientôt")
    # Un futur client (une entreprise de nettoyage) veut voir SES opportunités.
    # Le code CPV 90910000 = services de nettoyage ; on élargit avec un LIKE
    # sur l'objet pour rattraper les libellés non codés proprement.
    print(
        con.execute(
            """
            SELECT
                dateNotification,
                ROUND(dureeRestanteMois)         AS mois_restants,
                acheteur_nom,
                ROUND(montant)                   AS montant_eur,
                SUBSTR(objet, 1, 70)             AS objet_court
            FROM marches
            WHERE dureeRestanteMois > 0 AND dureeRestanteMois <= 12
              AND (codeCPV LIKE '9091%' OR LOWER(objet) LIKE '%nettoyage%')
            ORDER BY dureeRestanteMois ASC
            LIMIT 15
            """
        ).df().to_string(index=False)
    )

    # 7 -------------------------------------------------------------------
    titre("7. Où sont les opportunités ? (par département, échéance <12 mois)")
    print(
        con.execute(
            """
            SELECT
                acheteur_departement_nom         AS departement,
                COUNT(*)                         AS nb_marches_a_venir
            FROM marches
            WHERE dureeRestanteMois > 0 AND dureeRestanteMois <= 12
              AND acheteur_departement_nom IS NOT NULL
            GROUP BY acheteur_departement_nom
            ORDER BY nb_marches_a_venir DESC
            LIMIT 15
            """
        ).df().to_string(index=False)
    )

    con.close()
    print("\nÀ toi : change '%nettoyage%' en '%informatique%', '%formation%', "
          "'%restauration%'... pour voir les opportunités d'un autre secteur.")


if __name__ == "__main__":
    main()
