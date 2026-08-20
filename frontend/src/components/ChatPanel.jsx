import { useState } from "react";
import { Send, FileText } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { queryDocumentsStream } from "../api/client";

const CONFIDENCE_LEVELS = { high: 3, medium: 2, low: 1 };

function ConfidenceMeter({ level }) {
  const filled = CONFIDENCE_LEVELS[level] || 0;
  return (
    <div className="confidence-row">
      <div className="confidence-meter">
        {[0, 1, 2].map((i) => (
          <span key={i} className={i < filled ? `filled ${level}` : ""} />
        ))}
      </div>
      <span className="confidence-label">{level} confidence</span>
    </div>
  );
}

export default function ChatPanel() {
  const { getToken } = useAuth();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;

    const userText = question;
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setQuestion("");
    setLoading(true);

    const assistantIndex = messages.length + 1;
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: "", confidence: null, sources: [], streaming: true },
    ]);

    const updateAssistant = (patch) => {
      setMessages((prev) => {
        const next = [...prev];
        next[assistantIndex] = { ...next[assistantIndex], ...patch };
        return next;
      });
    };

    try {
      const token = await getToken();
      await queryDocumentsStream(userText, token, {
        onMeta: ({ confidence, sources }) => updateAssistant({ confidence, sources }),
        onToken: (delta) => {
          setMessages((prev) => {
            const next = [...prev];
            next[assistantIndex] = {
              ...next[assistantIndex],
              text: next[assistantIndex].text + delta,
            };
            return next;
          });
        },
        onError: (message) => updateAssistant({ text: `Error: ${message}`, streaming: false }),
        onDone: () => updateAssistant({ streaming: false }),
      });
    } catch (err) {
      updateAssistant({ text: `Error: ${err.message}`, confidence: "low", streaming: false });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-panel">
      {messages.length === 0 ? (
        <div className="empty-state">Ask a question about a document you've uploaded.</div>
      ) : (
        <div className="messages">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              <p>
                {m.text}
                {m.streaming && <span className="cursor">▋</span>}
              </p>
              {m.role === "assistant" && m.confidence && (
                <>
                  <ConfidenceMeter level={m.confidence} />
                  {m.sources?.length > 0 && (
                    <ul className="sources">
                      {m.sources.map((s, j) => (
                        <li key={j}>
                          <FileText size={12} />
                          <span>
                            <span className="source-name">
                              {s.filename}
                              {s.page ? `:${s.page}` : ""}
                            </span>
                            {" — "}
                            {s.excerpt}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
      <form onSubmit={handleAsk} className="ask-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question…"
        />
        <button type="submit" className="pixel-btn" disabled={loading}>
          <Send size={14} />
          Ask
        </button>
      </form>
    </div>
  );
}
