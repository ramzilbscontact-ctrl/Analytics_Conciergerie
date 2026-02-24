"""
Analytics_Conciergerie.py
=========================
Analyse des opérations de conciergerie - Booking Strasbourg
Objectif : Réduire les coûts opérationnels de 10% en anticipant les pics de flux

Auteur  : Responsable Conciergerie (Bachelor Business & Data)
Version : 1.0
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
import random

# ─── Reproductibilité ────────────────────────────────────────────────────────
np.random.seed(42)
random.seed(42)

# ─── 1. GÉNÉRATION DU DATASET (500 réservations) ─────────────────────────────

def generer_dataset(n: int = 500) -> pd.DataFrame:
    """Génère un dataset réaliste de réservations de conciergerie."""

    types_logement = ["Studio", "Appartement T2", "Appartement T3", "Suite"]
    poids_logement  = [0.35, 0.40, 0.15, 0.10]

    motifs_reclamation = ["Ménage insuffisant", "Bruit voisins", "Check-in tardif",
                          "Équipement défaillant", "Aucune réclamation"]
    poids_motifs = [0.18, 0.12, 0.20, 0.10, 0.40]

    dates_arrivee = [
        datetime(2023, 1, 1) + timedelta(days=int(x))
        for x in np.random.uniform(0, 364, n)
    ]

    durees_sejour = np.random.choice([1, 2, 3, 4, 5, 7, 10, 14],
                                     size=n,
                                     p=[0.15, 0.25, 0.20, 0.15, 0.10, 0.08, 0.05, 0.02])

    types = np.random.choice(types_logement, size=n, p=poids_logement)
    motifs = np.random.choice(motifs_reclamation, size=n, p=poids_motifs)

    # Temps d'attente check-in (minutes) – varie selon le mois et l'heure d'arrivée
    heures_arrivee = np.random.choice(range(14, 23), size=n,
                                      p=[0.05, 0.10, 0.20, 0.25, 0.18, 0.10, 0.06, 0.04, 0.02])
    mois = [d.month for d in dates_arrivee]
    is_haute_saison = np.array([1 if m in [6, 7, 8, 12] else 0 for m in mois])

    temps_attente = (
        np.random.exponential(scale=8, size=n)
        + is_haute_saison * np.random.uniform(5, 20, n)
        + (heures_arrivee > 19).astype(int) * np.random.uniform(3, 15, n)
    ).clip(0, 90).round(1)

    # Score NPS (0-10) : corrélé négativement avec le temps d'attente
    nps_base = np.random.normal(loc=7.5, scale=1.2, size=n)
    nps_penalite = (temps_attente / 90) * np.random.uniform(1.5, 3.0, size=n)
    nps_reclamation = np.array([1.5 if m != "Aucune réclamation" else 0 for m in motifs])
    nps = (nps_base - nps_penalite - nps_reclamation).clip(1, 10).round(1)

    # Coûts opérationnels
    cout_base = {"Studio": 45, "Appartement T2": 65, "Appartement T3": 85, "Suite": 120}
    cout_personnel = np.array([cout_base[t] for t in types], dtype=float)
    cout_maintenance = np.random.uniform(10, 40, n) + (durees_sejour > 5) * 15
    cout_reclamation = np.array([25 if m != "Aucune réclamation" else 0 for m in motifs])
    cout_total = (cout_personnel + cout_maintenance + cout_reclamation).round(2)

    df = pd.DataFrame({
        "id_reservation"    : range(1, n + 1),
        "date_arrivee"      : dates_arrivee,
        "mois"              : mois,
        "heure_arrivee"     : heures_arrivee,
        "duree_sejour"      : durees_sejour,
        "type_logement"     : types,
        "temps_attente_min" : temps_attente,
        "score_nps"         : nps,
        "motif_reclamation" : motifs,
        "cout_personnel"    : cout_personnel,
        "cout_maintenance"  : cout_maintenance.round(2),
        "cout_reclamation"  : cout_reclamation,
        "cout_total"        : cout_total,
        "haute_saison"      : is_haute_saison.astype(bool),
    })

    return df


# ─── 2. ANALYSES ──────────────────────────────────────────────────────────────

def analyser(df: pd.DataFrame) -> dict:
    """Calcule les KPIs et les données analytiques."""

    # KPIs globaux
    kpis = {
        "total_reservations" : len(df),
        "nps_moyen"          : round(df["score_nps"].mean(), 2),
        "cout_moyen"         : round(df["cout_total"].mean(), 2),
        "attente_moyenne"    : round(df["temps_attente_min"].mean(), 2),
        "taux_reclamation"   : round((df["motif_reclamation"] != "Aucune réclamation").mean() * 100, 1),
    }

    # Corrélation attente / NPS
    corr = df["temps_attente_min"].corr(df["score_nps"])
    kpis["correlation_attente_nps"] = round(corr, 3)

    # Coûts par mois
    couts_mensuels = df.groupby("mois")["cout_total"].agg(["mean", "sum", "count"]).reset_index()
    couts_mensuels.columns = ["mois", "cout_moyen", "cout_total", "nb_reservations"]

    # NPS par type de logement
    nps_logement = df.groupby("type_logement")["score_nps"].mean().round(2).to_dict()

    # Répartition des réclamations
    reclam = df["motif_reclamation"].value_counts().to_dict()

    # Attente par tranche horaire
    df["tranche_horaire"] = pd.cut(df["heure_arrivee"],
                                    bins=[13, 16, 18, 20, 23],
                                    labels=["14-16h", "17-18h", "19-20h", "21-23h"])
    attente_horaire = df.groupby("tranche_horaire", observed=True)["temps_attente_min"].mean().round(1).to_dict()

    # Simulation économies 10%
    cout_actuel = df["cout_total"].sum()
    cout_cible  = cout_actuel * 0.90
    economies   = cout_actuel - cout_cible

    # Scatter data pour graphique corrélation
    scatter_data = df[["temps_attente_min", "score_nps", "type_logement", "haute_saison"]].to_dict(orient="records")

    return {
        "kpis"           : kpis,
        "couts_mensuels" : couts_mensuels.to_dict(orient="records"),
        "nps_logement"   : nps_logement,
        "reclam"         : reclam,
        "attente_horaire": attente_horaire,
        "economies"      : {"actuel": round(cout_actuel, 2),
                            "cible" : round(cout_cible,  2),
                            "gain"  : round(economies,   2)},
        "scatter_data"   : scatter_data,
    }


# ─── 3. EXPORT JSON ───────────────────────────────────────────────────────────

def sauvegarder(df: pd.DataFrame, analyses: dict, dossier: str = ".") -> None:
    os.makedirs(dossier, exist_ok=True)

    # Dataset CSV
    csv_path = os.path.join(dossier, "reservations.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"[✓] Dataset CSV sauvegardé : {csv_path}")

    # Analyses JSON
    json_path = os.path.join(dossier, "analyses.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(analyses, f, ensure_ascii=False, indent=2, default=str)
    print(f"[✓] Analyses JSON sauvegardées : {json_path}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  Analytics Conciergerie – Booking Strasbourg")
    print("=" * 60)

    df       = generer_dataset(500)
    analyses = analyser(df)

    sauvegarder(df, analyses)

    kpis = analyses["kpis"]
    print(f"\n📊 KPIs Clés")
    print(f"  • Réservations analysées : {kpis['total_reservations']}")
    print(f"  • NPS moyen              : {kpis['nps_moyen']}/10")
    print(f"  • Coût moyen/réservation : {kpis['cout_moyen']} €")
    print(f"  • Temps d'attente moyen  : {kpis['attente_moyenne']} min")
    print(f"  • Taux de réclamation    : {kpis['taux_reclamation']}%")
    print(f"  • Corrélation attente/NPS: {kpis['correlation_attente_nps']}")

    eco = analyses["economies"]
    print(f"\n💰 Objectif Réduction Coûts (-10%)")
    print(f"  • Coût actuel  : {eco['actuel']:,.2f} €")
    print(f"  • Coût cible   : {eco['cible']:,.2f} €")
    print(f"  • Économies    : {eco['gain']:,.2f} €")

    print("\n[✓] Analyse terminée. Générez le dashboard avec build_dashboard.py")
