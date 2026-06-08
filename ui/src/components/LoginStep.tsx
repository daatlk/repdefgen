import { useState } from 'react';
import kaizensLogo from '../assets/kaizens-logo.webp';
import { login } from '../api';

interface Props {
  onLogin: () => void;
}

export default function LoginStep({ onLogin }: Props) {
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!password.trim() || loading) return;
    setLoading(true);
    setError('');
    try {
      await login(password);
      onLogin();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 bg-slate-950">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-10">
          <img src={kaizensLogo} alt="Kaizens" className="h-10 w-auto mb-6" />
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">RepDefGen</h1>
          <p className="mt-1 text-sm text-slate-400">Sign in to continue</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter password"
              autoFocus
              disabled={loading}
              className="w-full rounded-xl bg-slate-900 border border-slate-700 px-4 py-3
                         text-sm text-slate-100 placeholder-slate-500
                         focus:outline-none focus:ring-2 focus:ring-indigo-500
                         disabled:opacity-50"
            />
          </div>

          {error && (
            <div className="rounded-lg bg-red-950/50 border border-red-800 text-red-300 text-sm px-4 py-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!password.trim() || loading}
            className="w-full py-3 rounded-xl font-semibold text-sm tracking-wide transition-all
                       bg-indigo-600 hover:bg-indigo-500 text-white
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Spinner /> Signing in…
              </span>
            ) : (
              'Sign in'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
