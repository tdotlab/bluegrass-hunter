from models import ResearchReport
from scoring import priority_label, priority_score


def render_markdown(report: ResearchReport) -> str:
    ranked = sorted(report.leads, key=priority_score, reverse=True)
    lines = [
        f"# Lead research: {report.target}",
        "",
        report.method_note,
        "",
        "## Ranked prospects",
        "",
        "| Priority | Business | Town | Activity | Website status | Why it matters |",
        "|---:|---|---|---|---|---|",
    ]

    for lead in ranked:
        score = priority_score(lead)
        lines.append(
            f"| {score}/5 ({priority_label(score)}) | {lead.business_name} | "
            f"{lead.town} | {lead.activity_status.replace('_', ' ')} | "
            f"{lead.website_status.replace('_', ' ')} | {lead.reasoning} |"
        )

    for lead in ranked:
        score = priority_score(lead)
        lines.extend(
            [
                "",
                f"### {lead.business_name} — {score}/5",
                f"**Activity status:** {lead.activity_status}",
                f"**Website status:** {lead.website_status}",
                f"**Locality tier:** {lead.locality_tier}",
                "",
                f"**Evidence:** {'; '.join(lead.evidence)}",
                "",
                f"**Observed problems:** {'; '.join(lead.observed_problems) or 'None recorded'}",
                "",
                f"**Contradictions:** {'; '.join(lead.contradictions) or 'None recorded'}",
                "",
                f"**Verification notes:** {lead.verification_notes or 'None recorded'}",
                "",
                f"**Reasoning:** {lead.reasoning}",
                "",
                f"**Contact hint:** {lead.contact_hint or 'None recorded'}",
                "",
                "**Sources:**",
            ]
        )
        lines.extend(f"- {url}" for url in lead.source_urls)

    if report.exclusions:
        lines.extend(["", "## Exclusions and cautions", ""])
        lines.extend(f"- {item}" for item in report.exclusions)

    return "\n".join(lines) + "\n"
