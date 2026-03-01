# Inspection Certificates

**Verifiable proof of ephemeral execution**

## The Concept

Inspection Certificates provide cryptographic proof that a computation happened without storing the data.

### Two Use Cases

#### 1. Skill Verification
**Inspect:** Does this agent skill work?
```
Input: Skill code + test cases
Execute: Run skill in isolation
Output: Certificate proving tests passed
```

#### 2. Data Inspection  
**Inspect:** Does this dataset have claimed properties?
```
Input: Private dataset + inspection prompt
Execute: Run analysis in isolation
Output: Certificate proving the claim
```

### Common Pattern

Both follow the same ephemeral execution model:

```
┌─────────────────────────────────┐
│  INPUTS (one-time)              │
│  ├─ Code or data                │
│  ├─ Test/analysis spec          │
│  └─ Execution environment       │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  EXECUTION (isolated)           │
│  ├─ Load → memory ONLY          │
│  ├─ Run computation             │
│  ├─ Log every action            │
│  ├─ Generate certificate        │
│  ├─ DELETE input data           │
│  └─ Destroy sandbox             │
└─────────────────────────────────┘
            ↓
┌─────────────────────────────────┐
│  OUTPUT (permanent)             │
│  ├─ Execution certificate       │
│  ├─ Result/attestation          │
│  ├─ Proof of execution          │
│  └─ Input data: GONE            │
└─────────────────────────────────┘
```

**Key insight:** The input (skill or dataset) is NEVER stored. Only the execution certificate persists.

## Use Cases

### Skill Verification (Original)
**Claim:** "This Hermes skill works correctly"

**Inspection:**
- Load skill code
- Run test suite in isolation
- Log test results
- Generate attestation
- Delete skill code

**Certificate proves:**
- ✅ Tests: 6/6 passed
- ✅ Duration: 2.2s
- ✅ Exit code: 0
- ✅ Attestation: 0xfb41b44...

### Data Inspection (New)
**Claim:** "I have 5,000 support tickets about refunds"

**Inspection:**
- Load private dataset
- Run LLM analysis
- Count tickets, check themes
- Generate certificate
- Delete dataset

**Certificate proves:**
- ✅ Dataset hash: abc123...
- ✅ Analysis: "4,987 tickets, 73% about refunds"
- ✅ Themes: shipping delays, product defects
- ❌ Actual tickets: NOT ACCESSIBLE

### API Key Verification (New)
**Claim:** "I have a valid Anthropic API key with $50 credit"

**Inspection:**
- Load API key (secret)
- Test with LLM call
- Check balance
- Generate certificate
- Delete key

**Certificate proves:**
- ✅ Key is valid
- ✅ Credit: $52.34
- ✅ Rate limit: good standing
- ❌ Key value: NOT REVEALED

## Three Implementation Paths

### 1. Docker Containers (Current - Skill Verifier)
**Best for:** Skill verification, local testing

```bash
POST /verify
{
  "skillUrl": "https://example.com/skill.md",
  "environment": "node:18"
}
```

**Isolation:** Docker container  
**Trust:** Docker daemon  
**Good for:** Skills, reproducible tests

### 2. GitHub Actions (New - Soft TEE)
**Best for:** Data inspection, pre-buy inspection

```yaml
workflow_dispatch:
  inputs:
    dataset_secret: "PRIVATE_DATASET"
    inspection_prompt: "Analyze for X"
```

**Isolation:** GitHub runners  
**Trust:** GitHub infrastructure  
**Good for:** Datasets, public verifiability

### 3. dstack TEE (Future - Hard TEE)
**Best for:** High-stakes verification, production

```yaml
dstack run --tee intel-tdx \
  --input dataset.enc \
  --script analyze.py
```

**Isolation:** Intel TDX hardware  
**Trust:** CPU manufacturer  
**Good for:** Regulatory compliance, high-value data

## Documentation

### Skill Verification
- [README.md](README.md) - Skill verifier overview
- [DEMO.md](DEMO.md) - Live skill verification example
- [TEE_READY.md](TEE_READY.md) - TEE integration plan

### Data Inspection
- [../data-collab-market/AUDITOR-GUIDE.md](../data-collab-market/AUDITOR-GUIDE.md) - How to verify inspection certificates
- [../data-collab-market/GITHUB-ACTIONS-QUICKSTART.md](../data-collab-market/GITHUB-ACTIONS-QUICKSTART.md) - 5-minute demo
- [../data-collab-market/ARCHITECTURE-EPHEMERAL.md](../data-collab-market/ARCHITECTURE-EPHEMERAL.md) - Ephemeral execution model

## Unification Plan

**Phase 1 (Current):**
- ✅ Skill verifier working (Docker)
- ✅ Data inspection working (GitHub Actions)
- ⏳ Separate codebases

**Phase 2 (Next):**
- [ ] Unified API endpoint
- [ ] Both use same certificate format
- [ ] Pluggable execution backends (Docker, GitHub, TEE)

**Phase 3 (Future):**
- [ ] Deploy to dstack TEE
- [ ] Real cryptographic attestations
- [ ] On-chain certificate registry

## API Design (Unified)

```typescript
POST /inspect
{
  "type": "skill" | "data",
  "input": {
    // For skills:
    "skillUrl": "https://...",
    "tests": [...],
    
    // For data:
    "dataSecret": "PRIVATE_DATASET",
    "prompt": "Analyze for X"
  },
  "backend": "docker" | "github-actions" | "dstack-tee"
}

Response:
{
  "certificateId": "cert_xyz",
  "result": {
    "passed": true,
    "output": "...",
    "hash": "sha256:..."
  },
  "proof": {
    "backend": "docker",
    "attestation": "0x...",
    "timestamp": "2026-02-01T13:55:00Z"
  },
  "certificate_url": "/certificate/cert_xyz",
  "lifecycle": {
    "input_deleted": true,
    "sandbox_destroyed": true
  }
}
```

## Why "Inspection Certificates"?

**"Inspection"** = Verify properties without full exposure
- Like a home inspection before buying
- Like a pre-buy car inspection
- Like an audit that doesn't reveal everything

**"Certificate"** = Verifiable proof
- Can be shared publicly
- Anyone can verify
- Tamper-proof

**Together:** Proof that something was inspected, without revealing what was inspected.

## Comparison

| Aspect | Skill Verification | Data Inspection |
|--------|-------------------|-----------------|
| **Input** | Code + tests | Dataset + prompt |
| **Isolation** | Docker container | GitHub runner / TEE |
| **Execute** | Run tests | Run LLM analysis |
| **Output** | Test results | Analysis result |
| **Certificate** | Attestation | Signed claim |
| **Privacy** | Code is usually public | Dataset is private |
| **Use case** | "Skill works" | "Data is valuable" |

**Both:** Ephemeral execution, permanent proof!

---

**Next steps:**
1. Move data inspection code into skill-verifier repo
2. Unify under "Inspection Certificates" branding
3. Create unified API
4. Deploy both to dstack TEE

🦞 **Verifiable execution for skills AND data**
