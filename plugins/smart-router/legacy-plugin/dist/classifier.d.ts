export interface RoutingDecision {
    tier: "SIMPLE" | "MEDIUM" | "COMPLEX" | "REASONING" | "ONDEMAND";
    confidence: number;
    recommendedModel: string;
    costEstimate: number;
    reasoning: string;
    scores?: Record<string, number>;
    fallbackModel?: string;
}
export declare function classify(query: string, verbose?: boolean): RoutingDecision;
export declare function getFallbackModel(tier: RoutingDecision["tier"]): string | undefined;
