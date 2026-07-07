"use client";

import { ArrowUpRight, CreditCard, ShieldCheck, Sparkles, WalletCards } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { useI18n } from "../../lib/i18n";

export function AuthScreen({ onLogin }: { onLogin: (token: string) => void }) {
  const { t } = useI18n();
  const [mode, setMode] = useState<"login" | "register" | "forgot" | "reset">("login");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("reset_token");
    if (token) {
      setResetToken(token);
      setMode("reset");
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      if (mode === "forgot") {
        const result = await apiFetch<{ message: string }>("/auth/forgot-password", null, {
          method: "POST",
          body: JSON.stringify({ email: String(form.get("email")) })
        });
        setNotice(result.message);
        return;
      }
      if (mode === "reset") {
        const result = await apiFetch<{ message: string }>("/auth/reset-password", null, {
          method: "POST",
          body: JSON.stringify({ token: resetToken, password })
        });
        window.history.replaceState({}, "", window.location.pathname);
        setNotice(result.message);
        setPassword("");
        setMode("login");
        return;
      }
      const body = {
        email: String(form.get("email")),
        password,
        full_name: String(form.get("full_name") || "")
      };
      const result = await apiFetch<{ access_token: string }>(mode === "login" ? "/auth/login" : "/auth/register", null, {
        method: "POST",
        body: JSON.stringify(body)
      });
      onLogin(result.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  function suggestPassword() {
    const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@$%*";
    const values = new Uint32Array(16);
    crypto.getRandomValues(values);
    const suggested = Array.from(values, (value) => alphabet[value % alphabet.length]).join("");
    setPassword(suggested);
    setNotice("Strong password suggested. Save it somewhere safe.");
    setError("");
  }

  function changeMode(nextMode: "login" | "register" | "forgot") {
    setMode(nextMode);
    setError("");
    setNotice("");
    setPassword("");
  }

  return (
    <main className="auth-page">
      <section className="auth-showcase">
        <div className="brand auth-logo">
          <span className="brand-mark"><Sparkles size={24} /></span>
          <span>Finlio</span>
        </div>
        <div className="auth-pitch">
          <h1>Your money, finally in one place.</h1>
          <p>Track accounts, cards, transactions, investments and insurance with clear manual money tracking.</p>
          <div className="feature-grid">
            <span><WalletCards size={20} />Accounts</span>
            <span><CreditCard size={20} />Cards</span>
            <span><ArrowUpRight size={20} />Investments</span>
            <span><ShieldCheck size={20} />Insurance</span>
          </div>
        </div>
        <small>Built for people who care about their financial future.</small>
      </section>
      <section className="auth-form-side">
        <div className="auth-panel">
          <h2>{mode === "login" ? t("Welcome back") : mode === "register" ? t("Create your account") : mode === "forgot" ? t("Forgot password?") : "Choose a new password"}</h2>
          <p>{mode === "login" ? "Sign in to your Finlio dashboard" : mode === "register" ? "A few details and you're ready to go" : mode === "forgot" ? "We'll email you a secure reset link" : "Make it strong and easy for you to store"}</p>
          <form onSubmit={submit} className="form">
            {mode === "register" && <label className="field"><span>{t("Full name")}</span><input name="full_name" placeholder="Your name" required /></label>}
            {mode !== "reset" && <label className="field"><span>{t("Email")}</span><input name="email" type="email" placeholder="you@example.com" required /></label>}
            {mode !== "forgot" && (
              <label className="field">
                <span>{mode === "reset" ? "New password" : t("Password")}</span>
                <span className="password-input">
                  <input name="password" type={mode === "login" ? "password" : "text"} placeholder="At least 8 characters" minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} required />
                  {(mode === "register" || mode === "reset") && <button type="button" className="suggest-password" onClick={suggestPassword} title="Suggest a strong password" aria-label="Suggest a strong password"><Sparkles size={19} /></button>}
                </span>
              </label>
            )}
            {mode === "login" && <button className="forgot-link" type="button" onClick={() => changeMode("forgot")}>{t("Forgot password?")}</button>}
            {error && <p className="error">{error}</p>}
            {notice && <p className="auth-notice">{notice}</p>}
            <button className="auth-submit wide" type="submit" disabled={busy}>
              {mode === "login" ? t("Sign in") : mode === "register" ? t("Create account") : mode === "forgot" ? "Send reset link" : "Update password"}
            </button>
          </form>
          {mode === "login" || mode === "register" ? (
            <p className="auth-switch">
              {mode === "login" ? t("Don't have an account?") : "Already have an account?"}
              <button type="button" onClick={() => changeMode(mode === "login" ? "register" : "login")}>
                {mode === "login" ? t("Sign up") : t("Sign in")}
              </button>
            </p>
          ) : (
            <button className="back-to-login" type="button" onClick={() => changeMode("login")}>Back to sign in</button>
          )}
        </div>
      </section>
    </main>
  );
}
