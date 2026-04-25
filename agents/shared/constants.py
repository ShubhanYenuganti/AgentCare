"""Runtime constants for Sprint 1 scaffold and quickstarter mocks."""

from __future__ import annotations

# review_by windows in hours (= expiry deadline)
REVIEW_BY_HOURS = {
    "tier_0": 2,
    "tier_1": 24,
    "tier_2": 48,
    "tier_3": 168,  # 7 days
}

# Urgency score for global action ranking
URGENCY_SCORES = {
    "tier_0": 100,
    "tier_1": 75,
    "tier_2": 50,
    "tier_3": 25,
}

# Overdue actions boosted above any non-overdue action
OVERDUE_SCORE_BOOST = 200

# Domain priority bonus added to urgency score
DOMAIN_PRIORITY = {
    "health": 10,
    "appointment": 7,
    "financial": 5,
    "grocery": 3,
    "scheduling": 8,
}

# Expiration loop interval (seconds)
EXPIRATION_CHECK_INTERVAL = 900  # 15 minutes

# Minimum gap between escalation notifications per action
ESCALATION_COOLDOWN = 900

# Token limits
QA_MAX_TOKENS = 300
MODIFICATION_MAX_TOKENS = 800

# Org context fields injected per domain
ORG_CONTEXT_MAP = {
    "health": ["health_protocol", "care_philosophy", "escalation_chain", "escalation_lead"],
    "appointment": ["transport_protocol", "visit_frequency_default", "care_philosophy"],
    "grocery": ["care_philosophy", "visit_frequency_default"],
    "financial": ["financial_protocol", "escalation_lead"],
    "executor": ["org_name", "escalation_lead", "escalation_chain"],
}

# Detection only fires on these triggers (no scheduled loops on supervisors)
DETECTION_TRIGGERS = ["patient_create", "patient_update"]

# Modification pipeline: health domain only in v1
MODIFICATION_ENABLED_DOMAINS = ["health"]

# Domains that may need Worker involvement for live API data
DOMAINS_WITH_LIVE_API = {
    "health": ["OpenFDA drug status", "recall updates"],
    "appointment": ["Google Maps route refresh"],
    "grocery": ["Instacart cart re-build"],
    "financial": [],
}

DOMAIN_COLORS = {
    "health": "#EF4444",
    "appointment": "#3B82F6",
    "grocery": "#10B981",
    "financial": "#F59E0B",
    "scheduling": "#8B5CF6",
}

DOMAIN_KEYWORDS = {
    "health": ["health", "medication", "pharmacy", "refill", "dose"],
    "appointment": ["appointment", "clinic", "doctor", "transport", "visit"],
    "grocery": ["grocery", "food", "delivery", "diet", "instacart"],
    "financial": ["financial", "bill", "payment", "autopay", "invoice"],
    "scheduling": ["schedule", "availability", "caregiver", "slot"],
}

AGENT_PORTS = {
    "executor": 8001,
    "health_supervisor": 8101,
    "health_worker": 8102,
    "appointment_supervisor": 8201,
    "appointment_worker": 8202,
    "grocery_supervisor": 8301,
    "grocery_worker": 8302,
    "financial_supervisor": 8401,
    "financial_worker": 8402,
    "scheduling_agent": 8501,
}

SUPPORTED_DOMAINS = ("health", "appointment", "grocery", "financial", "scheduling")
