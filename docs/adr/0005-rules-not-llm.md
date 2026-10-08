# 5. Deterministic rules, LLM only for language

Status: accepted, 2026-10-08

## Context

The advice concerns children's health. A principal must be able to trust, and a judge must be able to audit, why a
line says "move PE indoors".

## Decision

Every action comes from `rules/rules.yaml` through the deterministic engine and carries a rule ID. The standard parent
note uses reviewed English and Hindi templates. The LLM (Strands Agents; Gemini while Bedrock is blocked on this account, see the README) has two jobs a template can't do:

1. Translate the principal's own free-text addition into Hindi. A validator checks that numbers and times survive and
   that the output is Devanagari; otherwise the line stays in English.
2. Answer planning questions ("sports day tomorrow afternoon?") by calling read-only tools that wrap the engine. The
   answer must be `{answer, ruleIds}`, every cited ID must have come from a tool in that turn, and an evaluation without
   a citation is rejected and retried once, then the raw rule result is shown.

## Consequences

- The morning email works with no model at all. A model outage only disables chat and free-text translation.
- Chat answers can't invent rules; they can only phrase what the engine returned.
- Model choice is a parameter (`ModelProvider`, `ModelId`). Gemini is the current default only because Bedrock invocation is blocked on this new account; on Bedrock, Nova Lite would be the choice because it needs no Marketplace
  subscription and is cheap per turn.
