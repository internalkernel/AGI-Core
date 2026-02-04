#!/usr/bin/env node

/**
 * Memory Search with Decay Weighting
 * 
 * Implements ACT-R inspired memory retrieval with:
 * - Recency weighting (older memories fade)
 * - Access frequency boosting (frequently used memories strengthen)
 * - Semantic search across memory files
 */

const fs = require('fs');
const path = require('path');

// Configuration
const HALF_LIFE_DAYS = 30; // ACT-R inspired half-life
const ACCESS_BOOST = 0.2; // How much each access strengthens memory
const MIN_SCORE = 0.1; // Minimum relevance score to include

// Load access log
const ACCESS_LOG_PATH = path.join(__dirname, 'access-log.json');
let accessLog = {};

try {
  if (fs.existsSync(ACCESS_LOG_PATH)) {
    accessLog = JSON.parse(fs.readFileSync(ACCESS_LOG_PATH, 'utf8'));
  }
} catch (err) {
  console.error('Could not load access log:', err.message);
}

/**
 * Calculate decay factor based on age
 * Uses exponential decay: score = base_score * 0.5^(age/half_life)
 */
function calculateDecayFactor(lastAccessed) {
  if (!lastAccessed) return 0.5; // Default for new/untracked files
  
  const now = Date.now();
  const ageMs = now - lastAccessed;
  const ageDays = ageMs / (1000 * 60 * 60 * 24);
  
  // Exponential decay
  return Math.pow(0.5, ageDays / HALF_LIFE_DAYS);
}

/**
 * Update access log when a file is accessed
 */
function updateAccessLog(filePath) {
  accessLog[filePath] = Date.now();
  
  try {
    fs.writeFileSync(ACCESS_LOG_PATH, JSON.stringify(accessLog, null, 2));
  } catch (err) {
    console.error('Could not update access log:', err.message);
  }
}

/**
 * Search memory files with decay weighting
 */
function searchMemory(query, options = {}) {
  const results = [];
  const searchTerms = query.toLowerCase().split(/\s+/);
  
  // Get all memory files
  const memoryDir = path.join(__dirname);
  const files = fs.readdirSync(memoryDir)
    .filter(f => f.endsWith('.md') || f.endsWith('.json'))
    .filter(f => !f.startsWith('.'));
  
  // Search each file
  files.forEach(file => {
    const filePath = path.join(memoryDir, file);
    
    try {
      let content = '';
      let score = 0;
      
      if (file.endsWith('.md')) {
        content = fs.readFileSync(filePath, 'utf8');
        
        // Basic keyword matching
        const contentLower = content.toLowerCase();
        searchTerms.forEach(term => {
          if (contentLower.includes(term)) {
            score += 1;
            // Bonus for title/header matches
            if (contentLower.split('\n')[0].includes(term)) {
              score += 2;
            }
          }
        });
      }
      
      // Apply decay weighting
      const lastAccessed = accessLog[filePath];
      const decayFactor = calculateDecayFactor(lastAccessed);
      const accessBoost = (accessLog[filePath] ? 1 + ACCESS_BOOST : 1);
      
      const finalScore = score * decayFactor * accessBoost;
      
      if (finalScore >= MIN_SCORE) {
        results.push({
          file: file,
          path: filePath,
          score: finalScore,
          decayFactor: decayFactor,
          lastAccessed: lastAccessed,
          excerpt: content.substring(0, 200) + '...'
        });
      }
    } catch (err) {
      console.error(`Error reading ${file}:`, err.message);
    }
  });
  
  // Sort by score (highest first)
  results.sort((a, b) => b.score - a.score);
  
  // Update access log for top results
  results.slice(0, 3).forEach(result => {
    updateAccessLog(result.path);
  });
  
  return results;
}

/**
 * Format search results
 */
function formatResults(results, query) {
  if (results.length === 0) {
    return `No relevant memories found for "${query}"`;
  }
  
  let output = `🔍 Search results for "${query}" (${results.length} matches)\n`;
  output += '='.repeat(50) + '\n\n';
  
  results.forEach((result, index) => {
    const daysSince = result.lastAccessed 
      ? Math.floor((Date.now() - result.lastAccessed) / (1000 * 60 * 60 * 24))
      : 'Never';
    
    output += `${index + 1}. **${result.file}** (Score: ${result.score.toFixed(2)})\n`;
    output += `   Last accessed: ${daysSince} days ago\n`;
    output += `   Decay factor: ${result.decayFactor.toFixed(2)}\n`;
    output += `   ${result.excerpt}\n\n`;
  });
  
  return output;
}

// CLI interface
if (require.main === module) {
  const query = process.argv.slice(2).join(' ');
  
  if (!query) {
    console.log('Usage: node memory-search.js <query>');
    console.log('Example: node memory-search.js "Docker skill verification"');
    process.exit(1);
  }
  
  const results = searchMemory(query);
  console.log(formatResults(results, query));
}

module.exports = { searchMemory, formatResults, calculateDecayFactor };