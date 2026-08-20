import { FileStack, LogOut } from "lucide-react";
import { useAuth } from "./context/AuthContext";
import Login from "./components/Login";
import UploadPanel from "./components/UploadPanel";
import ChatPanel from "./components/ChatPanel";

export default function App() {
  const { user, loading, logout } = useAuth();

  if (loading) return null;
  if (!user) return <Login />;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <FileStack size={20} />
          Documents
        </div>
        <div className="sidebar-section">
          <UploadPanel />
        </div>
        <div className="sidebar-footer">
          <span className="user-email">{user.email}</span>
          <button onClick={logout} title="Log out">
            <LogOut size={14} />
          </button>
        </div>
      </aside>
      <main className="workspace">
        <div className="workspace-header">Ask about your documents</div>
        <ChatPanel />
      </main>
    </div>
  );
}
