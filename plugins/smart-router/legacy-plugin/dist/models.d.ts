export interface ModelConfig {
    provider: "anthropic" | "google" | "synthetic" | "local";
    model: string;
    inputCost: number;
    outputCost: number;
}
export declare const ModelRegistry: Map<string, ModelConfig>;
