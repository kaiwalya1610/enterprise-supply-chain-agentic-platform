import { useState } from "react";
import { FileText, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { clsx } from "clsx";
import type { Citation } from "@/lib/api";

interface CitationPanelProps {
  citations: Citation[];
}

export function CitationPanel({ citations }: CitationPanelProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (!citations.length) return null;

  return (
    <div className="mt-4 border-t border-surface-800/60 pt-4">
      <div className="flex items-center gap-1.5 text-[10px] font-medium text-surface-500 uppercase tracking-wider mb-2.5">
        <FileText size={11} />
        <span>Sources ({citations.length})</span>
      </div>
      <div className="space-y-1.5">
        {citations.map((cite, idx) => (
          <CitationItem
            key={idx}
            citation={cite}
            index={idx}
            isExpanded={expanded === idx}
            onToggle={() => setExpanded(expanded === idx ? null : idx)}
          />
        ))}
      </div>
    </div>
  );
}

function CitationItem({
  citation,
  index,
  isExpanded,
  onToggle,
}: {
  citation: Citation;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const source = citation.source_file || citation.source || "Unknown source";
  const title = citation.section_heading || citation.title || source;
  const section = citation.section_path || citation.section;
  const hasLines = citation.start_line != null && citation.end_line != null;
  const location = hasLines
    ? `Lines ${citation.start_line}-${citation.end_line}`
    : citation.page != null
      ? `Page ${citation.page}`
      : null;
  const relevance = citation.relevance_score;
  const relevanceColor =
    relevance != null && relevance >= 0.8
      ? "bg-accent-900/30 text-accent-400"
      : relevance != null && relevance >= 0.5
        ? "bg-warn-500/10 text-warn-400"
        : "bg-surface-800 text-surface-500";
  const expandedText = citation.chunk_text || section || title;

  return (
    <div
      className={clsx(
        "rounded-lg border transition-colors",
        isExpanded
          ? "border-surface-700 bg-surface-900"
          : "border-surface-800 hover:border-surface-700 hover:bg-surface-900/50",
      )}
    >
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2.5 px-3 py-2 text-left"
      >
        <span className="flex items-center justify-center w-5 h-5 rounded bg-surface-800 text-surface-400 text-[10px] font-mono font-bold shrink-0">
          {index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-body text-surface-200 truncate">
            {title}
          </p>
          {(section || location) && (
            <p className="text-[11px] text-surface-500 truncate mt-0.5 font-body">
              {[section, location].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
        {relevance != null && (
          <span
            className={clsx(
              "px-1.5 py-0.5 rounded text-[10px] font-mono",
              relevanceColor,
            )}
          >
            {Math.round(relevance * 100)}%
          </span>
        )}
        {isExpanded ? (
          <ChevronUp size={14} className="text-surface-600" />
        ) : (
          <ChevronDown size={14} className="text-surface-600" />
        )}
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 animate-fade-in">
          <div className="bg-surface-950 rounded-md p-3 border border-surface-800">
            <p className="text-xs text-surface-300 leading-relaxed font-body whitespace-pre-wrap">
              {expandedText}
            </p>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <span className="text-[10px] text-surface-600 font-mono flex items-center gap-1">
              <ExternalLink size={10} />
              {source}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export function InlineCitation({
  index,
  onClick,
}: {
  index: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center justify-center w-4 h-4 rounded bg-surface-800 text-surface-400 text-[9px] font-mono font-bold hover:bg-surface-700 hover:text-surface-200 transition-colors align-super ml-0.5 cursor-pointer"
      title={`View source ${index + 1}`}
    >
      {index + 1}
    </button>
  );
}
