#!/usr/bin/env node
/**
 * Skill Verifier API Server
 * REST API for submitting and checking skill verifications
 */

const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const SkillVerifier = require('./verifier.js');

const app = express();
const PORT = process.env.PORT || 3000;
const VERIFIER_API_KEY = process.env.VERIFIER_API_KEY || '';

// Auth middleware — all non-health endpoints require Bearer token
function checkAuth(req, res, next) {
  if (!VERIFIER_API_KEY) {
    return res.status(503).json({ error: 'VERIFIER_API_KEY not configured' });
  }
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  const provided = Buffer.from(auth.slice(7));
  const expected = Buffer.from(VERIFIER_API_KEY);
  if (provided.length !== expected.length || !crypto.timingSafeEqual(provided, expected)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}

// Storage setup
const uploadDir = path.join(__dirname, 'uploads');
const resultsDir = path.join(__dirname, 'results');
[uploadDir, resultsDir].forEach(dir => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
});

const upload = multer({ dest: uploadDir, limits: { fileSize: 50 * 1024 * 1024 } }); // 50MB max

// Job queue (in-memory for now) with concurrency + TTL limits
const jobs = new Map();
const MAX_CONCURRENT_JOBS = 5;
const MAX_TOTAL_JOBS = 100;
const JOB_TTL_MS = 3600000; // 1 hour

// Auto-cleanup expired jobs every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [id, job] of jobs) {
    if (now - new Date(job.createdAt).getTime() > JOB_TTL_MS) {
      // Cleanup uploaded file if exists
      if (job.skillPath && fs.existsSync(job.skillPath)) {
        try { fs.unlinkSync(job.skillPath); } catch {}
      }
      // Cleanup result file on disk
      const resultPath = path.join(resultsDir, `${id}.json`);
      if (fs.existsSync(resultPath)) {
        try { fs.unlinkSync(resultPath); } catch {}
      }
      jobs.delete(id);
    }
  }
}, 300000);

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Enable CORS (restrict origins to configured trusted domain or same-origin)
const CORS_ORIGIN = process.env.CORS_ORIGIN || '';
app.use((req, res, next) => {
  if (CORS_ORIGIN) {
    res.header('Access-Control-Allow-Origin', CORS_ORIGIN);
  }
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.header('Access-Control-Allow-Methods', 'GET, POST, DELETE');
  next();
});

/**
 * Health check
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    jobs: {
      total: jobs.size,
      pending: Array.from(jobs.values()).filter(j => j.status === 'pending').length,
      running: Array.from(jobs.values()).filter(j => j.status === 'running').length,
      completed: Array.from(jobs.values()).filter(j => j.status === 'completed').length,
      failed: Array.from(jobs.values()).filter(j => j.status === 'failed').length
    }
  });
});

/**
 * Submit skill for verification
 * POST /verify
 * Body: multipart/form-data with 'skill' file (tarball or directory as zip)
 * OR JSON with { skillPath: "/path/to/skill" }
 */
app.post('/verify', checkAuth, upload.single('skill'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No skill file provided. Upload a tarball as multipart "skill" field.' });
    }

    // Enforce job limits
    const activeJobs = Array.from(jobs.values()).filter(j => j.status === 'pending' || j.status === 'running').length;
    if (activeJobs >= MAX_CONCURRENT_JOBS) {
      fs.unlinkSync(req.file.path);
      return res.status(429).json({ error: 'Too many active jobs. Try again later.' });
    }
    if (jobs.size >= MAX_TOTAL_JOBS) {
      fs.unlinkSync(req.file.path);
      return res.status(429).json({ error: 'Job queue full. Try again later.' });
    }

    const skillPath = req.file.path;

    // Create job
    const jobId = crypto.randomBytes(16).toString('hex');
    const job = {
      id: jobId,
      skillPath,
      status: 'pending',
      createdAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
      result: null,
      error: null
    };

    jobs.set(jobId, job);

    // Start verification asynchronously
    runVerification(jobId, skillPath);

    res.status(202).json({
      jobId,
      status: 'pending',
      statusUrl: `/verify/${jobId}`,
      message: 'Verification job created'
    });

  } catch (error) {
    console.error('Error creating verification job:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

/**
 * Get verification status
 * GET /verify/:jobId
 */
app.get('/verify/:jobId', checkAuth, (req, res) => {
  const job = jobs.get(req.params.jobId);
  
  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }

  const response = {
    jobId: job.id,
    status: job.status,
    createdAt: job.createdAt,
    startedAt: job.startedAt,
    completedAt: job.completedAt
  };

  if (job.status === 'completed') {
    response.result = job.result;
  } else if (job.status === 'failed') {
    response.error = job.error;
  }

  res.json(response);
});

/**
 * List all jobs
 * GET /jobs
 */
app.get('/jobs', checkAuth, (req, res) => {
  const status = req.query.status;
  const limit = parseInt(req.query.limit) || 50;
  
  let jobList = Array.from(jobs.values());
  
  if (status) {
    jobList = jobList.filter(j => j.status === status);
  }
  
  jobList = jobList
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    .slice(0, limit)
    .map(j => ({
      id: j.id,
      status: j.status,
      createdAt: j.createdAt,
      completedAt: j.completedAt,
      skillId: j.result?.skillId || null
    }));

  res.json({
    jobs: jobList,
    total: jobs.size
  });
});

/**
 * Delete a job
 * DELETE /verify/:jobId
 */
app.delete('/verify/:jobId', checkAuth, (req, res) => {
  const job = jobs.get(req.params.jobId);

  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }

  // Reject deletion of active jobs to prevent concurrency limit bypass
  if (job.status === 'pending' || job.status === 'running') {
    return res.status(409).json({ error: 'Cannot delete active job. Wait for completion or failure.' });
  }

  // Clean up uploaded file if exists
  if (job.skillPath && job.skillPath.startsWith(uploadDir)) {
    try {
      fs.unlinkSync(job.skillPath);
    } catch (e) {
      // Ignore cleanup errors
    }
  }

  // Clean up result file on disk
  const resultPath = path.join(resultsDir, `${req.params.jobId}.json`);
  if (fs.existsSync(resultPath)) {
    try { fs.unlinkSync(resultPath); } catch {}
  }

  jobs.delete(req.params.jobId);

  res.json({ message: 'Job deleted' });
});

/**
 * Get verification result attestation
 * GET /verify/:jobId/attestation
 */
app.get('/verify/:jobId/attestation', checkAuth, (req, res) => {
  const job = jobs.get(req.params.jobId);
  
  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }

  if (job.status !== 'completed') {
    return res.status(400).json({ error: 'Job not completed' });
  }

  res.json({
    jobId: job.id,
    skillId: job.result.skillId,
    timestamp: job.result.timestamp,
    passed: job.result.result.passed,
    attestation: job.result.attestation
  });
});

/**
 * Run verification job
 */
async function runVerification(jobId, skillPath) {
  const job = jobs.get(jobId);

  try {
    job.status = 'running';
    job.startedAt = new Date().toISOString();

    const verifier = new SkillVerifier();
    const result = await verifier.verify(skillPath);

    job.status = 'completed';
    job.completedAt = new Date().toISOString();
    job.result = result;

    // Save result to file
    const resultPath = path.join(resultsDir, `${jobId}.json`);
    fs.writeFileSync(resultPath, JSON.stringify(result, null, 2), { mode: 0o600 });

    console.log(`✅ Job ${jobId} completed: ${result.skillId} (${result.result.passed ? 'PASSED' : 'FAILED'})`);

  } catch (error) {
    job.status = 'failed';
    job.completedAt = new Date().toISOString();
    job.error = error.message;

    console.error(`❌ Job ${jobId} failed:`, error.message);
  } finally {
    // Always clean up uploaded file to prevent disk exhaustion
    if (skillPath && skillPath.startsWith(uploadDir) && fs.existsSync(skillPath)) {
      try { fs.unlinkSync(skillPath); } catch {}
    }
  }
}

// Start server
app.listen(PORT, () => {
  console.log(`🚀 Skill Verifier API running on port ${PORT}`);
  console.log(`   Health: http://localhost:${PORT}/health`);
  console.log(`   Docs: http://localhost:${PORT}/docs`);
});

/**
 * API Documentation endpoint
 */
app.get('/docs', (req, res) => {
  res.type('text/html').send(`
<!DOCTYPE html>
<html>
<head>
  <title>Skill Verifier API</title>
  <style>
    body { font-family: monospace; max-width: 800px; margin: 50px auto; padding: 20px; }
    h1 { color: #333; }
    h2 { color: #666; margin-top: 30px; }
    code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
    pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }
    .endpoint { background: #e8f4f8; padding: 10px; margin: 10px 0; border-left: 3px solid #0066cc; }
  </style>
</head>
<body>
  <h1>🔐 Skill Verifier API</h1>
  <p>Verify agent skills in isolated Docker containers with cryptographic attestations.</p>
  
  <h2>Endpoints</h2>
  
  <div class="endpoint">
    <strong>POST /verify</strong><br>
    Submit a skill for verification<br>
    <pre>curl -X POST http://localhost:${PORT}/verify \\
  -F "skill=@skill.tar.gz"

# Or with local path:
curl -X POST http://localhost:${PORT}/verify \\
  -H "Content-Type: application/json" \\
  -d '{"skillPath": "/path/to/skill"}'</pre>
  </div>

  <div class="endpoint">
    <strong>GET /verify/:jobId</strong><br>
    Get verification status and results<br>
    <pre>curl http://localhost:${PORT}/verify/{jobId}</pre>
  </div>

  <div class="endpoint">
    <strong>GET /verify/:jobId/attestation</strong><br>
    Get attestation only<br>
    <pre>curl http://localhost:${PORT}/verify/{jobId}/attestation</pre>
  </div>

  <div class="endpoint">
    <strong>GET /jobs</strong><br>
    List all verification jobs<br>
    <pre>curl http://localhost:${PORT}/jobs?status=completed&limit=10</pre>
  </div>

  <div class="endpoint">
    <strong>DELETE /verify/:jobId</strong><br>
    Delete a job<br>
    <pre>curl -X DELETE http://localhost:${PORT}/verify/{jobId}</pre>
  </div>

  <div class="endpoint">
    <strong>GET /health</strong><br>
    Server health check<br>
    <pre>curl http://localhost:${PORT}/health</pre>
  </div>

  <h2>Skill Manifest Format</h2>
  <p>Skills must include a <code>SKILL.md</code> with frontmatter:</p>
  <pre>---
name: my-skill
version: 1.0.0
description: Does something cool
runtime: node:20-alpine
test_command: ["npm", "test"]
---

# My Skill

Skill documentation here...</pre>

  <h2>Response Format</h2>
  <pre>{
  "skillId": "my-skill@1.0.0",
  "timestamp": "2026-01-30T18:00:00.000Z",
  "duration": 1234,
  "result": {
    "passed": true,
    "exitCode": 0,
    "stdout": "...",
    "stderr": "",
    "duration": 500
  },
  "attestation": {
    "quote": "0x...",
    "resultHash": "abc123...",
    "verifier": "skill-verifier/v0.1"
  }
}</pre>
</body>
</html>
  `);
});

module.exports = app;
