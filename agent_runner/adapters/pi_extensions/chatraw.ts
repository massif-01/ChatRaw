import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const question = Type.Object({
  text: Type.String({ minLength: 1, maxLength: 4000 }),
  options: Type.Optional(Type.Array(Type.String({ minLength: 1, maxLength: 300 }), { minItems: 1, maxItems: 12 })),
  multi: Type.Optional(Type.Boolean()),
  allowCustom: Type.Optional(Type.Boolean()),
});

export default function chatraw(pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    const tool = event.toolName;
    if (tool !== "bash" && tool !== "write" && tool !== "edit") return;

    const deny = { block: true, reason: "The user did not approve the Pi tool call." };
    if (ctx.mode !== "rpc" || ctx.signal?.aborted) return deny;
    try {
      const argument = tool === "bash" ? event.input.command : event.input.path;
      if (typeof argument !== "string" || !argument.trim()) return deny;
      if (tool !== "bash" && argument.length > 4000) return deny;
      const operation = tool === "bash" ? { tool, command: argument } : { tool, paths: [argument] };
      const preview = JSON.stringify(operation);
      if (preview.length > 8000) {
        return { block: true, reason: "Pi tool call is too long to review in ChatRaw." };
      }
      const allowed = await ctx.ui.confirm("ChatRaw:tool-approval", preview, { signal: ctx.signal });
      if (allowed !== true || ctx.signal?.aborted) return deny;
    } catch {
      return deny;
    }
  });

  pi.registerTool({
    name: "ask_user",
    label: "Ask user",
    description: "Ask the user for a decision or missing information. Group related questions in one request.",
    parameters: Type.Object({
      title: Type.String({ minLength: 1, maxLength: 300 }),
      questions: Type.Array(question, { minItems: 1, maxItems: 8 }),
    }),
    async execute(_id, params, signal, _onUpdate, ctx) {
      if (ctx.mode !== "rpc") {
        return { content: [{ type: "text", text: "This ask_user tool requires ChatRaw RPC." }] };
      }
      const questions = params.questions.map((item, index) => {
        const options = (item.options ?? []).map((label, i) => ({ id: String(i + 1), label }));
        return {
          id: String(index + 1),
          text: item.text,
          type: options.length ? (item.multi ? "multi" : "single") : "text",
          options,
          allow_custom: options.length === 0 || item.allowCustom === true,
          required: true,
        };
      });
      const title = "ChatRaw:questions:" + JSON.stringify({ title: params.title, questions });
      const value = await ctx.ui.input(title, undefined, { signal });
      if (value === undefined || signal?.aborted) {
        return { content: [{ type: "text", text: "The user dismissed the question." }] };
      }
      const answers = JSON.parse(value).map((answer: { question_id: string; option_ids: string[]; text?: string }) => {
        const item = questions[Number(answer.question_id) - 1];
        return {
          question: item.text,
          selected: answer.option_ids.map((id) => item.options[Number(id) - 1].label),
          text: answer.text,
        };
      });
      return { content: [{ type: "text", text: JSON.stringify(answers) }] };
    },
  });

  pi.registerCommand("chatraw-bridge-v1", {
    description: "Check that the ChatRaw RPC extension is loaded.",
    handler: async () => {},
  });
}
