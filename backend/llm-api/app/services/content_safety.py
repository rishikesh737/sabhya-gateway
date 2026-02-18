"""
Content Safety Service - Sabhya AI v0.4.0
Blocks harmful, dangerous, or policy-violating content.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import structlog

log = structlog.get_logger()


@dataclass
class ContentCheckResult:
    """Result of content safety check."""

    is_safe: bool
    blocked_reason: Optional[str] = None
    matched_category: Optional[str] = None
    matched_pattern: Optional[str] = None
    risk_score: float = 0.0


# Categories of harmful content with patterns
HARMFUL_CATEGORIES = {
    "weapons_explosives": {
        "description": "Weapons, explosives, or dangerous materials",
        "patterns": [
            r"\b(make|build|create|construct|manufacture)\b.{0,30}\b(bomb|explosive|ied|grenade|weapon|gun|firearm)\b",
            r"\b(bomb|explosive|ied|grenade)\b.{0,30}\b(make|build|create|instructions|how to)\b",
            r"\b(time\s*bomb|pipe\s*bomb|nail\s*bomb|car\s*bomb|dirty\s*bomb)\b",
            r"\b(gunpowder|thermite|napalm|molotov)\b.{0,30}\b(recipe|make|create)\b",
            r"\b(3d\s*print|ghost\s*gun)\b.{0,20}\b(weapon|gun|firearm)\b",
        ],
        "risk_weight": 1.0,
    },
    "violence_harm": {
        "description": "Violence, self-harm, or harm to others",
        "patterns": [
            r"\b(kill|murder|assassinate|attack)\b.{0,30}\b(how to|ways to|method)\b",
            r"\b(how to|ways to)\b.{0,30}\b(kill|murder|poison|suffocate)\b.{0,20}\b(someone|person|people)\b",
            r"\b(torture|kidnap|abduct)\b.{0,20}\b(how to|instructions)\b",
            r"\b(suicide|self.?harm)\b.{0,20}\b(method|how to|ways)\b",
        ],
        "risk_weight": 1.0,
    },
    "illegal_activities": {
        "description": "Illegal hacking, fraud, or criminal activities",
        "patterns": [
            r"\b(hack|crack|breach|penetrate)\b.{0,30}\b(bank|atm|credit\s*card|password|account|system|server|computer)\b",
            r"\b(steal|clone|copy)\b.{0,20}\b(identity|credit\s*card|credentials|password|data)\b",
            r"\b(phishing|ransomware|malware|virus|trojan|worm)\b.{0,20}\b(create|make|build|how to|write)\b",
            r"\b(counterfeit|forge)\b.{0,20}\b(money|currency|documents|id)\b",
            r"\b(bypass|evade|circumvent)\b.{0,20}\b(security|authentication|firewall|antivirus|police)\b",
            r"\b(how to|ways to|how do i)\b.{0,30}\b(get into|break into|access|log into)\b.{0,20}\b(computer|phone|account|email|server|pc|laptop)\b",
            r"\b(how do i|how to)\b.{0,10}\b(into)\b.{0,20}\b(computer|phone|account|email|server|pc|laptop)\b",
            r"\b(unauthorized|illegal)\b.{0,20}\b(access|entry)\b",
        ],
        "risk_weight": 0.9,
    },
    "drugs_substances": {
        "description": "Illegal drug synthesis or trafficking",
        "patterns": [
            r"\b(synthesize|make|cook|manufacture)\b.{0,30}\b(meth|cocaine|heroin|fentanyl|lsd|mdma)\b",
            r"\b(meth|cocaine|heroin|fentanyl)\b.{0,30}\b(recipe|synthesis|cook|make)\b",
            r"\b(drug\s*lab|clandestine\s*lab)\b",
        ],
        "risk_weight": 0.9,
    },
    "csam_exploitation": {
        "description": "Child exploitation or CSAM",
        "patterns": [
            r"\b(child|minor|underage)\b.{0,30}\b(porn|sexual|nude|naked|exploit)\b",
            r"\b(lolita|pedo|cp\b|csam)\b",
        ],
        "risk_weight": 1.0,
    },
}

# Quick block keywords (immediate rejection without regex)
BLOCK_KEYWORDS = [
    "make a bomb",
    "build a bomb",
    "how to make bomb",
    "make explosives",
    "build explosives",
    "synthesize meth",
    "cook meth",
    "make fentanyl",
    "child porn",
    "child pornography",
    "hack into",
    "break into computer",
    "steal password",
    "how to hack",
    "generate malware",
]


class ContentSafetyService:
    """Service to check content for harmful, dangerous, or policy-violating material."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._compile_patterns()
        log.info(
            "content_safety_initialized",
            enabled=enabled,
            categories=len(HARMFUL_CATEGORIES),
        )

    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        for category, config in HARMFUL_CATEGORIES.items():
            self._compiled_patterns[category] = [
                re.compile(pattern, re.IGNORECASE) for pattern in config["patterns"]
            ]

    def check_content(self, text: str) -> ContentCheckResult:
        """
        Check if the content contains harmful material.

        Returns:
            ContentCheckResult with is_safe=False if harmful content detected.
        """
        if not self.enabled:
            return ContentCheckResult(is_safe=True)

        if not text or not text.strip():
            return ContentCheckResult(is_safe=True)

        text_lower = text.lower()

        # Quick keyword check first (fast path)
        for keyword in BLOCK_KEYWORDS:
            if keyword in text_lower:
                log.warning(
                    "content_blocked_keyword", keyword=keyword, text_preview=text[:50]
                )
                return ContentCheckResult(
                    is_safe=False,
                    blocked_reason="This request contains content that violates our usage policy.",
                    matched_category="blocked_keyword",
                    matched_pattern=keyword,
                    risk_score=1.0,
                )

        # Regex pattern matching
        for category, patterns in self._compiled_patterns.items():
            config = HARMFUL_CATEGORIES[category]
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    log.warning(
                        "content_blocked_pattern",
                        category=category,
                        pattern=pattern.pattern[:50],
                        matched_text=match.group(0)[:30],
                        text_preview=text[:50],
                    )
                    return ContentCheckResult(
                        is_safe=False,
                        blocked_reason=f"This request was blocked: {config['description']}",
                        matched_category=category,
                        matched_pattern=pattern.pattern,
                        risk_score=config["risk_weight"],
                    )

        return ContentCheckResult(is_safe=True)

    def is_safe(self, text: str) -> bool:
        """Simple boolean check for content safety."""
        return self.check_content(text).is_safe


# Global service instance
content_safety_service = ContentSafetyService()
