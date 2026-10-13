
import { useState } from 'react'
import './App.css'

const API = 'http://localhost:8001'

function App() {
  const [subject, setSubject] = useState('Science')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hi! I am your AI study tutor. Ask me anything about your Math or Science syllabus, or generate a practice set to test your understanding.',
    },
  ])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState(null)
  const [practice, setPractice] = useState('')
  const [studentId, setStudentId] = useState('test_student')

  async function sendQuestion(event) {
    event.preventDefault()
    const text = question.trim()
    if (!text || loading) return

    setMessages((previous) => [...previous, { role: 'user', text }])
    setQuestion('')
    setLoading(true)
    setError('')

    try {
      const response = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          subject,
          student_id: studentId,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'The tutor could not answer.')
      }

      const answer =
        data.answer || data.response || data.message || JSON.stringify(data)

      setMessages((previous) => [
        ...previous,
        { role: 'assistant', text: answer },
      ])
    } catch (err) {
      setError(
        `${err.message}. Check that the FastAPI backend is running on port 8001.`,
      )
    } finally {
      setLoading(false)
    }
  }

  async function loadProfile() {
    setLoading(true)
    setError('')
    setProfile(null)

    try {
      const response = await fetch(`${API}/student/${studentId}/profile`)
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Could not load the profile.')
      }
      setProfile(data)
    } catch (err) {
      setError(
        `${err.message} The profile endpoint may use a different URL in your backend.`,
      )
    } finally {
      setLoading(false)
    }
  }

  async function generatePractice() {
    setLoading(true)
    setError('')
    setPractice('')

    try {
      const response = await fetch(`${API}/practice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          subject,
          topic: null,
          difficulty: 'medium',
          count: 5,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Could not generate practice questions.')
      }

      setPractice(
        typeof data === 'string'
          ? data
          : data.questions || data.practice_set || data.result || JSON.stringify(data, null, 2),
      )
    } catch (err) {
      setError(
        `${err.message} The practice endpoint may use a different URL in your backend.`,
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">E</div>
          <div>
            <h2>ExamPrep AI</h2>
            <span>YOUR PERSONAL STUDY PARTNER</span>
          </div>
        </div>

        <div className="side-label">WORKSPACE</div>
        <a className="nav-item active" href="#tutor">✦ <span>AI Tutor</span></a>
        <a className="nav-item" href="#practice">▤ <span>Practice Questions</span></a>
        <a className="nav-item" href="#progress">◷ <span>My Progress</span></a>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          <div>
            <strong>Study mode</strong>
            <p>Learn at your own pace</p>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">YOUR LEARNING SPACE</p>
            <h1>Let's make learning click.</h1>
          </div>
          <div className="student-chip">
            <div className="avatar">S</div>
            <div>
              <strong>Student</strong>
              <span>Personal study space</span>
            </div>
          </div>
        </header>

        <section className="welcome-banner">
          <div>
            <span className="banner-tag">✦ AI-POWERED LEARNING</span>
            <h2>Understand more.<br />Remember longer.</h2>
            <p>Ask questions, practise concepts, and focus on the topics that need attention.</p>
            <a href="#tutor" className="primary-link">Start learning <span>→</span></a>
          </div>
          <div className="banner-art" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="book-illustration">✧</div>
            <div className="float-card card-top">✦ Smart tutor</div>
            <div className="float-card card-bottom">✓ Learn step by step</div>
          </div>
        </section>

        <section className="quick-stats">
          <article className="stat-card">
            <div className="stat-icon purple">✦</div>
            <div><span>AI learning assistant</span><strong>Always ready</strong><small>Ask your next question</small></div>
          </article>
          <article className="stat-card">
            <div className="stat-icon orange">▤</div>
            <div><span>Practice sets</span><strong>On demand</strong><small>Generate 5 questions</small></div>
          </article>
          <article className="stat-card">
            <div className="stat-icon green">◉</div>
            <div><span>Personalized learning</span><strong>Topic aware</strong><small>Track mastery over time</small></div>
          </article>
        </section>

        <section className="workspace-grid">
          <article className="panel tutor-panel" id="tutor">
            <div className="panel-heading">
              <div>
                <span className="section-kicker">YOUR STUDY COMPANION</span>
                <h2>Ask your AI tutor</h2>
                <p>Get explanations grounded in your study material.</p>
              </div>
              <span className="live-badge"><i /> AI Tutor</span>
            </div>

            <div className="tutor-controls">
              <label>
                Subject
                <select value={subject} onChange={(event) => setSubject(event.target.value)}>
                  <option>Science</option>
                  <option>Math</option>
                </select>
              </label>
              <label>
                Student ID
                <input value={studentId} onChange={(event) => setStudentId(event.target.value)} />
              </label>
            </div>

            <div className="chat-messages">
              {messages.map((message, index) => (
                <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                  <div className="message-avatar">{message.role === 'assistant' ? '✦' : 'S'}</div>
                  <div className="message-body">
                    <strong>{message.role === 'assistant' ? 'ExamPrep AI' : 'You'}</strong>
                    <p>{message.text}</p>
                  </div>
                </div>
              ))}
              {loading && <div className="loading-note">Working on your request…</div>}
            </div>

            {error && <div className="error-message">{error}</div>}

            <form className="chat-form" onSubmit={sendQuestion}>
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a question, e.g. Explain photosynthesis..."
                aria-label="Your question"
              />
              <button type="submit" disabled={loading || !question.trim()}>
                {loading ? '…' : 'Send ↑'}
              </button>
            </form>
            <p className="privacy-note">✧ Answers may depend on the available curriculum and retrieved study material.</p>
          </article>

          <div className="right-column">
            <article className="panel practice-panel" id="practice">
              <div className="panel-heading">
                <div>
                  <span className="section-kicker">TEST YOURSELF</span>
                  <h2>Practice questions</h2>
                </div>
                <span className="practice-icon">✎</span>
              </div>
              <p className="panel-description">Create a set of five medium-difficulty questions for your selected subject.</p>
              <button className="secondary-button" onClick={generatePractice} disabled={loading}>
                Generate practice set <span>→</span>
              </button>
              {practice && <pre className="result-box">{practice}</pre>}
            </article>

            <article className="panel progress-panel" id="progress">
              <div className="panel-heading">
                <div>
                  <span className="section-kicker">LEARN SMARTER</span>
                  <h2>Learning progress</h2>
                </div>
                <span className="progress-icon">◉</span>
              </div>
              <p className="panel-description">Load your student profile to see recorded topics and mastery scores.</p>
              <button className="secondary-button" onClick={loadProfile} disabled={loading}>
                View my progress <span>→</span>
              </button>
              {profile && (
                <div className="profile-results">
                  <strong>Student: {profile.student_id || studentId}</strong>
                  {(profile.topics || profile.mastery_records || []).map((topic, index) => {
                    const score = Number(topic.mastery_score ?? topic.mastery ?? 0)
                    return (
                      <div className="mastery-item" key={`${topic.topic}-${index}`}>
                        <div><span>{topic.topic}</span><strong>{Math.round(score * 100)}%</strong></div>
                        <div className="progress-track"><div style={{ width: `${Math.max(0, Math.min(100, score * 100))}%` }} /></div>
                        <small>{topic.subject}</small>
                      </div>
                    )
                  })}
                  {!(profile.topics || profile.mastery_records || []).length && <p>No mastery records found yet.</p>}
                </div>
              )}
            </article>
          </div>
        </section>

        <footer className="footer">
          <span>ExamPrep AI · RAG-powered study assistant</span>
          <span>Math · Science · Personalized practice</span>
        </footer>
      </main>
    </div>
  )
}

export default App
