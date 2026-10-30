
import { useEffect, useState } from 'react'
import { onIdTokenChanged } from 'firebase/auth'
import { auth } from './firebase'
import Auth from './Auth'
import App from './App'

function AuthWrapper() {
  const [user, setUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [authError, setAuthError] = useState('')

  useEffect(() => {
    let active = true

    const unsubscribe = onIdTokenChanged(auth, async (currentUser) => {
      if (!active) return

      
      setAuthError('')

      if (!currentUser) {
        setUser(null)
        setCheckingAuth(false)
        return
      }

      try {
        // Wait until Firebase can provide the user's ID token.
        await currentUser.getIdToken()

        if (active) {
          setUser(currentUser)
        }
      } catch (error) {
        console.error('Firebase authentication initialization failed:', error)

        if (active) {
          setUser(null)
          setAuthError('Unable to initialize authentication. Please sign in again.')
        }
      } finally {
        if (active) {
          setCheckingAuth(false)
        }
      }
    })

    return () => {
      active = false
      unsubscribe()
    }
  }, [])

  if (checkingAuth) {
    return (
      <div className="auth-loading">
        <div className="auth-loader"></div>
        <p>Loading ExamPrep AI...</p>
      </div>
    )
  }

  if (authError) {
    return (
      <div className="auth-loading">
        <p>{authError}</p>
        <button onClick={() => auth.signOut()}>
          Return to sign in
        </button>
      </div>
    )
  }

  if (!user) {
    return <Auth />
  }

  return <App user={user} />
}

export default AuthWrapper
