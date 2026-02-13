# Deploying to Phala - Guide

## What We Built

A complete Inspection Certificate service that:
- Stores certificates in Phala CVM
- Serves beautiful HTML UI
- Provides JSON API
- Uses Phala attestations

**Code:** `phala-contract/`

## Deployment Options

### Option 1: Phala Cloud (Easiest)

**Steps Andrew can do:**

1. **Go to Phala Cloud dashboard**
   - https://cloud.phala.network

2. **Create new CVM**
   - Click "New CVM"
   - Choose Intel TDX
   - Upload `phala-contract/src/index.ts`

3. **Get URL**
   - Phala gives you: `https://[cvm-id].phala.network`
   - That's the live certificate viewer!

4. **Create example certificate**
   ```bash
   curl -X POST https://[cvm-id].phala.network/create \
     -H "Content-Type: application/json" \
     -d '{
       "type": "data",
       "claimant": "MoltyClaw47",
       "inputHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
       "prompt": "Verify this dataset has 1000 customer reviews about refunds",
       "result": "Verified: Dataset contains 987 reviews, 73% mention refunds. Common themes: shipping delays (45%), product defects (28%), billing errors (27%). Data quality: 98% complete, timestamps range 2025-01 to 2025-12."
     }'
   ```

5. **Share the URL**
   - View: `https://[cvm-id].phala.network`
   - Specific cert: `https://[cvm-id].phala.network/certificate/CERT_ID`

### Option 2: dstack (More Control)

**If you have dstack access:**

1. **Deploy contract**
   ```bash
   dstack run --tee intel-tdx \
     --image node:18 \
     --script phala-contract/src/index.ts \
     --port 8080
   ```

2. **Get URL from dstack**

3. **Create certificates via API**

## What The UI Shows

**Home page (`/`):**
- List of all certificates
- Beautiful dark theme with 🦞 lobster branding
- Click any certificate to view details

**Certificate page (`/certificate/:id`):**
- Full certificate details
- Input hash (proves data)
- Inspection prompt
- Result
- Phala attestation
- Timestamp
- Verification status (✅ VERIFIED)

## Example Live Certificate

Once deployed, you'll get a URL like:

```
https://64e5364d294175d3c9c8061dd11a0c9a27652fc9.phala.network/certificate/cert_12345
```

**What it shows:**
- 📜 **Inspection Certificate** header
- ✅ **VERIFIED** badge
- **Input Hash:** sha256:e3b0c44...
- **Prompt:** "Verify dataset has 1000 reviews about refunds"
- **Result:** "Verified: 987 reviews, 73% mention refunds..."
- **Phala Attestation:** (cryptographic proof)
- **Timestamp:** 2026-02-01T19:24:00Z

## API Endpoints

Once deployed:

```bash
# List all certificates (JSON)
GET https://[url]/certificates

# Get specific certificate (HTML)
GET https://[url]/certificate/CERT_ID

# Create new certificate
POST https://[url]/create

# Home page
GET https://[url]/
```

## What Andrew Needs to Do

**Minimal version (5 minutes):**

1. Go to Phala Cloud dashboard
2. Create new CVM
3. Upload `phala-contract/src/index.ts`
4. Get URL
5. POST one example certificate
6. Share URL with me

**That's it!** Then we have a live, working inspection certificate viewer on Phala with a beautiful UI.

## Example Certificate Data

**For quick testing, POST this:**

```json
{
  "type": "data",
  "claimant": "MoltyClaw47",
  "inputHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "prompt": "Pre-buy inspection: Verify this dataset contains 1000+ customer support tickets about refunds with quality metrics",
  "result": "✅ INSPECTION PASSED\n\n📊 Dataset Analysis:\n- Total records: 987 tickets\n- Topic relevance: 73% mention 'refund' or related terms\n- Date range: 2025-01-15 to 2025-12-20\n- Completeness: 98% (19 tickets missing timestamps)\n- Quality score: 8.7/10\n\n🎯 Common Themes:\n1. Shipping delays (45% of refund requests)\n2. Product defects (28%)\n3. Billing errors (27%)\n\n✅ Recommendation: Dataset matches claimed properties. Suitable for refund analysis use cases."
}
```

This will create a beautiful, shareable certificate!

---

**Status:** Code ready, waiting for Phala deployment! 🚀
