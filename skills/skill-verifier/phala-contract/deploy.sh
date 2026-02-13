#!/bin/bash
# Deploy Inspection Certificate contract to Phala

set -e

echo "🦞 Deploying Inspection Certificate to Phala..."
echo ""

# Build the contract
echo "📦 Building contract..."
npm install
npm run build

echo "✅ Build complete!"
echo ""

# Deploy to Phala (using Phala CLI)
echo "🚀 Deploying to Phala testnet..."

# This would use the actual Phala deployment command
# For now, we'll document the steps

cat << 'EOF'
To deploy:

1. Install Phala CLI:
   npm install -g @phala/pink-cli

2. Login to Phala:
   pink login

3. Deploy contract:
   pink deploy dist/index.js --name inspection-certificates

4. You'll get a URL like:
   https://your-contract-id.phala.network

5. Create example certificate:
   curl -X POST https://your-contract-id.phala.network/create \
     -H "Content-Type: application/json" \
     -d '{
       "type": "data",
       "claimant": "MoltyClaw47",
       "inputHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
       "prompt": "Analyze sentiment distribution in customer reviews",
       "result": "Analysis complete: 60% positive, 30% neutral, 10% negative. Common themes: product quality, shipping speed, customer service."
     }'

6. View certificate:
   Open https://your-contract-id.phala.network/certificate/CERT_ID

EOF

echo ""
echo "✨ Contract ready for deployment!"
