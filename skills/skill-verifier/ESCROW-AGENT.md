# Inspection Certificates as Escrow Agent

## The Three-Party Model

```
┌─────────────────────────────────────────────────────────┐
│  BUYER                                                  │
│  "I'll pay $100 for skill X that passes tests Y"       │
└─────────────────────────────────────────────────────────┘
                          ↓ locks payment
┌─────────────────────────────────────────────────────────┐
│  ESCROW AGENT (Inspection Certificate Service in TEE)  │
│  - Holds $100 in KMS-sealed wallet                     │
│  - Waits for delivery                                  │
│  - Verifies work via ephemeral execution               │
│  - Releases payment ONLY if verification passes        │
└─────────────────────────────────────────────────────────┘
                          ↓ delivers work
┌─────────────────────────────────────────────────────────┐
│  SELLER                                                 │
│  "Here's skill X"                                       │
└─────────────────────────────────────────────────────────┘
                          ↓ if tests pass
                   Payment released ✅
```

## Why This Works

### Traditional Escrow Problems

**Centralized escrow (PayPal, Escrow.com):**
- ❌ Trust the escrow company
- ❌ Disputes require human arbitration
- ❌ High fees (5-10%)
- ❌ Opaque verification process
- ❌ Can't verify they actually checked the work

**Smart contract escrow (Ethereum):**
- ❌ Can't verify off-chain work (skills, datasets)
- ❌ Oracle problem (who verifies?)
- ❌ Expensive gas fees
- ❌ Slow finality

### TEE + KMS Escrow Solution

**Advantages:**
- ✅ **Automated verification** - TEE runs actual tests
- ✅ **Cryptographic proof** - Attestation shows verification happened
- ✅ **Trustless** - KMS only releases funds if TEE proof valid
- ✅ **Transparent** - Anyone can audit the verification code
- ✅ **Fast** - Seconds, not days
- ✅ **Cheap** - No gas fees, just compute costs
- ✅ **Decentralized** - Anyone with Phala/dstack access can run

## The Flow

### Step 1: Create Escrow

**Buyer initiates:**
```bash
POST /escrow/create
{
  "buyer": "buyer_wallet_address",
  "amount": 100,
  "currency": "USDC",
  "deliverable": {
    "type": "skill",
    "requirements": {
      "tests": ["test_api_call", "test_error_handling"],
      "environment": "node:18",
      "timeout": 30
    }
  },
  "deadline": "2026-02-15T00:00:00Z"
}

Response:
{
  "escrowId": "escrow_abc123",
  "kmsSealedWallet": "0x...",
  "attestation": "0x...",
  "depositAddress": "0x..."
}
```

**Buyer deposits funds:**
```bash
# Send $100 USDC to depositAddress
# KMS seals funds (only TEE can release)
```

### Step 2: Seller Delivers

**Seller submits work:**
```bash
POST /escrow/escrow_abc123/deliver
{
  "seller": "seller_wallet_address",
  "skillUrl": "https://example.com/skill.md"
}

# TEE does:
1. Load skill from URL
2. Run verification (ephemeral execution)
3. Generate inspection certificate
4. Check if requirements met
```

### Step 3: Automated Release (or Refund)

**If verification passes:**
```bash
TEE generates proof:
{
  "escrowId": "escrow_abc123",
  "verified": true,
  "certificate": {
    "tests": { "passed": 2, "failed": 0 },
    "attestation": "0x..."
  }
}

KMS sees proof → Releases $100 to seller
Buyer gets inspection certificate
```

**If verification fails:**
```bash
TEE generates proof:
{
  "escrowId": "escrow_abc123",
  "verified": false,
  "certificate": {
    "tests": { "passed": 1, "failed": 1 },
    "failures": ["test_error_handling failed"]
  }
}

KMS sees proof → Refunds $100 to buyer
Seller gets failure report
```

**If deadline passes without delivery:**
```bash
TEE checks: deadline expired, no delivery

KMS → Automatic refund to buyer
```

## Why dstack + Phala KMS?

### Key Management Service (KMS)

**Problem:** How does TEE control funds without exposing private keys?

**Solution:** KMS seals keys inside TEE

```
┌─────────────────────────────────────┐
│  KMS (Key Management Service)      │
│  ├─ Generates wallet inside TEE    │
│  ├─ Private key NEVER leaves TEE   │
│  ├─ Signs transactions in TEE      │
│  └─ Only releases based on proof   │
└─────────────────────────────────────┘
```

**Benefits:**
- ✅ Private key sealed in TEE hardware
- ✅ Can't be extracted (even by operator)
- ✅ Survives TEE restarts (KMS persists sealed keys)
- ✅ Reproducible (same attestation → same keys)

### Phala Network Integration

**Why Phala?**
- ✅ Built-in KMS for TEE wallets
- ✅ On-chain verification of attestations
- ✅ Decentralized (many CVMs run the service)
- ✅ No single point of failure

**How it works:**
```typescript
// Deploy escrow agent to Phala CVM
const escrowAgent = await phala.deployContract({
  code: "inspection-certificate-escrow",
  tee: "intel-tdx",
  kms: true  // Enable KMS for wallet management
});

// KMS creates sealed wallet
const wallet = await escrowAgent.createKMSWallet();
// wallet.address = public (for deposits)
// wallet.privateKey = sealed in TEE (never exposed)

// Fund escrow
await buyer.deposit(wallet.address, 100);

// Seller delivers
await escrowAgent.verifyAndRelease({
  skillUrl: "...",
  tests: [...]
});

// TEE verifies, KMS auto-releases if pass
```

## Use Cases

### 1. Skill Marketplace

**Buyer:** "I need a Hermes skill that passes these 5 tests"

**Flow:**
1. Buyer locks $50 in escrow
2. Seller builds skill, submits URL
3. TEE verifies skill (runs tests)
4. If 5/5 tests pass → $50 released to seller
5. Buyer gets working skill + certificate

**No disputes, instant settlement.**

### 2. Data Marketplace

**Buyer:** "I need 10K support tickets about refunds"

**Flow:**
1. Buyer locks $500 in escrow
2. Seller uploads dataset (encrypted)
3. TEE inspects: "9,847 tickets, 73% mention refunds"
4. If criteria met → $500 released
5. Buyer gets dataset + inspection certificate

**Seller can't fake data (TEE actually checks).**

### 3. API Key Sales

**Buyer:** "I need a valid Anthropic API key with $100 credit"

**Flow:**
1. Buyer locks $80 in escrow
2. Seller submits API key (via KMS-encrypted channel)
3. TEE tests key: calls API, checks balance
4. If valid + $100+ credit → $80 released
5. Buyer gets key + verification certificate

**Buyer knows key is valid before paying.**

### 4. Research Validation

**Journal:** "We'll pay $1000 for reproducing this result"

**Flow:**
1. Journal locks $1000 in escrow
2. Researcher submits reproduction code
3. TEE runs code on test data
4. If results match paper → $1000 released
5. Journal gets reproduction certificate

**Automated peer review.**

## Security Properties

### What TEE Guarantees

1. **Verification integrity:**
   - Tests actually ran as specified
   - No fake results
   - Results match what TEE computed

2. **Payment integrity:**
   - KMS only releases if verification passed
   - Can't steal funds (key sealed in TEE)
   - Can't manipulate results to get paid

3. **Privacy:**
   - Private keys never exposed
   - Dataset remains private during verification
   - Only inspection result is public

### What Attestation Proves

```json
{
  "attestation": {
    "tee_quote": "0x...",  // Intel TDX signature
    "compose_hash": "sha256:...",  // Reproducible build
    "verification": {
      "escrowId": "escrow_abc123",
      "skillUrl": "https://...",
      "tests": { "passed": 5, "failed": 0 },
      "timestamp": "2026-02-01T14:00:00Z"
    },
    "kms_action": {
      "from": "escrow_wallet_0x...",
      "to": "seller_wallet_0x...",
      "amount": 100,
      "released": true
    }
  }
}
```

**Anyone can verify:**
- ✅ TEE quote is valid (Intel signed it)
- ✅ Compose hash matches published code
- ✅ Verification actually ran
- ✅ Payment was correct
- ✅ KMS released based on TEE proof

### Attack Scenarios

**Attack 1: Fake verification**
```
Attacker: "I'll say tests passed even if they failed"

Defense: Attestation proves code that ran
          Anyone can audit: did it actually test?
          Reproducible builds: re-run to verify
```

**Attack 2: Steal escrowed funds**
```
Attacker: "I'll extract private key and take the money"

Defense: KMS seals key in TEE hardware
          Physically impossible to extract
          Intel TDX prevents even hypervisor access
```

**Attack 3: Malicious seller (fake skill)**
```
Attacker: "I'll submit garbage and hope verification passes"

Defense: TEE actually runs tests
          If tests fail, no payment
          Certificate proves it was tested
```

**Attack 4: Malicious buyer (refuse payment)**
```
Attacker: "I'll claim it failed even if it passed"

Defense: Attestation proves verification result
          Payment automatic (KMS, not buyer)
          Buyer can't block release if TEE says pass
```

## Economic Model

### Fees

**Escrow service charges:**
- 1-2% transaction fee (vs 5-10% traditional escrow)
- Covers: TEE compute, KMS operations, on-chain verification

**Fee distribution:**
```
100 USDC transaction
├─ 98 USDC to seller (if verified)
├─ 1.5 USDC to TEE operator (compute costs)
└─ 0.5 USDC to Phala validators (on-chain verification)
```

### Revenue Sharing

**For marketplace operators:**
- Run multiple escrow CVMs
- Earn fees from all transactions
- Stake Phala tokens for priority

**For buyers/sellers:**
- Lower fees than traditional escrow
- Instant settlement (no 7-day holds)
- Trustless (don't need reputation)

## Implementation Plan

### Phase 1: MVP (Local Testing)
- [ ] Simple escrow smart contract
- [ ] TEE verification engine (Docker simulation)
- [ ] Mock KMS (local wallet)
- [ ] Single test case (skill verification)

**Goal:** Prove the concept works

### Phase 2: Phala Integration
- [ ] Deploy to Phala CVM
- [ ] Real KMS integration
- [ ] Intel TDX attestations
- [ ] On-chain escrow contract

**Goal:** Production-ready escrow agent

### Phase 3: Marketplace
- [ ] Web UI for escrow creation
- [ ] Browse active escrows
- [ ] Dispute resolution (multi-sig override)
- [ ] Reputation system

**Goal:** Full marketplace platform

## Code Sketch

### Escrow Smart Contract (Phala)

```typescript
import { Contract } from '@phala/fn';

export class InspectionEscrow extends Contract {
  async createEscrow(params: {
    buyer: string,
    amount: number,
    requirements: any
  }) {
    // Create KMS wallet for this escrow
    const wallet = await this.kms.createWallet();
    
    // Store escrow metadata
    const escrow = {
      id: generateId(),
      buyer: params.buyer,
      escrowWallet: wallet.address,
      amount: params.amount,
      requirements: params.requirements,
      status: 'awaiting_delivery',
      created: Date.now()
    };
    
    await this.storage.set(escrow.id, escrow);
    
    return {
      escrowId: escrow.id,
      depositAddress: wallet.address,
      attestation: await this.getAttestation()
    };
  }
  
  async deliver(escrowId: string, deliverable: any) {
    const escrow = await this.storage.get(escrowId);
    
    // Run verification in TEE
    const result = await this.verifyDeliverable(
      deliverable,
      escrow.requirements
    );
    
    // Generate inspection certificate
    const certificate = {
      escrowId,
      verified: result.passed,
      tests: result.tests,
      attestation: await this.getAttestation()
    };
    
    // If verified, release funds via KMS
    if (result.passed) {
      await this.kms.transfer({
        from: escrow.escrowWallet,
        to: deliverable.seller,
        amount: escrow.amount
      });
      
      escrow.status = 'completed';
    } else {
      escrow.status = 'failed';
    }
    
    await this.storage.set(escrowId, escrow);
    
    return certificate;
  }
  
  async verifyDeliverable(deliverable: any, requirements: any) {
    // Run tests ephemerally
    const container = await docker.run({
      image: requirements.environment,
      // ... load skill, run tests
    });
    
    // Return results (container destroyed after)
    return {
      passed: container.exitCode === 0,
      tests: container.testResults
    };
  }
}
```

## Integration with Info Bazaar

**Info Bazaar = Marketplace for private data**

**Inspection Escrow enables:**
1. **Discovery:** Browse datasets with inspection certificates
2. **Verification:** Escrow agent pre-inspects before you pay
3. **Transaction:** Pay only if inspection passes
4. **Delivery:** Get data + certificate

**Flow:**
```
Buyer: "I need data about X"
  ↓
Browse: See datasets with inspection certificates
  ↓
Choose: "This one looks good (certificate shows relevance)"
  ↓
Escrow: Lock $500, request inspection
  ↓
TEE: Runs inspection, verifies relevance
  ↓
Release: If passed, buyer gets data + $500 goes to seller
```

**Arrow's Paradox solved:**
- Seller proves value WITHOUT revealing data (inspection certificate)
- Buyer pays only if inspection passes (escrow)
- Both parties trust TEE + KMS (not each other)

## Comparison to Alternatives

| Approach | Trust | Speed | Cost | Automation |
|----------|-------|-------|------|------------|
| **Traditional escrow** | Escrow company | Days | 5-10% | ❌ Human arbitration |
| **Smart contract** | Blockchain | Hours | Gas fees | ⚠️ Oracle problem |
| **Multi-sig** | M-of-N parties | Varies | Free | ❌ Manual approval |
| **TEE + KMS Escrow** | TEE hardware | Seconds | 1-2% | ✅ Fully automated |

**TEE + KMS wins on:**
- Speed (seconds vs days)
- Cost (1-2% vs 5-10%)
- Automation (no humans needed)
- Trust (hardware, not companies)

## Next Steps

1. **Prototype escrow contract** (Phala testnet)
2. **Integrate KMS** (wallet creation + sealed keys)
3. **Test end-to-end flow** (create escrow → deliver → verify → release)
4. **Deploy to mainnet** (production escrow agent)
5. **Build marketplace UI** (browse escrows, create new ones)

---

**Inspection Certificates aren't just proofs - they're automated escrow agents** 🦞💰
