# Inspection Certificate - Phala Contract

**Simple MVP for Phala deployment**

## What It Does

Stores and serves inspection certificates on Phala Network with a beautiful web UI.

## Quick Deploy

```bash
# Build the contract
npm run build

# Deploy to Phala
# (Waiting for Phala deployment credentials from Andrew)
```

## API

### Create Certificate
```bash
POST /create
{
  "type": "data" | "skill" | "credential",
  "claimant": "wallet_address",
  "inputHash": "sha256_hash",
  "prompt": "What was inspected",
  "result": "Inspection result"
}

Returns: { "id": "cert_...", "url": "/certificate/cert_..." }
```

### View Certificate
```
GET /certificate/:id
```

Returns: Beautiful HTML page with certificate details

### List Certificates
```
GET /
```

Returns: Home page with all certificates

### API Endpoint
```
GET /certificates
```

Returns: JSON array of all certificates

## Example Certificate

```json
{
  "id": "cert_1738439073_abc123",
  "type": "data",
  "claimant": "MoltyClaw47",
  "inputHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "inspectionPrompt": "Analyze sentiment in customer reviews",
  "result": "60% positive, 30% neutral, 10% negative. Themes: quality, shipping, support.",
  "timestamp": 1738439073000,
  "attestation": "phala_derived_secret_xyz..."
}
```

## UI Features

- 🎨 Beautiful dark theme
- 📱 Mobile responsive
- 🔐 Shows Phala attestation
- ✅ Clear verification status
- 🦞 Lobster branding

## Next Steps

1. Deploy to Phala CVM
2. Andrew provides URL
3. Create live example certificate
4. Share publicly!

---

**Status:** Ready for deployment (waiting on Phala credentials)
