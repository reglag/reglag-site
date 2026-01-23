# Evidence Snapshot — RD-2 Proof-of-Work

**Review period:** January 20–24, 2026  
**Associated PoW:** rd-2-proof-of-work-2026-01-24.md  
**Object:** RD-2 — Liquidity Reallocation & Plumbing

This snapshot records the minimum quantitative and factual evidence evaluated to support the RD-2 Proof-of-Work Review for the stated period.

---

## 1) Treasury issuance & auctions

**Source**
- U.S. Treasury auction results (TreasuryDirect)  
  https://www.treasurydirect.gov/auctions/auction-query/

**Observation dates**
- January 20, 2026
- January 22, 2026
- January 23, 2026

**Relevant excerpts**
- Dealer take-down:
  - Jan 20: ~42%
  - Jan 22: ~44%
  - Jan 23: ~41%
- Auction tails:
  - Bills: ~0.6 bp
  - 2y: ~0.8 bp
  - No maturities ≥3 bp
- Bid-to-cover:
  - Range across auctions: ~2.4–2.7×

**Pre-committed triggers tested**
- Dealer take-down >50% across ≥2 consecutive auctions
- Auction tails ≥3 bp in ≥2 maturities within same week

**Result**
- No trigger met; no persistence or clustering observed.

---

## 2) Dealer balance-sheet capacity

**Sources**
- Bank holding company filings (SEC EDGAR)  
  https://www.sec.gov/edgar/searchedgar/companysearch.html
- Supplemental leverage ratio disclosures (bank regulatory filings)

**Observation dates**
- Latest available filings as of January 22, 2026

**Relevant excerpts**
- Inventory roll-off behavior:
  - Typical clearance observed within ~3–5 trading days post-auction
- No indications of early balance-sheet compression ahead of quarter-end

**Pre-committed triggers tested**
- Inventory persistence >10 trading days post-auction
- Balance-sheet tightening prior to quarter-end

**Result**
- No trigger met; inventory behavior within expected norms.

---

## 3) Financing layer (repo)

**Sources**
- Federal Reserve Bank of New York — Repo operations and reference rates  
  https://www.newyorkfed.org/markets/desk-operations
- DTCC — FICC GCF Repo and fails data  
  https://www.dtcc.com/charts/dtcc-gcf-repo-index

**Observation dates**
- January 21–23, 2026

**Relevant excerpts**
- Specials persistence:
  - Typically 1–2 sessions
- Repo fails:
  - Within ~±10–15% of trailing-month average
- No observable shift toward longer-dated term repo usage

**Pre-committed triggers tested**
- Specials persistence >5 sessions
- Repo fails >2× trailing-month average for a full week
- Material extension of repo maturity profile

**Result**
- No trigger met; financing remained short-dated and reversible.

---

## 4) Official absorption (Federal Reserve)

**Sources**
- Federal Reserve — H.4.1 Factors Affecting Reserve Balances  
  https://www.federalreserve.gov/releases/h41/
- Standing Repo Facility and Discount Window information  
  https://www.federalreserve.gov/monetarypolicy.htm

**Observation date**
- Week ended January 22, 2026

**Relevant excerpts**
- ON RRP usage:
  - Weekly variation ~±$25–30bn
  - No directional trend
- Balance-sheet composition unchanged
- No evidence of normalized facility reliance

**Pre-committed triggers tested**
- Directional facility usage persisting >3 consecutive weeks
- Structural reallocation toward absorption tools

**Result**
- No trigger met; official backstops remain episodic.

---

## 5) Coordination & settlement speed (stablecoins)

**Sources**
- Stablecoin reserve attestations (issuer disclosures)  
  Examples:  
  https://tether.to/en/transparency/  
  https://www.circle.com/en/usdc
- Public redemption and settlement mechanics disclosures

**Observation date**
- January 23, 2026

**Relevant excerpts**
- Reserve composition:
  - >90% cash and short-dated Treasuries
  - No change vs prior attestations
- Redemption terms:
  - T+0 / T+1
  - No structural modifications announced

**Pre-committed triggers tested**
- Reserve composition shift >10 percentage points into non-bill assets
- Material change in redemption mechanics affecting settlement speed

**Result**
- No trigger met; coordination dynamics unchanged.

---

## Decision rationale

Across all five RD-2 control-surface layers, observed values remained meaningfully inside pre-committed trigger thresholds. No persistence, clustering, or directional normalization was detected. Quantitative deltas versus trigger conditions were sufficient to support restraint. The RD-2 belief state therefore held without revision for this review period.

---

*End of evidence snapshot.*
