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
