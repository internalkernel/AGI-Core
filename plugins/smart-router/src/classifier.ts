// src/classifier.ts
import { ModelRegistry } from "./models.js";

export interface RoutingDecision {
  tier: "SIMPLE" | "MEDIUM" | "COMPLEX" | "REASONING" | "ONDEMAND";
  confidence: number;
  recommendedModel: string;
  costEstimate: number;
  reasoning: string;
  scores?: Record<string, number>;
  fallbackModel?: string;
}

interface ScoringWeights {
  reasoningMarkers: number;
  codePresence: number;
  simpleIndicators: number;
  multiStep: number;
  technicalTerms: number;
  tokenCount: number;
  creativeMarkers: number;
  questionComplexity: number;
  constraintCount: number;
  imperativeVerbs: number;
  outputFormat: number;
  domainSpecificity: number;
  referenceComplexity: number;
  negationComplexity: number;
}

const WEIGHTS: ScoringWeights = {
  reasoningMarkers: 0.18,
  codePresence: 0.15,
  simpleIndicators: 0.12,
  multiStep: 0.12,
  technicalTerms: 0.10,
  tokenCount: 0.08,
  creativeMarkers: 0.05,
  questionComplexity: 0.05,
  constraintCount: 0.04,
  imperativeVerbs: 0.03,
  outputFormat: 0.03,
  domainSpecificity: 0.02,
  referenceComplexity: 0.02,
  negationComplexity: 0.01,
};

const PATTERNS = {
  reasoningMarkers: [
    "prove", "theorem", "proof", "demonstrate", "derive",
    "step by step", "step-by-step", "reasoning", "logic",
    "证明", "定理", "証明", // Chinese, Japanese
  ],
  codePresence: [
    "function", "class", "import", "async", "await",
    "def ", "const ", "let ", "var ", "```",
    "algorithm", "implement", "code", "script",
  ],
  simpleIndicators: [
    "what is", "define", "translate", "hello", "hi",
    "how are", "thanks", "thank you", "什么是", "你好",
  ],
  multiStep: [
    "first", "then", "next", "finally", "after that",
    "step 1", "step 2", "phase", "stage",
  ],
  technicalTerms: [
    "kubernetes", "docker", "api", "database", "algorithm",
    "neural", "machine learning", "distributed", "architecture",
  ],
  creativeMarkers: [
    "story", "poem", "creative", "imagine", "brainstorm",
    "fiction", "narrative", "novel",
  ],
  imperativeVerbs: [
    "build", "create", "make", "generate", "design",
    "implement", "develop", "construct",
  ],
  outputFormat: [
    "json", "yaml", "xml", "csv", "markdown",
    "table", "list", "schema", "format",
  ],
  domainSpecificity: [
    "quantum", "genomics", "fpga", "blockchain",
    "cryptocurrency", "biotech", "aerospace",
  ],
  negationComplexity: [
    "don't", "avoid", "without", "except", "excluding",
    "not", "never", "neither",
  ],
};

function sigmoid(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

function estimateTokens(text: string): number {
  return Math.floor(text.length / 4);
}

function scoreDimension(text: string, dimension: keyof ScoringWeights): number {
  const textLower = text.toLowerCase();

  // Special handling for non-pattern dimensions
  if (dimension === "tokenCount") {
    const tokens = estimateTokens(text);
    if (tokens < 50) return 0.0;
    if (tokens < 200) return 0.3;
    if (tokens < 500) return 0.6;
    return 1.0;
  }

  if (dimension === "questionComplexity") {
    const questionMarks = (text.match(/\?/g) || []).length;
    if (questionMarks === 0) return 0.0;
    if (questionMarks === 1) return 0.3;
    return 0.8;
  }

  if (dimension === "constraintCount") {
    const constraints = ["at most", "at least", "exactly", "maximum", "minimum", "O(n)", "O(log n)"];
    const count = constraints.filter(c => textLower.includes(c)).length;
    return Math.min(count * 0.3, 1.0);
  }

  if (dimension === "referenceComplexity") {
    const refs = ["above", "below", "the previous", "the docs", "the api", "as mentioned"];
    const count = refs.filter(r => textLower.includes(r)).length;
    return Math.min(count * 0.4, 1.0);
  }

  // Pattern-based dimensions
  const patternKey = dimension.charAt(0).toLowerCase() + dimension.slice(1);
  const patterns = PATTERNS[patternKey as keyof typeof PATTERNS];
  
  if (patterns) {
    const matches = patterns.filter(p => textLower.includes(p)).length;
    
    // Simple indicators are inverted (more matches = simpler)
    if (dimension === "simpleIndicators") {
      return Math.max(0, 1.0 - matches * 0.5);
    }
    
    return Math.min(matches * 0.3, 1.0);
  }

  return 0.0;
}

export function classify(query: string, verbose = false): RoutingDecision {
  // Calculate scores for each dimension
  const scores: Record<string, number> = {};
  let totalScore = 0;

  for (const [dimension, weight] of Object.entries(WEIGHTS)) {
    const rawScore = scoreDimension(query, dimension as keyof ScoringWeights);
    const weightedScore = rawScore * weight;
    scores[dimension] = weightedScore;
    totalScore += weightedScore;
  }

  // Apply sigmoid for confidence calibration
  let confidence = sigmoid((totalScore - 0.5) * 10);

  // Special rule: 2+ reasoning markers → REASONING tier
  const reasoningCount = PATTERNS.reasoningMarkers.filter(p =>
    query.toLowerCase().includes(p)
  ).length;

  let tier: RoutingDecision["tier"];
  let reasoning: string;

  if (reasoningCount >= 2) {
    tier = "REASONING";
    confidence = 0.97;
    reasoning = `Detected ${reasoningCount} reasoning markers → REASONING tier`;
  } else {
    // Determine tier based on confidence
    if (confidence < 0.65) {
      tier = "SIMPLE";
    } else if (confidence < 0.80) {
      tier = "MEDIUM";
    } else if (confidence < 0.90) {
      tier = "COMPLEX";
    } else {
      tier = "REASONING";
    }

    // Generate reasoning from top dimensions
    const topDimensions = Object.entries(scores)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([dim]) => dim);
    
    reasoning = `Top factors: ${topDimensions.join(", ")}`;
  }

  // Get model for tier
  const recommendedModel = getModelForTier(tier);
  const modelConfig = ModelRegistry.get(recommendedModel);
  
  if (!modelConfig) {
    throw new Error(`Model not found: ${recommendedModel}`);
  }

  // Estimate cost (assume 1K tokens in, 1K tokens out)
  const costEstimate = (modelConfig.inputCost + modelConfig.outputCost) / 1000;

  // Get fallback model if available
  const fallbackModel = getFallbackModel(tier);

  return {
    tier,
    confidence,
    recommendedModel,
    costEstimate,
    reasoning,
    scores: verbose ? scores : undefined,
    fallbackModel,
  };
}

function getModelForTier(tier: RoutingDecision["tier"]): string {
  const tierModels = {
    SIMPLE: "local/mistral-7b",
    MEDIUM: "synthetic/kimi-2.5",
    COMPLEX: "anthropic/claude-sonnet-4.5",
    REASONING: "synthetic/kimi-k2-thinking",
    ONDEMAND: "anthropic/claude-opus-4.6",
  };

  return tierModels[tier];
}

export function getFallbackModel(tier: RoutingDecision["tier"]): string | undefined {
  // Only REASONING tier has a fallback to ONDEMAND
  if (tier === "REASONING") {
    return "anthropic/claude-opus-4.6";
  }
  return undefined;
}
