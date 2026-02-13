# Inspection Certificates - Live Examples

**Verifiable proof of ephemeral execution**

This repo demonstrates Inspection Certificates with 3 engaging examples you can run yourself!

## 🎯 Examples

### Example 1: API Key Verification ✅
**Claim:** "I have a valid Anthropic API key with $50+ credit"

**What it proves:**
- ✅ API key is valid (not expired)
- ✅ Credit balance is accurate
- ✅ Rate limits are in good standing
- ❌ API key value is NOT revealed

**[Run it yourself →](examples/api-key-verification)**

### Example 2: Dataset Pre-Buy Inspection 📊
**Claim:** "I have 1,000 customer support tickets about refunds"

**What it proves:**
- ✅ Dataset has claimed number of records
- ✅ Records match claimed topic
- ✅ Quality metrics (completeness, freshness)
- ❌ Actual ticket content is NOT revealed

**[Run it yourself →](examples/dataset-inspection)**

### Example 3: TLS Transcript Verification 🔐
**Claim:** "I have an authentic transcript from Wikipedia fetched via TLS"

**What it proves:**
- ✅ TLS connection was established
- ✅ Certificate is valid
- ✅ Content matches expected source
- ❌ Full transcript is NOT revealed (only hash)

**[Run it yourself →](examples/tls-transcript)**

## Quick Start

**1. Fork this repo**

**2. Add GitHub Secrets:**
```
Settings → Secrets and variables → Actions → New repository secret

For Example 1:
- Name: ANTHROPIC_API_KEY
- Value: sk-ant-your-key-here

For Example 2:
- Name: SUPPORT_TICKETS
- Value: <your sample dataset>
```

**3. Run a workflow:**
```bash
# Go to Actions tab → Select workflow → Run workflow
# Or use GitHub CLI:
gh workflow run api-key-verification.yml
```

**4. View your certificate:**
```
https://github.com/YOUR_USERNAME/inspection-certificates-demo/actions/runs/RUN_ID
```

**5. Share it!**
Anyone can verify your claim by viewing the logs.

## How It Works

### The Pattern

```
┌─────────────────────────────────┐
│  INPUTS (private)               │
│  - API key / dataset / data     │
│  - Stored in GitHub Secrets     │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  EXECUTION (GitHub runner)      │
│  - Load secret (not logged)     │
│  - Run verification             │
│  - Log result publicly          │
│  - Runner destroyed             │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  CERTIFICATE (permanent)        │
│  - Workflow run URL             │
│  - Public execution logs        │
│  - Result + timestamp           │
│  - Anyone can verify            │
└─────────────────────────────────┘
```

**Key insight:** Secret values are NEVER logged, only hashes and results.

## Why This Matters

**Traditional approach:**
- "Trust me, I have valid credentials"
- "Trust me, my data is valuable"
- No way to verify without exposing

**Inspection Certificates:**
- Cryptographic proof (hash of inputs)
- Public verification (anyone can audit logs)
- Ephemeral execution (no data retention)
- Automated (no human needed)

## Use Cases

- **Marketplace pre-buy:** Verify data quality before purchasing
- **API key sales:** Prove credentials are valid
- **Research validation:** Prove results without exposing test data
- **Credential verification:** Prove you have access without sharing keys

## Trust Model

**What you're trusting:**
- GitHub infrastructure (runners are isolated)
- GitHub secrets (values are redacted from logs)
- Workflow code (open source, auditable)

**What you're NOT trusting:**
- Seller's word alone (verified by execution)
- Centralized escrow company

## Next: Automated Escrow

These examples show **verification**.

Next step: **Automated payment release** using TEE + KMS.

See [Escrow Agent docs](https://github.com/amiller/skill-verifier/blob/main/ESCROW-AGENT.md)

## Live Examples

**Example certificates** (click to verify):
- [ ] API Key Verification (running soon)
- [ ] Dataset Inspection (running soon)
- [ ] TLS Transcript (running soon)

## Contributing

1. Add your own example!
2. Share your certificate URL
3. Help improve the workflows

## Learn More

- **[Main repo](https://github.com/amiller/skill-verifier)** - Full architecture
- **[Auditor Guide](https://github.com/amiller/skill-verifier/blob/main/docs/data-inspection/AUDITOR-GUIDE.md)** - How to verify certificates
- **[Escrow Agent](https://github.com/amiller/skill-verifier/blob/main/ESCROW-AGENT.md)** - Automated payment model

---

**Inspection Certificates: Prove claims about private data** 🦞🔐
