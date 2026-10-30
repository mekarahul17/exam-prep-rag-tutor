import { useEffect, useState } from 'react'
import { signOut } from 'firebase/auth'
import ReactMarkdown from 'react-markdown'
import remarkMath from 'remark-math'
import rehypeKatex from 'rehype-katex'
import 'katex/dist/katex.min.css'
import { auth } from './firebase'
import './App.css'

const API = 'http://127.0.0.1:8001'

// Remove Markdown escape characters sometimes emitted by the LLM.
// LaTeX commands such as \frac, \sqrt, \theta and \text are preserved.
function normalizeMarkdown(value) {
  if (typeof value !== 'string') return String(value ?? '')

  return value
    .replace(/\\([\\`*_{}\[\]()#+.!|>~-])/g, '$1')
    .replace(/&#x20;/gi, ' ')
    .replace(/&#x69;/gi, 'i')
    .replace(/&nbsp;/gi, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .trim()
}

function TutorMarkdown({ content }) {
  return (
    <div className="tutor-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer">{children}</a>
          ),
        }}
      >
        {normalizeMarkdown(content)}
      </ReactMarkdown>
    </div>
  )
}

function App({ user }) {
  const [subject, setSubject] = useState('Auto')
  const [studentId] = useState(user?.uid || '')
  const [question, setQuestion] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)
  const [imageMode, setImageMode] = useState('handwritten')
  const [imagePreview, setImagePreview] = useState('')
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Hi! I am your AI study tutor. Ask me anything about your Math or Science syllabus, or generate a practice set to test your understanding.',
    },
  ])

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [profile, setProfile] = useState(null)
  const [quiz, setQuiz] = useState(null)
  const [answers, setAnswers] = useState({})
  const [evaluation, setEvaluation] = useState(null)

  // Persistent conversation history
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [historySearch, setHistorySearch] = useState('')
  const [historyLoading, setHistoryLoading] = useState(false)

  useEffect(() => {
    if (!selectedImage) {
      setImagePreview('')
      return undefined
    }

    const previewUrl = URL.createObjectURL(selectedImage)
    setImagePreview(previewUrl)
    return () => URL.revokeObjectURL(previewUrl)
  }, [selectedImage])

  
async function apiRequest(url, options = {}) {
  // Always use the latest authenticated Firebase user.
  const currentUser = auth.currentUser || user;

  if (!currentUser) {
    throw new Error('You must be signed in to use ExamPrep AI.');
  }

  async function sendRequest(forceRefresh = false) {
    const idToken = await currentUser.getIdToken(forceRefresh);

    const response = await fetch(`${API}${url}`, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${idToken}`,
      },
    });

    let data = {};

    try {
      data = await response.json();
    } catch {
      data = {};
    }

    return { response, data };
  }

  // First attempt using the current Firebase token.
  let { response, data } = await sendRequest(false);

  // If authentication fails, refresh the token and retry once.
  if (response.status === 401) {
    ({ response, data } = await sendRequest(true));
  }

  if (!response.ok) {
    throw new Error(
      data.detail || `Request failed with status ${response.status}`
    );
  }

  return data;
}


  async function loadConversations(search = '') {
    setHistoryLoading(true)
    try {
      const query = search.trim()
        ? `?search=${encodeURIComponent(search.trim())}`
        : ''
      const data = await apiRequest(`/conversations${query}`)
      setConversations(data.conversations || [])
    } finally {
      setHistoryLoading(false)
    }
  }

  async function openConversation(conversationId) {
    if (loading) return
    setLoading(true)
    setError('')
    try {
      const data = await apiRequest(
        `/conversations/${encodeURIComponent(conversationId)}`
      )
      setActiveConversationId(conversationId)
      setMessages((data.messages || []).map((message) => ({
        role: message.role,
        text: message.content,
      })))
      setQuestion('')
      setSelectedImage(null)
      setQuiz(null)
      setAnswers({})
      setEvaluation(null)
      setProfile(null)
      document.getElementById('tutor')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function createNewChat() {
    if (loading) return
    setActiveConversationId(null)
    setMessages([{
      role: 'assistant',
      text: 'Hi! I am your AI study tutor. Ask me anything about your Math or Science syllabus, or generate a practice set to test your understanding.',
    }])
    setQuestion('')
    setSelectedImage(null)
    setQuiz(null)
    setAnswers({})
    setEvaluation(null)
    setProfile(null)
    setError('')
  }

  async function renameConversation(conversationId, currentTitle) {
    const newTitle = window.prompt('Enter a new conversation name:', currentTitle)
    if (newTitle === null || !newTitle.trim()) return
    try {
      await apiRequest(`/conversations/${encodeURIComponent(conversationId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle.trim() }),
      })
      await loadConversations(historySearch)
    } catch (err) {
      setError(err.message)
    }
  }

  async function deleteConversation(conversationId) {
    if (!window.confirm('Delete this conversation permanently?')) return
    try {
      await apiRequest(`/conversations/${encodeURIComponent(conversationId)}`, {
        method: 'DELETE',
      })
      setConversations((previous) => previous.filter(
        (item) => item.conversation_id !== conversationId
      ))
      if (activeConversationId === conversationId) createNewChat()
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    if (!user?.uid) {
      setConversations([])
      setActiveConversationId(null)
      return
    }
    loadConversations().catch((err) => {
      setError(`Unable to load chat history: ${err.message}`)
    })
    // Reload history when the authenticated Firebase account changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.uid])

  async function sendQuestion(event) {
    event.preventDefault()
    const text = question.trim()
    if ((!text && !selectedImage) || loading) return

    const imageToSend = selectedImage
    const selectedMode = imageMode
    const promptText = text || (
      selectedMode === 'handwritten'
        ? 'Please read my handwritten notes and explain the content.'
        : 'Please explain this textbook diagram.'
    )

    setMessages((previous) => [...previous, { role: 'user', text: promptText }])
    setQuestion('')
    setSelectedImage(null)
    setLoading(true)
    setError('')

    try {
      // Create a conversation only when the first question is sent.
      let conversationId = activeConversationId
      if (!conversationId) {
        const created = await apiRequest('/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: promptText.slice(0, 60) || 'New chat' }),
        })
        conversationId = created.conversation_id
        setActiveConversationId(conversationId)
      }

      let data
      if (imageToSend) {
        const formData = new FormData()
        formData.append('image', imageToSend)
        formData.append('mode', selectedMode)
        formData.append('subject', subject)
        formData.append('question', text)

        // Do not set Content-Type manually: the browser adds the multipart boundary.
        data = await apiRequest('/multimodal', {
          method: 'POST',
          body: formData,
        })
      } else {
        data = await apiRequest('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: text,
            subject,
            student_id: studentId,
          }),
        })
      }

      const answer =
        data.answer || data.response || data.message || JSON.stringify(data)

      setMessages((previous) => [...previous, { role: 'assistant', text: answer }])

      // Save the completed text or image exchange in persistent chat history.
      try {
        await apiRequest(
          `/conversations/${encodeURIComponent(conversationId)}/turn`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_message: promptText,
              assistant_message: answer,
              metadata: {
                type: imageToSend ? 'multimodal' : 'text',
                image_mode: imageToSend ? selectedMode : null,
                image_name: imageToSend ? imageToSend.name : null,
                subject,
              },
            }),
          }
        )
        await loadConversations(historySearch)
      } catch (saveError) {
        setError(
          `Your answer was generated, but chat history could not be saved: ${saveError.message}`
        )
      }
    } catch (err) {
      setError(`${err.message} Check that the backend is running on port 8001.`)
    } finally {
      setLoading(false)
    }
  }

  function handleImageSelection(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    if (!file.type.startsWith('image/')) {
      setError('Please select an image file.')
      return
    }

    if (file.size > 5 * 1024 * 1024) {
      setError('Image must be 5 MB or smaller.')
      return
    }

    setError('')
    setSelectedImage(file)
  }

  async function generatePractice() {
    if (loading) return
    if (subject === 'Auto') {
      setError('Choose Mathematics or Science before generating a practice set.')
      return
    }

    setLoading(true)
    setError('')
    setQuiz(null)
    setAnswers({})
    setEvaluation(null)

    try {
      const data = await apiRequest('/practice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId.trim(),
          subject,
          topic: null,
          difficulty: 'medium',
          count: 5,
        }),
      })

      if (!data.quiz_id || !Array.isArray(data.questions)) {
        throw new Error('Unexpected practice response from backend.')
      }

      setQuiz(data)

      document.getElementById('practice')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function selectAnswer(questionId, selectedOption) {
    if (evaluation) return

    setAnswers((previous) => ({
      ...previous,
      [questionId]: selectedOption,
    }))
  }

  async function submitQuiz() {
    if (!quiz || loading) return

    if (Object.keys(answers).length === 0) {
      setError('Please answer at least one question before submitting.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const data = await apiRequest('/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          quiz_id: quiz.quiz_id,
          student_id: studentId.trim(),
          answers,
        }),
      })

      setEvaluation(data)
      setProfile(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadProfile() {
    if (loading) return

    setLoading(true)
    setError('')
    setProfile(null)

    try {
      const data = await apiRequest(
        `/student/${encodeURIComponent(studentId.trim())}/profile`
      )

      setProfile(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const profileTopics = profile?.topics || profile?.mastery_records || []

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

        <a className="nav-item active" href="#tutor">
          ✦ <span>AI Tutor</span>
        </a>

        <a className="nav-item" href="#practice">
          ▤ <span>Practice Questions</span>
        </a>

        <a className="nav-item" href="#progress">
          ◷ <span>My Progress</span>
        </a>

        <section className="history-section" aria-label="Chat history">
          <div className="history-heading">
            <span className="side-label">YOUR CHATS</span>
            <button
              type="button"
              className="new-chat-button"
              onClick={createNewChat}
              disabled={loading}
            >
              + New chat
            </button>
          </div>

          <form
            className="history-search"
            onSubmit={(event) => {
              event.preventDefault()
              loadConversations(historySearch).catch((err) => setError(err.message))
            }}
          >
            <input
              value={historySearch}
              onChange={(event) => setHistorySearch(event.target.value)}
              placeholder="Search chats..."
              aria-label="Search conversations"
            />
            <button type="submit" aria-label="Search conversations">⌕</button>
          </form>

          <div className="conversation-list">
            {historyLoading && <p className="history-empty">Loading chats...</p>}
            {!historyLoading && conversations.length === 0 && (
              <p className="history-empty">No conversations yet.</p>
            )}
            {conversations.map((conversation) => (
              <div
                className={`conversation-item ${
                  activeConversationId === conversation.conversation_id ? 'selected' : ''
                }`}
                key={conversation.conversation_id}
              >
                <button
                  type="button"
                  className="conversation-open"
                  onClick={() => openConversation(conversation.conversation_id)}
                  disabled={loading}
                  title={conversation.title}
                >
                  <span className="conversation-title">{conversation.title}</span>
                </button>
                <div className="conversation-actions">
                  <button
                    type="button"
                    title="Rename conversation"
                    aria-label="Rename conversation"
                    onClick={() => renameConversation(
                      conversation.conversation_id,
                      conversation.title
                    )}
                  >✎</button>
                  <button
                    type="button"
                    title="Delete conversation"
                    aria-label="Delete conversation"
                    onClick={() => deleteConversation(conversation.conversation_id)}
                  >×</button>
                </div>
              </div>
            ))}
          </div>
        </section>

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

          <div className="student-actions">
            <div className="student-chip">
              <div className="avatar">
                {(user?.displayName || user?.email || 'S')
                  .charAt(0)
                  .toUpperCase()}
              </div>
              <div>
                <strong>{user?.displayName || user?.email || 'Student'}</strong>
                <span>Personal study space</span>
              </div>
            </div>

            <button
              type="button"
              className="logout-btn"
              onClick={() => signOut(auth)}
            >
              Sign out
            </button>
          </div>
        </header>

        <section className="welcome-banner">
          <div>
            <span className="banner-tag">✦ AI-POWERED LEARNING</span>
            <h2>Understand more.<br />Remember longer.</h2>
            <p>
              Ask questions, practise concepts, and focus on the topics that
              need attention.
            </p>
            <a href="#tutor" className="primary-link">
              Start learning <span>→</span>
            </a>
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
            <div>
              <span>AI learning assistant</span>
              <strong>Always ready</strong>
              <small>Ask your next question</small>
            </div>
          </article>

          <article className="stat-card">
            <div className="stat-icon orange">▤</div>
            <div>
              <span>Practice sets</span>
              <strong>On demand</strong>
              <small>Generate 5 questions</small>
            </div>
          </article>

          <article className="stat-card">
            <div className="stat-icon green">◉</div>
            <div>
              <span>Personalized learning</span>
              <strong>Topic aware</strong>
              <small>Track mastery over time</small>
            </div>
          </article>
        </section>

        {error && (
          <div className="error-message">
            <span>⚠</span> {error}
            <button onClick={() => setError('')} aria-label="Dismiss error">
              ×
            </button>
          </div>
        )}

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
                <select
                  value={subject}
                  onChange={(event) => setSubject(event.target.value)}
                >
                  <option value="Auto">Auto Detect</option>
                  <option value="Science">Science</option>
                  <option value="Mathematics">Mathematics</option>
                </select>
              </label>

              <label>
                Student ID
                <input
                  value={studentId}
                  readOnly
                  aria-label="Authenticated student ID"
                  title="Your student ID is assigned by your signed-in account."
                />
              </label>
            </div>

            <div className="chat-messages">
              {messages.map((message, index) => (
                <div
                  className={`message ${message.role}`}
                  key={`${message.role}-${index}`}
                >
                  <div className="message-avatar">
                    {message.role === 'assistant' ? '✦' : 'S'}
                  </div>

                  <div className="message-body">
                    <strong>
                      {message.role === 'assistant' ? 'ExamPrep AI' : 'You'}
                    </strong>
                    <TutorMarkdown content={message.text} />
                  </div>
                </div>
              ))}

              {loading && (
                <div className="loading-note">
                  Working on your request…
                </div>
              )}
            </div>

            {selectedImage && (
              <div className="selected-image-card">
                <img src={imagePreview} alt="Selected study material preview" />
                <div className="selected-image-info">
                  <strong>{selectedImage.name}</strong>
                  <span>{(selectedImage.size / (1024 * 1024)).toFixed(2)} MB · Ready to upload</span>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedImage(null)}
                  aria-label="Remove selected image"
                  title="Remove image"
                >
                  ×
                </button>
              </div>
            )}

            <div className="image-tools-row">
              <label className="image-upload-button">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
                  onChange={handleImageSelection}
                  disabled={loading}
                />
                <span>＋ Add image</span>
              </label>

              <select
                value={imageMode}
                onChange={(event) => setImageMode(event.target.value)}
                disabled={loading}
                aria-label="Image type"
              >
                <option value="handwritten">Handwritten notes</option>
                <option value="diagram">Textbook diagram</option>
              </select>

              <span className="image-help-text">JPG, PNG, WEBP, BMP or TIFF · Max 5 MB</span>
            </div>

            <form className="chat-form" onSubmit={sendQuestion}>
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder={selectedImage ? 'Add an optional question about this image...' : 'Ask a question, e.g. Explain photosynthesis...'}
                aria-label="Your question"
              />

              <button type="submit" disabled={loading || (!question.trim() && !selectedImage)}>
                {loading ? '…' : selectedImage ? 'Upload & explain ↑' : 'Send ↑'}
              </button>
            </form>

            <p className="privacy-note">
              ✧ Answers may depend on the available curriculum and retrieved
              study material.
            </p>
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

              <p className="panel-description">
                Generate five medium-difficulty questions for {subject}.
                The tutor can select a weak topic automatically.
              </p>

              <button
                className="secondary-button"
                onClick={generatePractice}
                disabled={loading || !studentId.trim()}
              >
                {loading ? 'Generating…' : 'Generate practice set'}
                <span>→</span>
              </button>

              {quiz && (
                <div className="quiz-container">
                  <div className="quiz-heading">
                    <div>
                      <strong>{quiz.topic || subject}</strong>
                      <small>{quiz.difficulty || 'Medium'} difficulty</small>
                    </div>
                    <span>{quiz.questions.length} Questions</span>
                  </div>

                  {quiz.questions.map((item, index) => {
                    // FIX: Define result at question level so the entire
                    // question, options, and explanation can access it.
                    const result = evaluation?.results?.find(
                      (entry) => entry.question_id === item.id
                    )

                    return (
                      <div className="quiz-question" key={item.id}>
                        <h3>
                          <span>{index + 1}.</span> {item.question}
                        </h3>

                        <div className="quiz-options">
                          {(item.options || []).map((option, optionIndex) => {
                            const selected = answers[item.id] === option
                            let optionClass = selected ? 'selected' : ''

                            if (
                              evaluation &&
                              option === result?.correct_answer
                            ) {
                              optionClass = 'correct'
                            } else if (
                              evaluation &&
                              selected &&
                              !result?.is_correct
                            ) {
                              optionClass = 'incorrect'
                            }

                            return (
                              <button
                                type="button"
                                key={optionIndex}
                                className={`quiz-option ${optionClass}`}
                                disabled={Boolean(evaluation) || loading}
                                onClick={() => selectAnswer(item.id, option)}
                              >
                                <span className="option-letter">
                                  {String.fromCharCode(65 + optionIndex)}
                                </span>

                                <span>{option}</span>

                                {evaluation &&
                                  option === result?.correct_answer && (
                                    <span className="option-status">✓</span>
                                  )}
                              </button>
                            )
                          })}
                        </div>

                        {evaluation && (
                          <div
                            className={`answer-explanation ${
                              result?.is_correct ? 'right' : 'wrong'
                            }`}
                          >
                            <strong>
                              {result?.is_correct
                                ? 'Correct answer'
                                : 'Incorrect answer'}
                            </strong>

                            <p>
                              {result?.explanation ||
                                `Correct answer: ${
                                  result?.correct_answer || 'Not available'
                                }`}
                            </p>
                          </div>
                        )}
                      </div>
                    )
                  })}

                  {!evaluation ? (
                    <div className="quiz-submit-area">
                      <span>
                        {Object.keys(answers).length} of{' '}
                        {quiz.questions.length} answered
                      </span>

                      <button
                        className="submit-quiz-button"
                        onClick={submitQuiz}
                        disabled={
                          loading || Object.keys(answers).length === 0
                        }
                      >
                        {loading ? 'Submitting…' : 'Submit answers'}
                      </button>
                    </div>
                  ) : (
                    <div className="quiz-result">
                      <div className="result-score">
                        <strong>{evaluation.score}%</strong>
                        <span>Your score</span>
                      </div>

                      <div>
                        <h3>
                          {evaluation.correct} / {evaluation.total} correct
                        </h3>

                        <p>
                          {evaluation.score >= 80
                            ? 'Excellent work! Keep it up.'
                            : evaluation.score >= 50
                              ? 'Good effort. Review the explanations and try again.'
                              : 'Keep practising. Review the explanations and strengthen this topic.'}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </article>

            <article className="panel progress-panel" id="progress">
              <div className="panel-heading">
                <div>
                  <span className="section-kicker">LEARN SMARTER</span>
                  <h2>Learning progress</h2>
                </div>
                <span className="progress-icon">◉</span>
              </div>

              <p className="panel-description">
                View your recorded topics and mastery scores.
              </p>

              <button
                className="secondary-button"
                onClick={loadProfile}
                disabled={loading || !studentId.trim()}
              >
                {loading ? 'Loading…' : 'View my progress'}
                <span>→</span>
              </button>

              {profile && (
                <div className="profile-results">
                  <strong className="profile-student">
                    Student: {profile.student_id || studentId}
                  </strong>

                  {profileTopics.map((topic, index) => {
                    const score = Number(
                      topic.mastery_score ?? topic.mastery ?? 0
                    )

                    const percentage = Math.max(
                      0,
                      Math.min(100, score * 100)
                    )

                    return (
                      <div
                        className="mastery-item"
                        key={`${topic.topic}-${index}`}
                      >
                        <div className="mastery-label">
                          <span>{topic.topic}</span>
                          <strong>{Math.round(percentage)}%</strong>
                        </div>

                        <div className="progress-track">
                          <div style={{ width: `${percentage}%` }} />
                        </div>

                        <small>{topic.subject}</small>
                      </div>
                    )
                  })}

                  {profileTopics.length === 0 && (
                    <p className="empty-profile">
                      No mastery records found yet. Complete a practice quiz
                      to start tracking progress.
                    </p>
                  )}
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
