"""
Perplexity Research Lookup
==========================

Automated web research for 🔍 HUMAN LOOKUP items in the Improvement Plan.
Uses Perplexity's Sonar API for grounded, citation-backed answers.

Usage:
    # Single question
    python perplexity_lookup.py "What is the typical lifetime of a Caterpillar medium-speed diesel generator?"

    # Run all pending HUMAN LOOKUP items
    python perplexity_lookup.py --all

    # Run a specific HUMAN LOOKUP item by ID
    python perplexity_lookup.py --id H1

    # Save results to file
    python perplexity_lookup.py --all --output lookup_results.md

API Key:
    Set PERPLEXITY_API_KEY environment variable, or it will use the project default.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# API configuration
# ---------------------------------------------------------------------------
PERPLEXITY_API_KEY = os.environ.get(
    "PERPLEXITY_API_KEY",
    "",  # Set via environment variable: set PERPLEXITY_API_KEY=pplx-...
)
API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar-pro"  # Web-grounded model with citations

# ---------------------------------------------------------------------------
# HUMAN LOOKUP registry — maps H-IDs to structured research queries
# ---------------------------------------------------------------------------
HUMAN_LOOKUPS = {
    "H1": {
        "title": "Diesel genset lifetime (20yr source)",
        "blocks": "C3",
        "query": (
            "What is the rated design lifetime (in years) of a medium-speed diesel "
            "generator used for island power systems (500 kW–5 MW range)? "
            "Provide the source — preferably Caterpillar, Wärtsilä, MAN, or "
            "IRENA Renewable Power Generation Costs 2024. "
            "I need a citable reference with page/section number."
        ),
    },
    "H2": {
        "title": "HVDC submarine cable design life (40yr source)",
        "blocks": "C3",
        "query": (
            "What is the rated design life of an HVDC submarine power cable? "
            "Specifically for XLPE-insulated HVDC cables like NorNed, NordLink, or BorWin. "
            "Provide the source — preferably CIGRÉ Technical Brochure, ABB/Prysmian "
            "specifications, or IEC 62067. I need a citable reference."
        ),
    },
    "H3": {
        "title": "HVDC converter station cost (itemised)",
        "blocks": "C4",
        "query": (
            "What is the capital cost of an HVDC converter station (VSC type, "
            "200-500 MW capacity) in USD per MW or total cost? "
            "I need itemised costs separate from the submarine cable itself. "
            "Look for: CIGRÉ WG B4 reports, JICA India-Sri Lanka HVDC feasibility "
            "study 2019, ADB HVDC project appraisals, or IRENA innovation outlook "
            "for offshore infrastructure. Provide citable references."
        ),
    },
    "H4": {
        "title": "Inter-island AC submarine cable T&D losses",
        "blocks": "C2",
        "query": (
            "What are the transmission and distribution losses for short-distance "
            "(<30 km) submarine AC power cables connecting small islands? "
            "Look for: STELCO Maldives data, CIGRÉ TB 610, or Pacific island "
            "utility reports (Fiji, Tonga, Cook Islands). "
            "Provide percentage loss and citable reference."
        ),
    },
    "H5": {
        "title": "Per-island electricity generation in Maldives",
        "blocks": "M1, M3",
        "query": (
            "What is the per-island or per-atoll electricity generation (kWh/year) "
            "in the Maldives? Look for: STELCO Annual Report 2022 or 2023, "
            "Maldives Statistical Yearbook 2023, or ADB Maldives Energy Assessment. "
            "I need island-level or atoll-level consumption data, not just national totals."
        ),
    },
    "H6": {
        "title": "Outer-atoll fuel delivery surcharge",
        "blocks": "M3",
        "query": (
            "What is the fuel delivery cost premium for outer atolls in the Maldives "
            "compared to Malé? How much more does diesel cost per liter on remote "
            "Maldivian islands vs Malé? Look for: STO (State Trading Organisation) "
            "pricing data, STELCO operational reports, or World Bank Maldives energy studies."
        ),
    },
    "H7": {
        "title": "Sectoral electricity consumption (residential/tourism/desal)",
        "blocks": "M6",
        "query": (
            "What is the breakdown of electricity consumption by sector in the Maldives? "
            "Specifically: residential/commercial, tourism/resorts, and desalination/public "
            "services. Look for: STELCO annual report sectoral data, Maldives Energy Audit, "
            "or ADB/World Bank Maldives energy sector assessment."
        ),
    },
    "H8": {
        "title": "Health damage cost of diesel per MWh",
        "blocks": "L4",
        "query": (
            "What is the estimated health damage cost (in USD) per MWh of diesel "
            "electricity generation in developing countries or small island states? "
            "Look for: Parry et al. 2014 IMF Working Paper 14/199 'Getting Energy "
            "Prices Right' Table 3, WHO Global Health Observatory diesel health "
            "estimates, or Markandya & Wilkinson 2007 Lancet. Provide the value "
            "in USD/MWh and the citable reference."
        ),
    },
    "H9": {
        "title": "Climate adaptation CAPEX premium for SIDS infrastructure",
        "blocks": "L3",
        "query": (
            "What is the typical CAPEX premium (% increase) for climate-proofing "
            "energy infrastructure in Small Island Developing States (SIDS)? "
            "Look for: GCF Simplified Approval Process project documents for Pacific "
            "SIDS, ADB climate-proofing guidelines, World Bank climate resilient "
            "infrastructure reports. Provide the premium percentage and source."
        ),
    },
    "H10": {
        "title": "Commercial lending rate in Maldives",
        "blocks": "L5",
        "query": (
            "What is the current commercial lending interest rate in the Maldives "
            "for infrastructure projects? Look for: Maldives Monetary Authority "
            "annual report 2023 or 2024, IMF Article IV Consultation for Maldives "
            "2023-2024, or ADB Maldives country assessment. "
            "Provide the rate and citable source."
        ),
    },
    "H11": {
        "title": "Resort electricity consumption data",
        "blocks": "L6",
        "query": (
            "What is the typical electricity consumption of a tourist resort in "
            "the Maldives? In kWh per room-night or MW installed capacity per resort. "
            "Look for: Maldives Tourism Ministry data, MMPRC reports, or academic "
            "studies on Maldives resort energy consumption. "
            "There are ~160 resort islands with 0.5-5 MW diesel each."
        ),
    },
    "H12": {
        "title": "Eco-tourism willingness to pay for green power",
        "blocks": "L6",
        "query": (
            "What is the willingness to pay (WTP) premium for green/renewable energy "
            "among tourists in the Maldives or similar tropical SIDS destinations? "
            "In USD per room-night or $/kWh. Look for academic studies on eco-tourism "
            "WTP, green hotel certification premiums, or SIDS tourism sustainability surveys."
        ),
    },
    "H13": {
        "title": "Idle diesel fleet maintenance cost (strategic reserve)",
        "blocks": "L2",
        "query": (
            "What is the annual cost of maintaining idle diesel generators as strategic "
            "backup/reserve? In USD/MW/year or as a percentage of original CAPEX. "
            "Look for: Tasmania's diesel reserve costs after Basslink outages, "
            "or utility reports on diesel backup fleet maintenance for island systems."
        ),
    },
    "H14": {
        "title": "Household electricity connection cost in Maldives",
        "blocks": "L11",
        "query": (
            "What is the cost of a new household electricity connection in the Maldives? "
            "In USD per household. Look for: STELCO or FENAKA connection fee schedules, "
            "ADB island electrification project appraisals, or World Bank ESMAP reports "
            "on connection costs in SIDS."
        ),
    },
}


def query_perplexity(question: str, system_prompt: str = None) -> dict:
    """
    Query Perplexity's Sonar API for a web-grounded answer.

    Returns dict with 'answer', 'citations', 'model', 'usage'.
    """
    import urllib.request
    import urllib.error

    if system_prompt is None:
        system_prompt = (
            "You are an expert energy economist researching parameters for a "
            "Cost-Benefit Analysis of energy transition in the Maldives (SIDS). "
            "CRITICAL REQUIREMENTS:\n"
            "1. Provide PRECISE numerical values, not just qualitative discussion.\n"
            "2. Every value MUST have a FULL CITATION: Author(s), Year, Title, "
            "Publisher/Journal, page/section/table number.\n"
            "3. Prefer RECENT sources (2018-2026). Reject pre-2015 data unless it is "
            "the canonical reference (e.g., IPCC 2006 emission factors).\n"
            "4. Prefer peer-reviewed or official institutional sources: IRENA, IEA, ADB, "
            "World Bank, CIGR\u00c9, IMF, WHO, manufacturer datasheets.\n"
            "5. If you cannot find a precise value with a citable source, say EXPLICITLY: "
            "'NO CITABLE SOURCE FOUND' and explain what you did find.\n"
            "6. If a value is uncertain, give a range and explain the uncertainty.\n"
            "7. At the end of your answer, provide a VERDICT line in this exact format:\n"
            "   VERDICT: RESOLVED | <value> | <Author Year> or VERDICT: UNRESOLVED | <reason>\n"
            "   Example: VERDICT: RESOLVED | 40yr | CIGR\u00c9 TB 852 (2024)\n"
            "   Example: VERDICT: UNRESOLVED | No peer-reviewed SIDS-specific data found"
        )

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    })

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    req = urllib.request.Request(API_URL, data=payload.encode("utf-8"), headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}

    # Extract answer and citations
    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    citations = data.get("citations", [])
    usage = data.get("usage", {})

    return {
        "answer": answer,
        "citations": citations,
        "model": data.get("model", MODEL),
        "usage": usage,
    }


def lookup_single(h_id: str) -> str:
    """Run a single HUMAN LOOKUP item and return formatted result."""
    item = HUMAN_LOOKUPS.get(h_id.upper())
    if not item:
        return f"❌ Unknown HUMAN LOOKUP ID: {h_id}"

    print(f"\n🔍 Researching {h_id}: {item['title']}...")
    print(f"   Blocks: {item['blocks']}")
    print(f"   Query: {item['query'][:80]}...")

    result = query_perplexity(item["query"])

    if "error" in result:
        return f"❌ {h_id} — API Error: {result['error']}"

    output = []
    output.append(f"### {h_id}: {item['title']}")
    output.append(f"**Blocks:** {item['blocks']}")
    output.append(f"**Queried:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    output.append(f"**Model:** {result['model']}")
    output.append("")
    output.append("**Answer:**")
    output.append(result["answer"])
    output.append("")
    if result.get("citations"):
        output.append("**Citations from Perplexity:**")
        for i, cite in enumerate(result["citations"], 1):
            output.append(f"{i}. {cite}")
        output.append("")

    # Parse VERDICT line from answer
    verdict_line = ""
    for line in result["answer"].split("\n"):
        if line.strip().startswith("VERDICT:"):
            verdict_line = line.strip()
            break

    if "RESOLVED" in verdict_line and "UNRESOLVED" not in verdict_line:
        output.append(f"[RESOLVED] **STATUS: RESOLVED** -- {verdict_line}")
        output.append("")
        output.append("ACTION REQUIRED:")
        output.append(f"  1. Update `IMPROVEMENT_PLAN.md` -> H-table: mark {h_id} as ~~struck~~ RESOLVED")
        output.append(f"  2. Update `IMPROVEMENT_PLAN.md` -> Decision Log: update status with citation")
        output.append(f"  3. Update `parameters.csv` if the value/source needs adding")
        output.append(f"  4. Verify the citation URL/DOI actually exists before committing")
    else:
        output.append("SEARCH **STATUS: STILL NEEDS HUMAN LOOKUP**")
        output.append("")
        output.append("ACTION REQUIRED:")
        output.append(f"  1. Keep {h_id} in `IMPROVEMENT_PLAN.md` HUMAN LOOKUP table")
        output.append(f"  2. Add note: 'Perplexity searched {datetime.now().strftime('%Y-%m-%d')} -- no citable source found'")
        output.append(f"  3. Human must search primary sources listed in H-table")
        if verdict_line:
            output.append(f"  4. Perplexity said: {verdict_line}")
    output.append("")
    output.append("---")

    return "\n".join(output)


def lookup_all(ids: list = None) -> str:
    """Run all (or selected) HUMAN LOOKUP items."""
    if ids is None:
        ids = list(HUMAN_LOOKUPS.keys())

    results = []
    results.append(f"# 🔍 HUMAN LOOKUP Research Results")
    results.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    results.append(f"**API:** Perplexity Sonar Pro")
    results.append(f"**Items:** {len(ids)}")
    results.append("")

    for h_id in ids:
        result = lookup_single(h_id)
        results.append(result)
        print(f"   ✓ {h_id} complete")

    return "\n".join(results)


def main():
    parser = argparse.ArgumentParser(
        description="Research HUMAN LOOKUP items using Perplexity API"
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Free-form research question",
    )
    parser.add_argument(
        "--id",
        help="Run a specific HUMAN LOOKUP item (e.g., H1, H3)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all pending HUMAN LOOKUP items",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all HUMAN LOOKUP items",
    )
    parser.add_argument(
        "--output", "-o",
        help="Save results to file (Markdown)",
    )

    args = parser.parse_args()

    # List mode
    if args.list:
        print("\n🔍 HUMAN LOOKUP Items:")
        print(f"{'ID':<5} {'Blocks':<8} {'Title'}")
        print("-" * 60)
        for h_id, item in HUMAN_LOOKUPS.items():
            print(f"{h_id:<5} {item['blocks']:<8} {item['title']}")
        return

    # Single lookup by ID
    if args.id:
        result = lookup_single(args.id)
        print(result)
        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print(f"\n💾 Saved to {args.output}")
        return

    # All lookups
    if args.all:
        result = lookup_all()
        print(result)
        if args.output:
            Path(args.output).write_text(result, encoding="utf-8")
            print(f"\n💾 Saved to {args.output}")
        return

    # Free-form question
    if args.question:
        print(f"\n🔍 Researching: {args.question}")
        result = query_perplexity(args.question)
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"\n{result['answer']}")
            if result.get("citations"):
                print("\n📚 Citations:")
                for i, c in enumerate(result["citations"], 1):
                    print(f"  {i}. {c}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
