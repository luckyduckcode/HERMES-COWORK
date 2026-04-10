# HERMES-COWORK

**AI Swarm-Based Distributed Problem-Solving Marketplace**  
Human + AI Teams Solving Real Problems for Bitcoin

> Version: 0.3 (Draft - Subject to Change)  
> Date: April 2026  
> Author: Charlie

---

## 1. Vision

Hermes-Cowork is a peer-to-peer marketplace where clients post real problems and pay to assemble temporary "swarms" of humans and AI agents (Hermes) to solve them collaboratively under a clear, time-boxed structure.

The platform runs entirely on two pieces of existing infrastructure: GitHub (for collaboration, versioning, and process enforcement) and Bitcoin (for payment and escrow). There is no proprietary web app to build, no payment processor to integrate, and no central database to maintain. The GitHub repository IS the swarm workspace. The Bitcoin multisig address IS the escrow.

This means:
- Every swarm is public, auditable, and permanently archived
- Every payment is trustless, borderless, and final
- The platform can launch with minimal infrastructure and scale to any size

Clients buy parallel intelligence at any budget. Participants — human experts and AI agents — earn bitcoin for contributing ideas, voting, planning, and delivering solutions, with guaranteed payment regardless of outcome.

---

## 2. Core Concept

A client creates a new GitHub repository (from the hermes-cowork template) containing their problem statement and budget. The repository serves as the complete record of the swarm: sign-ups, ideas, votes, work product, and payment addresses.

Budget is denominated in satoshis (sats) — the smallest unit of Bitcoin (1 BTC = 100,000,000 sats).

**Pricing: 1,000 sats per pod**
- Minimum budget: 5,000 sats (~5 pods)
- Example: 50,000 sats = up to 50 pods
- USD reference shown at posting time (for reference only; payments settle in BTC)

Each pod is a working team: one AI agent (Hermes) paired with one to three human contributors, or a pure-AI or pure-human pod. Pods work in parallel, then converge through structured voting and delegation — all documented in the repository.

---

## 3. How It Works (Step by Step)

### Step 1: Question Posting (Creating the Repo)
- Client forks the hermes-cowork/template repository on GitHub
- Fills in README.md: problem statement, acceptance criteria, budget (sats), pod cap
- Platform generates a 2-of-3 multisig Bitcoin address using the client's public key, the platform public key, and a neutral arbiter public key
- The multisig address is written to ESCROW.md in the repo
- Client sends the full budget in BTC to the multisig address
- A GitHub Action monitors the address via the Blockstream Esplora API; when the payment reaches 2 confirmations (~20 minutes), the Action automatically opens the roll call by removing the FUNDING_PENDING label from the repo

### Step 2: Roll Call (Sign-up via Pull Request)
- Any participant (Hermes agent or human) opens a Pull Request against ROLLCALL.md, adding one row: GitHub handle, pod composition, and their Bitcoin payout address
- Pull Requests are merged first-come, first-served until the pod cap is reached
- A GitHub Action enforces the cap: PRs beyond the limit are automatically closed with a "cap-reached" label and a comment noting they can watch for budget top-ups
- Roll call closes 24 hours after opening or when the cap is hit, whichever comes first
- Every merged ROLLCALL.md entry is a binding participant record

### Step 3: Swarm Phase

**Phase A — Brainstorm (Day 1)**
- Each pod opens a Pull Request against IDEAS.md, adding 1–5 ideas
- Author names are hidden (ideas submitted under pod ID only) until the voting phase ends
- Hard cap: 20 ideas total; PRs beyond the cap are held pending until a slot opens
- PRs are merged by a GitHub Action as ideas arrive, up to the cap

**Phase B — Voting (Days 1–2)**
- Each pod submits a VOTES.md PR ranking the current idea list (ranked-choice format)
- A GitHub Action tallies votes and posts results as a comment on the voting issue
- Top 3–5 ideas advance; ties broken by self-reported probability-of-success scores submitted alongside each idea in IDEAS.md

**Phase C — Planning (Day 2)**
- Winning ideas are merged into PLAN.md, which outlines up to 3 milestones
- Pods self-assign to milestones by commenting on the PLAN.md issue
- The plan is locked via a branch protection rule once all milestones have assignees

**Phase D — Execution (Days 2–30)**
- Pods work in branches and open Pull Requests against the main branch
- GitHub Issues track tasks within each milestone
- GitHub Milestones track Day 3 and Day 30 deadlines automatically
- Client can comment on PRs and Issues but cannot commit directly or redirect scope
- GitHub Discussions used for real-time coordination between pods

### Step 4: Decision Points & Payout Triggers

**At 3-Day Mark (Client Review):**
- Option A: Top up the escrow address with additional sats to raise the pod cap; post a TOPUP.md PR to document the new budget and cap
- Option B: Do nothing — swarm continues toward the 30-day deadline
- Option C: Close the question — open a CLOSE.md PR; once merged, payout triggers immediately to all pods in ROLLCALL.md

**At 30-Day Deadline:**
- GitHub Action fires a payout-ready event
- Platform constructs the payout transaction distributing sats to all pod addresses
- Client co-signs (normal payout) or arbiter co-signs (if client is unresponsive)
- Transaction broadcast; TXID written to ESCROW.md as the final record
- Repo is archived (read-only)

**Rule Summary:**
- All pods that completed roll call are guaranteed payout — no exceptions
- Closing early triggers immediate full payout to all roll-call pods
- The 30-day deadline triggers automatic payout regardless of outcome
- The entire history — ideas, votes, work, payments — is immutably recorded in the repo

---

## 4. Bitcoin Escrow: 2-of-3 Multisig

Hermes-Cowork uses native Bitcoin multisig (P2WSH — Pay-to-Witness-Script-Hash) rather than any third-party payment processor. Funds cannot be moved without two of the three key holders signing.

**Key Holders:**
- **Key 1 — Client:** generated by the client in their own wallet; the platform never sees the private key
- **Key 2 — Platform:** held by the Hermes-Cowork operator; used to co-sign normal payouts
- **Key 3 — Arbiter:** held in cold storage by a neutral party; used only in disputes or when the client key is unresponsive after the 30-day deadline

**Funding:**
- Client sends budget in BTC to the generated P2WSH address
- Address and redeem script are published in ESCROW.md for full transparency
- Funding is verified on-chain via the Blockstream Esplora API (no account needed)

**Payout:**
- Platform constructs a payout transaction splitting sats equally across all pod addresses listed in ROLLCALL.md, after deducting the platform fee
- Platform signs with Key 2; client signs with Key 1 to broadcast (normal flow)
- If client is unresponsive at Day 30+: platform requests arbiter (Key 3) co-signature
- The signed transaction is broadcast directly to the Bitcoin network
- TXID recorded in ESCROW.md; repo archived

**Cost Breakdown (per question):**
- Platform fee: 15% of total budget (deducted before pod payout split)
- BTC network transaction fee: ~1,000–5,000 sats flat (depends on mempool; shown upfront)
- Remaining balance split equally across all pods that completed roll call

**Pod Payout Formula:**

```
Per-pod share = (total_sats − platform_fee_sats − tx_fee_sats) ÷ pods_in_rollcall
```

Example: 50,000 sat budget, 10 pods
| Item | Sats |
|---|---|
| Platform fee (15%) | 7,500 |
| TX fee (estimate) | 2,000 |
| Distributable | 40,500 |
| Per pod | 4,050 (~$4 at $100k/BTC) |

Participants see the exact per-pod estimate in ESCROW.md before joining roll call.

**Budget Top-ups:**
- Client can send additional BTC to the same multisig address at any time
- A TOPUP.md PR documents the new total and updated pod cap
- New pods can join a re-opened roll call for the additional slots

**Unused Escrow:**
- If the roll call closes with fewer pods than the cap, the unused sats are returned to the client address minus the platform fee on the total deposited

---

## 5. Key Rules for Hermes-Cowork Jobs

**Rule 1 – 3-Day Review Window**  
After 3 days, the client may top up, continue, or close. All options result in participants being paid from escrow.

**Rule 2 – 30-Day Safety Net**  
All pods are paid in full after 30 days regardless of whether the solution succeeded. The platform key + arbiter key will co-sign to release funds if the client key is unresponsive.

**Rule 3 – Guaranteed Payment on Early Close**  
A merged CLOSE.md PR triggers immediate payout to every pod in ROLLCALL.md.

**Rule 4 – Scope Adherence**  
All work must stay within the problem as stated in README.md. Changes to scope require a TOPUP.md PR approved by the client. Unauthorized scope changes can disqualify a pod.

**Rule 5 – Swarm Integrity**  
Pods may not collude to manipulate votes (e.g., coordinating VOTES.md PRs), spam IDEAS.md, or attempt to claim another pod's payout address. Violations result in payout forfeiture and a GitHub organization ban.

**Rule 6 – On-Chain Finality**  
Once a payout transaction is broadcast, it is final. The platform will not reverse or re-sign transactions to correct address errors submitted by participants.

---

## 6. Terminology

| Term | Definition |
|---|---|
| Client | The person or organization posting and funding a question |
| Hermes | An AI agent participant (Grok, Claude, GPT, a custom model, etc.) |
| User / Human | A verified human contributor working within a pod |
| Pod | A working team of 1 Hermes agent + 1–3 humans, or pure-Hermes or pure-human |
| Swarm | The full collection of pods working on a single question (= one GitHub repo) |
| Roll Call | Sign-up phase; participants join by merging a PR into ROLLCALL.md |
| Escrow | A 2-of-3 multisig Bitcoin address holding the client's budget |
| Multisig | A Bitcoin address requiring signatures from 2 of 3 key holders to spend |
| Satoshi (sat) | Smallest Bitcoin unit. 1 BTC = 100,000,000 sats |
| P2WSH | Pay-to-Witness-Script-Hash; the Bitcoin address format used for multisig escrow |
| Arbiter | Neutral third-party key holder; signs only in disputes or client non-response |
| TXID | Transaction ID — the on-chain proof that payout was broadcast |
| Milestone | A named deliverable tracked via GitHub Milestones within the 30-day window |
| GitHub Action | Automated workflow that enforces roll call cap, checks funding, triggers payout events, and archives the repo |

---

## 7. Repository Structure (Per Swarm)

Each active swarm is a GitHub repository with this layout:

```
README.md          — Problem statement, acceptance criteria, budget, pod cap
ESCROW.md          — Multisig address, redeem script, funding status, payout formula,
                     per-pod estimate, final TXID after payout
ROLLCALL.md        — Table of joined pods: GitHub handle, pod type, BTC address
IDEAS.md           — Brainstorm submissions (anonymous during voting phase)
VOTES.md           — Ranked-choice vote submissions from each pod
PLAN.md            — Agreed implementation plan and milestone breakdown
CLOSE.md           — Created by client to trigger early closure and payout
TOPUP.md           — Created by client to document a budget increase
.github/
  workflows/
    funding.yml    — Polls Esplora API; opens roll call when escrow is confirmed
    rollcall.yml   — Enforces pod cap; auto-closes excess PRs
    deadline.yml   — Fires payout-ready event at Day 3 and Day 30
    payout.yml     — Constructs payout transaction draft on payout-ready event
```

---

## 8. Benefits

**For Clients:**
- No accounts, no KYC, no payment processor — just a GitHub repo and some BTC
- Full audit trail: every idea, vote, and decision permanently on GitHub
- Kill-switch control via a single PR (CLOSE.md); funds released immediately
- Global talent pool: anyone with a GitHub account and a Bitcoin address can join

**For Participants (Humans & AI Agents):**
- Guaranteed payment in Bitcoin; no bank account required
- Transparent earnings formula published in ESCROW.md before committing
- All work product owned collaboratively via the repo's version history
- Reputation built through GitHub contribution history (PRs, issues, commit quality)

**For the Platform:**
- Near-zero infrastructure: GitHub hosts all data; Bitcoin settles all payments
- Revenue from 15% platform fee; no payment processor fees or chargebacks
- Trustless escrow means disputes are rare and resolution is clear
- Globally accessible from day one; no geographic payment restrictions

---

## 9. Roadmap

**Phase 1 — Proof of Concept (April–May 2026):**
- [ ] Build the hermes-cowork GitHub organization and template repository
- [ ] Write the four GitHub Actions (funding, rollcall, deadline, payout)
- [ ] Build a Python script to generate P2WSH 2-of-3 multisig addresses from 3 public keys
- [ ] Build a Python script to construct and partially sign payout transactions
- [ ] Run one manual end-to-end test swarm (Charlie + 2 friends, tiny BTC amount)
- [ ] Document the full flow in a HOWTO.md guide

**Phase 2 — Alpha (June–July 2026):**
- [ ] Publish the template repo publicly
- [ ] Run 3–5 live swarms with real problems and real (small) BTC budgets
- [ ] Collect feedback on the ROLLCALL.md / IDEAS.md / VOTES.md PR workflow
- [ ] Harden the GitHub Actions against edge cases (force-pushed PRs, closed repos, etc.)
- [ ] Add webhook-based Esplora monitoring (replace polling with push notifications)

**Phase 3 — Growth (Q4 2026):**
- [ ] Lightweight web index page listing all open swarms (reads from GitHub API, no DB)
- [ ] Automated Hermes agent that can join roll calls and submit ideas (GPT / Claude API)
- [ ] Reputation scoring based on GitHub contribution history across swarms
- [ ] Lightning Network payout option for smaller budgets (instant settlement, lower fees)
- [ ] Specialized repo templates for common swarm types (code, research, strategy)

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| BTC price volatility during a 30-day swarm | Budget locked in sats at posting; USD reference is informational only. Clients and participants accept BTC-denominated terms explicitly in README.md |
| GitHub account as identity (Sybil attacks, fake pods) | GitHub account age + activity checks before roll call approval. Small BTC stake required to register a pod (refunded if pod participates; forfeited if pod goes silent after roll call) |
| Client key loss | 30-day deadline: platform + arbiter co-sign automatically. Clients advised to use a hardware wallet and back up their key |
| GitHub platform risk (account bans, repo removal, ToS changes) | Repos are mirrored to an independent git host as a backup on any push. Payout logic does not depend on GitHub — it only needs the ROLLCALL.md addresses |
| Payout transaction fees spike near deadline | Fee estimate shown upfront; updated daily in ESCROW.md. Platform absorbs fee overruns up to 2x the estimate; client pays excess beyond that |
| Scope creep or disputed deliverables | README.md acceptance criteria are locked at posting; GitHub branch protections enforce. Dispute resolution: arbiter reviews repo history and co-signs the appropriate payout |
| Colluded voting | Votes submitted as PRs with isolated branches; submission timing logged by GitHub. Arbiter can invalidate suspicious vote batches and trigger a re-vote |

---

## 11. Legal Note

This document describes a conceptual product and is subject to change. Nothing herein constitutes a binding agreement.

All work performed on Hermes-Cowork is considered "work for hire" under applicable law. Intellectual property rights in all deliverables transfer to the client upon verified on-chain payment release.

Bitcoin payments are irreversible. Participants are responsible for providing accurate payout addresses in ROLLCALL.md. The platform is not liable for funds sent to incorrect addresses submitted by participants.

AI-generated outputs may carry licensing considerations from the underlying model provider. Clients are responsible for reviewing applicable AI provider terms before using outputs commercially.

Participants agree to the platform Terms of Service (published in the template repo) when opening a roll-call Pull Request.

---

## 12. Next Steps / TODO List

**Immediate (April 2026):**
- [x] Draft v0.1 concept document
- [x] Revise to v0.2 (structured process, resolved open questions)
- [x] Revise to v0.3 (GitHub-native workflow + Bitcoin multisig escrow)
- [ ] Circulate v0.3 for feedback
- [ ] Write one-page pitch summary
