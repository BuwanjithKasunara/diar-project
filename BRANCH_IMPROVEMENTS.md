# Branch Improvements: feat/annotation-adjudication-workflow

## Overview

This branch improves accuracy significantly by shifting from guessing to evidence-based analysis. The core philosophy: stop assuming and start validating.

---

## Key Improvements

### 1. **Stops Treating Every Keyword as Proof**

**Old System:**
- If a word like "Python" appears anywhere, it counts as a skill
- No distinction between different contexts or confidence levels

**New System:**
- Distinguishes between:
  - **Claimed skill** - explicitly stated experience
  - **Planned skill** - intent to learn in the future
  - **Negated skill** - explicitly ruled out or lack of experience
  - **Uncertain skill** - mentioned but confidence is low

**Example:**
- Old: "I plan to learn Docker" → counted as Docker experience ❌
- New: "I plan to learn Docker" → marked as "planned", not claimed ✅

---

### 2. **Reduces False Positives**

- Avoids overcounting repeated keywords
- Weak matches are not artificially amplified
- Example: "Python, Python, Python" does not become stronger evidence

**Benefit:** System becomes less noisy and more trustworthy.

---

### 3. **Handles Missing or Bad Data Correctly**

**Old System:**
- Missing resume/GitHub/LinkedIn could be treated as lack of skill
- Ambiguous or incomplete data caused confusion

**New System:**
- Separates data states:
  - **Not supplied** - data source not provided
  - **Partial** - incomplete information available
  - **Failed** - data retrieval/parsing failed
  - **Analysed** - successfully processed and validated

**Benefit:** System says "not enough evidence" instead of making false assumptions.

---

### 4. **Uses Smarter Scoring**

**Old System:**
- Simple skill count
- All matches weighted equally

**New System:**
- Scores skills based on:
  - Source quality
  - Match strength
  - Context relevance
  - Benchmark alignment

**Example:**
- A real strong match from a GitHub README or project matters more than a weak mention in a sentence

---

### 5. **Improved GitHub Data Analysis**

**Old System:**
- Treated all repository activity as equal proof
- Could not distinguish between active and stale repos

**New System:**
- Evaluates:
  - Repository quality
  - Activity recency
  - Relevance to the skill area

**Benefit:** Avoids treating outdated or unrelated repositories as proof of current ability.

---

### 6. **Better Privacy & Visibility Handling**

- Respects user preferences for data sharing (public, semi-public, private)
- Makes recommendations more suitable and less misleading
- Ensures compliance with privacy expectations

---

### 7. **Added Validation & Regression Tests**

The branch introduces explicit tests for:
- ✅ Extraction accuracy
- ✅ False positive detection
- ✅ GitHub parsing correctness
- ✅ API behavior consistency

**Benefit:** Prevents model drift and makes improvements measurable and reproducible.

---

## Summary

This feature branch transforms the system from **guess-based to evidence-based**:

| Aspect | Before | After |
|--------|--------|-------|
| **Keyword Matching** | Every keyword = proof | Context-aware classification |
| **Data Completeness** | Missing = lacking skill | Missing = insufficient evidence |
| **Scoring** | Count-based | Quality & context-based |
| **GitHub Analysis** | All activity equal | Quality, recency, relevance considered |
| **Testing** | Limited | Comprehensive validation suite |
| **Accuracy** | Moderate | High |

---

## Key Takeaway

By separating real skills from wishful thinking, handling incomplete data honestly, and validating results systematically, this branch significantly improves the reliability and trustworthiness of the skill annotation and adjudication workflow.
