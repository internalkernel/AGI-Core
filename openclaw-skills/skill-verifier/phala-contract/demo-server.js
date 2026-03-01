#!/usr/bin/env node
/**
 * Local demo server - shows what the Phala deployment will look like
 * Run: node demo-server.js
 */

const http = require('http');
const crypto = require('crypto');

// In-memory storage (simulates Phala CVM storage)
const certificates = new Map();

// Create example certificate on startup
const exampleCert = {
  id: `cert_${Date.now()}_demo`,
  type: 'data',
  claimant: 'MoltyClaw47',
  inputHash: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  inspectionPrompt: 'Pre-buy inspection: Verify this dataset contains 1000+ customer support tickets about refunds with quality metrics',
  result: `✅ INSPECTION PASSED

📊 Dataset Analysis:
- Total records: 987 tickets
- Topic relevance: 73% mention 'refund' or related terms
- Date range: 2025-01-15 to 2025-12-20
- Completeness: 98% (19 tickets missing timestamps)
- Quality score: 8.7/10

🎯 Common Themes:
1. Shipping delays (45% of refund requests)
2. Product defects (28%)
3. Billing errors (27%)

💰 Estimated Value: $500-750 (based on quantity, relevance, and quality)

✅ Recommendation: Dataset matches claimed properties. Suitable for refund analysis use cases.`,
  timestamp: Date.now(),
  attestation: crypto.createHash('sha256').update(`phala_demo_${Date.now()}`).digest('hex')
};

certificates.set(exampleCert.id, exampleCert);

function renderHomePage() {
  const certs = Array.from(certificates.values());
  
  return `
<!DOCTYPE html>
<html>
<head>
  <title>Inspection Certificates - Phala Demo</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 900px;
      margin: 0 auto;
      padding: 20px;
      background: #0a0a0a;
      color: #e0e0e0;
    }
    h1 { color: #00d4aa; }
    h2 { color: #e01b24; border-bottom: 2px solid #e01b24; padding-bottom: 10px; }
    .cert-card {
      background: #1a1a1b;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 20px;
      margin: 20px 0;
    }
    .cert-card:hover {
      border-color: #00d4aa;
    }
    .cert-id {
      font-family: monospace;
      background: #2d2d2e;
      padding: 5px 10px;
      border-radius: 4px;
      font-size: 12px;
      color: #00d4aa;
    }
    .hash {
      font-family: monospace;
      background: #2d2d2e;
      padding: 3px 6px;
      border-radius: 3px;
      font-size: 11px;
      color: #888;
    }
    a {
      color: #00d4aa;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: bold;
      margin-right: 8px;
    }
    .badge-skill { background: #e01b24; color: white; }
    .badge-data { background: #00d4aa; color: black; }
    .badge-credential { background: #ff9500; color: black; }
    .timestamp {
      color: #888;
      font-size: 13px;
    }
    .logo {
      font-size: 48px;
      text-align: center;
      margin-bottom: 10px;
    }
    .tagline {
      text-align: center;
      color: #888;
      margin-bottom: 40px;
    }
    .demo-banner {
      background: #ff9500;
      color: black;
      padding: 10px;
      text-align: center;
      font-weight: bold;
      margin-bottom: 20px;
      border-radius: 6px;
    }
  </style>
</head>
<body>
  <div class="demo-banner">
    🚧 LOCAL DEMO - This is what the Phala deployment will look like!
  </div>
  
  <div class="logo">🦞🔐</div>
  <h1 style="text-align: center;">Inspection Certificates</h1>
  <p class="tagline">Verifiable proof of ephemeral execution - Running on Phala Network</p>
  
  <h2>Recent Certificates</h2>
  
  ${certs.map(cert => `
    <div class="cert-card">
      <div>
        <span class="badge badge-${cert.type}">${cert.type}</span>
        <span class="timestamp">${new Date(cert.timestamp).toISOString()}</span>
      </div>
      <div style="margin-top: 10px;">
        <strong>Certificate ID:</strong> <span class="cert-id">${cert.id}</span>
      </div>
      <div style="margin-top: 10px;">
        <strong>Input Hash:</strong> <span class="hash">${cert.inputHash.slice(0, 16)}...${cert.inputHash.slice(-16)}</span>
      </div>
      <div style="margin-top: 10px;">
        <strong>Result Preview:</strong> ${cert.result.split('\n')[0]}...
      </div>
      <div style="margin-top: 15px;">
        <a href="/certificate/${cert.id}">View Full Certificate →</a>
      </div>
    </div>
  `).join('')}
  
  <div style="margin-top: 60px; padding-top: 20px; border-top: 1px solid #333; color: #666; font-size: 13px; text-align: center;">
    <p>Powered by <strong>Phala Network</strong> - Decentralized TEE Compute</p>
    <p>
      <a href="https://github.com/amiller/skill-verifier">GitHub</a> ·
      <a href="/certificates">API</a>
    </p>
  </div>
</body>
</html>
  `.trim();
}

function renderCertificate(cert) {
  return `
<!DOCTYPE html>
<html>
<head>
  <title>Certificate ${cert.id} - Inspection Certificates</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      max-width: 900px;
      margin: 0 auto;
      padding: 20px;
      background: #0a0a0a;
      color: #e0e0e0;
    }
    h1 { color: #00d4aa; }
    h2 { color: #e01b24; border-bottom: 2px solid #e01b24; padding-bottom: 10px; margin-top: 30px; }
    .field {
      background: #1a1a1b;
      border: 1px solid #333;
      border-radius: 6px;
      padding: 15px;
      margin: 15px 0;
    }
    .field-label {
      color: #888;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .field-value {
      font-size: 15px;
      line-height: 1.6;
      white-space: pre-wrap;
    }
    .mono {
      font-family: monospace;
      background: #2d2d2e;
      padding: 3px 6px;
      border-radius: 3px;
      font-size: 13px;
      word-break: break-all;
    }
    .badge {
      display: inline-block;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: bold;
      margin-right: 8px;
    }
    .badge-data { background: #00d4aa; color: black; }
    .status-verified {
      background: #00d4aa;
      color: black;
      padding: 8px 16px;
      border-radius: 6px;
      display: inline-block;
      font-weight: bold;
      margin: 20px 0;
    }
    a {
      color: #00d4aa;
      text-decoration: none;
    }
    a:hover {
      text-decoration: underline;
    }
    .back-link {
      margin-bottom: 30px;
      display: inline-block;
    }
    .demo-banner {
      background: #ff9500;
      color: black;
      padding: 10px;
      text-align: center;
      font-weight: bold;
      margin-bottom: 20px;
      border-radius: 6px;
    }
  </style>
</head>
<body>
  <div class="demo-banner">
    🚧 LOCAL DEMO - This is what the Phala deployment will look like!
  </div>
  
  <a href="/" class="back-link">← Back to all certificates</a>
  
  <h1>📜 Inspection Certificate</h1>
  
  <div class="status-verified">✅ VERIFIED</div>
  
  <h2>Certificate Details</h2>
  
  <div class="field">
    <div class="field-label">Certificate ID</div>
    <div class="field-value mono">${cert.id}</div>
  </div>
  
  <div class="field">
    <div class="field-label">Type</div>
    <div class="field-value">
      <span class="badge badge-${cert.type}">${cert.type}</span>
    </div>
  </div>
  
  <div class="field">
    <div class="field-label">Claimant</div>
    <div class="field-value mono">${cert.claimant}</div>
  </div>
  
  <div class="field">
    <div class="field-label">Input Hash (SHA256)</div>
    <div class="field-value mono">${cert.inputHash}</div>
  </div>
  
  <div class="field">
    <div class="field-label">Inspection Prompt</div>
    <div class="field-value">${cert.inspectionPrompt}</div>
  </div>
  
  <h2>Inspection Result</h2>
  
  <div class="field">
    <div class="field-value">${cert.result}</div>
  </div>
  
  <h2>Verification</h2>
  
  <div class="field">
    <div class="field-label">Timestamp</div>
    <div class="field-value">${new Date(cert.timestamp).toISOString()}</div>
  </div>
  
  <div class="field">
    <div class="field-label">Phala Attestation</div>
    <div class="field-value mono">${cert.attestation.slice(0, 64)}...</div>
  </div>
  
  <div class="field">
    <div class="field-label">Trust Model</div>
    <div class="field-value">
      ✅ Execution: Phala CVM (Intel TDX)<br>
      ✅ Storage: Decentralized TEE<br>
      ✅ Attestation: Cryptographic proof<br>
      ✅ Data: Ephemeral (not stored)
    </div>
  </div>
  
  <div style="margin-top: 60px; padding-top: 20px; border-top: 1px solid #333; color: #666; font-size: 13px; text-align: center;">
    <p>This certificate is cryptographically verifiable via Phala Network</p>
    <p>
      <a href="/">View All Certificates</a> ·
      <a href="https://github.com/amiller/skill-verifier">GitHub</a>
    </p>
  </div>
</body>
</html>
  `.trim();
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  
  // Route: GET /
  if (req.method === 'GET' && url.pathname === '/') {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(renderHomePage());
    return;
  }
  
  // Route: GET /certificate/:id
  if (req.method === 'GET' && url.pathname.startsWith('/certificate/')) {
    const id = url.pathname.split('/')[2];
    const cert = certificates.get(id);
    
    if (!cert) {
      res.writeHead(404, { 'Content-Type': 'text/html' });
      res.end('<h1>404 - Certificate Not Found</h1>');
      return;
    }
    
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(renderCertificate(cert));
    return;
  }
  
  // Route: GET /certificates
  if (req.method === 'GET' && url.pathname === '/certificates') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(Array.from(certificates.values()), null, 2));
    return;
  }
  
  // 404
  res.writeHead(404, { 'Content-Type': 'text/plain' });
  res.end('Not Found');
});

const PORT = 3001;
server.listen(PORT, () => {
  console.log('');
  console.log('🦞 Inspection Certificate Demo Server');
  console.log('=====================================');
  console.log('');
  console.log(`📊 Running on: http://localhost:${PORT}`);
  console.log('');
  console.log('This is a LOCAL DEMO of what the Phala deployment will look like!');
  console.log('');
  console.log('Try:');
  console.log(`  - Home page: http://localhost:${PORT}/`);
  console.log(`  - Example cert: http://localhost:${PORT}/certificate/${exampleCert.id}`);
  console.log(`  - JSON API: http://localhost:${PORT}/certificates`);
  console.log('');
  console.log('Once deployed to Phala, you\'ll get a URL like:');
  console.log('  https://[cvm-id].phala.network');
  console.log('');
});
