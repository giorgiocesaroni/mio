export type ToolCallStep = {
  type: "tool_call";
  name: string;
  args: Record<string, unknown>;
};

export type ToolCallStartStep = {
  type: "tool_call_start";
  name: string;
};

export type ContentTokenStep = {
  type: "content_token";
  token: string;
};

export type MessageStep = {
  type: "message";
  text: string;
};

export type UserMessageStep = {
  type: "user_message";
  text: string;
  data?: string;
  mime_type?: string;
};

export type RunAgentStep = ToolCallStep | MessageStep | UserMessageStep | ContentTokenStep | ToolCallStartStep;

export type Model = {
  id: string;
  provider: string;
  name: string;
};

export type ModelsResponse = {
  models: Model[];
  default: string;
};

export type UsageModel = {
  model_id: string;
  invocations: number;
  total_cost: number;
  uncached_input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  cost_per_message: number;
};

export type UsageOverview = {
  total: {
    total_invocations: number;
    total_cost: number;
    prompt_tokens: number;
    completion_tokens: number;
  };
  models: UsageModel[];
};
