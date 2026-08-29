FORMULA_VERSION = "1.0.0"

SEVERITY_PENALTY = {
    "critical": 28,
    "high": 16,
    "medium": 8,
    "low": 4,
    "info": 1,
}

WEBSITE_WEIGHTS = {
    "technical": 0.22,
    "performance": 0.10,
    "mobile": 0.15,
    "seo": 0.15,
    "conversion": 0.13,
    "ux": 0.10,
    "ui": 0.10,
    "trust": 0.05,
}

OPPORTUNITY_WEIGHTS = {
    "website_gap": 0.35,
    "business_potential": 0.30,
    "solvable_problems": 0.15,
    "conversion_opportunity": 0.10,
    "digital_activity": 0.10,
}


def clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))
