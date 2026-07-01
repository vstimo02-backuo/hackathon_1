# Implementation Plan: MergeWise AI Demo Polish

We will implement high-impact polishes for our client demo tomorrow. Below is the proposed architecture plan.

## 1. Why are we using native `urllib.request` instead of the `openai` Python SDK?
* **Zero Additional Dependencies**: In strict enterprise or sandboxed environments (such as a local-first offline POC), installing extra packages like `openai` can introduce version conflicts or registry fetching errors. Using the standard library `urllib` ensures total reliability, zero dependencies, and compatibility across both lightweight local runtimes and the backend container.
* **We will fix the API endpoint & format**: We will rewrite `_openai_explanation` to call the correct chat completion endpoint `https://api.openai.com/v1/chat/completions` using standard messages payloads and parse the JSON accurately.

## 2. Advanced Match Alignment (The Matching Focus)
Our sequence-matching metrics and tokens can be significantly smarter. We will:
* **Incorporate Semantic Match Domain Tokens**:
  * Expand `TOKEN_ALIASES` with mappings for enterprise identifiers:
    * `vat_registration_number`, `vat_no`, `tax_id`, `ein` -> `tax_identifier`
    * `primary_phone`, `phone_number`, `telephone`, `contact_no` -> `contact_phone`
    * `postal_code`, `zip_code`, `postcode` -> `zip_code`
    * `billing_address`, `street`, `address_line_1` -> `address`
* **Inject Quality & PII Checks**:
  * Identify and flag sensitive columns (e.g., mail, phone, tax details) with a label `pii: High/Medium/Low`.
  * Track quality fill rate (`non_empty_count / total_rows`). Display these dynamically.

## 3. High-Fidelity Interactive Preview & Merge UX
Instead of unstyled, raw, scrolled JSON block:
* We will implement a polished **Side-by-Side Unified Data Board** showing real sample record merges (File A Field ↔ File B Field) in a sleek React and CSS Grid layout.
* Highlight Trust bands dynamically with color indicators (Emerald for Auto-Merged, Amber for Review, Crimson for Separate/Low Confidence).
* Allow users to inspect field metrics, see PII compliance flags, and click "Confirm Low Confidence" inline with modern alerts instead of standard alert boxes.
