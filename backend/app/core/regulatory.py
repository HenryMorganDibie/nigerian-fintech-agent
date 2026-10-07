"""
Regulatory thresholds in one place
===================================
Every monetary threshold the scoring and filing logic depends on lives here,
so a compliance officer can review and change them without reading scoring code.

These values must be confirmed against the primary sources (MLPPA 2022, current
CBN AML/CFT regulations, NFIU guidance) by the deploying institution's
compliance function before going live. They are configuration, not law.
"""

# Currency Transaction Report threshold (single transaction / lodgement / transfer).
CTR_THRESHOLD_INDIVIDUAL_NGN = 5_000_000
CTR_THRESHOLD_CORPORATE_NGN = 10_000_000

# Structuring band: amounts kept deliberately just under the CTR threshold.
# Expressed as a fraction of the threshold so it tracks threshold changes.
STRUCTURING_BAND_FLOOR_RATIO = 0.90

# Suspicious Transaction Reports have no monetary floor: any suspicion triggers one.
STR_FILING_DEADLINE_HOURS = 24

POS_SINGLE_TX_LIMIT_NGN = 150_000


def ctr_threshold(customer_type: str = "individual") -> int:
    return CTR_THRESHOLD_CORPORATE_NGN if customer_type == "corporate" else CTR_THRESHOLD_INDIVIDUAL_NGN


def structuring_band(customer_type: str = "individual") -> tuple[float, float]:
    """Inclusive lower bound, exclusive upper bound."""
    threshold = ctr_threshold(customer_type)
    return threshold * STRUCTURING_BAND_FLOOR_RATIO, float(threshold)
