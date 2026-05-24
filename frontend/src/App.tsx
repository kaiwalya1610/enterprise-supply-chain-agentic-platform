import { useState, useCallback } from "react";
import { Sidebar } from "./components/Sidebar";
import { Thread } from "./components/Thread";
import { SupplyChainRuntimeProvider } from "./lib/runtime";
import type { SessionInfo } from "./lib/api";

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [threadKey, setThreadKey] = useState(0);

  const handleNewChat = useCallback(() => {
    setSessionId(null);
    setThreadKey((k) => k + 1);
  }, []);

  const handleSelectSession = useCallback((session: SessionInfo) => {
    setSessionId(session.session_id);
    setThreadKey((k) => k + 1);
  }, []);

  const handleSessionCreated = useCallback((id: string) => {
    setSessionId(id);
    setRefreshTrigger((r) => r + 1);
  }, []);

  const handleMessageAdded = useCallback(() => {
    setRefreshTrigger((r) => r + 1);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-surface-950">
      <Sidebar
        currentSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        refreshTrigger={refreshTrigger}
      />
      <main className="flex-1 flex flex-col min-w-0">
        <SupplyChainRuntimeProvider
          key={threadKey}
          sessionId={sessionId}
          onSessionCreated={handleSessionCreated}
          onMessageAdded={handleMessageAdded}
        >
          <Thread />
        </SupplyChainRuntimeProvider>
      </main>
    </div>
  );
}
