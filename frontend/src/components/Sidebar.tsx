import { useState, useEffect } from "react";
import {
  MessageSquare,
  Plus,
  Trash2,
  Container,
  PanelLeftClose,
  PanelLeft,
} from "lucide-react";
import { clsx } from "clsx";
import { fetchSessions, deleteSession, type SessionInfo } from "@/lib/api";

interface SidebarProps {
  currentSessionId: string | null;
  onSelectSession: (session: SessionInfo) => void;
  onNewChat: () => void;
  refreshTrigger: number;
}

export function Sidebar({
  currentSessionId,
  onSelectSession,
  onNewChat,
  refreshTrigger,
}: SidebarProps) {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    fetchSessions().then(setSessions);
  }, [refreshTrigger]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    await deleteSession(sessionId);
    setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
    if (currentSessionId === sessionId) {
      onNewChat();
    }
  };

  const getSessionTitle = (session: SessionInfo) => {
    const firstUserMsg = session.messages.find((m) => m.role === "user");
    if (firstUserMsg) {
      return firstUserMsg.content.slice(0, 45) + (firstUserMsg.content.length > 45 ? "..." : "");
    }
    return "New conversation";
  };

  if (collapsed) {
    return (
      <div className="w-12 h-full bg-surface-950 border-r border-surface-800/60 flex flex-col items-center py-4 gap-3">
        <button
          onClick={() => setCollapsed(false)}
          className="w-8 h-8 rounded-lg hover:bg-surface-800 flex items-center justify-center text-surface-400 hover:text-surface-200 transition-colors"
        >
          <PanelLeft size={16} />
        </button>
        <button
          onClick={onNewChat}
          className="w-8 h-8 rounded-lg hover:bg-surface-800 flex items-center justify-center text-surface-400 hover:text-surface-200 transition-colors"
        >
          <Plus size={15} />
        </button>
      </div>
    );
  }

  return (
    <div className="w-[260px] h-full bg-surface-950 border-r border-surface-800/60 flex flex-col">
      <div className="px-3 pt-4 pb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Container size={16} className="text-surface-400" />
          <span className="font-display font-semibold text-sm text-surface-200 tracking-tight">
            abc.co
          </span>
        </div>
        <button
          onClick={() => setCollapsed(true)}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-surface-500 hover:text-surface-300 hover:bg-surface-800 transition-colors"
        >
          <PanelLeftClose size={15} />
        </button>
      </div>

      <div className="px-3 pb-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-surface-800 hover:bg-surface-900 text-surface-300 hover:text-surface-100 transition-colors text-sm"
        >
          <Plus size={14} />
          <span className="font-body">New thread</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        <p className="text-[10px] font-medium uppercase tracking-wider text-surface-600 px-2 mb-1.5">
          Recent
        </p>
        <div className="space-y-0.5">
          {sessions.length === 0 && (
            <p className="text-xs text-surface-600 px-2 py-6 text-center font-body">
              No conversations yet
            </p>
          )}
          {sessions.map((session) => (
            <button
              key={session.session_id}
              onClick={() => onSelectSession(session)}
              className={clsx(
                "w-full group flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-colors",
                currentSessionId === session.session_id
                  ? "bg-surface-800 text-surface-100"
                  : "text-surface-400 hover:bg-surface-900 hover:text-surface-200",
              )}
            >
              <MessageSquare
                size={13}
                className={clsx(
                  "shrink-0",
                  currentSessionId === session.session_id
                    ? "text-surface-300"
                    : "opacity-50",
                )}
              />
              <span className="flex-1 text-xs truncate font-body">
                {getSessionTitle(session)}
              </span>
              <span
                onClick={(e) => handleDelete(e, session.session_id)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-surface-700 hover:text-red-400 transition-all"
              >
                <Trash2 size={11} />
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="px-3 py-3 border-t border-surface-800/60">
        <p className="text-[10px] text-surface-600 text-center font-body">
          Supply Chain Intelligence
        </p>
      </div>
    </div>
  );
}
