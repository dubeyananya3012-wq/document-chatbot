import { useState } from "react";
import { Chrome, AlertTriangle } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login, signup, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState("login"); // login | signup
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await signup(email, password);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-container">
        <p className="brand">Documents</p>
        <h1>{mode === "login" ? "Log in" : "Create an account"}</h1>
        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <p className="error">
              <AlertTriangle size={13} />
              {error}
            </p>
          )}
          <button type="submit" className="pixel-btn">
            {mode === "login" ? "Log in" : "Sign up"}
          </button>
        </form>
        <button className="auth-secondary pixel-btn" onClick={loginWithGoogle}>
          <Chrome size={15} />
          Continue with Google
        </button>
        <button className="auth-switch" onClick={() => setMode(mode === "login" ? "signup" : "login")}>
          {mode === "login" ? "Need an account? Sign up" : "Have an account? Log in"}
        </button>
      </div>
    </div>
  );
}
