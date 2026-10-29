
import { useEffect, useState } from 'react'
import { onAuthStateChanged } from 'firebase/auth'
import { auth } from './firebase'
import Auth from './Auth'
import App from './App'

function AuthWrapper() {
  const [user, setUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser)
      setCheckingAuth(false)
    })

    return () => unsubscribe()
  }, [])

  if (checkingAuth) {
    return (
      <div className="auth-loading">
        <div className="auth-loader"></div>
        <p>Loading ExamPrep AI...</p>
      </div>
    )
  }

  if (!user) {
    return <Auth />
  }

  return <App user={user} />
}

export default AuthWrapper

