from models import Lead


WEBSITE_POINTS = {
    "no_discoverable_website": 5,
    "social_or_directory_only": 5,
    "weak_website": 4,
    "unclear": 2,
    "adequate_website": 1,
}


def priority_score(lead: Lead) -> int:
    """Return a deterministic 1–5 prospecting score from the research evidence."""
    total = (
        WEBSITE_POINTS[lead.website_status]
        + lead.evidence_quality
        + lead.business_legitimacy
        + lead.service_value
        + lead.local_fit
    )
    return max(1, min(5, round(total / 5)))


def priority_label(score: int) -> str:
    return {
        5: "strong first bet",
        4: "good prospect",
        3: "worth a look",
        2: "low-confidence lead",
        1: "do not prioritize",
    }[score]
