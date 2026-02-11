"""Match 2018 Island Electricity Databook names to Census 2022 islands_master.csv names.
Produces island_name_matching_review.csv for human verification."""

import pandas as pd
from difflib import SequenceMatcher
from pathlib import Path

DATA_DIR = Path(__file__).parent

# Load both datasets
elec = pd.read_csv(DATA_DIR / "maldives_island_electricity_2018_clean_corrected.csv")
master = pd.read_csv(DATA_DIR / "islands_master.csv")

# Atoll name mapping: electricity (UPPERCASE + " ATOLL") → master (Title Case)
ATOLL_MAP = {
    "HAA ALIF ATOLL": "Haa Alifu",
    "ALIFU ALIFU ATOLL": "Alifu Alifu",
    "MEEMU ATOLL": "Meemu",
    "VAAVU ATOLL": "Vaavu",
    "KAAFU ATOLL": "Kaafu",
    "BAA ATOLL": "Baa",
    "FAAFU ATOLL": "Faafu",
    "GAAFU ALIF ATOLL": "Gaafu Alifu",
    "GNAVIYANI ATOLL": "Gnaviyani",
    "LAAMU ATOLL": "Laamu",
    "NOONU ATOLL": "Noonu",
    "RAA ATOLL": "Raa",
    "SEENU ATOLL": "Seenu",
}


def normalize(name: str) -> str:
    """Normalize island name for fuzzy comparison."""
    return name.strip().lower().replace("'", "").replace("-", "").replace(" ", "")


def find_best_match(island_name: str, mapped_atoll: str, master_df: pd.DataFrame):
    """Find best matching island in master dataset."""
    norm = normalize(island_name)

    # Same-atoll candidates
    if mapped_atoll and mapped_atoll in master_df["Atoll"].values:
        atoll_candidates = master_df[master_df["Atoll"] == mapped_atoll]
    else:
        atoll_candidates = pd.DataFrame()

    # Global best
    best_global = {"score": 0, "name": None, "pop": None, "pcode": None, "atoll": None}
    for _, row in master_df.iterrows():
        score = SequenceMatcher(None, norm, normalize(row["Island_Name"])).ratio()
        if score > best_global["score"]:
            best_global = {
                "score": score,
                "name": row["Island_Name"],
                "pop": row["Pop"],
                "pcode": row["PCode"],
                "atoll": row["Atoll"],
            }

    # Same-atoll best
    best_atoll = {"score": 0, "name": None, "pop": None, "pcode": None}
    for _, row in atoll_candidates.iterrows():
        score = SequenceMatcher(None, norm, normalize(row["Island_Name"])).ratio()
        if score > best_atoll["score"]:
            best_atoll = {
                "score": score,
                "name": row["Island_Name"],
                "pop": row["Pop"],
                "pcode": row["PCode"],
            }

    return best_global, best_atoll


# Build matching table
rows = []
for _, r in elec.iterrows():
    elec_atoll = r["Atoll"]
    elec_island = r["Island"]
    mapped_atoll = ATOLL_MAP.get(elec_atoll, "")

    best_global, best_atoll = find_best_match(elec_island, mapped_atoll, master)

    # Classify match quality
    if best_atoll["score"] >= 0.85:
        quality = "HIGH"
        match = {**best_atoll, "atoll": mapped_atoll}
    elif best_global["score"] >= 0.85:
        quality = "HIGH (diff atoll)"
        match = best_global
    elif best_atoll["score"] >= 0.6:
        quality = "REVIEW"
        match = {**best_atoll, "atoll": mapped_atoll}
    elif best_global["score"] >= 0.6:
        quality = "REVIEW (diff atoll)"
        match = best_global
    else:
        quality = "NO MATCH"
        match = best_global

    rows.append(
        {
            "elec_atoll": elec_atoll,
            "elec_island": elec_island,
            "elec_population_2018": r.get("Population", ""),
            "elec_production_kwh": r.get("Yearly_Electricity_Production_kWh", ""),
            "elec_capacity_kw": r.get("Total_Installed_Capacity_kW", ""),
            "match_quality": quality,
            "match_score": round(match["score"], 3),
            "master_island_name": match["name"],
            "master_atoll": match["atoll"],
            "master_pcode": match["pcode"],
            "master_pop_2022": match["pop"],
            "human_verified": "",
            "correct_master_match": "",
            "notes": "",
        }
    )

result = pd.DataFrame(rows)
result = result.sort_values(["match_quality", "match_score"], ascending=[True, True])

# Save
out_path = DATA_DIR / "island_name_matching_review.csv"
result.to_csv(out_path, index=False)

# Summary
print(f"Total electricity islands: {len(result)}")
print(f"\nMatch quality breakdown:")
for q, count in result["match_quality"].value_counts().items():
    print(f"  {q}: {count}")

# Also show master islands with NO match in electricity data
matched_pcodes = set(result["master_pcode"].dropna())
unmatched_master = master[~master["PCode"].isin(matched_pcodes)]
print(f"\nMaster islands NOT in electricity data: {len(unmatched_master)}")

# Show items needing review
review = result[result["match_quality"].str.contains("REVIEW|NO MATCH")]
if len(review) > 0:
    print(f"\n{'='*80}")
    print(f"  ITEMS NEEDING HUMAN REVIEW ({len(review)} items)")
    print(f"{'='*80}")
    for _, r2 in review.iterrows():
        print(
            f"  {r2.elec_island:25s} ({r2.elec_atoll:25s}) "
            f"--> {str(r2.master_island_name):20s} ({str(r2.master_atoll):15s}) "
            f"score={r2.match_score:.3f}  [{r2.match_quality}]"
        )
else:
    print("\n  All matches are HIGH confidence!")

print(f"\nSaved to: {out_path}")
