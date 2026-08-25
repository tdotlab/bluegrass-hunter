from typing import Literal

from pydantic import BaseModel, Field


WebsiteStatus = Literal[
    "no_discoverable_website",
    "social_or_directory_only",
    "weak_website",
    "adequate_website",
    "unclear",
]

ActivityStatus = Literal[
    "confirmed_active",
    "likely_active",
    "unclear",
    "likely_inactive",
    "conflicted",
]

LocalityTier = Literal["tier_a_exact_town", "tier_b_nearby_rural", "tier_c_regional_or_unclear"]


class Lead(BaseModel):
    business_name: str
    town: str
    website_status: WebsiteStatus
    activity_status: ActivityStatus = "unclear"
    locality_tier: LocalityTier = "tier_a_exact_town"
    evidence_quality: int = Field(ge=1, le=5)
    business_legitimacy: int = Field(ge=1, le=5)
    service_value: int = Field(ge=1, le=5)
    local_fit: int = Field(ge=1, le=5)
    evidence: list[str] = Field(min_length=1)
    source_urls: list[str] = Field(min_length=1)
    observed_problems: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    verification_notes: str | None = None
    reasoning: str
    contact_hint: str | None = None


class ResearchReport(BaseModel):
    target: str
    method_note: str
    leads: list[Lead]
    exclusions: list[str] = Field(default_factory=list)
