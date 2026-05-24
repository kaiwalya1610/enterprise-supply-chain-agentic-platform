import {
  ThreadPrimitive,
  MessagePrimitive,
  ComposerPrimitive,
  useMessage,
  useThread,
} from "@assistant-ui/react";
import { MarkdownTextPrimitive } from "@assistant-ui/react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowUp,
  Sparkles,
  User,
  Loader2,
  Boxes,
  TrendingUp,
  Truck,
  ClipboardList,
} from "lucide-react";
import { clsx } from "clsx";
import { CitationPanel } from "./CitationPanel";
import { MessageMetadata } from "./MessageMetadata";
import { useEnrichedMessages, type EnrichedMessage } from "@/lib/runtime";

export function Thread() {
  return (
    <ThreadPrimitive.Root className="flex flex-col h-full">
      <ThreadPrimitive.Viewport className="flex-1 overflow-y-auto">
        <div className="max-w-[var(--aui-thread-max-width)] mx-auto px-6 py-10">
          <ThreadPrimitive.Empty>
            <EmptyState />
          </ThreadPrimitive.Empty>

          <ThreadPrimitive.Messages
            components={{
              UserMessage,
              AssistantMessage,
            }}
          />
        </div>
      </ThreadPrimitive.Viewport>

      <div className="border-t border-surface-800/60 bg-surface-950">
        <div className="max-w-[var(--aui-thread-max-width)] mx-auto px-6 py-4">
          <Composer />
          <p className="text-[10px] text-surface-600 text-center mt-2.5 font-body">
            Answers are sourced from internal documents. Always verify critical decisions.
          </p>
        </div>
      </div>
    </ThreadPrimitive.Root>
  );
}

const SUGGESTION_ICONS = [Boxes, TrendingUp, ClipboardList, Truck];

const SUGGESTIONS = [
  "What are our reorder point policies?",
  "Show me supplier lead time metrics",
  "Explain our procurement approval flow",
  "What's the ABC classification criteria?",
];

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[480px] animate-fade-in">
      <div className="w-12 h-12 rounded-2xl bg-surface-900 border border-surface-800 flex items-center justify-center mb-6">
        <Sparkles size={22} className="text-surface-300" />
      </div>

      <h2 className="text-xl font-display font-bold text-surface-100 mb-1.5 tracking-tight">
        Supply Chain Assistant
      </h2>
      <p className="text-sm text-surface-500 text-center max-w-md leading-relaxed font-body mb-10">
        Ask about procurement, inventory, suppliers, or operations.
      </p>

      <div className="grid grid-cols-2 gap-2.5 max-w-lg w-full">
        {SUGGESTIONS.map((q, i) => {
          const Icon = SUGGESTION_ICONS[i];
          return (
            <ThreadPrimitive.Suggestion key={q} prompt={q} asChild>
              <button
                className={clsx(
                  "text-left px-4 py-3 rounded-xl border border-surface-800 bg-surface-950",
                  "text-xs text-surface-400 font-body leading-relaxed",
                  "hover:border-surface-700 hover:bg-surface-900 hover:text-surface-200",
                  "transition-all duration-200 group",
                  `animate-stagger-${i + 1}`,
                )}
              >
                <Icon
                  size={14}
                  className="text-surface-600 group-hover:text-surface-300 transition-colors mb-1.5"
                />
                {q}
              </button>
            </ThreadPrimitive.Suggestion>
          );
        })}
      </div>
    </div>
  );
}

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex gap-3 mb-6 animate-slide-up">
      <div className="w-7 h-7 rounded-full bg-surface-800 flex items-center justify-center shrink-0 mt-0.5">
        <User size={13} className="text-surface-400" />
      </div>
      <div className="flex-1 min-w-0 pt-0.5">
        <MessagePrimitive.Content
          components={{
            Text: ({ text }) => (
              <p className="text-sm text-surface-100 whitespace-pre-wrap leading-relaxed font-body">
                {text}
              </p>
            ),
          }}
        />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  const message = useMessage();
  const enrichedMessages = useEnrichedMessages();

  const enriched = enrichedMessages.find(
    (m) => m.id === message.id,
  ) as EnrichedMessage | undefined;

  return (
    <MessagePrimitive.Root className="flex gap-3 mb-6 animate-slide-up">
      <div className="w-7 h-7 rounded-full bg-surface-900 border border-surface-800 flex items-center justify-center shrink-0 mt-0.5">
        <Sparkles size={13} className="text-surface-300" />
      </div>
      <div className="flex-1 min-w-0 pt-0.5">
        <MessagePrimitive.Content
          components={{
            Text: AssistantTextContent,
          }}
        />
        {enriched?.citations && enriched.citations.length > 0 && (
          <CitationPanel citations={enriched.citations} />
        )}
        {enriched && (
          <MessageMetadata
            route={enriched.route}
            confidence={enriched.confidence}
            warnings={enriched.warnings}
            guardrail={enriched.guardrail}
            model={enriched.model}
          />
        )}
        <MessagePrimitive.If last>
          <LoadingIndicator status={enriched?.status} />
        </MessagePrimitive.If>
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantTextContent() {
  return (
    <div className="aui-md text-sm text-surface-200 leading-relaxed font-body">
      <MarkdownTextPrimitive
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children, ...props }) => (
            <div className="aui-table-scroll">
              <table {...props}>{children}</table>
            </div>
          ),
        }}
      />
    </div>
  );
}

function LoadingIndicator({ status }: { status?: string }) {
  const thread = useThread();
  if (!thread.isRunning) return null;
  return (
    <div className="flex items-center gap-2 mt-3 animate-fade-in">
      <Loader2 size={13} className="text-surface-400 animate-spin" />
      <span className="text-xs text-surface-500 font-body">
        {status || "Thinking..."}
      </span>
    </div>
  );
}

function Composer() {
  return (
    <ComposerPrimitive.Root className="relative">
      <ComposerPrimitive.Input
        placeholder="Ask anything..."
        className="w-full bg-surface-900 border border-surface-800 rounded-2xl pl-4 pr-12 py-3.5 text-sm text-surface-100 font-body placeholder:text-surface-600 focus:outline-none focus:border-surface-700 focus:ring-1 focus:ring-surface-700/50 resize-none min-h-[48px] max-h-[160px] transition-colors"
        autoFocus
      />
      <ComposerPrimitive.Send asChild>
        <button className="absolute right-2 bottom-2 w-8 h-8 rounded-xl bg-surface-100 hover:bg-white disabled:bg-surface-800 disabled:text-surface-600 text-surface-950 flex items-center justify-center transition-colors shrink-0">
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </ComposerPrimitive.Send>
    </ComposerPrimitive.Root>
  );
}
