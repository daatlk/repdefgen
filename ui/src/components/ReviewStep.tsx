import { useEffect, useRef, useState } from 'react';
import kaizensLogo from '../assets/kaizens-logo.webp';
import ReactMarkdown from 'react-markdown';
import { correctFieldList, generateFiles, type SessionCreatedResponse } from '../api';

interface Message {
  role: 'assistant' | 'user';
  content: string;
}

interface Props {
  sessionId: string;
  parsed: SessionCreatedResponse;
  initialMessage: string;
  onGenerated: (files: Record<string, string>) => void;
}

export default function ReviewStep({ sessionId, parsed, initialMessage, onGenerated }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: initialMessage },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendCorrection() {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    setError('');
    try {
      const res = await correctFieldList(sessionId, text);
      setMessages(prev => [...prev, { role: 'assistant', content: res.message }]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError('');
    try {
      const res = await generateFiles(sessionId);
      onGenerated(res.files);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setGenerating(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendCorrection();
    }
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="flex items-center gap-3">
          <img src={kaizensLogo} alt="Kaizens" className="h-7 w-auto" />
          <div>
            <p className="text-sm font-semibold text-slate-100">{parsed.report_name}</p>
            <p className="text-xs text-slate-500">{parsed.report_title} · {parsed.blocks.length} block{parsed.blocks.length !== 1 ? 's' : ''}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {parsed.blocks.map(b => (
            <span key={b.name} className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">
              {b.name} ({b.field_count})
            </span>
          ))}
        </div>
      </header>

      {/* Chat messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs mr-2 mt-0.5 shrink-0">
                AI
              </div>
            )}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed
                ${msg.role === 'assistant'
                  ? 'bg-slate-900 text-slate-100 rounded-tl-sm'
                  : 'bg-indigo-600 text-white rounded-tr-sm'
                }`}
            >
              {msg.role === 'assistant' ? (
                <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-800">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs mr-2 mt-0.5">AI</div>
            <div className="bg-slate-900 rounded-2xl rounded-tl-sm px-4 py-3">
              <TypingIndicator />
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-950/50 border border-red-800 text-red-300 text-xs px-4 py-2 mx-auto max-w-lg text-center">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Bottom bar */}
      <div className="border-t border-slate-800 bg-slate-950 px-4 py-3">
        <div className="max-w-3xl mx-auto flex gap-2 items-end">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a correction… (Enter to send, Shift+Enter for new line)"
            disabled={loading}
            className="flex-1 resize-none rounded-xl bg-slate-900 border border-slate-700 px-4 py-2.5
                       text-sm text-slate-100 placeholder-slate-500
                       focus:outline-none focus:ring-2 focus:ring-indigo-500
                       disabled:opacity-50 max-h-32"
          />
          <button
            onClick={sendCorrection}
            disabled={!input.trim() || loading}
            className="px-4 py-2.5 rounded-xl bg-slate-800 text-slate-300 text-sm font-medium
                       hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            Send
          </button>
          <button
            onClick={handleGenerate}
            disabled={loading || generating}
            className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold
                       disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0 whitespace-nowrap"
          >
            {generating ? (
              <span className="flex items-center gap-2"><Spinner />Generating…</span>
            ) : (
              'Generate IFS Report Definition ▶'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex gap-1 items-center h-4">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="block w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
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
