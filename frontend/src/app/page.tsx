"use client";

import {
  ArrowLeft,
  ArrowDownUp,
  ArrowDownRight,
  ArrowUpRight,
  Banknote,
  Building2,
  CalendarDays,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CreditCard,
  FileUp,
  Home,
  Landmark,
  LineChart,
  LogOut,
  Menu,
  PiggyBank,
  Pencil,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  WalletCards
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { apiFetch, formatMoney } from "../lib/api";
import { I18nContext, Language, normalizeLanguage, translate, useI18n } from "../lib/i18n";

type View =
  | "dashboard"
  | "banks"
  | "accounts"
  | "cards"
  | "transactions"
  | "import"
  | "investments"
  | "insurance"
  | "reports"
  | "settings"
  | "bank-detail";

const sections = [
  { id: "dashboard", label: "Overview", icon: Home },
  { id: "accounts", label: "Accounts", icon: Building2 },
  { id: "cards", label: "Cards", icon: CreditCard },
  { id: "transactions", label: "Transactions", icon: ArrowDownUp },
  { id: "investments", label: "Investments", icon: LineChart },
  { id: "insurance", label: "Insurance", icon: ShieldCheck }
] as const;

const mobileSections = sections.filter((item) => ["dashboard", "transactions", "accounts", "cards", "investments"].includes(item.id));

type Dashboard = {
  net_worth: number;
  total_liquidity: number;
  total_investments: number;
  insurance_value: number;
  total_debt: number;
  monthly_income: number;
  monthly_expenses: number;
  savings_rate: number;
  recent_transactions: Array<{ id: number; date: string; description: string; amount: number; currency: string }>;
  account_balances: Array<{ id: number; bank_id: number; name: string; type: string; current_balance: number; currency: string }>;
  card_balances: Array<{ id: number; bank_id: number; account_id: number; name: string; type: string; current_balance: number; last4: string }>;
};

type UserSettings = {
  theme: "system" | "light" | "dark";
  favorite_language: string;
  default_currency: string;
  date_format: string;
  number_format: string;
  profile_photo_url?: string | null;
  notifications_enabled: boolean;
};

type BankItem = { id: number; name: string; country?: string };
type AccountItem = { id: number; bank_id: number; name: string; type: string; currency: string; opening_balance?: number; current_balance: number };
type CardItem = { id: number; bank_id: number; account_id: number; name: string; type: string; last4: string; current_balance: number; credit_limit?: number | null; expiry_month?: number | null; expiry_year?: number | null };
type CategoryItem = { id: number; user_id?: number | null; name: string; type: "income" | "expense" | "investment"; color?: string | null; is_system: boolean };
type TransactionItem = { id: number; bank_id: number; account_id: number; card_id?: number; category_id?: number; type: string; source?: string; date: string; description: string; amount: number; currency: string };
type Profile = { id: number; email: string; full_name: string };

function applyTheme(theme: UserSettings["theme"]) {
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = theme;
  }
}

type SelectOption = { value: string; label: string };

function ModernSelect({
  name,
  options,
  value,
  defaultValue = "",
  onValueChange,
  placeholder = "Choose an option",
  disabled = false,
  required = false
}: {
  name?: string;
  options: SelectOption[];
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
}) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const currentValue = value ?? internalValue;
  const selected = options.find((option) => option.value === currentValue);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const form = rootRef.current?.closest("form");
    const reset = () => {
      if (value === undefined) setInternalValue(defaultValue);
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    form?.addEventListener("reset", reset);
    return () => {
      document.removeEventListener("mousedown", close);
      form?.removeEventListener("reset", reset);
    };
  }, [defaultValue, value]);

  function choose(nextValue: string) {
    if (value === undefined) setInternalValue(nextValue);
    onValueChange?.(nextValue);
    setOpen(false);
  }

  return (
    <div className={`modern-select ${open ? "open" : ""} ${disabled ? "disabled" : ""}`} ref={rootRef}>
      {name && <select className="modern-native-proxy" name={name} value={currentValue} onChange={() => undefined} required={required} disabled={disabled} tabIndex={-1} aria-hidden="true">{!options.some((option) => option.value === "") && <option value="" />}{options.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}</select>}
      <button type="button" className="modern-control" onClick={() => !disabled && setOpen((current) => !current)} disabled={disabled} aria-expanded={open} aria-haspopup="listbox" aria-required={required}>
        <span className={selected ? "" : "placeholder"}>{selected?.label || placeholder}</span>
        <ChevronDown size={19} />
      </button>
      {open && (
        <div className="modern-options" role="listbox">
          {options.map((option) => (
            <button type="button" role="option" aria-selected={option.value === currentValue} className={option.value === currentValue ? "selected" : ""} key={option.value} onClick={() => choose(option.value)}>
              <span>{option.label}</span>
              {option.value === currentValue && <Check size={19} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ModernDateInput({
  name,
  value,
  defaultValue = "",
  onValueChange,
  required = false,
  placeholder = "Choose a date"
}: {
  name: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  required?: boolean;
  placeholder?: string;
}) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const currentValue = value ?? internalValue;
  const selectedDate = currentValue ? parseDateValue(currentValue) : null;
  const [visibleMonth, setVisibleMonth] = useState(() => selectedDate || new Date());

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const form = rootRef.current?.closest("form");
    const reset = () => {
      if (value === undefined) setInternalValue(defaultValue);
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    form?.addEventListener("reset", reset);
    return () => {
      document.removeEventListener("mousedown", close);
      form?.removeEventListener("reset", reset);
    };
  }, [defaultValue, value]);

  function selectDate(date: Date) {
    const nextValue = formatDateValue(date);
    if (value === undefined) setInternalValue(nextValue);
    onValueChange?.(nextValue);
    setVisibleMonth(date);
    setOpen(false);
  }

  const year = visibleMonth.getFullYear();
  const month = visibleMonth.getMonth();
  const firstCell = new Date(year, month, 1 - new Date(year, month, 1).getDay());
  const days = Array.from({ length: 42 }, (_, index) => new Date(firstCell.getFullYear(), firstCell.getMonth(), firstCell.getDate() + index));

  return (
    <div className={`modern-date ${open ? "open" : ""}`} ref={rootRef}>
      <input className="modern-native-proxy" name={name} value={currentValue} onChange={() => undefined} required={required} tabIndex={-1} aria-hidden="true" />
      <button type="button" className="modern-control" onClick={() => { setVisibleMonth(selectedDate || new Date()); setOpen((current) => !current); }} aria-expanded={open} aria-haspopup="dialog" aria-required={required}>
        <span className={selectedDate ? "" : "placeholder"}>{selectedDate ? selectedDate.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" }) : placeholder}</span>
        <CalendarDays size={19} />
      </button>
      {open && (
        <div className="calendar-popover" role="dialog" aria-label="Choose a date">
          <div className="calendar-heading">
            <strong>{visibleMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}</strong>
            <span>
              <button type="button" onClick={() => setVisibleMonth(new Date(year, month - 1, 1))} aria-label="Previous month"><ChevronLeft size={21} /></button>
              <button type="button" onClick={() => setVisibleMonth(new Date(year, month + 1, 1))} aria-label="Next month"><ChevronRight size={21} /></button>
            </span>
          </div>
          <div className="calendar-weekdays">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-days">
            {days.map((day) => {
              const dayValue = formatDateValue(day);
              const isSelected = dayValue === currentValue;
              const isToday = dayValue === formatDateValue(new Date());
              return <button type="button" key={dayValue} className={`${day.getMonth() !== month ? "outside" : ""} ${isSelected ? "selected" : ""} ${isToday ? "today" : ""}`} onClick={() => selectDate(day)}>{day.getDate()}</button>;
            })}
          </div>
          <button type="button" className="calendar-today" onClick={() => selectDate(new Date())}>Today</button>
        </div>
      )}
    </div>
  );
}

function parseDateValue(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function formatDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [view, setView] = useState<View>("dashboard");
  const [profileOpen, setProfileOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profilePhoto, setProfilePhoto] = useState<string | null>(null);
  const [selectedBankId, setSelectedBankId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const t = (key: string) => translate(language, key);

  function applyLanguage(value: string) {
    const nextLanguage = normalizeLanguage(value);
    setLanguage(nextLanguage);
    localStorage.setItem("language", nextLanguage);
    document.documentElement.lang = nextLanguage;
  }

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    });
  }, []);

  useEffect(() => {
    if (!message) return;
    const isError = /(failed|could not|cannot|invalid|unable|must|required|not configured|not found|error)/i.test(message);
    const timer = window.setTimeout(() => setMessage(""), isError ? 5000 : 2400);
    return () => window.clearTimeout(timer);
  }, [message]);

  useEffect(() => {
    setMessage("");
  }, [view]);

  async function loadDashboard(nextToken = token) {
    if (!nextToken) return;
    const data = await apiFetch<Dashboard>("/reports/dashboard", nextToken);
    setDashboard(data);
  }

  function saveToken(nextToken: string | null) {
    setToken(nextToken);
    if (nextToken) localStorage.setItem("token", nextToken);
    else localStorage.removeItem("token");
  }

  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    applyLanguage(localStorage.getItem("language") || "en");
    setToken(storedToken);
    setSessionReady(true);
    if (storedToken) {
      loadDashboard(storedToken).catch(() => undefined);
      apiFetch<Profile>("/auth/me", storedToken).then(setProfile).catch(() => undefined);
      apiFetch<UserSettings>("/settings", storedToken)
        .then((settings) => {
          applyTheme(settings.theme);
          setProfilePhoto(settings.profile_photo_url || null);
          applyLanguage(settings.favorite_language);
        })
        .catch(() => undefined);
    }
  }, []);

  if (!sessionReady) {
    return <main className="auth-page" aria-busy="true" />;
  }

  if (!token) {
    return <I18nContext.Provider value={{ language, t }}><AuthScreen onLogin={(nextToken) => {
      saveToken(nextToken);
      loadDashboard(nextToken).catch(() => undefined);
      apiFetch<Profile>("/auth/me", nextToken).then(setProfile).catch(() => undefined);
      apiFetch<UserSettings>("/settings", nextToken).then((settings) => {
        applyTheme(settings.theme);
        setProfilePhoto(settings.profile_photo_url || null);
        applyLanguage(settings.favorite_language);
      }).catch(() => undefined);
    }} /></I18nContext.Provider>;
  }

  const initials = (profile?.full_name || profile?.email || "F").trim().charAt(0).toUpperCase();

  return (
    <I18nContext.Provider value={{ language, t }}>
    <main className="app-shell">
      <header className="app-header">
        <button className="brand brand-button" onClick={() => setView("dashboard")} aria-label="Finlio overview">
          <span className="brand-mark"><Sparkles size={24} /></span>
          <span>Finlio</span>
        </button>
        <div className="app-user">
          <div className="user-copy">
            <strong>{profile?.full_name || "Finlio user"}</strong>
            <span>{profile?.email || ""}</span>
          </div>
          <div className="profile-wrap">
            <button className={`user-avatar ${profilePhoto ? "has-photo" : ""}`} onClick={() => setProfileOpen((open) => !open)} title={t("Profile & settings")}>
              {profilePhoto ? <img src={profilePhoto} alt="" /> : initials}
            </button>
            {profileOpen && (
              <div className="profile-menu">
                <button onClick={() => { setView("settings"); setProfileOpen(false); }}>{t("Profile & settings")}</button>
                <button onClick={() => { setView("import"); setProfileOpen(false); }}><FileUp size={15} />{t("Import statements")}</button>
                <button onClick={() => saveToken(null)}>
                  <LogOut size={15} />
                  {t("Sign out")}
                </button>
              </div>
            )}
          </div>
          <button className="logout-button" onClick={() => saveToken(null)} title="Sign out"><LogOut size={21} /></button>
        </div>
      </header>

      <section className="workspace">
        <nav className="primary-nav">
          {sections.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id as View)}>
                <Icon size={19} />
                <span>{t(item.label)}</span>
              </button>
            );
          })}
          <button className="mobile-nav-toggle" onClick={() => setMobileMenuOpen((open) => !open)}><Menu size={20} />{t("Menu")}</button>
        </nav>
        {mobileMenuOpen && (
          <nav className="mobile-menu">
            {sections.map((item) => {
              const Icon = item.icon;
              return <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => { setView(item.id as View); setMobileMenuOpen(false); }}><Icon size={17} />{t(item.label)}</button>;
            })}
          </nav>
        )}
        {message && <p className={`notice ${/(failed|could not|cannot|invalid|unable|must|required|not configured|not found|error)/i.test(message) ? "notice-error" : ""}`}>{message}</p>}
        <Content view={view} token={token} dashboard={dashboard} refresh={loadDashboard} setMessage={setMessage} onProfilePhoto={setProfilePhoto} onProfileChange={setProfile} onLanguageChange={applyLanguage} selectedBankId={selectedBankId} onOpenBank={(bankId) => { setSelectedBankId(bankId); setView("bank-detail"); }} onCloseBank={() => setView("dashboard")} />
      </section>

      <nav className="bottom-nav">
        {mobileSections.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.id} className={view === item.id ? "active" : ""} onClick={() => setView(item.id as View)} title={t(item.label)}>
              <Icon size={19} />
              <span>{t(item.label)}</span>
            </button>
          );
        })}
      </nav>
    </main>
    </I18nContext.Provider>
  );
}

function AuthScreen({ onLogin }: { onLogin: (token: string) => void }) {
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

  async function tryDemo() {
    setError("");
    setBusy(true);
    try {
      const result = await apiFetch<{ access_token: string }>("/auth/demo", null, { method: "POST" });
      onLogin(result.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the demo");
    } finally {
      setBusy(false);
    }
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
          <p>Track accounts, cards, transactions, investments and insurance — with beautiful insights and one-click CSV/XLSX imports.</p>
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
          {mode === "login" && <button className="demo-button wide" type="button" onClick={tryDemo} disabled={busy}><Sparkles size={17} />{t("Try demo (auto-seeded)")}</button>}
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

function Content({ view, token, dashboard, refresh, setMessage, onProfilePhoto, onProfileChange, onLanguageChange, selectedBankId, onOpenBank, onCloseBank }: { view: View; token: string; dashboard: Dashboard | null; refresh: () => Promise<void>; setMessage: (msg: string) => void; onProfilePhoto: (url: string | null) => void; onProfileChange: (profile: Profile) => void; onLanguageChange: (language: string) => void; selectedBankId: number | null; onOpenBank: (bankId: number) => void; onCloseBank: () => void }) {
  if (view === "dashboard") return <DashboardView token={token} dashboard={dashboard} refresh={refresh} onOpenBank={onOpenBank} />;
  if (view === "bank-detail" && selectedBankId) return <BankDetailView token={token} bankId={selectedBankId} onBack={onCloseBank} setMessage={setMessage} />;
  if (view === "import") return <ImportView token={token} setMessage={setMessage} />;
  if (view === "settings") return <SettingsView token={token} setMessage={setMessage} onProfilePhoto={onProfilePhoto} onProfileChange={onProfileChange} onLanguageChange={onLanguageChange} />;
  if (view === "transactions") return <TransactionView token={token} setMessage={setMessage} />;
  if (view === "investments") return <SimplifiedInvestmentView token={token} setMessage={setMessage} />;
  if (view === "insurance") return <InsuranceView token={token} setMessage={setMessage} />;
  if (view === "reports") return <ReportsView token={token} />;
  if (view === "banks" || view === "accounts" || view === "cards") {
    return <EntityView kind={view} token={token} setMessage={setMessage} />;
  }
  return null;
}

function BankForecastPanel({ token, bankId }: { token: string; bankId: number }) {
  const { t } = useI18n();
  type ForecastItem = { id: number; name: string; date: string; amount: number; flow: "income" | "expense"; frequency: string };
  type ForecastMonth = { month: string; income: number; expenses: number; net: number; ending_balance: number; items: ForecastItem[] };
  type Forecast = { months: number; currency: string; starting_balance: number; projected_income: number; projected_expenses: number; projected_change: number; ending_balance: number; timeline: ForecastMonth[] };
  const [forecastMonths, setForecastMonths] = useState<3 | 6>(3);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    apiFetch<Forecast>(`/reports/forecast?months=${forecastMonths}${bankId ? `&bank_id=${bankId}` : ""}`, token)
      .then(setForecast)
      .catch(() => setForecast(null))
      .finally(() => setLoading(false));
  }, [token, bankId, forecastMonths]);

  const maxFlow = Math.max(1, ...(forecast?.timeline.flatMap((month) => [Number(month.income), Number(month.expenses)]) || [1]));
  const upcoming = forecast?.timeline.flatMap((month) => month.items).slice(0, 8) || [];
  return (
      <article className="analysis-chart-card bank-forecast-card">
        <div className="bank-forecast-heading">
          <div><h2>{t("Balance forecast")}</h2><p>{t("Recurring movements for this bank.")}</p></div>
          <div className="forecast-range" aria-label="Forecast period">
            <button className={forecastMonths === 3 ? "active" : ""} onClick={() => setForecastMonths(3)}>3m</button>
            <button className={forecastMonths === 6 ? "active" : ""} onClick={() => setForecastMonths(6)}>6m</button>
          </div>
        </div>
        {loading ? <p className="muted">Building forecast…</p> : forecast ? (
          <>
            <div className="bank-forecast-balance">
              <span>{t("Expected balance")}</span>
              <strong className={forecast.ending_balance >= 0 ? "positive" : "negative"}>{formatMoney(forecast.ending_balance, forecast.currency)}</strong>
              <small>From {formatMoney(forecast.starting_balance, forecast.currency)} {t("today")}</small>
            </div>
            <div className="bank-forecast-totals">
              <span><small>{t("Revenue")}</small><b className="positive">+{formatMoney(forecast.projected_income, forecast.currency)}</b></span>
              <span><small>{t("Payments")}</small><b className="negative">−{formatMoney(forecast.projected_expenses, forecast.currency)}</b></span>
              <span><small>{t("Change")}</small><b className={forecast.projected_change >= 0 ? "positive" : "negative"}>{forecast.projected_change >= 0 ? "+" : "−"}{formatMoney(Math.abs(forecast.projected_change), forecast.currency)}</b></span>
            </div>
            <div className="bank-forecast-months">
              {forecast.timeline.map((month) => <div key={month.month}><span>{new Date(`${month.month}-02`).toLocaleDateString(undefined, { month: "short" })}</span><div><i className="income" style={{ width: `${Number(month.income) / maxFlow * 100}%` }} /><i className="expense" style={{ width: `${Number(month.expenses) / maxFlow * 100}%` }} /></div><b className={month.net >= 0 ? "positive" : "negative"}>{month.net >= 0 ? "+" : "−"}{formatMoney(Math.abs(month.net), forecast.currency)}</b></div>)}
            </div>
            {!upcoming.length && <p className="muted bank-forecast-empty">Link recurring movements to this bank’s account in Transactions.</p>}
          </>
        ) : <p className="muted">The forecast could not be loaded.</p>}
      </article>
  );
}

function DashboardView({ token, dashboard, refresh, onOpenBank }: { token: string; dashboard: Dashboard | null; refresh: () => Promise<void>; onOpenBank: (bankId: number) => void }) {
  const { t } = useI18n();
  const [banks, setBanks] = useState<BankItem[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [selectedBankId, setSelectedBankId] = useState<number | null>(null);
  const [selectedCardId, setSelectedCardId] = useState<number | null>(null);
  const [bankTransactions, setBankTransactions] = useState<TransactionItem[]>([]);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch<BankItem[]>("/banks", token),
      apiFetch<AccountItem[]>("/accounts", token),
      apiFetch<CardItem[]>("/cards", token)
    ]).then(([nextBanks, nextAccounts, nextCards]) => {
      setBanks(nextBanks);
      setAccounts(nextAccounts);
      setCards(nextCards);
    }).catch(() => undefined);
  }, [token, dashboard]);

  useEffect(() => {
    setSelectedCardId(null);
  }, [selectedBankId]);

  useEffect(() => {
    if (!selectedBankId) {
      setBankTransactions([]);
      return;
    }
    setAnalysisLoading(true);
    const cardBelongsToBank = cards.some((card) => card.id === selectedCardId && card.bank_id === selectedBankId);
    const cardFilter = cardBelongsToBank ? `&card_id=${selectedCardId}` : "";
    apiFetch<TransactionItem[]>(`/transactions?bank_id=${selectedBankId}${cardFilter}`, token)
      .then(setBankTransactions)
      .catch(() => setBankTransactions([]))
      .finally(() => setAnalysisLoading(false));
  }, [selectedBankId, selectedCardId, token, cards]);

  const palette = ["#7547ee", "#17a9d8", "#16b98b", "#f59e0b", "#ef5b75", "#8b5cf6", "#5d7ce8"];
  const bankSlices = banks.map((bank, index) => {
    const bankAccounts = accounts.filter((account) => account.bank_id === bank.id);
    const balance = bankAccounts.reduce((sum, account) => sum + Number(account.current_balance), 0);
    return { ...bank, balance, weight: Math.abs(balance), color: palette[index % palette.length] };
  });
  const rawWeight = bankSlices.reduce((sum, bank) => sum + bank.weight, 0);
  const totalBankBalances = bankSlices.reduce((sum, bank) => sum + bank.balance, 0);
  const ringTotal = rawWeight || bankSlices.length || 1;
  let ringOffset = 0;
  const ringSlices = bankSlices.map((bank) => {
    const percent = ((rawWeight ? bank.weight : 1) / ringTotal) * 100;
    const slice = { ...bank, percent, offset: ringOffset };
    ringOffset += percent;
    return slice;
  });

  const selectedBank = banks.find((bank) => bank.id === selectedBankId);
  const selectedAccounts = accounts.filter((account) => account.bank_id === selectedBankId);
  const selectedCards = cards.filter((card) => card.bank_id === selectedBankId);
  const selectedCard = selectedCards.find((card) => card.id === selectedCardId);
  const selectedBalance = selectedAccounts.reduce((sum, account) => sum + Number(account.current_balance), 0);
  const selectedIncome = bankTransactions.filter((transaction) => Number(transaction.amount) > 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0);
  const selectedSpending = Math.abs(bankTransactions.filter((transaction) => Number(transaction.amount) < 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0));

  return (
    <div className="page-grid bank-overview-page">
      <section className="net-worth-intro">
        <span>{t("Your total net worth")}</span>
        <strong>{formatMoney(dashboard?.net_worth || 0)}</strong>
        <p>Liquid accounts and investments, plus insurance value, less recorded debt.</p>
        <button className="secondary overview-refresh" onClick={() => refresh()}>Refresh overview</button>
      </section>

      <section className="simple-stats">
        <article><WalletCards size={20} /><span>{t("Cash")}</span><strong>{formatMoney(dashboard?.total_liquidity || 0)}</strong></article>
        <article><LineChart size={20} /><span>{t("Investments")}</span><strong>{formatMoney(dashboard?.total_investments || 0)}</strong></article>
        <article><ShieldCheck size={20} /><span>{t("Insurance")}</span><strong>{formatMoney(dashboard?.insurance_value || 0)}</strong></article>
        <article><CreditCard size={20} /><span>{t("Debt")}</span><strong>{formatMoney(dashboard?.total_debt || 0)}</strong></article>
      </section>

      <section className="bank-ring-card">
        <div className="bank-ring-heading">
          <div><h2>{t("Your money by bank")}</h2><p>{t("Select a segment to open that bank’s complete analysis.")}</p></div>
        </div>
        {banks.length ? (
          <div className="bank-ring-layout">
            <div className="bank-ring">
              <svg viewBox="0 0 200 200" aria-label="Balances by bank">
                <circle className="bank-ring-track" cx="100" cy="100" r="78" pathLength="100" />
                {ringSlices.map((bank) => (
                  <circle
                    key={bank.id}
                    className={`bank-ring-segment ${selectedBankId === bank.id ? "active" : ""}`}
                    cx="100"
                    cy="100"
                    r="78"
                    pathLength="100"
                    stroke={bank.color}
                    strokeDasharray={`${Math.max(0, bank.percent - 0.8)} ${100 - Math.max(0, bank.percent - 0.8)}`}
                    strokeDashoffset={-bank.offset}
                    transform="rotate(-90 100 100)"
                    onClick={() => onOpenBank(bank.id)}
                  />
                ))}
              </svg>
              <div className="bank-ring-center"><span>{t("Bank balances")}</span><strong>{formatMoney(totalBankBalances)}</strong><small>{banks.length} bank{banks.length === 1 ? "" : "s"}</small></div>
            </div>
            <div className="bank-ring-legend">
              {ringSlices.map((bank) => (
                <button key={bank.id} onClick={() => onOpenBank(bank.id)}>
                  <i style={{ background: bank.color }} />
                  <span><strong>{bank.name}</strong><small>{accounts.some((account) => account.bank_id === bank.id) ? "Account connected" : "No account"} · {cards.filter((card) => card.bank_id === bank.id).length} cards</small></span>
                  <b>{formatMoney(bank.balance)}</b>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="bank-ring-empty"><Landmark size={34} /><strong>{t("No banks yet")}</strong><span>Add your first bank and account to build this overview.</span></div>
        )}
      </section>

      {selectedBank && (
        <section className="bank-analysis">
          <div className="bank-analysis-heading">
            <div><span className="analysis-bank-icon"><Landmark size={22} /></span><div><h2>{selectedBank.name}</h2><p>Accounts, cards, and activity for this bank.</p></div></div>
            <button className="secondary" onClick={() => setSelectedBankId(null)}>Close analysis</button>
          </div>
          <div className="bank-analysis-stats">
            <div><span>Total balance</span><strong>{formatMoney(selectedBalance)}</strong></div>
            <div><span>Total income</span><strong className="positive">{formatMoney(selectedIncome)}</strong></div>
            <div><span>Total spending</span><strong className="negative">{formatMoney(selectedSpending)}</strong></div>
            <div><span>Transactions</span><strong>{bankTransactions.length}</strong></div>
          </div>
          <div className="bank-analysis-grid">
            <div className="analysis-list"><h3>Account</h3>{selectedAccounts.length ? selectedAccounts.map((account) => <div key={account.id}><span><Building2 size={17} /><span><strong>{account.name}</strong><small>{account.type}</small></span></span><b>{formatMoney(account.current_balance, account.currency)}</b></div>) : <p className="muted">No account for this bank.</p>}</div>
            <div className="analysis-list"><h3>Cards <small>· select one to filter activity</small></h3>{selectedCards.length ? selectedCards.map((card) => <button type="button" className={`analysis-card-row ${selectedCardId === card.id ? "active" : ""}`} key={card.id} onClick={() => setSelectedCardId(selectedCardId === card.id ? null : card.id)}><span><CreditCard size={17} /><span><strong>{card.name}</strong><small>{card.type} · •••• {card.last4}</small></span></span><b>{formatMoney(card.current_balance)}</b></button>) : <p className="muted">No cards for this bank.</p>}</div>
          </div>
          <div className="bank-transactions">
            <div className="bank-transactions-heading"><h3>{selectedCard ? `${selectedCard.name} transactions` : "All bank transactions"}</h3>{selectedCard && <button type="button" onClick={() => setSelectedCardId(null)}>Show all bank activity</button>}</div>
            {analysisLoading ? <p className="muted">Loading activity…</p> : <DataPanel title="" rows={bankTransactions.slice(0, 12).map((transaction) => [transaction.date, transaction.description, formatMoney(transaction.amount, transaction.currency)])} empty="No transactions for this bank yet." />}
          </div>
        </section>
      )}
    </div>
  );
}

function BankDetailView({ token, bankId, onBack, setMessage }: { token: string; bankId: number; onBack: () => void; setMessage: (message: string) => void }) {
  const { t } = useI18n();
  const [bank, setBank] = useState<BankItem | null>(null);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<number | null>(null);
  const [transactionFormOpen, setTransactionFormOpen] = useState(false);
  const [transactionAccountId, setTransactionAccountId] = useState("");
  const [transactionType, setTransactionType] = useState<"expense" | "income">("expense");
  const [error, setError] = useState("");

  async function loadBank() {
    const [nextBank, nextAccounts, nextCards, nextCategories, nextTransactions] = await Promise.all([
      apiFetch<BankItem>(`/banks/${bankId}`, token),
      apiFetch<AccountItem[]>("/accounts", token),
      apiFetch<CardItem[]>("/cards", token),
      apiFetch<CategoryItem[]>("/categories", token),
      apiFetch<TransactionItem[]>(`/transactions?bank_id=${bankId}`, token)
    ]);
    const bankAccounts = nextAccounts.filter((account) => account.bank_id === bankId);
    setBank(nextBank);
    setAccounts(bankAccounts);
    setCards(nextCards.filter((card) => card.bank_id === bankId));
    setCategories(nextCategories);
    setTransactions(nextTransactions);
    setTransactionAccountId((current) => current || (bankAccounts[0] ? String(bankAccounts[0].id) : ""));
  }

  useEffect(() => {
    loadBank().catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load this bank"));
  }, [bankId, token]);

  async function addTransaction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    if (!account) {
      setMessage("Choose an account for this bank");
      return;
    }
    const amount = Math.abs(Number(form.amount));
    try {
      await apiFetch("/transactions", token, {
        method: "POST",
        body: JSON.stringify({
          bank_id: bankId,
          account_id: account.id,
          card_id: form.card_id ? Number(form.card_id) : null,
          category_id: form.category_id ? Number(form.category_id) : null,
          date: form.date,
          description: form.description,
          amount: form.type === "expense" ? -amount : amount,
          currency: account.currency,
          type: form.type
        })
      });
      formElement.reset();
      setTransactionType("expense");
      setTransactionFormOpen(false);
      setMessage(`Transaction added to ${bank?.name || "bank"}`);
      await loadBank();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Could not save transaction");
    }
  }

  const visibleTransactions = selectedCardId ? transactions.filter((transaction) => transaction.card_id === selectedCardId) : transactions;
  const balance = accounts.reduce((sum, account) => sum + Number(account.current_balance), 0);
  const income = visibleTransactions.filter((transaction) => Number(transaction.amount) > 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0);
  const spending = Math.abs(visibleTransactions.filter((transaction) => Number(transaction.amount) < 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0));
  const monthlyMap = new Map<string, { income: number; expenses: number }>();
  transactions.forEach((transaction) => {
    const month = transaction.date.slice(0, 7);
    const bucket = monthlyMap.get(month) || { income: 0, expenses: 0 };
    const amount = Number(transaction.amount);
    if (amount >= 0) bucket.income += amount;
    else bucket.expenses += Math.abs(amount);
    monthlyMap.set(month, bucket);
  });
  const monthly = Array.from(monthlyMap.entries()).sort(([a], [b]) => a.localeCompare(b)).slice(-6);
  const monthlyMax = Math.max(1, ...monthly.flatMap(([, values]) => [values.income, values.expenses]));
  const cardMetrics = cards.map((card) => {
    const activity = transactions.filter((transaction) => transaction.card_id === card.id);
    const incoming = activity.filter((transaction) => Number(transaction.amount) > 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0);
    const spending = Math.abs(activity.filter((transaction) => Number(transaction.amount) < 0).reduce((sum, transaction) => sum + Number(transaction.amount), 0));
    const net = incoming - spending;
    const used = Math.abs(net);
    const limit = Number(card.credit_limit || 0);
    return { ...card, incoming, spending, net, used, limit, available: limit ? Math.max(0, limit - used) : 0 };
  });
  const cardMax = Math.max(1, ...cardMetrics.map((card) => Math.max(Math.abs(card.net), card.spending)));

  if (!bank && !error) return <div className="page-grid"><div className="settings-loading">Building bank analysis…</div></div>;

  return (
    <div className="page-grid bank-detail-page">
      <button className="bank-back" onClick={onBack}><ArrowLeft size={18} />{t("Back to overview")}</button>
      {error ? <p className="notice notice-error">{error}</p> : bank && (
        <>
          <section className="bank-detail-hero">
            <div><span className="analysis-bank-icon"><Landmark size={24} /></span><div><p>{t("Bank analysis")}</p><h1>{bank.name}</h1><span>{bank.country || "Country not set"} · {accounts.length ? accounts[0].name : "No account"} · {cards.length} card{cards.length === 1 ? "" : "s"}</span></div></div>
            <div className="bank-detail-hero-actions"><strong>{formatMoney(balance)}</strong><button onClick={() => setTransactionFormOpen((open) => !open)}><Plus size={17} />{transactionFormOpen ? "Close" : t("Add transaction")}</button></div>
          </section>

          {transactionFormOpen && (
            <section className="bank-quick-transaction">
              <div className="settings-card-heading"><h2>Add transaction to {bank.name}</h2><p>The bank and its account are already selected; optionally choose a card.</p></div>
              <form className="guided-form" onSubmit={addTransaction}>
                <label className="field"><span>Flow</span><ModernSelect name="type" value={transactionType} onValueChange={(value) => setTransactionType(value as "expense" | "income")} options={[{ value: "expense", label: "Money out" }, { value: "income", label: "Money in" }]} /></label>
                <label className="field"><span>Account</span><input value={accounts[0]?.name || "No account connected"} disabled /><input type="hidden" name="account_id" value={transactionAccountId} /></label>
                <label className="field"><span>Card (optional)</span><ModernSelect name="card_id" options={[{ value: "", label: "No card / bank transfer" }, ...cards.filter((card) => card.account_id === Number(transactionAccountId)).map((card) => ({ value: String(card.id), label: `${card.name} · •••• ${card.last4}` }))]} /></label>
                <label className="field"><span>Category</span><ModernSelect name="category_id" required placeholder="Choose category" options={categories.filter((category) => category.type === transactionType).map((category) => ({ value: String(category.id), label: category.name }))} /></label>
                <label className="field"><span>Date</span><ModernDateInput name="date" defaultValue={formatDateValue(new Date())} required /></label>
                <label className="field field-wide"><span>Description</span><input name="description" placeholder="What was this transaction for?" required /></label>
                <label className="field"><span>Amount</span><input name="amount" type="number" min="0.01" step="0.01" placeholder="0.00" required /></label>
                <button className="primary form-action" type="submit"><Plus size={16} />Save transaction</button>
              </form>
            </section>
          )}

          <section className="bank-detail-stats">
            <article><span>{t("Total balance")}</span><strong>{formatMoney(balance)}</strong></article>
            <article><span>{selectedCardId ? "Card income" : t("Total income")}</span><strong className="positive">{formatMoney(income)}</strong></article>
            <article><span>{selectedCardId ? t("Card spending") : t("Total spending")}</span><strong className="negative">{formatMoney(spending)}</strong></article>
            <article><span>{t("Transactions shown")}</span><strong>{visibleTransactions.length}</strong></article>
          </section>

          <section className="bank-detail-charts">
            <article className="analysis-chart-card">
              <div className="settings-card-heading"><h2>{t("Cash flow")}</h2><p>Income and spending over the last six active months.</p></div>
              <div className="cashflow-columns">
                {monthly.length ? monthly.map(([month, values]) => <div className="cashflow-month" key={month}><div><i className="cashflow-income" style={{ height: `${Math.max(4, values.income / monthlyMax * 100)}%` }} /><i className="cashflow-expense" style={{ height: `${Math.max(4, values.expenses / monthlyMax * 100)}%` }} /></div><span>{new Date(`${month}-02`).toLocaleDateString(undefined, { month: "short" })}</span></div>) : <p className="muted">No transaction history yet.</p>}
              </div>
              <div className="analysis-legend"><span><i className="cashflow-income" />{t("Income")}</span><span><i className="cashflow-expense" />{t("Spending")}</span></div>
            </article>
            <BankForecastPanel token={token} bankId={bankId} />
          </section>

          <section className="bank-cards-analysis">
            <div className="settings-card-heading"><h2>{t("Card spending")}</h2><p>Select a card to filter the transaction history below.</p></div>
            <div className="bank-card-grid">
              {cardMetrics.length ? cardMetrics.map((card) => <button key={card.id} className={selectedCardId === card.id ? "active" : ""} onClick={() => setSelectedCardId(selectedCardId === card.id ? null : card.id)}><span><CreditCard size={20} /><span><strong>{card.name}</strong><small>{card.type} · •••• {card.last4}{card.expiry_month && card.expiry_year ? ` · expires ${String(card.expiry_month).padStart(2, "0")}/${String(card.expiry_year).slice(-2)}` : " · expiry not set"}</small></span></span><div className="card-metric-values"><span><small>Current balance</small><b>{formatMoney(card.used)}</b></span>{card.limit > 0 && <span><small>Available of total limit</small><b>{formatMoney(card.available)} / {formatMoney(card.limit)}</b></span>}</div><i><em style={{ width: `${card.limit > 0 ? Math.min(100, card.used / card.limit * 100) : Math.abs(card.net) / cardMax * 100}%` }} /></i></button>) : <p className="muted">No cards connected to this bank.</p>}
            </div>
          </section>

          <section className="bank-transaction-history">
            <div className="settings-card-heading action-title"><div><h2>{selectedCardId ? `${cards.find((card) => card.id === selectedCardId)?.name} transactions` : t("All bank transactions")}</h2><p>{t("Latest activity for the selected scope.")}</p></div>{selectedCardId && <button className="secondary" onClick={() => setSelectedCardId(null)}>Clear card filter</button>}</div>
            {visibleTransactions.length ? (
              <div className="recognizable-transactions">
                <table>
                  <thead><tr><th>{t("Date")}</th><th>{t("Flow")}</th><th>{t("Description")}</th><th>{t("Account")}</th><th>{t("Card")}</th><th>{t("Amount")}</th></tr></thead>
                  <tbody>{visibleTransactions.map((transaction) => {
                    const isRevenue = Number(transaction.amount) >= 0;
                    return <tr key={transaction.id}>
                      <td>{transaction.date}</td>
                      <td><span className={`transaction-kind ${isRevenue ? "revenue" : "payment"}`}>{isRevenue ? t("Revenue") : t("Payment")}</span></td>
                      <td><strong>{transaction.description}</strong></td>
                      <td>{accounts.find((account) => account.id === transaction.account_id)?.name || "Account"}</td>
                      <td>{cards.find((card) => card.id === transaction.card_id)?.name || "No card"}</td>
                      <td className={isRevenue ? "positive" : "negative"}>{isRevenue ? "+" : "−"}{formatMoney(Math.abs(Number(transaction.amount)), transaction.currency)}</td>
                    </tr>;
                  })}</tbody>
                </table>
              </div>
            ) : <p className="muted">No transactions found.</p>}
          </section>
        </>
      )}
    </div>
  );
}

function EntityView({ kind, token, setMessage }: { kind: "banks" | "accounts" | "cards"; token: string; setMessage: (msg: string) => void }) {
  const { t } = useI18n();
  type EditingEntity = { entity: "banks" | "accounts" | "cards"; id: number; values: Record<string, string | number> };
  const [banks, setBanks] = useState<BankItem[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [editing, setEditing] = useState<EditingEntity | null>(null);
  async function load() {
    const [nextBanks, nextAccounts, nextCards] = await Promise.all([
      apiFetch<BankItem[]>("/banks", token),
      apiFetch<AccountItem[]>("/accounts", token),
      apiFetch<CardItem[]>("/cards", token)
    ]);
    setBanks(nextBanks);
    setAccounts(nextAccounts);
    setCards(nextCards);
    setLoaded(true);
  }
  useEffect(() => {
    setEditing(null);
    load().catch(() => setLoaded(true));
  }, [kind, token]);
  async function addBank(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    try {
      await apiFetch("/banks", token, {
        method: "POST",
        body: JSON.stringify({ name: form.name, country: form.country })
      });
      formElement.reset();
      setMessage("Bank saved");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save bank");
    }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    const body =
      kind === "banks"
        ? { name: form.name, country: form.country }
        : kind === "accounts"
          ? { bank_id: Number(form.bank_id), name: form.name, type: form.type || "checking", currency: form.currency || "EUR", opening_balance: Number(form.current_balance || 0), current_balance: Number(form.current_balance || 0) }
          : { bank_id: account?.bank_id, account_id: account?.id, name: form.name, type: form.type || "debit", last4: form.last4, credit_limit: form.credit_limit ? Number(form.credit_limit) : null, expiry_month: form.expiry_month ? Number(form.expiry_month) : null, expiry_year: form.expiry_year ? Number(form.expiry_year) : null };
    try {
      await apiFetch(`/${kind}`, token, { method: "POST", body: JSON.stringify(body) });
      formElement.reset();
      setMessage(`${kind.slice(0, -1)} saved`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `Could not save ${kind.slice(0, -1)}`);
    }
  }
  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    const body = editing.entity === "banks"
      ? { name: form.name, country: form.country }
      : editing.entity === "accounts"
        ? { bank_id: Number(form.bank_id), name: form.name, type: form.type, currency: form.currency, current_balance: Number(form.current_balance || 0), opening_balance: Number(form.opening_balance || 0) }
        : { bank_id: account?.bank_id, account_id: account?.id, name: form.name, type: form.type, last4: form.last4, current_balance: Number(form.current_balance || 0), credit_limit: form.credit_limit ? Number(form.credit_limit) : null, expiry_month: form.expiry_month ? Number(form.expiry_month) : null, expiry_year: form.expiry_year ? Number(form.expiry_year) : null };
    try {
      await apiFetch(`/${editing.entity}/${editing.id}`, token, { method: "PATCH", body: JSON.stringify(body) });
      setEditing(null);
      setMessage(`${editing.entity.slice(0, -1)} updated`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update item");
    }
  }
  async function archive(entity: "banks" | "accounts" | "cards", id: number, label: string) {
    const cascade = entity === "banks" ? " Its accounts and cards will also be archived." : entity === "accounts" ? " Its cards will also be archived." : "";
    if (!window.confirm(`Archive ${label}?${cascade}`)) return;
    try {
      await apiFetch(`/${entity}/${id}`, token, { method: "DELETE" });
      setEditing(null);
      setMessage(`${label} archived`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : `Could not archive ${label}`);
    }
  }
  const bankName = (bankId: number) => banks.find((bank) => bank.id === bankId)?.name || "Unknown bank";
  const accountName = (accountId: number) => accounts.find((account) => account.id === accountId)?.name || "Unknown account";
  const banksWithoutAccounts = banks.filter((bank) => !accounts.some((account) => account.bank_id === bank.id));
  const canCreate = kind === "banks" || (kind === "accounts" ? banksWithoutAccounts.length > 0 : accounts.length > 0);
  const rows = kind === "banks"
    ? banks.map((item) => [item.name, item.country || "Country not set"])
    : kind === "accounts"
      ? accounts.map((item) => [item.name, bankName(item.bank_id), item.type, `${cards.filter((card) => card.account_id === item.id).length} card(s)`, formatMoney(item.current_balance, item.currency)])
      : cards.map((item) => [item.name, accountName(item.account_id), `•••• ${item.last4}`, item.type]);
  return (
    <div className="page-grid">
      <div className="page-heading">
        <h1>{t(kind[0].toUpperCase() + kind.slice(1))}</h1>
        <p>{t(kind === "banks" ? "Start with the institutions you use." : kind === "accounts" ? "Each bank has one primary account where its balance and transactions live." : "Connect each card to the account it spends from.")}</p>
      </div>
      {kind === "accounts" && (
        <section className="module-section">
          <div className="section-title"><div><h2>{t("Your banks")}</h2><p>Create the bank first, then connect its single primary account below.</p></div></div>
          <form className="inline-form compact-form" onSubmit={addBank}>
            <label className="field"><span>{t("Bank name")}</span><input name="name" placeholder="e.g. Intesa Sanpaolo" required /></label>
            <label className="field"><span>{t("Country")}</span><input name="country" placeholder="e.g. Italy" /></label>
            <button className="primary form-action" type="submit"><Plus size={16} />{t("Add bank")}</button>
          </form>
          {banks.length > 0 && <div className="entity-management-list">{banks.map((bank) => <article key={bank.id}><span className="entity-management-icon"><Landmark size={18} /></span><span><strong>{bank.name}</strong><small>{bank.country || "Country not set"}</small></span><div><button type="button" onClick={() => setEditing({ entity: "banks", id: bank.id, values: { name: bank.name, country: bank.country || "" } })}><Pencil size={16} />Edit</button><button type="button" className="danger-action" onClick={() => archive("banks", bank.id, bank.name)}><Trash2 size={16} />Archive</button></div></article>)}</div>}
        </section>
      )}
      {!canCreate && loaded ? (
        <section className="setup-callout">
          <strong>{kind === "accounts" ? (banks.length ? "Every bank already has an account" : "Add a bank first") : "Add an account first"}</strong>
          <span>{kind === "accounts" ? (banks.length ? "Edit the existing account below, or add another bank to create a new one." : "Each bank can have one primary account.") : "A card needs a linked account so purchases affect the right cash flow."}</span>
        </section>
      ) : (
        <form className="inline-form guided-form" onSubmit={submit}>
          {kind === "accounts" && (
            <label className="field"><span>Bank</span><ModernSelect name="bank_id" required placeholder="Choose a bank" options={banksWithoutAccounts.map((bank) => ({ value: String(bank.id), label: bank.name }))} /></label>
          )}
          {kind === "cards" && (
            <label className="field"><span>Account charged by this card</span><ModernSelect name="account_id" required placeholder="Choose an account" options={accounts.map((account) => ({ value: String(account.id), label: `${account.name} · ${bankName(account.bank_id)}` }))} /></label>
          )}
          <label className="field"><span>{t(kind === "banks" ? "Bank name" : kind === "accounts" ? "Account nickname" : "Card nickname")}</span><input name="name" placeholder={kind === "banks" ? "e.g. Intesa Sanpaolo" : kind === "accounts" ? "e.g. Main current account" : "e.g. Everyday debit card"} required /></label>
          {kind === "banks" && <label className="field"><span>Country</span><input name="country" placeholder="e.g. Italy" /></label>}
          {kind === "accounts" && <label className="field"><span>{t("Account type")}</span><ModernSelect name="type" defaultValue="checking" options={[{ value: "checking", label: "Current account" }, { value: "savings", label: "Savings" }, { value: "cash", label: "Cash wallet" }, { value: "brokerage", label: "Brokerage" }, { value: "loan", label: "Loan" }, { value: "mortgage", label: "Mortgage" }, { value: "other", label: "Other" }]} /></label>}
          {kind === "accounts" && <label className="field"><span>{t("Currency")}</span><input name="currency" defaultValue="EUR" maxLength={3} /></label>}
          {kind === "accounts" && <label className="field"><span>{t("Balance today")}</span><input name="current_balance" type="number" step="0.01" defaultValue="0" /></label>}
          {kind === "cards" && <label className="field"><span>{t("Card type")}</span><ModernSelect name="type" defaultValue="debit" options={[{ value: "debit", label: "Debit card" }, { value: "credit", label: "Credit card" }, { value: "prepaid", label: "Prepaid card" }]} /></label>}
          {kind === "cards" && <label className="field"><span>{t("Last 4 digits")}</span><input name="last4" inputMode="numeric" pattern="[0-9]{4}" placeholder="1234" minLength={4} maxLength={4} required /></label>}
          {kind === "cards" && <label className="field"><span>{t("Credit / spending limit")}</span><input name="credit_limit" type="number" min="0" step="0.01" placeholder="Optional" /></label>}
          {kind === "cards" && <label className="field"><span>Expiry month</span><ModernSelect name="expiry_month" placeholder="Month" options={Array.from({ length: 12 }, (_, index) => ({ value: String(index + 1), label: String(index + 1).padStart(2, "0") }))} /></label>}
          {kind === "cards" && <label className="field"><span>Expiry year</span><ModernSelect name="expiry_year" placeholder="Year" options={Array.from({ length: 15 }, (_, index) => ({ value: String(new Date().getFullYear() + index), label: String(new Date().getFullYear() + index) }))} /></label>}
          <button className="primary form-action" type="submit"><Plus size={16} />{t(`Add ${kind.slice(0, -1)}`)}</button>
        </form>
      )}
      {editing && (
        <form className="entity-edit-form guided-form" onSubmit={saveEdit}>
          <div className="section-title field-wide"><h2>Edit {editing.entity.slice(0, -1)}</h2><p>Update the details below, then save your changes.</p></div>
          {editing.entity === "banks" && <><label className="field"><span>Bank name</span><input name="name" defaultValue={editing.values.name} required /></label><label className="field"><span>Country</span><input name="country" defaultValue={editing.values.country} /></label></>}
          {editing.entity === "accounts" && <><label className="field"><span>Bank</span><ModernSelect key={`bank-${editing.id}`} name="bank_id" defaultValue={String(editing.values.bank_id)} options={banks.map((bank) => ({ value: String(bank.id), label: bank.name }))} required /></label><label className="field"><span>Account name</span><input name="name" defaultValue={editing.values.name} required /></label><label className="field"><span>Type</span><ModernSelect key={`account-type-${editing.id}`} name="type" defaultValue={String(editing.values.type)} options={[{ value: "checking", label: "Current account" }, { value: "savings", label: "Savings" }, { value: "cash", label: "Cash wallet" }, { value: "brokerage", label: "Brokerage" }, { value: "loan", label: "Loan" }, { value: "mortgage", label: "Mortgage" }, { value: "other", label: "Other" }]} /></label><label className="field"><span>Currency</span><input name="currency" defaultValue={editing.values.currency} maxLength={3} required /></label><label className="field"><span>Current balance</span><input name="current_balance" type="number" step="0.01" defaultValue={editing.values.current_balance} /></label><input type="hidden" name="opening_balance" value={editing.values.opening_balance} /></>}
          {editing.entity === "cards" && <><label className="field"><span>Linked account</span><ModernSelect key={`card-account-${editing.id}`} name="account_id" defaultValue={String(editing.values.account_id)} options={accounts.map((account) => ({ value: String(account.id), label: `${account.name} · ${bankName(account.bank_id)}` }))} required /></label><label className="field"><span>Card name</span><input name="name" defaultValue={editing.values.name} required /></label><label className="field"><span>Type</span><ModernSelect key={`card-type-${editing.id}`} name="type" defaultValue={String(editing.values.type)} options={[{ value: "debit", label: "Debit card" }, { value: "credit", label: "Credit card" }, { value: "prepaid", label: "Prepaid card" }]} /></label><label className="field"><span>Last 4 digits</span><input name="last4" defaultValue={editing.values.last4} pattern="[0-9]{4}" maxLength={4} required /></label><label className="field"><span>Current net activity</span><input name="current_balance" type="number" step="0.01" defaultValue={editing.values.current_balance} /></label><label className="field"><span>Credit / spending limit</span><input name="credit_limit" type="number" min="0" step="0.01" defaultValue={editing.values.credit_limit} /></label><label className="field"><span>Expiry month</span><ModernSelect name="expiry_month" defaultValue={editing.values.expiry_month ? String(editing.values.expiry_month) : ""} placeholder="Month" options={Array.from({ length: 12 }, (_, index) => ({ value: String(index + 1), label: String(index + 1).padStart(2, "0") }))} /></label><label className="field"><span>Expiry year</span><ModernSelect name="expiry_year" defaultValue={editing.values.expiry_year ? String(editing.values.expiry_year) : ""} placeholder="Year" options={Array.from({ length: 15 }, (_, index) => ({ value: String(new Date().getFullYear() + index), label: String(new Date().getFullYear() + index) }))} /></label></>}
          <div className="entity-edit-actions field-wide"><button className="secondary" type="button" onClick={() => setEditing(null)}>Cancel</button><button className="primary" type="submit">Save changes</button></div>
        </form>
      )}
      <section className="managed-entities">
        <div className="section-title"><h2>{t(`Your ${kind}`)}</h2><p>Edit details or archive items you no longer use.</p></div>
        {kind === "banks" ? null : kind === "accounts" ? (
          accounts.length ? <div className="managed-entity-grid">{accounts.map((account) => <article key={account.id}><div><span className="entity-management-icon"><Building2 size={19} /></span><span><strong>{account.name}</strong><small>{bankName(account.bank_id)} · {account.type}</small></span></div><b>{formatMoney(account.current_balance, account.currency)}</b><div className="managed-actions"><button onClick={() => setEditing({ entity: "accounts", id: account.id, values: { bank_id: account.bank_id, name: account.name, type: account.type, currency: account.currency, current_balance: account.current_balance, opening_balance: account.opening_balance || 0 } })}><Pencil size={16} />Edit</button><button className="danger-action" onClick={() => archive("accounts", account.id, account.name)}><Trash2 size={16} />Archive</button></div></article>)}</div> : <p className="muted">No accounts yet.</p>
        ) : cards.length ? <div className="managed-entity-grid">{cards.map((card) => <article key={card.id}><div><span className="entity-management-icon"><CreditCard size={19} /></span><span><strong>{card.name}</strong><small>{accountName(card.account_id)} · {card.type} · •••• {card.last4}{card.expiry_month && card.expiry_year ? ` · expires ${String(card.expiry_month).padStart(2, "0")}/${String(card.expiry_year).slice(-2)}` : ""}</small></span></div><b>{formatMoney(card.current_balance)}</b><div className="managed-actions"><button onClick={() => setEditing({ entity: "cards", id: card.id, values: { account_id: card.account_id, name: card.name, type: card.type, last4: card.last4, current_balance: card.current_balance, credit_limit: card.credit_limit || 0, expiry_month: card.expiry_month || "", expiry_year: card.expiry_year || "" } })}><Pencil size={16} />Edit</button><button className="danger-action" onClick={() => archive("cards", card.id, card.name)}><Trash2 size={16} />Archive</button></div></article>)}</div> : <p className="muted">No cards yet.</p>}
      </section>
    </div>
  );
}

function TransactionView({ token, setMessage }: { token: string; setMessage: (msg: string) => void }) {
  const { t } = useI18n();
  type RecurringItem = { id: number; account_id?: number; card_id?: number; name: string; kind: string; amount: number; currency: string; frequency: string; next_due_date: string; notify_days_before: number };
  const [banks, setBanks] = useState<BankItem[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [cards, setCards] = useState<CardItem[]>([]);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [transactions, setTransactions] = useState<TransactionItem[]>([]);
  const [recurring, setRecurring] = useState<RecurringItem[]>([]);
  const [bankId, setBankId] = useState("");
  const [accountId, setAccountId] = useState("");
  const [transactionType, setTransactionType] = useState<"expense" | "income">("expense");
  const [editingTransaction, setEditingTransaction] = useState<TransactionItem | null>(null);
  const [recurringAccountId, setRecurringAccountId] = useState("");
  const [recurringKind, setRecurringKind] = useState("subscription");
  async function load() {
    const [nextBanks, nextAccounts, nextCards, nextCategories, nextTransactions, nextRecurring] = await Promise.all([
      apiFetch<BankItem[]>("/banks", token),
      apiFetch<AccountItem[]>("/accounts", token),
      apiFetch<CardItem[]>("/cards", token),
      apiFetch<CategoryItem[]>("/categories", token),
      apiFetch<TransactionItem[]>("/transactions", token),
      apiFetch<RecurringItem[]>("/recurring-payments", token)
    ]);
    setBanks(nextBanks);
    setAccounts(nextAccounts);
    setCards(nextCards);
    setCategories(nextCategories);
    setTransactions(nextTransactions);
    setRecurring(nextRecurring);
    setBankId((current) => current || (nextBanks[0] ? String(nextBanks[0].id) : ""));
  }
  useEffect(() => {
    load().catch((error) => setMessage(error instanceof Error ? error.message : "Could not load transactions"));
  }, [token]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    if (!account) return;
    const amount = Math.abs(Number(form.amount));
    try {
      await apiFetch("/transactions", token, {
        method: "POST",
        body: JSON.stringify({
          bank_id: account.bank_id,
          account_id: account.id,
          card_id: form.card_id ? Number(form.card_id) : null,
          date: form.date,
          description: form.description,
          amount: form.type === "expense" ? -amount : amount,
          currency: account.currency,
          type: form.type,
          category_id: form.category_id ? Number(form.category_id) : null
        })
      });
      formElement.reset();
      setAccountId("");
      setTransactionType("expense");
      setMessage("Transaction saved");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save transaction");
    }
  }
  async function addRecurring(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    try {
      await apiFetch("/recurring-payments", token, {
        method: "POST",
        body: JSON.stringify({
          account_id: account?.id || null,
          card_id: form.card_id ? Number(form.card_id) : null,
          name: form.name,
          kind: form.kind,
          amount: Number(form.amount),
          currency: account?.currency || "EUR",
          frequency: form.frequency,
          next_due_date: form.next_due_date,
          notify_days_before: Number(form.notify_days_before || 3)
        })
      });
      formElement.reset();
      setRecurringAccountId("");
      setRecurringKind("subscription");
      setMessage(form.kind === "income" ? "Recurring revenue saved" : "Recurring payment saved");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save recurring payment");
    }
  }
  async function saveTransactionEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingTransaction) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    if (!account) return;
    const amount = Math.abs(Number(form.amount));
    try {
      await apiFetch(`/transactions/${editingTransaction.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({
          bank_id: account.bank_id,
          account_id: account.id,
          card_id: form.card_id ? Number(form.card_id) : null,
          category_id: form.category_id ? Number(form.category_id) : null,
          date: form.date,
          description: form.description,
          amount: form.type === "expense" ? -amount : amount,
          currency: account.currency,
          type: form.type
        })
      });
      setEditingTransaction(null);
      setMessage("Transaction updated and balance recalculated");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update transaction");
    }
  }
  async function removeTransaction(transaction: TransactionItem) {
    if (!window.confirm(`Delete "${transaction.description}"? Its balance effect will be reversed.`)) return;
    try {
      await apiFetch(`/transactions/${transaction.id}`, token, { method: "DELETE" });
      setEditingTransaction(null);
      setMessage("Transaction deleted and balance recalculated");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete transaction");
    }
  }
  async function sendReminders() {
    try {
      const result = await apiFetch<{ count: number }>("/recurring-payments/send-due", token, { method: "POST" });
      setMessage(result.count ? `${result.count} reminder email(s) sent` : "No reminders are due today");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not send reminders");
    }
  }
  async function removeRecurring(item: RecurringItem) {
    if (!window.confirm(`Remove recurring item "${item.name}"?`)) return;
    try {
      await apiFetch(`/recurring-payments/${item.id}`, token, { method: "DELETE" });
      setMessage("Recurring item removed");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not remove recurring item");
    }
  }
  const bankAccounts = accounts.filter((account) => account.bank_id === Number(bankId));
  const bankTransactions = transactions.filter((transaction) => transaction.bank_id === Number(bankId));
  const matchingCategories = categories.filter((category) => category.type === transactionType);
  const categoryName = (categoryId?: number) => categories.find((category) => category.id === categoryId)?.name || "Uncategorized";
  return (
    <div className="page-grid transactions-page">
      <div className="page-heading"><h1>{t("Transactions")}</h1><p>{t("Choose a bank first, then record or review its activity.")}</p></div>
      <section className="transaction-bank-picker">
        <span>{t("Working with")}</span>
        <ModernSelect value={bankId} onValueChange={(value) => { setBankId(value); setAccountId(""); }} placeholder="Choose a bank" options={banks.map((bank) => ({ value: String(bank.id), label: bank.name }))} />
      </section>
      {bankAccounts.length === 0 ? (
        <section className="setup-callout"><strong>Add an account for this bank first</strong><span>Transactions need an account belonging to the selected bank.</span></section>
      ) : (
        <form className="inline-form guided-form" onSubmit={submit}>
          <label className="field"><span>{t("Flow")}</span><ModernSelect name="type" value={transactionType} onValueChange={(value) => setTransactionType(value as "expense" | "income")} options={[{ value: "expense", label: t("Money out") }, { value: "income", label: t("Money in") }]} /></label>
          <label className="field"><span>{t("Account")}</span><ModernSelect name="account_id" value={accountId} onValueChange={setAccountId} required placeholder="Choose account" options={bankAccounts.map((account) => ({ value: String(account.id), label: account.name }))} /></label>
          <label className="field"><span>Card used (optional)</span><ModernSelect name="card_id" disabled={!accountId} defaultValue="" options={[{ value: "", label: "No card / bank transfer" }, ...cards.filter((card) => card.account_id === Number(accountId)).map((card) => ({ value: String(card.id), label: `${card.name} · •••• ${card.last4}` }))]} /></label>
          <label className="field"><span>{t("Category")}</span><ModernSelect name="category_id" required placeholder={`Choose ${transactionType} category`} options={matchingCategories.map((category) => ({ value: String(category.id), label: category.name }))} /></label>
          <label className="field"><span>{t("Date")}</span><ModernDateInput name="date" defaultValue={formatDateValue(new Date())} required /></label>
          <label className="field field-wide"><span>{t("Description")}</span><input name="description" placeholder="e.g. Grocery shopping or Salary" required /></label>
          <label className="field"><span>{t("Amount")}</span><input name="amount" type="number" min="0.01" step="0.01" placeholder="0.00" required /></label>
          <button className="primary form-action" type="submit"><Plus size={16} />{t("Save transaction")}</button>
        </form>
      )}
      {editingTransaction && (
        <form className="entity-edit-form guided-form" onSubmit={saveTransactionEdit}>
          <div className="section-title field-wide"><h2>Edit transaction</h2><p>The old balance effect is reversed automatically before applying these changes.</p></div>
          <label className="field"><span>Flow</span><ModernSelect name="type" defaultValue={Number(editingTransaction.amount) < 0 ? "expense" : "income"} options={[{ value: "expense", label: "Money out" }, { value: "income", label: "Money in" }]} /></label>
          <label className="field"><span>Account</span><ModernSelect name="account_id" defaultValue={String(editingTransaction.account_id)} options={bankAccounts.map((account) => ({ value: String(account.id), label: account.name }))} required /></label>
          <label className="field"><span>Card</span><ModernSelect name="card_id" defaultValue={editingTransaction.card_id ? String(editingTransaction.card_id) : ""} options={[{ value: "", label: "No card / bank transfer" }, ...cards.filter((card) => card.bank_id === Number(bankId)).map((card) => ({ value: String(card.id), label: `${card.name} · •••• ${card.last4}` }))]} /></label>
          <label className="field"><span>Category</span><ModernSelect name="category_id" defaultValue={editingTransaction.category_id ? String(editingTransaction.category_id) : ""} options={categories.filter((category) => category.type === (Number(editingTransaction.amount) < 0 ? "expense" : "income")).map((category) => ({ value: String(category.id), label: category.name }))} required /></label>
          <label className="field"><span>Date</span><ModernDateInput name="date" defaultValue={editingTransaction.date} required /></label>
          <label className="field field-wide"><span>Description</span><input name="description" defaultValue={editingTransaction.description} required /></label>
          <label className="field"><span>Amount</span><input name="amount" type="number" min="0.01" step="0.01" defaultValue={Math.abs(Number(editingTransaction.amount))} required /></label>
          <div className="entity-edit-actions field-wide"><button type="button" className="secondary" onClick={() => setEditingTransaction(null)}>Cancel</button><button className="primary" type="submit">Save changes</button></div>
        </form>
      )}
      <section className="transaction-management">
        <div className="section-title"><h2>{banks.find((bank) => bank.id === Number(bankId))?.name || "Bank"} activity</h2><p>Edit or delete manual transactions; investment-linked activity stays managed from Investments.</p></div>
        {bankTransactions.length ? <div className="transaction-list">{bankTransactions.slice(0, 50).map((transaction) => <article key={transaction.id}><span><strong>{transaction.description}</strong><small>{transaction.date} · {categoryName(transaction.category_id)} · {accounts.find((account) => account.id === transaction.account_id)?.name || "Account"}</small></span><b className={Number(transaction.amount) >= 0 ? "positive" : "negative"}>{formatMoney(transaction.amount, transaction.currency)}</b>{transaction.source === "investment" ? <em>Managed in Investments</em> : <div><button onClick={() => setEditingTransaction(transaction)}><Pencil size={15} />Edit</button><button className="danger-action" onClick={() => removeTransaction(transaction)}><Trash2 size={15} />Delete</button></div>}</article>)}</div> : <p className="muted">No transactions for this bank yet.</p>}
      </section>
      <section className="module-section">
        <div className="section-title action-title"><div><h2>{t("Recurring cash flow")}</h2><p>Add salaries and recurring revenues alongside subscriptions and bills. They feed your Overview forecast.</p></div><button className="secondary" type="button" onClick={sendReminders}>Send due reminders</button></div>
        <form className="inline-form guided-form" onSubmit={addRecurring}>
          <label className="field"><span>Name</span><input name="name" placeholder={recurringKind === "income" ? "e.g. Monthly salary" : "e.g. Netflix"} required /></label>
          <label className="field"><span>Type</span><ModernSelect name="kind" value={recurringKind} onValueChange={setRecurringKind} options={[{ value: "income", label: t("Recurring revenue") }, { value: "subscription", label: t("Subscription") }, { value: "bill", label: t("Recurring bill") }, { value: "payment", label: t("Recurring payment") }]} /></label>
          <label className="field"><span>Account</span><ModernSelect name="account_id" value={recurringAccountId} onValueChange={setRecurringAccountId} options={[{ value: "", label: "No linked account" }, ...accounts.map((account) => ({ value: String(account.id), label: account.name }))]} /></label>
          <label className="field"><span>Card (optional)</span><ModernSelect name="card_id" disabled={!recurringAccountId || recurringKind === "income"} options={[{ value: "", label: "No card" }, ...cards.filter((card) => card.account_id === Number(recurringAccountId)).map((card) => ({ value: String(card.id), label: `${card.name} · •••• ${card.last4}` }))]} /></label>
          <label className="field"><span>{t("Amount")}</span><input name="amount" type="number" min="0" step="0.01" required /></label>
          <label className="field"><span>{t("Frequency")}</span><ModernSelect name="frequency" defaultValue="monthly" options={[{ value: "weekly", label: "Weekly" }, { value: "monthly", label: "Monthly" }, { value: "quarterly", label: "Quarterly" }, { value: "yearly", label: "Yearly" }]} /></label>
          <label className="field"><span>{t("Next due date")}</span><ModernDateInput name="next_due_date" required /></label>
          <label className="field"><span>Remind me before</span><ModernSelect name="notify_days_before" defaultValue="3" options={[{ value: "1", label: "1 day" }, { value: "3", label: "3 days" }, { value: "7", label: "7 days" }]} /></label>
          <button className="primary form-action" type="submit"><Plus size={16} />Add {recurringKind === "income" ? "revenue" : "payment"}</button>
        </form>
        <div className="recurring-list">
          <h3>{t("Upcoming recurring movements")}</h3>
          {recurring.length ? recurring.map((item) => {
            const isIncome = ["income", "revenue", "salary"].includes(item.kind);
            return <article key={item.id}><span className={`forecast-flow ${isIncome ? "income" : "expense"}`}>{isIncome ? <ArrowDownRight size={16} /> : <ArrowUpRight size={16} />}</span><span><strong>{item.name}</strong><small>{item.next_due_date} · {item.frequency} · {item.notify_days_before}-day reminder</small></span><b className={isIncome ? "positive" : "negative"}>{isIncome ? "+" : "−"}{formatMoney(item.amount, item.currency)}</b><button className="danger-action" onClick={() => removeRecurring(item)} title="Remove recurring item"><Trash2 size={16} /></button></article>;
          }) : <p className="muted">No recurring revenues or payments yet.</p>}
        </div>
      </section>
    </div>
  );
}

function ImportView({ token, setMessage }: { token: string; setMessage: (msg: string) => void }) {
  const [batchId, setBatchId] = useState<number | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  useEffect(() => {
    apiFetch<AccountItem[]>("/accounts", token).then(setAccounts).catch(() => undefined);
  }, [token]);
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const result = await apiFetch<{ batch_id: number; columns: string[] }>("/imports/upload", token, { method: "POST", body: data });
    setBatchId(result.batch_id);
    setColumns(result.columns);
    setMessage("File uploaded. Map the columns next.");
  }
  async function map(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!batchId) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const account = accounts.find((item) => item.id === Number(form.account_id));
    if (!account) {
      setMessage("Choose an account for this statement");
      return;
    }
    const result = await apiFetch<any>(`/imports/${batchId}/map`, token, {
      method: "POST",
      body: JSON.stringify({
        bank_id: account.bank_id,
        account_id: account.id,
        mapping: { date: form.date, description: form.description, amount: form.amount, currency: form.currency || null },
        decimal_separator: form.decimal_separator || ".",
        save_template_name: form.save_template_name || null
      })
    });
    setMessage(`Ready: ${result.ready_rows}, duplicates: ${result.duplicate_rows}, errors: ${result.error_rows}`);
  }
  async function confirm() {
    if (!batchId) return;
    const result = await apiFetch<any>(`/imports/${batchId}/confirm`, token, { method: "POST" });
    setMessage(`Imported ${result.imported_rows} transactions`);
  }
  async function cancel() {
    if (!batchId) return;
    await apiFetch(`/imports/${batchId}`, token, { method: "DELETE" });
    setBatchId(null);
    setColumns([]);
    setMessage("Import cancelled");
  }
  return (
    <div className="page-grid">
      <h1>Import center</h1>
      <p className="section-intro">Upload a CSV or Excel statement, then tell Money Manager which columns contain the date, description, and amount.</p>
      {accounts.length === 0 && <section className="setup-callout"><strong>An account is required</strong><span>Create the account represented by this statement before importing it.</span></section>}
      <form className="dropzone" onSubmit={upload}>
        <FileUp size={34} />
        <input name="file" type="file" accept=".csv,.xlsx,.xls" required />
        <button className="primary" type="submit">Upload statement</button>
      </form>
      {batchId && (
        <form className="inline-form" onSubmit={map}>
          <label className="field"><span>Import into</span><ModernSelect name="account_id" required placeholder="Choose an account" options={accounts.map((account) => ({ value: String(account.id), label: account.name }))} /></label>
          {["date", "description", "amount", "currency"].map((name) => (
            <label className="field" key={name}><span>{name[0].toUpperCase() + name.slice(1)} column</span><ModernSelect name={name} required={name !== "currency"} placeholder="Choose column" options={columns.map((column) => ({ value: column, label: column }))} /></label>
          ))}
          <label className="field"><span>Decimal style</span><ModernSelect name="decimal_separator" defaultValue="." options={[{ value: ".", label: "Decimal dot · 1,234.56" }, { value: ",", label: "Decimal comma · 1.234,56" }]} /></label>
          <label className="field"><span>Save mapping as (optional)</span><input name="save_template_name" placeholder="e.g. Monthly statement" /></label>
          <button className="secondary" type="submit">Preview mapping</button>
          <button className="primary" type="button" onClick={confirm}>Confirm import</button>
          <button className="secondary" type="button" onClick={cancel}>Cancel</button>
        </form>
      )}
    </div>
  );
}

function SimplifiedInvestmentView({ token, setMessage }: { token: string; setMessage: (msg: string) => void }) {
  const { t } = useI18n();
  type PortfolioItem = { id: number; name: string; currency: string };
  type InvestmentSummaryItem = {
    portfolio_id: number;
    portfolio_name: string;
    currency: string;
    total_invested: number;
    withdrawn: number;
    net_invested: number;
    worth_today: number;
    profit_loss: number;
    profit_percent: number;
  };
  const [portfolios, setPortfolios] = useState<PortfolioItem[]>([]);
  const [summaries, setSummaries] = useState<InvestmentSummaryItem[]>([]);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState("");
  const [editingPortfolio, setEditingPortfolio] = useState<PortfolioItem | null>(null);

  async function load(preferredPortfolioId?: string) {
    const [nextPortfolios, nextSummaries] = await Promise.all([
      apiFetch<PortfolioItem[]>("/investments/portfolios", token),
      apiFetch<InvestmentSummaryItem[]>("/investments/summaries", token)
    ]);
    setPortfolios(nextPortfolios);
    setSummaries(nextSummaries);
    const candidate = preferredPortfolioId || selectedPortfolioId;
    setSelectedPortfolioId(candidate && nextPortfolios.some((portfolio) => String(portfolio.id) === candidate) ? candidate : nextPortfolios[0] ? String(nextPortfolios[0].id) : "");
  }

  useEffect(() => {
    load().catch((error) => setMessage(error instanceof Error ? error.message : "Could not load investments"));
  }, [token]);

  async function saveSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPortfolioId) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await apiFetch(`/investments/portfolios/${selectedPortfolioId}/summary`, token, {
        method: "PUT",
        body: JSON.stringify({
          data: {
            total_invested: Number(form.total_invested),
            net_invested: Number(form.net_invested),
            worth_today: Number(form.worth_today)
          }
        })
      });
      setMessage("Investment totals saved");
      await load(selectedPortfolioId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save investment totals");
    }
  }

  async function addPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    try {
      const created = await apiFetch<PortfolioItem>("/investments/portfolios", token, {
        method: "POST",
        body: JSON.stringify({ data: { name: form.name, currency: form.currency } })
      });
      formElement.reset();
      setMessage("Portfolio created");
      await load(String(created.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create portfolio");
    }
  }

  async function savePortfolioEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingPortfolio) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await apiFetch(`/investments/portfolios/${editingPortfolio.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({ data: { name: form.name, currency: form.currency } })
      });
      setEditingPortfolio(null);
      setMessage("Portfolio updated");
      await load(String(editingPortfolio.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update portfolio");
    }
  }

  async function removePortfolio(portfolio: PortfolioItem) {
    if (!window.confirm(`Delete ${portfolio.name}?`)) return;
    try {
      await apiFetch(`/investments/portfolios/${portfolio.id}`, token, { method: "DELETE" });
      setEditingPortfolio(null);
      setMessage("Portfolio deleted");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete portfolio");
    }
  }

  const selectedSummary = summaries.find((summary) => String(summary.portfolio_id) === selectedPortfolioId);
  const currencyOptions = [{ value: "EUR", label: "EUR — Euro" }, { value: "USD", label: "USD — US Dollar" }, { value: "GBP", label: "GBP — British Pound" }, { value: "CHF", label: "CHF — Swiss Franc" }];
  return (
    <div className="page-grid simple-investments">
      <div className="page-heading"><h1>{t("Investments")}</h1><p>Keep the numbers that matter visible. The rest is calculated automatically.</p></div>

      {portfolios.length > 0 && selectedSummary && (
        <section className="investment-summary-hero">
          <div className="investment-summary-heading">
            <div><span>Selected portfolio</span><h2>{selectedSummary.portfolio_name}</h2></div>
            <ModernSelect value={selectedPortfolioId} onValueChange={setSelectedPortfolioId} options={portfolios.map((portfolio) => ({ value: String(portfolio.id), label: portfolio.name }))} />
          </div>
          <div className="investment-metric-grid">
            <article><span>{t("Total invested")}</span><strong>{formatMoney(selectedSummary.total_invested, selectedSummary.currency)}</strong></article>
            <article><span>{t("Withdrawn")}</span><strong>{formatMoney(selectedSummary.withdrawn, selectedSummary.currency)}</strong><small>Calculated from total minus net invested</small></article>
            <article className="metric-primary"><span>{t("Total − withdrawn")}</span><strong>{formatMoney(selectedSummary.net_invested, selectedSummary.currency)}</strong></article>
            <article className="metric-primary"><span>{t("Worth today")}</span><strong>{formatMoney(selectedSummary.worth_today, selectedSummary.currency)}</strong></article>
            <article><span>{t("Profit / loss")}</span><strong className={selectedSummary.profit_loss >= 0 ? "positive" : "negative"}>{formatMoney(selectedSummary.profit_loss, selectedSummary.currency)}</strong></article>
            <article><span>{t("% of profit")}</span><strong className={selectedSummary.profit_percent >= 0 ? "positive" : "negative"}>{selectedSummary.profit_percent >= 0 ? "+" : ""}{Number(selectedSummary.profit_percent).toFixed(2)}%</strong></article>
          </div>
        </section>
      )}

      <section className="module-section investment-editor">
        <div className="section-title"><div><h2>{t("Update investment totals")}</h2><p>Enter three values. Withdrawn, profit/loss, and profit percentage are worked out for you.</p></div></div>
        {portfolios.length ? (
          <form className="inline-form guided-form" key={selectedPortfolioId} onSubmit={saveSummary}>
            <label className="field field-wide"><span>Portfolio</span><ModernSelect value={selectedPortfolioId} onValueChange={setSelectedPortfolioId} options={portfolios.map((portfolio) => ({ value: String(portfolio.id), label: portfolio.name }))} /></label>
            <label className="field"><span>{t("Total invested")}</span><input name="total_invested" type="number" min="0" step="0.01" defaultValue={selectedSummary?.total_invested || 0} required /><small className="field-help">Everything you have deposited over time.</small></label>
            <label className="field"><span>{t("Total − withdrawn")}</span><input name="net_invested" type="number" min="0" step="0.01" defaultValue={selectedSummary?.net_invested || 0} required /><small className="field-help">The amount of your own money still invested.</small></label>
            <label className="field"><span>{t("Worth today")}</span><input name="worth_today" type="number" min="0" step="0.01" defaultValue={selectedSummary?.worth_today || 0} required /><small className="field-help">The portfolio’s current market value.</small></label>
            <button className="primary form-action" type="submit">{t("Save totals")}</button>
          </form>
        ) : <div className="setup-callout"><strong>Create a portfolio first</strong><span>Then you can enter its investment totals.</span></div>}
        <div className="investment-formula-note">
          <span><b>Withdrawn</b> = total invested − net invested</span>
          <span><b>Profit / loss</b> = worth today − net invested</span>
          <span><b>Profit %</b> = profit or loss ÷ net invested</span>
        </div>
      </section>

      <section className="module-section">
        <div className="section-title"><div><h2>{t("Portfolios")}</h2><p>Create a separate summary for every broker or investment goal.</p></div></div>
        <form className="inline-form compact-form" onSubmit={addPortfolio}>
          <label className="field"><span>{t("Portfolio name")}</span><input name="name" placeholder="e.g. Long-term investing" required /></label>
          <label className="field"><span>Currency</span><ModernSelect name="currency" defaultValue="EUR" options={currencyOptions} /></label>
          <button className="primary form-action" type="submit"><Plus size={16} />{t("Create portfolio")}</button>
        </form>
        {portfolios.length > 0 && <div className="portfolio-management">{portfolios.map((portfolio) => <article key={portfolio.id}><span><LineChart size={18} /><span><strong>{portfolio.name}</strong><small>{portfolio.currency}</small></span></span><div><button onClick={() => { setSelectedPortfolioId(String(portfolio.id)); setEditingPortfolio(portfolio); }}><Pencil size={15} />Edit</button><button className="danger-action" onClick={() => removePortfolio(portfolio)}><Trash2 size={15} />Delete</button></div></article>)}</div>}
        {editingPortfolio && <form className="entity-edit-form compact-form" onSubmit={savePortfolioEdit}><label className="field"><span>Portfolio name</span><input name="name" defaultValue={editingPortfolio.name} required /></label><label className="field"><span>Currency</span><ModernSelect name="currency" defaultValue={editingPortfolio.currency} options={currencyOptions} /></label><div className="entity-edit-actions"><button type="button" className="secondary" onClick={() => setEditingPortfolio(null)}>Cancel</button><button className="primary" type="submit">Save portfolio</button></div></form>}
      </section>
    </div>
  );
}

function InvestmentView({ token, setMessage }: { token: string; setMessage: (msg: string) => void }) {
  type PortfolioItem = { id: number; name: string; currency: string };
  type AssetItem = { id: number; symbol: string; name: string; asset_type: string; currency: string };
  type HoldingRow = { id: number; portfolio: string; symbol: string; name: string; quantity: number; average_price: number; current_price: number; value: number; cost: number; currency: string };
  type InvestmentActivity = { id: number; portfolio_id: number; asset_id: number; account_id?: number; date: string; type: "buy" | "sell"; quantity: number; price: number; fees: number; taxes: number; currency: string };
  const [portfolios, setPortfolios] = useState<PortfolioItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [holdings, setHoldings] = useState<HoldingRow[]>([]);
  const [banks, setBanks] = useState<BankItem[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [fundingAccountId, setFundingAccountId] = useState("");
  const [investmentSymbol, setInvestmentSymbol] = useState("");
  const [investmentName, setInvestmentName] = useState("");
  const [investmentPrice, setInvestmentPrice] = useState("");
  const [investmentQuantity, setInvestmentQuantity] = useState("");
  const [investmentFees, setInvestmentFees] = useState("0");
  const [tradingCurrency, setTradingCurrency] = useState("USD");
  const [activities, setActivities] = useState<InvestmentActivity[]>([]);
  const [editingPortfolio, setEditingPortfolio] = useState<PortfolioItem | null>(null);
  const [editingActivity, setEditingActivity] = useState<InvestmentActivity | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [liveQuote, setLiveQuote] = useState<{ symbol: string; current: number; change: number; percent_change: number; high: number; low: number } | null>(null);

  async function load() {
    const [nextPortfolios, nextAssets, report, nextBanks, nextAccounts, nextActivities] = await Promise.all([
      apiFetch<PortfolioItem[]>("/investments/portfolios", token),
      apiFetch<AssetItem[]>("/investments/assets", token),
      apiFetch<{ holdings: HoldingRow[] }>("/reports/investments", token),
      apiFetch<BankItem[]>("/banks", token),
      apiFetch<AccountItem[]>("/accounts", token),
      apiFetch<InvestmentActivity[]>("/investments/transactions", token)
    ]);
    setPortfolios(nextPortfolios);
    setAssets(nextAssets);
    setHoldings(report.holdings);
    setBanks(nextBanks);
    setAccounts(nextAccounts);
    setActivities(nextActivities);
    setFundingAccountId((current) => current || (nextAccounts[0] ? String(nextAccounts[0].id) : ""));
  }
  useEffect(() => {
    load().catch((error) => setMessage(error instanceof Error ? error.message : "Could not load investments"));
  }, [token]);

  async function addPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    try {
      await apiFetch("/investments/portfolios", token, {
        method: "POST",
        body: JSON.stringify({ data: { name: form.name, currency: form.currency || "EUR" } })
      });
      formElement.reset();
      setMessage("Portfolio created");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create portfolio");
    }
  }

  async function savePortfolioEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingPortfolio) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await apiFetch(`/investments/portfolios/${editingPortfolio.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({ data: { name: form.name, currency: form.currency } })
      });
      setEditingPortfolio(null);
      setMessage("Portfolio updated");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update portfolio");
    }
  }

  async function removePortfolio(portfolio: PortfolioItem) {
    if (!window.confirm(`Delete ${portfolio.name}? Empty portfolios can be deleted immediately.`)) return;
    try {
      await apiFetch(`/investments/portfolios/${portfolio.id}`, token, { method: "DELETE" });
      setEditingPortfolio(null);
      setMessage("Portfolio deleted");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete portfolio");
    }
  }

  async function addInvestment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    try {
      const symbol = String(form.symbol).trim().toUpperCase();
      let asset = assets.find((item) => item.symbol.toUpperCase() === symbol);
      if (!asset) {
        asset = await apiFetch<AssetItem>("/investments/assets", token, {
          method: "POST",
          body: JSON.stringify({ data: { symbol, name: form.asset_name, asset_type: form.asset_type, currency: form.currency || "EUR" } })
        });
      }
      await apiFetch("/investments/transactions", token, {
        method: "POST",
        body: JSON.stringify({
          data: {
            portfolio_id: Number(form.portfolio_id),
            asset_id: asset.id,
            account_id: Number(form.account_id),
            date: form.date,
            type: form.type,
            quantity: Number(form.quantity),
            price: Number(form.price),
            fees: Number(form.fees || 0),
            currency: form.currency || "EUR"
          }
        })
      });
      formElement.reset();
      setInvestmentSymbol("");
      setInvestmentName("");
      setInvestmentPrice("");
      setInvestmentQuantity("");
      setInvestmentFees("0");
      setLiveQuote(null);
      setMessage("Investment activity saved");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save investment");
    }
  }

  async function refreshMarketPrices() {
    try {
      const result = await apiFetch<{ updated: Array<{ symbol: string }>; errors: Array<{ symbol: string }> }>("/investments/refresh-prices", token, { method: "POST" });
      setMessage(`Updated ${result.updated.length} live price(s)${result.errors.length ? `; ${result.errors.length} unavailable` : ""}`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not refresh market prices");
    }
  }

  async function saveActivityEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingActivity) return;
    const form = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await apiFetch(`/investments/transactions/${editingActivity.id}`, token, {
        method: "PATCH",
        body: JSON.stringify({
          data: {
            portfolio_id: Number(form.portfolio_id),
            asset_id: editingActivity.asset_id,
            account_id: Number(form.account_id),
            date: form.date,
            type: form.type,
            quantity: Number(form.quantity),
            price: Number(form.price),
            fees: Number(form.fees || 0),
            taxes: Number(form.taxes || 0),
            currency: form.currency
          }
        })
      });
      setEditingActivity(null);
      setMessage("Investment activity updated; holdings and cash were recalculated");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not update investment activity");
    }
  }

  async function removeActivity(activity: InvestmentActivity) {
    const asset = assets.find((item) => item.id === activity.asset_id);
    if (!window.confirm(`Delete this ${activity.type} of ${asset?.symbol || "investment"}? Cash and holdings will be recalculated.`)) return;
    try {
      await apiFetch(`/investments/transactions/${activity.id}`, token, { method: "DELETE" });
      setEditingActivity(null);
      setMessage("Investment activity deleted; holdings and cash were recalculated");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete investment activity");
    }
  }

  async function lookupQuote(symbol = investmentSymbol) {
    const cleanSymbol = symbol.trim().toUpperCase();
    if (!cleanSymbol) {
      setMessage("Enter a market symbol first");
      return;
    }
    setQuoteLoading(true);
    try {
      const quote = await apiFetch<{ symbol: string; current: number; change: number; percent_change: number; high: number; low: number }>(`/market/quote/${encodeURIComponent(cleanSymbol)}`, token);
      setInvestmentSymbol(quote.symbol);
      const knownAsset = assets.find((asset) => asset.symbol.toUpperCase() === quote.symbol);
      if (knownAsset) setInvestmentName(knownAsset.name);
      setInvestmentPrice(String(quote.current));
      setLiveQuote(quote);
      setMessage(`Live Finnhub price loaded for ${quote.symbol}`);
    } catch (error) {
      setLiveQuote(null);
      setMessage(error instanceof Error ? error.message : "Could not load the live price");
    } finally {
      setQuoteLoading(false);
    }
  }

  const totalValue = holdings.reduce((sum, holding) => sum + Number(holding.value), 0);
  const totalCost = holdings.reduce((sum, holding) => sum + Number(holding.cost), 0);
  const fundingAccount = accounts.find((account) => account.id === Number(fundingAccountId));
  const estimatedCash = Number(investmentQuantity || 0) * Number(investmentPrice || 0) + Number(investmentFees || 0);
  const bankName = (bankId: number) => banks.find((bank) => bank.id === bankId)?.name || "Bank";
  return (
    <div className="page-grid">
      <div className="page-heading action-title"><div><h1>Investments</h1><p>Track what you own and refresh current stock prices through Finnhub.</p></div><button className="secondary" onClick={refreshMarketPrices}><LineChart size={16} />Refresh live prices</button></div>
      <section className="summary-strip">
        <div><span>Portfolio value</span><strong>{formatMoney(totalValue)}</strong></div>
        <div><span>Cost basis</span><strong>{formatMoney(totalCost)}</strong></div>
        <div><span>Gain / loss</span><strong className={totalValue - totalCost >= 0 ? "positive" : "negative"}>{formatMoney(totalValue - totalCost)}</strong></div>
      </section>
      <section className="module-section">
        <div className="section-title"><div><h2>1. Portfolios</h2><p>Create one for each broker or investment goal.</p></div></div>
        <form className="inline-form compact-form" onSubmit={addPortfolio}>
          <label className="field"><span>Portfolio name</span><input name="name" placeholder="e.g. Long-term investing" required /></label>
          <label className="field"><span>Currency</span><ModernSelect name="currency" defaultValue="EUR" options={[{ value: "EUR", label: "EUR — Euro" }, { value: "USD", label: "USD — US Dollar" }, { value: "GBP", label: "GBP — British Pound" }, { value: "CHF", label: "CHF — Swiss Franc" }]} /></label>
          <button className="primary form-action" type="submit"><Plus size={16} />Create portfolio</button>
        </form>
        {portfolios.length > 0 && <div className="portfolio-management">{portfolios.map((portfolio) => <article key={portfolio.id}><span><LineChart size={18} /><span><strong>{portfolio.name}</strong><small>{portfolio.currency}</small></span></span><div><button onClick={() => setEditingPortfolio(portfolio)}><Pencil size={15} />Edit</button><button className="danger-action" onClick={() => removePortfolio(portfolio)}><Trash2 size={15} />Delete</button></div></article>)}</div>}
        {editingPortfolio && <form className="entity-edit-form compact-form" onSubmit={savePortfolioEdit}><label className="field"><span>Portfolio name</span><input name="name" defaultValue={editingPortfolio.name} required /></label><label className="field"><span>Currency</span><ModernSelect name="currency" defaultValue={editingPortfolio.currency} options={[{ value: "EUR", label: "EUR — Euro" }, { value: "USD", label: "USD — US Dollar" }, { value: "GBP", label: "GBP — British Pound" }, { value: "CHF", label: "CHF — Swiss Franc" }]} /></label><div className="entity-edit-actions"><button type="button" className="secondary" onClick={() => setEditingPortfolio(null)}>Cancel</button><button className="primary" type="submit">Save portfolio</button></div></form>}
      </section>
      <section className="module-section">
        <div className="section-title"><div><h2>2. Record a purchase or sale</h2><p>The symbol identifies the investment; existing symbols are reused automatically.</p></div></div>
        {portfolios.length === 0 ? <div className="setup-callout"><strong>Create a portfolio first</strong><span>Then you can add funds, shares, bonds, or crypto to it.</span></div> : (
          <form className="inline-form guided-form" onSubmit={addInvestment}>
            <label className="field field-wide investment-funding-field"><span>Money comes from</span><ModernSelect name="account_id" value={fundingAccountId} onValueChange={setFundingAccountId} required placeholder="Choose the funding account" options={accounts.map((account) => ({ value: String(account.id), label: `${account.name} · ${bankName(account.bank_id)} · ${formatMoney(account.current_balance, account.currency)}` }))} /><small className="field-help">Buying deducts money from this account; selling adds the proceeds back.</small></label>
            <label className="field"><span>Portfolio</span><ModernSelect name="portfolio_id" required placeholder="Choose portfolio" options={portfolios.map((portfolio) => ({ value: String(portfolio.id), label: portfolio.name }))} /></label>
            <label className="field"><span>Action</span><ModernSelect name="type" defaultValue="buy" options={[{ value: "buy", label: "Buy" }, { value: "sell", label: "Sell" }]} /></label>
            <label className="field"><span>Market symbol</span><span className="quote-input"><input name="symbol" list="asset-symbols" placeholder="e.g. AAPL" value={investmentSymbol} onChange={(event) => { const symbol = event.target.value.toUpperCase(); setInvestmentSymbol(symbol); const known = assets.find((asset) => asset.symbol.toUpperCase() === symbol); if (known) setInvestmentName(known.name); setLiveQuote(null); }} onBlur={() => investmentSymbol && lookupQuote()} required /><button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => lookupQuote()} disabled={quoteLoading}><Sparkles size={17} />{quoteLoading ? "Loading" : "Live price"}</button></span><datalist id="asset-symbols">{assets.map((asset) => <option key={asset.id} value={asset.symbol}>{asset.name}</option>)}</datalist></label>
            <label className="field"><span>Investment name</span><input name="asset_name" value={investmentName} onChange={(event) => setInvestmentName(event.target.value)} placeholder="e.g. Apple or Vanguard FTSE All-World" required /></label>
            <label className="field"><span>Type</span><ModernSelect name="asset_type" defaultValue="stock" options={[{ value: "stock", label: "Share" }, { value: "etf", label: "ETF / fund" }, { value: "bond", label: "Bond" }, { value: "crypto", label: "Crypto" }, { value: "other", label: "Other" }]} /></label>
            <label className="field"><span>Date</span><ModernDateInput name="date" defaultValue={formatDateValue(new Date())} required /></label>
            <label className="field"><span>Quantity</span><input name="quantity" type="number" min="0.000001" step="0.000001" value={investmentQuantity} onChange={(event) => setInvestmentQuantity(event.target.value)} required /></label>
            <label className="field"><span>Price per unit</span><input name="price" type="number" min="0" step="0.0001" value={investmentPrice} onChange={(event) => setInvestmentPrice(event.target.value)} placeholder="Loaded from Finnhub" required />{liveQuote && <small className="live-quote">Finnhub: {formatMoney(liveQuote.current, "USD")} · {liveQuote.percent_change >= 0 ? "+" : ""}{Number(liveQuote.percent_change).toFixed(2)}% today</small>}</label>
            <label className="field"><span>Fees</span><input name="fees" type="number" min="0" step="0.01" value={investmentFees} onChange={(event) => setInvestmentFees(event.target.value)} /></label>
            <label className="field"><span>Trading currency</span><ModernSelect name="currency" value={tradingCurrency} onValueChange={setTradingCurrency} options={[{ value: "USD", label: "USD — US Dollar" }, { value: "EUR", label: "EUR — Euro" }, { value: "GBP", label: "GBP — British Pound" }, { value: "CHF", label: "CHF — Swiss Franc" }]} /></label>
            <div className="investment-cash-preview field-wide"><span>Estimated cash movement</span><strong>{formatMoney(estimatedCash, tradingCurrency)}</strong><small>{fundingAccount ? fundingAccount.currency === tradingCurrency ? `From ${fundingAccount.name}` : `Converted using a live FX rate into ${fundingAccount.currency} for ${fundingAccount.name}` : "Choose a funding account"}</small></div>
            <button className="primary form-action" type="submit">Save activity</button>
          </form>
        )}
      </section>
      <DataPanel title="Current holdings" rows={holdings.map((holding) => [holding.portfolio, `${holding.symbol} · ${holding.name}`, `${holding.quantity} units`, formatMoney(holding.value, holding.currency), formatMoney(holding.value - holding.cost, holding.currency)])} empty="No investments recorded yet" />
      {editingActivity && (
        <form className="entity-edit-form guided-form" onSubmit={saveActivityEdit}>
          <div className="section-title field-wide"><h2>Edit investment activity</h2><p>Finlio will reverse the old cash movement and rebuild the holding after saving.</p></div>
          <label className="field"><span>Investment</span><input value={`${assets.find((asset) => asset.id === editingActivity.asset_id)?.symbol || ""} · ${assets.find((asset) => asset.id === editingActivity.asset_id)?.name || ""}`} disabled /></label>
          <label className="field"><span>Portfolio</span><ModernSelect name="portfolio_id" defaultValue={String(editingActivity.portfolio_id)} options={portfolios.map((portfolio) => ({ value: String(portfolio.id), label: portfolio.name }))} required /></label>
          <label className="field"><span>Funding account</span><ModernSelect name="account_id" defaultValue={editingActivity.account_id ? String(editingActivity.account_id) : ""} options={accounts.map((account) => ({ value: String(account.id), label: `${account.name} · ${bankName(account.bank_id)}` }))} required /></label>
          <label className="field"><span>Action</span><ModernSelect name="type" defaultValue={editingActivity.type} options={[{ value: "buy", label: "Buy" }, { value: "sell", label: "Sell" }]} /></label>
          <label className="field"><span>Date</span><ModernDateInput name="date" defaultValue={editingActivity.date} required /></label>
          <label className="field"><span>Quantity</span><input name="quantity" type="number" min="0.000001" step="0.000001" defaultValue={editingActivity.quantity} required /></label>
          <label className="field"><span>Price per unit</span><input name="price" type="number" min="0" step="0.0001" defaultValue={editingActivity.price} required /></label>
          <label className="field"><span>Fees</span><input name="fees" type="number" min="0" step="0.01" defaultValue={editingActivity.fees} /></label>
          <label className="field"><span>Taxes</span><input name="taxes" type="number" min="0" step="0.01" defaultValue={editingActivity.taxes} /></label>
          <label className="field"><span>Currency</span><ModernSelect name="currency" defaultValue={editingActivity.currency} options={[{ value: "USD", label: "USD — US Dollar" }, { value: "EUR", label: "EUR — Euro" }, { value: "GBP", label: "GBP — British Pound" }, { value: "CHF", label: "CHF — Swiss Franc" }]} /></label>
          <div className="entity-edit-actions field-wide"><button type="button" className="secondary" onClick={() => setEditingActivity(null)}>Cancel</button><button className="primary" type="submit">Recalculate and save</button></div>
        </form>
      )}
      <section className="investment-activity-management">
        <div className="section-title"><h2>Investment activity</h2><p>Edit or delete purchases and sales; linked account balances and holdings stay synchronized.</p></div>
        {activities.length ? <div className="transaction-list">{activities.map((activity) => { const asset = assets.find((item) => item.id === activity.asset_id); const portfolio = portfolios.find((item) => item.id === activity.portfolio_id); return <article key={activity.id}><span><strong>{activity.type === "buy" ? "Bought" : "Sold"} {asset?.symbol || "investment"}</strong><small>{activity.date} · {activity.quantity} units at {formatMoney(activity.price, activity.currency)} · {portfolio?.name || "Portfolio"}</small></span><b>{formatMoney(Number(activity.quantity) * Number(activity.price), activity.currency)}</b><div><button onClick={() => setEditingActivity(activity)}><Pencil size={15} />Edit</button><button className="danger-action" onClick={() => removeActivity(activity)}><Trash2 size={15} />Delete</button></div></article>; })}</div> : <p className="muted">No investment activity yet.</p>}
      </section>
    </div>
  );
}

function InsuranceView({ token, setMessage }: { token: string; setMessage: (msg: string) => void }) {
  const { t } = useI18n();
  type PolicyItem = { id: number; provider_name: string; policy_name: string; policy_type: string; premium_amount: number; premium_frequency: string; insured_amount: number; end_date?: string };
  type InsuranceSummary = { total_cover: number; annual_premiums: number; active_policies: number };
  const [policies, setPolicies] = useState<PolicyItem[]>([]);
  const [accounts, setAccounts] = useState<AccountItem[]>([]);
  const [summary, setSummary] = useState<InsuranceSummary>({ total_cover: 0, annual_premiums: 0, active_policies: 0 });
  const [formOpen, setFormOpen] = useState(false);
  async function load() {
    const [nextPolicies, nextAccounts, nextSummary] = await Promise.all([
      apiFetch<PolicyItem[]>("/insurance/policies", token),
      apiFetch<AccountItem[]>("/accounts", token),
      apiFetch<InsuranceSummary>("/reports/insurance", token)
    ]);
    setPolicies(nextPolicies);
    setAccounts(nextAccounts);
    setSummary(nextSummary);
  }
  useEffect(() => {
    load().catch((error) => setMessage(error instanceof Error ? error.message : "Could not load insurance"));
  }, [token]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    try {
      await apiFetch("/insurance/policies", token, {
        method: "POST",
        body: JSON.stringify({
          data: {
            provider_name: form.provider_name,
            policy_name: form.policy_name,
            policy_type: form.policy_type,
            policy_number: form.policy_number || null,
            start_date: form.start_date || null,
            end_date: form.end_date || null,
            premium_amount: Number(form.premium_amount || 0),
            premium_frequency: form.premium_frequency,
            insured_amount: Number(form.insured_amount || 0),
            linked_account_id: form.linked_account_id ? Number(form.linked_account_id) : null
          }
        })
      });
      formElement.reset();
      setFormOpen(false);
      setMessage("Insurance policy saved");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save policy");
    }
  }
  async function removePolicy(policyId: number) {
    if (!window.confirm("Remove this insurance policy?")) return;
    try {
      await apiFetch(`/insurance/policies/${policyId}`, token, { method: "DELETE" });
      setMessage("Insurance policy removed");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not remove policy");
    }
  }
  const frequencyLabel: Record<string, string> = { monthly: "mo", quarterly: "quarter", yearly: "yr", annual: "yr" };
  return (
    <div className="page-grid insurance-page">
      <section className="insurance-shell">
        <div className="insurance-heading">
          <div><span className="insurance-heading-icon"><ShieldCheck size={27} /></span><div><h1>{t("Insurance Policies")}</h1><p>{summary.active_policies} active · {formatMoney(summary.total_cover)} total coverage · {formatMoney(summary.annual_premiums)} yearly premiums</p></div></div>
          <button className="insurance-add" onClick={() => setFormOpen((open) => !open)}><Plus size={20} />{formOpen ? "Close" : t("Add")}</button>
        </div>

        {formOpen && (
          <form className="insurance-form guided-form" onSubmit={submit}>
            <label className="field"><span>{t("Provider")}</span><input name="provider_name" placeholder="e.g. Allianz" required /></label>
            <label className="field"><span>{t("Policy name")}</span><input name="policy_name" placeholder="e.g. Family health cover" required /></label>
            <label className="field"><span>{t("Policy type")}</span><ModernSelect name="policy_type" defaultValue="health" options={[{ value: "health", label: "Health" }, { value: "life", label: "Life" }, { value: "home", label: "Home" }, { value: "car", label: "Auto" }, { value: "travel", label: "Travel" }, { value: "other", label: "Other" }]} /></label>
            <label className="field"><span>Policy number (optional)</span><input name="policy_number" /></label>
            <label className="field"><span>Starts</span><ModernDateInput name="start_date" /></label>
            <label className="field"><span>Renews / ends</span><ModernDateInput name="end_date" /></label>
            <label className="field"><span>{t("Premium")}</span><input name="premium_amount" type="number" min="0" step="0.01" defaultValue="0" /></label>
            <label className="field"><span>Paid</span><ModernSelect name="premium_frequency" defaultValue="monthly" options={[{ value: "monthly", label: "Monthly" }, { value: "quarterly", label: "Quarterly" }, { value: "yearly", label: "Yearly" }]} /></label>
            <label className="field"><span>{t("Coverage")}</span><input name="insured_amount" type="number" min="0" step="0.01" defaultValue="0" /></label>
            <label className="field"><span>Paid from (optional)</span><ModernSelect name="linked_account_id" options={[{ value: "", label: "No linked account" }, ...accounts.map((account) => ({ value: String(account.id), label: account.name }))]} /></label>
            <button className="primary form-action" type="submit"><Plus size={16} />{t("Save policy")}</button>
          </form>
        )}

        {policies.length ? (
          <div className="policy-grid">
            {policies.map((policy) => (
              <article className="policy-card" key={policy.id}>
                <div className="policy-card-top"><span><ShieldCheck size={24} /></span><b>{policy.policy_type === "car" ? "auto" : policy.policy_type}</b></div>
                <h2>{policy.policy_name}</h2>
                <p>{policy.provider_name}</p>
                <div className="policy-divider" />
                <div className="policy-values">
                  <div><span>Premium</span><strong>{formatMoney(policy.premium_amount)}/{frequencyLabel[policy.premium_frequency] || policy.premium_frequency}</strong></div>
                  <div><span>Coverage</span><strong>{formatMoney(policy.insured_amount)}</strong></div>
                </div>
                <small>Renews: {policy.end_date || "Not specified"}</small>
                <button className="policy-delete" onClick={() => removePolicy(policy.id)} title="Remove policy"><Trash2 size={19} /></button>
              </article>
            ))}
          </div>
        ) : (
          <div className="insurance-empty"><ShieldCheck size={36} /><strong>{t("No policies yet")}</strong><span>Add your first policy to keep coverage and renewals organized.</span><button onClick={() => setFormOpen(true)}><Plus size={17} />{t("Add")} policy</button></div>
        )}
      </section>
    </div>
  );
}

function ReportsView({ token }: { token: string }) {
  type CashflowMonth = { month: string; income: number; expenses: number; net: number };
  type CategorySpend = { name: string; amount: number };
  type NetWorthReport = { net_worth: number; breakdown: Array<{ name: string; amount: number }> };
  const [cashflow, setCashflow] = useState<CashflowMonth[]>([]);
  const [categories, setCategories] = useState<CategorySpend[]>([]);
  const [netWorth, setNetWorth] = useState<NetWorthReport>({ net_worth: 0, breakdown: [] });
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      apiFetch<{ months: CashflowMonth[] }>("/reports/cashflow", token),
      apiFetch<{ categories: CategorySpend[] }>("/reports/category-spending", token),
      apiFetch<NetWorthReport>("/reports/net-worth", token)
    ]).then(([flow, spending, worth]) => {
      setCashflow(flow.months);
      setCategories(spending.categories);
      setNetWorth(worth);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load reports"));
  }, [token]);
  const maxFlow = Math.max(1, ...cashflow.flatMap((month) => [Number(month.income), Number(month.expenses)]));
  const maxCategory = Math.max(1, ...categories.map((category) => Number(category.amount)));
  return (
    <div className="page-grid">
      <div className="page-heading"><h1>Reports</h1><p>See where money comes from, where it goes, and what your current net worth contains.</p></div>
      {error && <p className="error">{error}</p>}
      <section className="report-hero"><span>Current net worth</span><strong>{formatMoney(netWorth.net_worth)}</strong></section>
      <section className="two-column report-grid">
        <div className="data-panel">
          <h2>Cash flow by month</h2>
          {cashflow.length === 0 ? <p className="muted">Add transactions to see cash flow.</p> : cashflow.map((month) => (
            <div className="chart-row" key={month.month}>
              <span>{month.month}</span>
              <div className="bar-track"><i className="bar income" style={{ width: `${Number(month.income) / maxFlow * 100}%` }} /><i className="bar expense" style={{ width: `${Number(month.expenses) / maxFlow * 100}%` }} /></div>
              <strong className={Number(month.net) >= 0 ? "positive" : "negative"}>{formatMoney(month.net)}</strong>
            </div>
          ))}
          {cashflow.length > 0 && <div className="legend"><span><i className="legend-income" />Income</span><span><i className="legend-expense" />Expenses</span></div>}
        </div>
        <DataPanel title="Net worth breakdown" rows={netWorth.breakdown.map((item) => [item.name, formatMoney(item.amount)])} empty="No balances yet" />
      </section>
      <section className="data-panel">
        <h2>Spending by category</h2>
        {categories.length === 0 ? <p className="muted">Expense categories will appear here.</p> : categories.map((category) => (
          <div className="category-row" key={category.name}><span>{category.name}</span><div className="single-bar"><i style={{ width: `${Number(category.amount) / maxCategory * 100}%` }} /></div><strong>{formatMoney(category.amount)}</strong></div>
        ))}
      </section>
    </div>
  );
}

function SettingsView({ token, setMessage, onProfilePhoto, onProfileChange, onLanguageChange }: { token: string; setMessage: (msg: string) => void; onProfilePhoto: (url: string | null) => void; onProfileChange: (profile: Profile) => void; onLanguageChange: (language: string) => void }) {
  const { t } = useI18n();
  const [profile, setProfile] = useState<Profile>({ id: 0, full_name: "", email: "" });
  const [preferences, setPreferences] = useState<UserSettings>({
    theme: "system",
    favorite_language: "en",
    default_currency: "EUR",
    date_format: "YYYY-MM-DD",
    number_format: "1,234.56",
    profile_photo_url: null,
    notifications_enabled: true
  });
  const [loaded, setLoaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [editingCategory, setEditingCategory] = useState<CategoryItem | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<Profile>("/profile", token),
      apiFetch<UserSettings>("/settings", token),
      apiFetch<CategoryItem[]>("/categories", token)
    ]).then(([nextProfile, nextPreferences, nextCategories]) => {
      setProfile(nextProfile);
      onProfileChange(nextProfile);
      setPreferences(nextPreferences);
      setCategories(nextCategories);
      setLoaded(true);
    }).catch((error) => {
      setMessage(error instanceof Error ? error.message : "Could not load settings");
      setLoaded(true);
    });
  }, [token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const nextProfile = await apiFetch<Profile>("/profile", token, {
        method: "PATCH",
        body: JSON.stringify({ full_name: profile.full_name.trim(), email: profile.email.trim() })
      });
      const settings = await apiFetch<UserSettings>("/settings", token, {
        method: "PATCH",
        body: JSON.stringify(preferences)
      });
      setProfile(nextProfile);
      setPreferences(settings);
      applyTheme(settings.theme);
      setMessage("Settings saved");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save settings");
    }
  }

  async function uploadPhoto(file?: File) {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setMessage("Choose an image file");
      return;
    }
    const data = new FormData();
    data.append("file", file);
    setUploading(true);
    try {
      const settings = await apiFetch<UserSettings>("/settings/profile-photo", token, { method: "POST", body: data });
      setPreferences(settings);
      onProfilePhoto(settings.profile_photo_url || null);
      setMessage("Profile photo updated");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not upload the image");
    } finally {
      setUploading(false);
    }
  }

  async function saveCategory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = Object.fromEntries(new FormData(formElement));
    try {
      await apiFetch(editingCategory ? `/categories/${editingCategory.id}` : "/categories", token, {
        method: editingCategory ? "PATCH" : "POST",
        body: JSON.stringify({ name: form.name, type: form.type, color: form.color || null })
      });
      const nextCategories = await apiFetch<CategoryItem[]>("/categories", token);
      setCategories(nextCategories);
      setEditingCategory(null);
      formElement.reset();
      setMessage(editingCategory ? "Category updated" : "Category created");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save category");
    }
  }

  async function removeCategory(category: CategoryItem) {
    if (!window.confirm(`Delete the ${category.name} category? Existing transactions will become uncategorized.`)) return;
    try {
      await apiFetch(`/categories/${category.id}`, token, { method: "DELETE" });
      setCategories((current) => current.filter((item) => item.id !== category.id));
      setEditingCategory(null);
      setMessage("Category deleted");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not delete category");
    }
  }

  const updatePreference = <K extends keyof UserSettings>(key: K, value: UserSettings[K]) => {
    setPreferences((current) => ({ ...current, [key]: value }));
  };

  if (!loaded) return <div className="page-grid"><div className="settings-loading">Loading your settings…</div></div>;

  return (
    <div className="page-grid settings-page">
      <div className="page-heading">
        <h1>{t("Profile and settings")}</h1>
        <p>Personalize how Finlio looks, formats your money, and keeps you informed.</p>
      </div>
      <form className="settings-layout" onSubmit={submit}>
        <section className="settings-card profile-settings-card">
          <div className="settings-card-heading"><h2>Your profile</h2><p>This information appears in your Finlio header.</p></div>
          <div className="profile-editor">
            <label
              className={`photo-dropzone ${uploading ? "uploading" : ""}`}
              htmlFor="profile-photo"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => { event.preventDefault(); uploadPhoto(event.dataTransfer.files[0]); }}
            >
              <span className="photo-preview">
                {preferences.profile_photo_url ? <img src={preferences.profile_photo_url} alt="" /> : <UserRound size={34} />}
              </span>
              <span><strong>{uploading ? "Uploading…" : "Drop your photo here"}</strong><small>or click to choose · JPG, PNG, WebP or GIF · max 5 MB</small></span>
              <FileUp size={22} />
              <input id="profile-photo" type="file" accept="image/jpeg,image/png,image/webp,image/gif" onChange={(event) => uploadPhoto(event.target.files?.[0])} />
            </label>
            <div className="settings-fields two-settings-fields">
              <label className="field"><span>{t("Full name")}</span><input value={profile.full_name} onChange={(event) => setProfile((current) => ({ ...current, full_name: event.target.value }))} autoComplete="name" /></label>
              <label className="field"><span>{t("Email")}</span><input type="email" value={profile.email} onChange={(event) => setProfile((current) => ({ ...current, email: event.target.value }))} autoComplete="email" required /></label>
            </div>
          </div>
        </section>

        <section className="settings-card">
          <div className="settings-card-heading"><h2>{t("Regional preferences")}</h2><p>Choose how dates and amounts should be displayed.</p></div>
          <div className="settings-fields two-settings-fields">
            <label className="field"><span>{t("Language")}</span><ModernSelect value={preferences.favorite_language} onValueChange={(value) => { updatePreference("favorite_language", value); onLanguageChange(value); }} options={[{ value: "en", label: "English" }, { value: "it", label: "Italiano" }, { value: "fr", label: "Français" }, { value: "de", label: "Deutsch" }, { value: "es", label: "Español" }]} /></label>
            <label className="field"><span>{t("Default currency")}</span><ModernSelect value={preferences.default_currency} onValueChange={(value) => updatePreference("default_currency", value)} options={[{ value: "EUR", label: "EUR — Euro" }, { value: "USD", label: "USD — US Dollar" }, { value: "GBP", label: "GBP — British Pound" }, { value: "CHF", label: "CHF — Swiss Franc" }, { value: "JPY", label: "JPY — Japanese Yen" }, { value: "CAD", label: "CAD — Canadian Dollar" }, { value: "AUD", label: "AUD — Australian Dollar" }]} /></label>
            <label className="field"><span>{t("Date format")}</span><ModernSelect value={preferences.date_format} onValueChange={(value) => updatePreference("date_format", value)} options={[{ value: "YYYY-MM-DD", label: "2026-07-04 — Year, month, day" }, { value: "DD/MM/YYYY", label: "04/07/2026 — Day, month, year" }, { value: "MM/DD/YYYY", label: "07/04/2026 — Month, day, year" }, { value: "DD.MM.YYYY", label: "04.07.2026 — Dotted European" }]} /></label>
            <label className="field"><span>{t("Number format")}</span><ModernSelect value={preferences.number_format} onValueChange={(value) => updatePreference("number_format", value)} options={[{ value: "1,234.56", label: "1,234.56 — comma thousands, dot decimals" }, { value: "1.234,56", label: "1.234,56 — dot thousands, comma decimals" }, { value: "1 234,56", label: "1 234,56 — space thousands, comma decimals" }, { value: "1234.56", label: "1234.56 — no thousands separator" }]} /><small className="field-help">The final two digits are cents; the other separator groups thousands.</small></label>
          </div>
        </section>

        <section className="settings-card">
          <div className="settings-card-heading"><h2>Appearance and notifications</h2><p>Match your device or choose a fixed Finlio theme.</p></div>
          <div className="settings-fields two-settings-fields">
            <label className="field"><span>{t("Theme")}</span><ModernSelect value={preferences.theme} onValueChange={(value) => { const theme = value as UserSettings["theme"]; updatePreference("theme", theme); applyTheme(theme); }} options={[{ value: "system", label: t("System") }, { value: "light", label: t("Light") }, { value: "dark", label: t("Dark") }]} /></label>
            <label className="settings-toggle"><span><strong>Email notifications</strong><small>Payment reminders and important account updates</small></span><input type="checkbox" checked={preferences.notifications_enabled} onChange={(event) => updatePreference("notifications_enabled", event.target.checked)} /><i /></label>
          </div>
        </section>

        <div className="settings-actions">
          <span>Changes are saved to your Finlio profile.</span>
          <button className="primary settings-save" type="submit">{t("Save settings")}</button>
        </div>
      </form>

      <section className="settings-card category-settings">
        <div className="settings-card-heading"><h2>Transaction categories</h2><p>Built-in categories are always available. Add your own for the way you manage money.</p></div>
        <form key={editingCategory?.id || "new-category"} className="category-editor" onSubmit={saveCategory}>
          <label className="field"><span>Category name</span><input name="name" defaultValue={editingCategory?.name || ""} placeholder="e.g. Family, Gym, Side project" required /></label>
          <label className="field"><span>Used for</span><ModernSelect name="type" defaultValue={editingCategory?.type || "expense"} options={[{ value: "expense", label: "Money out" }, { value: "income", label: "Money in" }, { value: "investment", label: "Investment" }]} /></label>
          <label className="field"><span>Color</span><ModernSelect name="color" defaultValue={editingCategory?.color || "#7547ee"} options={[{ value: "#7547ee", label: "Purple" }, { value: "#17a9d8", label: "Blue" }, { value: "#16b98b", label: "Green" }, { value: "#f59e0b", label: "Amber" }, { value: "#ef5b75", label: "Coral" }]} /></label>
          <div className="category-editor-actions"><button className="primary" type="submit">{editingCategory ? "Save category" : "Add category"}</button>{editingCategory && <button className="secondary" type="button" onClick={() => setEditingCategory(null)}>Cancel</button>}</div>
        </form>
        <div className="category-groups">
          {(["expense", "income", "investment"] as const).map((type) => (
            <div key={type}>
              <h3>{type === "expense" ? "Money out" : type === "income" ? "Money in" : "Investments"}</h3>
              <div className="category-chip-list">
                {categories.filter((category) => category.type === type).map((category) => (
                  <article key={category.id} className={category.is_system ? "system" : ""}>
                    <i style={{ background: category.color || (category.is_system ? "#8a94a6" : "#7547ee") }} />
                    <span><strong>{category.name}</strong><small>{category.is_system ? "Built in" : "Custom"}</small></span>
                    {!category.is_system && <div><button type="button" onClick={() => setEditingCategory(category)} title="Edit category"><Pencil size={15} /></button><button type="button" onClick={() => removeCategory(category)} title="Delete category"><Trash2 size={15} /></button></div>}
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function SimpleModule({ title }: { title: string }) {
  return (
    <div className="page-grid">
      <h1>{title}</h1>
      <section className="empty-state">
        <LineChart size={36} />
        <strong>{title} workspace</strong>
        <span>API endpoints are ready for this module. Add your first record from the connected screens or API.</span>
      </section>
    </div>
  );
}

function DataPanel({ title, rows, empty }: { title: string; rows: Array<Array<unknown>>; empty: string }) {
  return (
    <section className="data-panel">
      <h2>{title}</h2>
      {rows.length === 0 ? <p className="muted">{empty}</p> : (
        <table>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {row.map((cell, cellIndex) => <td key={cellIndex}>{String(cell)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
