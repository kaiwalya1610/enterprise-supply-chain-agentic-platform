import { Shield, Route, Zap, AlertTriangle, Cpu } from "lucide-react";
import { clsx } from "clsx";
import type { GuardrailInfo } from "@/lib/api";

interface MessageMetadataProps {
  route?: string;
  confidence?: string;
  warnings?: string[];
  guardrail?: GuardrailInfo;
  model?: string;
}

export function MessageMetadata({
  route,
  confidence,
  warnings,
  guardrail,
  model,
}: MessageMetadataProps) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-3 text-[10px]">
      {route && (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-surface-900 text-surface-500 border border-surface-800 font-mono">
          <Route size={9} />
          {route}
        </span>
      )}
      {confidence && (
        <span
          className={clsx(
            "inline-flex items-center gap-1 px-1.5 py-0.5 rounded border font-mono",
            confidence === "high"
              ? "bg-accent-900/20 text-accent-500 border-accent-800/40"
              : confidence === "medium"
                ? "bg-warn-500/10 text-warn-400 border-warn-500/20"
                : "bg-surface-900 text-surface-500 border-surface-800",
          )}
        >
          <Zap size={9} />
          {confidence}
        </span>
      )}
      {guardrail && (
        <span
          className={clsx(
            "inline-flex items-center gap-1 px-1.5 py-0.5 rounded border font-mono",
            guardrail.hallucination_detected
              ? "bg-red-950/40 text-red-400 border-red-900/40"
              : "bg-accent-900/20 text-accent-500 border-accent-800/40",
          )}
        >
          <Shield size={9} />
          {guardrail.hallucination_detected ? "flagged" : "verified"}
        </span>
      )}
      {model && (
        <span className="inline-flex items-center gap-1 text-surface-600 font-mono">
          <Cpu size={8} />
          {model}
        </span>
      )}
      {warnings && warnings.length > 0 && (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-warn-500/10 text-warn-400 border border-warn-500/20 font-mono">
          <AlertTriangle size={9} />
          {warnings.length} warning{warnings.length > 1 ? "s" : ""}
        </span>
      )}
    </div>
  );
}
