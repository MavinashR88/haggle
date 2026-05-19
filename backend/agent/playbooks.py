"""
Provider-specific playbooks: known escalation paths, magic phrases,
hold music patterns, and leverage data for each provider.
Injected into the negotiation context at call time.
"""

PLAYBOOKS = {
    "comcast": {
        "display_name": "Comcast Xfinity",
        "retention_number": "1-800-934-6489",
        "retention_dept": "Customer Solutions / Loyalty queue",
        "magic_phrases": [
            "I'd like to speak to the retention department",
            "Customer Solutions team",
        ],
        "frontline_cap": "$10 credit — real discounts require retention queue",
        "known_competitors": ["T-Mobile Home Internet ($50/mo)", "Verizon Fios", "Spectrum"],
        "leverage_notes": "Comcast has the highest churn sensitivity of any ISP. 3yr+ tenure + competitor pricing = ~40% off. Never accept 6-month offers — push for 12.",
        "typical_discount_range": "20-40%",
        "escalation_trigger": "ask for retention after first declined offer",
        "dtmf_ivr": ["1", "3", "0"],  # Press 1 for billing, 3 for cancel/reduce, 0 for operator
    },
    "att": {
        "display_name": "AT&T",
        "retention_number": "1-800-288-2020",
        "retention_dept": "Loyalty Department",
        "magic_phrases": ["I'd like to speak with the loyalty department", "cancellation request"],
        "frontline_cap": "$5-10 credit",
        "known_competitors": ["T-Mobile", "Verizon", "Spectrum Mobile"],
        "leverage_notes": "AT&T responds strongly to bundle threats. If internet-only, threaten to move wireless too. Loyalty dept has $20-30/mo off authority.",
        "typical_discount_range": "15-25%",
        "escalation_trigger": "mention mobile bundle threat after first decline",
        "dtmf_ivr": ["2", "4"],
    },
    "verizon": {
        "display_name": "Verizon",
        "retention_number": "1-800-922-0204",
        "retention_dept": "Customer Retention",
        "magic_phrases": ["retention", "thinking about cancelling", "better offer from competitor"],
        "frontline_cap": "$15 credit",
        "known_competitors": ["T-Mobile Home Internet", "Comcast", "AT&T Fiber"],
        "leverage_notes": "Verizon is the hardest to negotiate with — they rely on reliability reputation. Lead with competitor speed+price combo. Best results: 10-20% off.",
        "typical_discount_range": "10-20%",
        "escalation_trigger": "escalate immediately to supervisor if first offer <10%",
        "dtmf_ivr": ["4", "0"],
    },
    "spectrum": {
        "display_name": "Spectrum / Charter",
        "retention_number": "1-855-707-7328",
        "retention_dept": "Retention Team",
        "magic_phrases": ["I want to cancel", "retention team", "loyalty discount"],
        "frontline_cap": "$10 one-time credit",
        "known_competitors": ["Comcast Xfinity", "AT&T Fiber", "T-Mobile"],
        "leverage_notes": "Spectrum has no contracts — use this against them. 'Since there's no contract I can leave anytime — what can you offer to keep me?'",
        "typical_discount_range": "20-35%",
        "escalation_trigger": "threaten immediate cancellation — no contract makes this credible",
        "dtmf_ivr": ["1", "2", "0"],
    },
    "planet_fitness": {
        "display_name": "Planet Fitness",
        "retention_number": "local club number",
        "retention_dept": "Club manager",
        "magic_phrases": ["I'd like to speak with the manager", "membership freeze instead of cancel"],
        "frontline_cap": "Cannot discount — only freeze or cancel",
        "known_competitors": ["YMCA", "LA Fitness", "Anytime Fitness"],
        "leverage_notes": "Gym staff have very limited discount authority. Best play: threaten cancel + ask for manager + request 3-month freeze as compromise. Annual Black Card members get more flexibility.",
        "typical_discount_range": "0% (freeze only)",
        "escalation_trigger": "ask for manager immediately",
        "dtmf_ivr": [],
    },
    "chase": {
        "display_name": "Chase",
        "retention_number": "number on back of card",
        "retention_dept": "Account Services / Retention",
        "magic_phrases": ["I'd like to request a credit limit increase", "APR reduction request"],
        "leverage_notes": "Chase responds to: 3+ years on-time payments, income increase, competitor offers with better limits. Soft pull first — ask before they run hard inquiry.",
        "typical_discount_range": "Limit: 50-100% increase typical. APR: 3-5 points reduction.",
        "escalation_trigger": "If declined on limit: ask what criteria to meet; request reconsideration in 6 months",
        "dtmf_ivr": ["0"],
    },
    "capital_one": {
        "display_name": "Capital One",
        "retention_number": "1-800-227-4825",
        "retention_dept": "Account Services",
        "magic_phrases": ["credit limit increase", "I've been a customer for X years with no missed payments"],
        "leverage_notes": "Capital One uses internal credit score model. Emphasize: account age, payment history, utilization under 30%. They auto-approve limit increases online first — mention you prefer to discuss with agent.",
        "typical_discount_range": "Limit: 25-100% increase. APR: 2-4 points.",
        "escalation_trigger": "mention competitor offer after first decline",
        "dtmf_ivr": ["0"],
    },
}

DEFAULT_PLAYBOOK = {
    "display_name": "Provider",
    "retention_dept": "Customer Retention",
    "magic_phrases": ["I'd like to speak with a supervisor", "retention team"],
    "leverage_notes": "Use competitor pricing and tenure as primary leverage.",
    "typical_discount_range": "10-25%",
    "escalation_trigger": "escalate to supervisor after two declines",
    "dtmf_ivr": ["0"],
}


def get_playbook(provider_key: str) -> dict:
    return PLAYBOOKS.get(provider_key.lower().replace(" ", "_"), DEFAULT_PLAYBOOK)


def format_leverage_points(playbook: dict, context: dict) -> str:
    """Build ranked leverage bullet list for the system prompt."""
    points = []
    tenure = context.get("tenure", 1)
    current_bill = context.get("current_bill", "")
    competitors = playbook.get("known_competitors", [])

    if competitors:
        comp = competitors[0]
        points.append(f"1. COMPETITOR PRICING: Cite {comp} as a cheaper alternative you're seriously considering.")
    if tenure >= 2:
        points.append(f"2. TENURE: 'I have been a customer for {tenure} years on autopay. I'd expect loyalty to count for something.'")
    if len(competitors) > 1:
        points.append(f"3. MULTIPLE OPTIONS: You have other choices: {', '.join(competitors[:2])}.")
    points.append(f"4. MAGIC PHRASE for escalation: '{playbook['magic_phrases'][0]}'")
    points.append(f"5. NOTE: {playbook.get('leverage_notes', '')}")
    return "\n".join(points)
