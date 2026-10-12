import { useEffect, useState } from 'react'

import './App.css'

const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

const navigation = [

  { label: 'Overview', icon: '◫' },

  { label: 'Repository Analysis', icon: '⌘' },

  { label: 'Evaluations', icon: '◎' },

]

function Icon({ children }) {

  return <span className="nav-icon" aria-hidden="true">{children}</span>

}

function ScoreCard({ label, score, description }) {

  const available = typeof score === 'number'

  return (

    <article className="score-card">

      <div className="score-card-top">

        <span>{label}</span>

        <span className="score-dot" />

      </div>

      <div className="score-value">

        {available ? score : '—'}

        {available && <small>/100</small>}

      </div>

      <p>{description}</p>

      <div className="score-track">

        <div

          className="score-progress"

          style={{ width: `${available ? Math.min(100, Math.max(0, score)) : 0}%` }}

        />

      </div>

    </article>

  )

}

function FindingCard({ finding }) {

  return (

    <article className="finding-card">

      <div className="finding-heading">

        <span className={`severity severity-${finding.severity}`}>

          {finding.severity}

        </span>

        <span className="finding-category">{finding.category}</span>

      </div>

      <h3>{finding.title}</h3>

      <p>{finding.explanation}</p>

      {finding.evidence?.length > 0 && (

        <div className="evidence-box">

          <span className="evidence-label">EVIDENCE</span>

          {finding.evidence.map((item, index) => (

            <div className="evidence-item" key={`${item.category}-${item.metric}-${index}`}>

              <code>{item.metric}</code>

              <span>{String(

                typeof item.value === 'object'

                  ? JSON.stringify(item.value)

                  : item.value,

              )}</span>

            </div>

          ))}

        </div>

      )}

      <div className="finding-fix">

        <span>Suggested fix</span>

        <p>{finding.recommendation}</p>

      </div>

    </article>

  )

}

function App() {

  const [repositoryUrl, setRepositoryUrl] = useState('')

  const [report, setReport] = useState(null)

  const [error, setError] = useState('')

  const [loading, setLoading] = useState(false)

  const [activeNav, setActiveNav] = useState('Overview')
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('repopilot-theme') === 'light' ? 'light' : 'dark'
    } catch {
      return 'dark'
    }
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('repopilot-theme', theme)
    } catch {
      // Theme still works for the current session if storage is unavailable.
    }
  }, [theme])

  async function analyzeRepository(event) {

    event.preventDefault()

    setError('')

    setReport(null)

    setLoading(true)

    try {

      const response = await fetch(`${API_URL}/api/analyze`, {

        method: 'POST',

        headers: { 'Content-Type': 'application/json' },

        body: JSON.stringify({ repository_url: repositoryUrl.trim() }),

      })

      const data = await response.json().catch(() => ({}))

      if (!response.ok) {

        const detail = data.detail

        throw new Error(

          typeof detail === 'string'

            ? detail

            : 'Unable to analyze this repository. Check the URL and backend.',

        )

      }

      if (

        !data ||

        typeof data !== 'object' ||

        typeof data.overall_score !== 'number' ||

        !data.engineering_scores ||

        !data.recruiter_scores

      ) {

        throw new Error('The API returned a report in an unexpected format.')

      }

      setReport(data)

      setActiveNav('Overview')

    } catch (err) {

      setError(

        err instanceof TypeError

          ? 'Could not connect to the RepoPilot API. Make sure the backend is running and CORS permits this frontend.'

          : err.message || 'An unexpected error occurred.',

      )

    } finally {

      setLoading(false)

    }

  }

  const engineeringScore = report?.engineering_scores?.overall

  const recruiterScore = report?.recruiter_scores?.overall

  const findings = report

    ? [

        ...(report.engineering_review?.findings || []),

        ...(report.recruiter_review?.findings || []),

      ]

    : []

  const recommendations = report?.recommendations || []

  return (

    <div className="app-shell">

      <aside className="sidebar">

        <a className="brand" href="#" onClick={() => setActiveNav('Overview')}>

          <img className="brand-logo" src="/repopilot-logo.png" alt="RepoPilot logo" />

          <span>

            <strong>RepoPilot</strong>

            <small>REPOSITORY INTELLIGENCE</small>

          </span>

        </a>

        <div className="sidebar-label">WORKSPACE</div>

        <nav className="sidebar-nav" aria-label="Main navigation">

          {navigation.map((item) => (

            <button

              key={item.label}

              className={`nav-item ${activeNav === item.label ? 'active' : ''}`}

              onClick={() => {

                setActiveNav(item.label)

                if (item.label === 'Repository Analysis') {

                  document.getElementById('repository-form')?.scrollIntoView({

                    behavior: 'smooth',

                    block: 'center',

                  })

                }

              }}

              type="button"

            >

              <Icon>{item.icon}</Icon>

              {item.label}

              {item.label === 'Repository Analysis' && (

                <span className="nav-arrow">↗</span>

              )}

            </button>

          ))}

        </nav>

        <div className="sidebar-bottom">

          <div className="security-note">

            <span className="security-symbol">◇</span>

            <strong>Built for safe analysis</strong>

            <p>Repository content is treated as untrusted input.</p>

          </div>

          <div className="profile-row">

            <div className="profile-avatar">RP</div>

            <div>

              <strong>RepoPilot</strong>

              <small>AI repository reviewer</small>

            </div>

            <span className="online-dot" title="Interface loaded" />

          </div>

        </div>

      </aside>

      <main className="main-content">

        <header className="topbar">

          <div className="breadcrumb">

            Workspace <span>/</span> <strong>{activeNav}</strong>

          </div>

          <div className="topbar-right">

            <button
              className="theme-toggle"
              type="button"
              onClick={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
              aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              <span aria-hidden="true">{theme === 'dark' ? '☀' : '☾'}</span>
              <span>{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
            </button>

            <span className="status-pill">

              <span className="online-dot" />

              Analysis workspace

            </span>

            <a

              className="github-link"

              href="https://github.com/priyam200409/Agent_RepoPilot"

              target="_blank"

              rel="noreferrer"

            >

              GitHub ↗

            </a>

          </div>

        </header>

        <div className="page-content">

          <section className="welcome-section">

            <div>

              <div className="eyebrow">

                <span className="eyebrow-line" />

                AI-POWERED REPOSITORY REVIEW

              </div>

              <h1>Build better repositories.</h1>

              <p className="welcome-copy">

                Get an engineering review and recruiter-readiness assessment

                backed by repository evidence.

              </p>

            </div>

            <div className="hero-badge">

              <span className="hero-badge-icon">✳</span>

              <div>

                <strong>Evidence first</strong>

                <small>Scores are validated</small>

              </div>

            </div>

          </section>

          <section className="analyzer-panel" id="repository-form">

            <div className="panel-heading">

              <div className="panel-icon">⌘</div>

              <div>

                <h2>Analyze a repository</h2>

                <p>Enter the URL of a public GitHub repository.</p>

              </div>

            </div>

            <form className="repository-form" onSubmit={analyzeRepository}>

              <label htmlFor="repository-url">GITHUB REPOSITORY URL</label>

              <div className="input-row">

                <span className="input-github-icon">⌘</span>

                <input

                  id="repository-url"

                  type="url"

                  placeholder="https://github.com/owner/repository"

                  value={repositoryUrl}

                  onChange={(event) => setRepositoryUrl(event.target.value)}

                  required

                  disabled={loading}

                />

                <button

                  className="analyze-button"

                  type="submit"

                  disabled={loading}

                >

                  {loading ? (

                    <>

                      <span className="spinner" />

                      Analyzing...

                    </>

                  ) : (

                    <>Analyze repository <span>→</span></>

                  )}

                </button>

              </div>

              <div className="form-hint">

                <span>ⓘ</span>

                Public repositories only. Repository code is never executed.

              </div>

            </form>

            {error && (

              <div className="error-message" role="alert">

                <strong>Analysis failed</strong>

                <p>{error}</p>

              </div>

            )}

            {loading && (

              <div className="loading-message" role="status">

                <span className="spinner" />

                <div>

                  <strong>Reviewing your repository</strong>

                  <p>Collecting repository evidence and validating the report.</p>

                </div>

              </div>

            )}

          </section>

          <section className="section-block">

            <div className="section-heading">

              <div>

                <div className="section-kicker">YOUR RESULTS</div>

                <h2>Repository overview</h2>

              </div>

              <span className={`result-tag ${report ? 'complete' : ''}`}>

                <span className="online-dot" />

                {report ? 'Analysis complete' : 'Awaiting analysis'}

              </span>

            </div>

            <div className="score-grid">

              <ScoreCard

                label="Overall score"

                score={report?.overall_score}

                description="Combined review score"

              />

              <ScoreCard

                label="Engineering"

                score={engineeringScore}

                description="Technical quality"

              />

              <ScoreCard

                label="Recruiter readiness"

                score={recruiterScore}

                description="Portfolio presentation"

              />

              <ScoreCard

                label="Security"

                score={undefined}

                description="Not separately scored yet"

              />

            </div>

          </section>

          {report && (

            <>

              <section className="section-block report-meta">

                <div className="section-heading">

                  <div>

                    <div className="section-kicker">ANALYZED REPOSITORY</div>

                    <h2>{report.repository_name}</h2>

                  </div>

                  <a

                    href={report.repository_url}

                    target="_blank"

                    rel="noreferrer"

                    className="external-link"

                  >

                    View repository ↗

                  </a>

                </div>

                <p className="repository-url">{report.repository_url}</p>

              </section>

              <section className="section-block">

                <div className="section-heading">

                  <div>

                    <div className="section-kicker">ENGINEERING REVIEW</div>

                    <h2>Key findings <span className="count-badge">{findings.length}</span></h2>

                  </div>

                </div>

                {findings.length ? (

                  <div className="findings-grid">

                    {findings.map((finding) => (

                      <FindingCard key={finding.id} finding={finding} />

                    ))}

                  </div>

                ) : (

                  <div className="empty-state">

                    <span>✓</span>

                    <h3>No findings reported</h3>

                    <p>The reviewers did not return any findings for this repository.</p>

                  </div>

                )}

              </section>

              <section className="section-block">

                <div className="section-heading">

                  <div>

                    <div className="section-kicker">NEXT STEPS</div>

                    <h2>Prioritized recommendations</h2>

                  </div>

                  <span className="count-badge">{recommendations.length}</span>

                </div>

                {recommendations.length ? (

                  <div className="recommendation-list">

                    {recommendations.map((item, index) => (

                      <article className="recommendation-card" key={item.id}>

                        <span className="recommendation-number">

                          {String(index + 1).padStart(2, '0')}

                        </span>

                        <div className="recommendation-content">

                          <div className="recommendation-top">

                            <span className={`priority priority-${item.priority}`}>

                              {item.priority} priority

                            </span>

                          </div>

                          <h3>{item.title}</h3>

                          <p>{item.action}</p>

                          <small>{item.rationale}</small>

                        </div>

                      </article>

                    ))}

                  </div>

                ) : (

                  <div className="empty-state">

                    <h3>No recommendations returned</h3>

                    <p>The report contains no prioritized actions.</p>

                  </div>

                )}

              </section>

              <section className="section-block">

                <div className="section-heading">

                  <div>

                    <div className="section-kicker">REVIEW SUMMARIES</div>

                    <h2>Reviewer perspectives</h2>

                  </div>

                </div>

                <div className="summary-grid">

                  <article className="summary-card">

                    <h3>Engineering reviewer</h3>

                    <p>{report.engineering_review?.summary}</p>

                  </article>

                  <article className="summary-card">

                    <h3>Recruiter reviewer</h3>

                    <p>{report.recruiter_review?.summary}</p>

                  </article>

                </div>

              </section>

            </>

          )}

          {!report && (

            <section className="empty-dashboard">

              <div className="empty-illustration">

                <div className="illustration-window">

                  <span />

                  <span />

                  <span />

                  <div className="illustration-code">

                    <i />

                    <i />

                    <i />

                    <i />

                  </div>

                  <div className="illustration-check">✓</div>

                </div>

              </div>

              <h2>Your next review starts here</h2>

              <p>

                Analyze a repository to see validated scores, findings,

                evidence, and actionable improvements.

              </p>

            </section>

          )}

          <footer className="page-footer">

            <span>RepoPilot <span className="footer-separator">/</span> AI Repository Intelligence</span>

            <span>Evidence-based reviews, not guesswork.</span>

          </footer>

        </div>

      </main>

    </div>

  )

}

export default App
