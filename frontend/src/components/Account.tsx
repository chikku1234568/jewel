import { SIGN_IN_URL, type Me } from '../lib/api'

const SIGN_IN_ERRORS: Record<string, string> = {
  google_denied: 'Google sign-in was cancelled.',
  missing_code: 'Google did not return a sign-in code. Please try again.',
  invalid_state: 'That sign-in link expired. Please try again.',
  token_invalid: 'Google sign-in could not be verified. Please try again.',
}

interface AccountProps {
  me: Me | null
  loading: boolean
  signInError: string | null
  onSignOut: () => void
  signingOut: boolean
}

/** Sign-in region: a link to the API's Google sign-in, or the signed-in user. */
export function Account({ me, loading, signInError, onSignOut, signingOut }: AccountProps) {
  if (loading) {
    return <p className="hint">Checking your session…</p>
  }

  if (me) {
    return (
      <div className="account">
        <div>
          <strong>{me.name ?? me.email}</strong>
          {me.name ? <span className="muted"> {me.email}</span> : null}
        </div>
        <button type="button" onClick={onSignOut} disabled={signingOut}>
          {signingOut ? 'Signing out…' : 'Sign out'}
        </button>
      </div>
    )
  }

  return (
    <div>
      <a className="button" href={SIGN_IN_URL}>
        Sign in with Google
      </a>
      {signInError ? (
        <p className="error" role="alert">
          {SIGN_IN_ERRORS[signInError] ?? 'Sign-in failed. Please try again.'}
        </p>
      ) : (
        <p className="hint">Sign in to upload and keep your documents.</p>
      )}
    </div>
  )
}
