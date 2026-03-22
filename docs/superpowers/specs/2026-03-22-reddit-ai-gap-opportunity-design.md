# Reddit “AI-shaped pain, low AI discourse” opportunity platform

## Summary

Build **one core system** that ingests public Reddit activity, classifies **task-shaped demand** (summarize, rewrite, explain, organize, template, OCR-adjacent help, etc.) versus **AI supply** (tool names, prompt culture, model discourse), and produces a **gap score** per subreddit (and optionally per topic cluster). Ship **three go-to-market surfaces** from the same data:

| Wedge | Surface | Primary user |
|-------|---------|--------------|
| **A** | Ranked directory / “opportunity map” (+ optional newsletter, SEO pages) | Researchers, indie hackers, marketers |
| **B** | Exportable lists & filters for **B2B outreach** (CRM CSV, enrichment hooks) | Founders, SDRs, niche tool builders |
| **C** | **Consumer** product marketed **outside** Reddit (“for people who [job/hobby]”) using segments derived from gap clusters | End users; acquisition via content/ads, not sub spam |

**Principle:** Same signals, different packaging and weighting—not three separate scrapers.

---

## Goals

1. **Operationalize the gap:** repeatable **Pain index**, **AI penetration index**, and **Gap score** (and explainable sub-scores) per subreddit over a rolling window.
2. **Support all three wedges** with one pipeline: **directory** (browse/sort), **B2B** (export, filters, “actionability” and liability flags), **consumer** (export segment labels and copy hooks for positioning—no requirement to name Reddit in user-facing copy).
3. **Transparency:** store enough metadata to answer “why this score?” (top matching phrases, sample sizes, date range).
4. **Sustainable ingestion:** design against **Reddit API / terms** first; document fallback constraints if using third-party datasets.

## Non-goals (v1)

- Real-time comment streaming at massive scale without budget for API/compute.
- Automated posting or “growth hacking” inside Reddit on the user’s behalf.
- Claims of **causality** (“this sub will buy X”)—outputs are **signals**, not guarantees.
- Medical/legal **advice** products positioned as substituting professionals; the platform may **flag** high-liability niches for down-ranking B2B/certain consumer verticals.

---

## Definitions

### Pain (task-shaped demand)

Posts/comments whose **intent** matches high-LLM-fit tasks, e.g.:

- Explanation: ELI5, “what does this mean,” “in plain English”
- Compression: TL;DR, summarize, too long
- Rewriting: tone, shorter, professional, email/letter/script
- Structure: outline, bullet points, organize, study guide
- Extraction from messy input: screenshots of letters/forms (reading help—not professional interpretation where regulated)

**Implementation note:** maintain a **versioned lexicon + optional classifier** (see Testing). Lexicon alone is cheaper; classifier improves recall.

### AI supply (discourse penetration)

On-topic mentions of assistants, models, prompts, or obvious “use ChatGPT for…” culture. Include common brand names and generic terms (`LLM`, `prompt`, `AI slop` as negative quality signal if needed—separate bucket).

### Gap score (conceptual)

\[
\text{Gap} = f(\text{Pain}, \text{AI\_penetration}, \text{penalties}, \text{bonuses})
\]

Default linear-ish form for interpretability:

- `gap_raw = pain_index - k * ai_penetration_index` (tune `k` per calibration)
- Apply **penalties**: strict no-AI rules + enforcement, meme/low-text ratio, extreme liability (down-rank **outreach** and some **consumer** segments—not necessarily directory if labeled clearly)

---

## Wedge-specific weighting (same raw features)

| Feature | A Directory | B B2B export | C Consumer app |
|---------|-------------|--------------|----------------|
| High pain index | Yes | Yes | Yes |
| Low AI penetration | Yes | Yes | Yes (positioning “untapped norm”) |
| Recurring threads / flairs | Nice | **Strong** (workflow) | **Strong** (habit) |
| Comment labor (long helpful threads) | Nice | Strong (substitution story) | Medium |
| Ban AI / hostile norms | Label; still interesting | **Down-rank** or tag “off-Reddit only” | **Prefer** adjacent marketing, product doesn’t depend on in-sub distribution |
| Liability-heavy | Label | **Flag / exclude** default | **Exclude** or narrow scope |

**B2B-only columns (manual or semi-auto enrichment later):** estimated persona (modality), budget proxies (e.g. business flairs), English vs other languages—out of scope for automated v1 except what text implies.

---

## Architecture (logical)

1. **Ingestion layer**  
   - Inputs: listing posts/comments per target subreddit over window(s).  
   - Respect rate limits, store raw text + ids + timestamps + permalink (for audit).

2. **Normalization**  
   - Language detection; optional English-first MVP.

3. **Classification**  
   - **Pain labels** (multi-tag): lexicon hits, optional small model classifier.  
   - **AI-supply labels:** dictionary + optional classifier.  
   - **Subreddit metadata:** sidebar/rules text for “no AI” keywords (regex + manual override table).

4. **Aggregation**  
   - Per subreddit, per rolling 30/90d: rates per 1k posts, confidence intervals from sample size.  
   - **Stability:** week-over-week delta to avoid one viral thread dominating.

5. **Scoring service**  
   - Emits `pain_index`, `ai_penetration_index`, `gap_score`, `flags[]`, `evidence` (top n-grams / examples with redaction options).

6. **Surfaces**  
   - **A:** Web table + filters + static pages for SEO; optional weekly email digest of “largest gap delta.”  
   - **B:** Authenticated export (CSV/JSON), saved filters, “do not contact” / liability tags.  
   - **C:** Internal “segment cards” (persona, pain phrases, positioning hooks)—consumer app repo may be separate but consumes exported segments or API.

---

## Data, compliance, ethics

- **Terms of use:** Prefer **official Reddit API** (or licensed data) for production; document prohibited uses (spam, harassment, evasion of mod rules).  
- **PII:** Minimize storage of usernames in customer-facing exports; aggregate by default.  
- **Manipulation:** Do not sell “mass DM” or “ban evasion” features.

---

## Error handling & limits

- Small sample size → wide confidence + “low confidence” badge; optionally hide from B2B default exports.  
- Viral off-topic threads → cap influence via robust aggregation (trimmed means or median week).  
- Lexicon drift → version lexicon; re-run history when lexicon bumps (changelog).

---

## Testing strategy

1. **Golden set:** hand-label 200–500 Reddit posts across diverse subs for pain / AI / neither.  
2. **Precision/recall** targets documented per milestone (e.g. lexicon v1: prioritize precision on pain).  
3. **Regression:** scoring snapshots on fixed corpora when lexicon or weights change.

---

## Phasing

| Phase | Deliverable |
|-------|-------------|
| **MVP** | Ingestion for a **manual seed list** of subreddits; lexicon-based pain/AI; weekly batch job; **directory** (A) with CSV download; basic flags. |
| **v2** | B2B saved filters + exports + liability tags; newsletter for A. |
| **v3** | Classifier assist; multi-language; consumer-facing segment API for C; optional enrichment hooks for B. |

---

## Open questions

1. **Business model:** directory free + paid deep exports vs. subscription for B vs. consumer app subscription—decide before implementation.  
2. **Reddit API access tier** at launch (cost/rate limits) vs. initial corpus from archived dumps (legal/licensing).  
3. **Brand:** whether the public directory names Reddit explicitly or uses neutral “community interest clusters.”

---

## Approval

This spec encodes the **all-wedges** direction: **one engine**, **three surfaces**, **phased MVP** starting at directory + exports.
