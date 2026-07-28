const windowsDownload =
  "https://github.com/ciao9090real/Money-Manager-DAD/releases/latest/download/MoneyManager.exe";
const androidDownload =
  "https://github.com/ciao9090real/Money-Manager-DAD/releases/latest/download/MoneyManager.apk";
const repository = "https://github.com/ciao9090real/Money-Manager-DAD";

function WindowsIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 5.3 10.6 4v7.4H3V5.3Zm8.6-1.5L21 2.3v9.1h-9.4V3.8ZM3 12.5h7.6V20L3 18.7v-6.2Zm8.6 0H21v9.2l-9.4-1.5v-7.7Z" />
    </svg>
  );
}

function AndroidIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7.1 8.4-1.6-2.8.9-.5L8 8a9.2 9.2 0 0 1 8 0l1.6-2.9.9.5-1.6 2.8A8 8 0 0 1 21 15H3a8 8 0 0 1 4.1-6.6ZM8 12.5a1 1 0 1 0 0-2 1 1 0 0 0 0 2Zm8 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z" />
    </svg>
  );
}

function ArrowIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M4 10h11M11 6l4 4-4 4" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 2.5 20 6v6c0 5-3.3 8.5-8 9.5C7.3 20.5 4 17 4 12V6l8-3.5Z" />
      <path d="m8.7 12.1 2.1 2.1 4.7-5" />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="4" y="10" width="16" height="11" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3" />
    </svg>
  );
}

function WifiIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3.5 9a13.3 13.3 0 0 1 17 0M6.5 12a8.7 8.7 0 0 1 11 0M9.5 15a4 4 0 0 1 5 0" />
      <circle cx="12" cy="18.5" r="1" />
    </svg>
  );
}

function DatabaseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <ellipse cx="12" cy="5" rx="8" ry="3" />
      <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
    </svg>
  );
}

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="Money Manager home">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>Money Manager</span>
        </a>

        <nav className="desktop-nav" aria-label="Primary navigation">
          <a href="#features">Features</a>
          <a href="#security">Security</a>
          <a href="#mobile">Mobile</a>
          <a className="nav-download" href="#download">
            Download
          </a>
        </nav>

        <details className="mobile-nav">
          <summary aria-label="Open navigation">
            <span />
            <span />
          </summary>
          <div>
            <a href="#features">Features</a>
            <a href="#security">Security</a>
            <a href="#mobile">Mobile</a>
            <a href="#download">Download</a>
          </div>
        </details>
      </header>

      <section className="hero section-grid" id="top">
        <div className="hero-copy">
          <div className="privacy-chip">
            <ShieldIcon />
            <span>Private by design</span>
            <i />
            <span>No cloud account</span>
          </div>

          <h1>
            Your money.
            <br />
            Your devices.
            <br />
            <em>Nobody else&apos;s.</em>
          </h1>

          <p>
            A local-first finance manager for Windows with an encrypted Android
            companion. Track accounts, budgets, goals and forecasts without
            sending your financial life to the cloud.
          </p>

          <div className="hero-actions">
            <a className="button button-primary" href={windowsDownload}>
              <WindowsIcon />
              Download for Windows
            </a>
            <a className="button button-secondary" href="#features">
              Explore the app
              <ArrowIcon />
            </a>
          </div>

          <div className="trust-row" aria-label="Privacy highlights">
            <span>
              <LockIcon /> Encrypted locally
            </span>
            <span>
              <DatabaseIcon /> Offline-first
            </span>
            <span>
              <WifiIcon /> Direct Wi-Fi sync
            </span>
          </div>
        </div>

        <div className="hero-stage" aria-label="Money Manager desktop app">
          <div className="signal signal-one">LOCAL / ENCRYPTED</div>
          <div className="signal signal-two">SYNC / DIRECT WI-FI</div>
          <div className="app-window">
            <div className="window-bar">
              <span className="window-app">
                <b aria-hidden="true">▥</b>
                Money Manager
              </span>
              <span aria-hidden="true">— &nbsp; □ &nbsp; ×</span>
            </div>
            <img
              src="/product/home.png"
              alt="Money Manager home dashboard showing the current position, recent activity, and upcoming decisions"
            />
          </div>
          <div className="sync-line" aria-hidden="true">
            <span />
            <i />
            <span />
          </div>
          <div className="stage-meta">
            <span>DATA: STORED LOCALLY</span>
            <span>STATUS: OFFLINE READY</span>
          </div>
        </div>
      </section>

      <section className="proof-strip" aria-label="Money Manager principles">
        <div>
          <strong>01</strong>
          <span>One clear financial position</span>
        </div>
        <div>
          <strong>02</strong>
          <span>Real planning, without a subscription</span>
        </div>
        <div>
          <strong>03</strong>
          <span>Your database stays yours</span>
        </div>
      </section>

      <section className="features section-grid" id="features">
        <div className="section-intro">
          <span className="kicker">The full picture</span>
          <h2>From the day-to-day to the long view.</h2>
          <p>
            Money Manager keeps transactions, plans, accounts and investments
            connected, so every screen answers a real financial question.
          </p>
        </div>

        <div className="feature-showcase">
          <article className="feature-panel feature-panel-wide">
            <div className="feature-copy">
              <span>PLAN / 01</span>
              <h3>See where your cash is going.</h3>
              <p>
                Combine recorded income and expenses with future schedules to
                understand your six-month direction before commitments arrive.
              </p>
            </div>
            <div className="screen-frame">
              <img
                src="/product/forecast.png"
                alt="Six-month Money Manager cash forecast with current balance and recorded cash flow"
              />
            </div>
          </article>

          <article className="feature-panel">
            <div className="feature-copy">
              <span>ACTIVITY / 02</span>
              <h3>Review every movement.</h3>
              <p>
                Search, filter and reconcile transactions across accounts,
                including imports and repeating payments.
              </p>
            </div>
            <div className="screen-frame screen-frame-small">
              <img
                src="/product/transactions.png"
                alt="Money Manager transaction list with search, filters, accounts, categories, and amounts"
              />
            </div>
          </article>

          <article className="feature-panel feature-panel-blue">
            <div className="feature-copy">
              <span>POSITION / 03</span>
              <h3>Measure wealth, not noise.</h3>
              <p>
                Follow assets, liabilities and net worth over time. Investments
                stay tied to deposits, withdrawals and recorded market values.
              </p>
            </div>
            <div className="screen-frame screen-frame-small">
              <img
                src="/product/history.png"
                alt="Money Manager net-worth history chart showing assets, liabilities, and net worth"
              />
            </div>
          </article>
        </div>
      </section>

      <section className="security" id="security">
        <div className="security-heading">
          <span className="kicker kicker-dark">Security model</span>
          <h2>No financial cloud. No hidden audience.</h2>
          <p>
            The desktop app owns the complete ledger. The phone gets an
            encrypted companion copy only when you choose to pair it.
          </p>
        </div>

        <div className="security-grid">
          <article>
            <span className="security-number">01</span>
            <LockIcon />
            <h3>Locked on Windows</h3>
            <p>
              Open with your app password or Windows Hello. The app can lock
              again when minimized.
            </p>
          </article>
          <article>
            <span className="security-number">02</span>
            <DatabaseIcon />
            <h3>SQLCipher at rest</h3>
            <p>
              The local database is encrypted, with its random key protected
              for the signed-in Windows user.
            </p>
          </article>
          <article>
            <span className="security-number">03</span>
            <WifiIcon />
            <h3>Local HTTPS sync</h3>
            <p>
              Pair by one-time QR code over your own Wi-Fi. Sync is
              authenticated and certificate-pinned.
            </p>
          </article>
          <article>
            <span className="security-number">04</span>
            <ShieldIcon />
            <h3>Offline Android cache</h3>
            <p>
              The Android companion keeps its own encrypted cache and requires
              enrolled device biometrics.
            </p>
          </article>
        </div>
      </section>

      <section className="mobile-section section-grid" id="mobile">
        <div className="mobile-copy">
          <span className="kicker">Desktop + Android</span>
          <h2>Two devices. One private connection.</h2>
          <p>
            Start phone sync from Settings, scan the QR code in the Android
            app, then exchange data directly over local Wi-Fi. The sync server
            exists only while the desktop app is open and phone sync is enabled.
          </p>
          <ul>
            <li>
              <span>01</span>Opt-in pairing with a one-time code
            </li>
            <li>
              <span>02</span>Encrypted storage on both devices
            </li>
            <li>
              <span>03</span>Private reminders without sensitive lock-screen
              text
            </li>
          </ul>
          <a className="text-link" href={repository}>
            Read the technical overview <ArrowIcon />
          </a>
        </div>

        <div
          className="mobile-visual"
          role="img"
          aria-label="Diagram showing the Windows Money Manager app syncing directly to its Android companion over local HTTPS, with no cloud relay"
        >
          <div className="device-card desktop-device">
            <span className="device-label">PRIMARY / WINDOWS</span>
            <WindowsIcon />
            <strong>Complete ledger</strong>
            <small>SQLCIPHER DATABASE</small>
            <i className="status-dot">LOCAL</i>
          </div>

          <div className="pairing-channel">
            <span />
            <div>
              <WifiIcon />
              <b>DIRECT WI-FI</b>
              <small>PINNED LOCAL HTTPS</small>
            </div>
            <span />
          </div>

          <div className="device-card phone-device">
            <span className="device-label">COMPANION / ANDROID</span>
            <AndroidIcon />
            <strong>Private companion</strong>
            <small>ENCRYPTED OFFLINE CACHE</small>
            <i className="status-dot">BIOMETRIC</i>
          </div>

          <div className="no-cloud">
            <ShieldIcon />
            <span>NO CLOUD DATABASE</span>
          </div>
        </div>
      </section>

      <section className="download-section" id="download">
        <div className="download-copy">
          <span className="kicker kicker-dark">Available from GitHub</span>
          <h2>Your ledger, on your terms.</h2>
          <p>
            Download the current Windows app and Android companion directly
            from the project&apos;s latest release.
          </p>
        </div>

        <div className="download-grid">
          <a href={windowsDownload} className="download-card">
            <WindowsIcon />
            <span>
              <small>PRIMARY APP</small>
              <strong>Windows</strong>
              <em>Download .exe</em>
            </span>
            <ArrowIcon />
          </a>
          <a href={androidDownload} className="download-card">
            <AndroidIcon />
            <span>
              <small>COMPANION</small>
              <strong>Android</strong>
              <em>Download .apk</em>
            </span>
            <ArrowIcon />
          </a>
        </div>

        <p className="download-note">
          Free to use · No account required · Source available on GitHub
        </p>
      </section>

      <footer>
        <a className="brand footer-brand" href="#top">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span>Money Manager</span>
        </a>
        <p>Private, offline personal finance for Windows and Android.</p>
        <div>
          <a href={repository}>GitHub</a>
          <a href="#security">Privacy model</a>
          <a href="#download">Download</a>
        </div>
      </footer>
    </main>
  );
}
