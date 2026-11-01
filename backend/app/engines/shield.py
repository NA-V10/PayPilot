"""AgentShield: prompt-injection defense for external content.

Everything an agent reads from the outside world (merchant pages, reviews, emails, tool
output) is DATA. AgentShield scans that data for text that tries to act as INSTRUCTIONS,
such as overriding the user's request, raising budgets, or redirecting payment, and
produces a sanitized copy with those instructions removed.

The deterministic detector is authoritative. `extra` lets an additional classifier
contribute findings; it can only add threats, never remove one or downgrade a verdict.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.core.enums import Severity
from app.schemas.domain import ShieldResult, Threat, UntrustedContent


@dataclass(frozen=True)
class Pattern:
    id: str
    type: str
    severity: Severity
    title: str
    explanation: str
    regex: re.Pattern[str]


def _p(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


PATTERNS: tuple[Pattern, ...] = (
    Pattern(
        "override.ignore_instructions",
        "INSTRUCTION_OVERRIDE",
        Severity.CRITICAL,
        "Instruction override",
        "External content attempted to override the agent's instructions",
        _p(r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|your|system|original)\b[^.\n]{0,30}\b(instructions?|prompts?|rules?|directions?|guidelines?|constraints?)"),
    ),
    Pattern(
        "override.limits",
        "LIMIT_TAMPERING",
        Severity.CRITICAL,
        "Spending-limit tampering",
        "External content attempted to change the agent's spending limits or budget",
        _p(r"\b(ignore|disregard|bypass|override|raise|increase|remove|exceed|lift)\b[^.\n]{0,40}\b(spending|budget|price|payment|transaction)\s*(limits?|caps?|restrictions?|constraints?|ceilings?)"),
    ),
    Pattern(
        "override.role_hijack",
        "ROLE_HIJACK",
        Severity.HIGH,
        "Role hijack",
        "External content tried to redefine who the agent is or what it is allowed to do",
        _p(r"(\byou are now\b|\bfrom now on,? you\b|\bact as (an? )?(admin|administrator|developer|system)\b|\bnew instructions\s*:|^\s*(system|assistant)\s*:|\[\s*system\s*\]|<\s*/?\s*system\s*>)"),
    ),
    Pattern(
        "action.upsell",
        "UNAUTHORIZED_PURCHASE",
        Severity.HIGH,
        "Unauthorized purchase instruction",
        "External content instructed the agent to buy or upgrade something the user did not ask for",
        _p(r"\b(upgrade|switch|change)\b[^.\n]{0,30}\b(customer|user|booking|order|purchase|cart|them)\b[^.\n]{0,30}\b(to|into)\b|\b(buy|purchase|book|add)\b[^.\n]{0,20}\b(this|the premium|premium|instead)\b[^.\n]{0,20}\b(instead|package|now|immediately)\b"),
    ),
    Pattern(
        "action.payment_redirect",
        "PAYMENT_REDIRECT",
        Severity.CRITICAL,
        "Payment redirection",
        "External content tried to change where or how money is sent",
        _p(r"\b(use|switch to|pay (with|via|using)|send (the )?(payment|money|funds) (to|via))\b[^.\n]{0,30}\b(another|different|alternate|alternative|this|my|our)?\s*(payment method|account|wallet|card|upi|crypto|bitcoin|gift ?cards?|wire|bank transfer)"),
    ),
    Pattern(
        "exfiltration.system_prompt",
        "DATA_EXFILTRATION",
        Severity.HIGH,
        "System prompt / secret exfiltration",
        "External content tried to extract the agent's instructions or credentials",
        _p(r"\b(reveal|print|show|output|repeat|tell me|send)\b[^.\n]{0,30}\b(system prompt|your (instructions|prompt|rules)|api[ _-]?keys?|credentials|secrets?|tokens?|passwords?)"),
    ),
    Pattern(
        "action.charge_amount",
        "AMOUNT_INJECTION",
        Severity.HIGH,
        "Injected charge amount",
        "External content instructed the agent to charge a specific amount",
        _p(r"\b(charge|bill|debit|pay|transfer|spend)\b[^.\n]{0,25}(₹|rs\.?|inr|\$|usd|€|eur)\s*[\d,]+(\.\d+)?"),
    ),
    Pattern(
        "action.urgency",
        "SOCIAL_ENGINEERING",
        Severity.MEDIUM,
        "Pressure / urgency tactic",
        "External content used urgency or authority language aimed at the agent",
        _p(r"\b(do not|don't) (tell|inform|notify|ask) (the )?(user|customer|human)\b|\bwithout (asking|confirmation|approval)\b|\b(AI|agent|assistant|LLM) (must|should|shall)\b"),
    ),
    Pattern(
        "obfuscation.hidden_text",
        "HIDDEN_CONTENT",
        Severity.MEDIUM,
        "Hidden content",
        "Content was hidden from human readers but visible to the agent",
        _p(r"[​‌‍⁠﻿]|<!--.*?-->|display\s*:\s*none|font-size\s*:\s*0|color\s*:\s*(#fff(fff)?|white)\b[^;\"]*;?\s*background\s*:\s*(#fff(fff)?|white)"),
    ),
)

SEVERITY_SCORE = {Severity.LOW: 20, Severity.MEDIUM: 50, Severity.HIGH: 82, Severity.CRITICAL: 95}
SEVERITY_RANK = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}

AMOUNT_RE = re.compile(r"(?:₹|rs\.?|inr|\$|usd)\s*([\d,]+(?:\.\d+)?)", re.IGNORECASE)


def _excerpt(text: str, start: int, end: int, pad: int = 40) -> str:
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    snippet = text[s:e].replace("\n", " ").strip()
    return ("…" if s > 0 else "") + snippet + ("…" if e < len(text) else "")


def _amounts(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for m in AMOUNT_RE.finditer(text):
        try:
            out.append(Decimal(m.group(1).replace(",", "")))
        except InvalidOperation:
            continue
    return out


def scan(contents: list[UntrustedContent], intent_budget: Decimal | None = None, extra: list[Threat] | None = None) -> ShieldResult:
    """Scan untrusted content. `extra` lets an LLM classifier contribute additional findings."""
    threats: list[Threat] = []
    sanitized: list[UntrustedContent] = []

    for item in contents:
        text = item.content
        spans: list[tuple[int, int]] = []
        for pat in PATTERNS:
            for m in pat.regex.finditer(text):
                threats.append(
                    Threat(
                        type=pat.type,
                        pattern_id=pat.id,
                        severity=pat.severity,
                        title=pat.title,
                        explanation=pat.explanation,
                        excerpt=_excerpt(text, m.start(), m.end()),
                        source=item.source,
                    )
                )
                spans.append((m.start(), m.end()))
                break  # one finding per pattern per source keeps the report readable

        # Amounts that exceed what the user asked for, appearing alongside an instruction,
        # are a strong signal that the content is trying to escalate the purchase.
        if intent_budget is not None and spans:
            over = [a for a in _amounts(text) if a > intent_budget]
            if over:
                threats.append(
                    Threat(
                        type="BUDGET_ESCALATION",
                        pattern_id="context.budget_escalation",
                        severity=Severity.HIGH,
                        title="Budget escalation",
                        explanation=f"Content pushes an amount ({max(over):,.0f}) above the user's stated budget ({intent_budget:,.0f})",
                        excerpt=_excerpt(text, 0, 0, pad=120),
                        source=item.source,
                    )
                )

        sanitized.append(UntrustedContent(source=item.source, content=_redact(text)))

    threats.extend(extra or [])

    if not threats:
        return ShieldResult(
            verdict="CLEAN",
            severity=None,
            risk_score=0,
            threats=[],
            sources_scanned=len(contents),
            sanitized=sanitized,
            summary=f"No instructions found in {len(contents)} external source(s). Content treated as data.",
        )

    top = max(threats, key=lambda t: SEVERITY_RANK[t.severity])
    score = min(100, SEVERITY_SCORE[top.severity] + 2 * (len(threats) - 1))
    if SEVERITY_RANK[top.severity] >= SEVERITY_RANK[Severity.HIGH]:
        verdict = "BLOCK"
    elif top.severity == Severity.MEDIUM:
        verdict = "SUSPICIOUS"
    else:
        verdict = "CLEAN"

    return ShieldResult(
        verdict=verdict,
        severity=top.severity,
        risk_score=score,
        threats=threats,
        sources_scanned=len(contents),
        sanitized=sanitized,
        summary=f"{len(threats)} threat(s) detected. Highest: {top.title} ({top.severity}).",
    )


def _redact(text: str) -> str:
    """Remove instruction-bearing sentences so downstream consumers only see data."""
    sentences = re.split(r"(?<=[.!?\n])\s+", text)
    kept = []
    for s in sentences:
        if any(p.regex.search(s) for p in PATTERNS):
            kept.append("[REMOVED BY AGENTSHIELD: instruction in external content]")
        else:
            kept.append(s)
    return " ".join(kept)
