import { useEffect, useRef, useState } from 'react';
import kaizensLogo from '../assets/kaizens-logo.webp';
import ReactMarkdown from 'react-markdown';
import FieldListPanel from './FieldListPanel';
import {
  correctFieldList,
  generateFiles,
  type FieldListData,
  type SessionCreatedResponse,
} from '../api';

interface Message {
  role: 'assistant' | 'user';
  content: string;
}

interface Props {
  sessionId: string;
  parsed: SessionCreatedResponse;
  initialMessage: string;
  initialFieldList: FieldListData;
  onGenerated: (files: Record<string, string>) => void;
}

/** Keys ("BLOCK:FIELD") that differ between two field list versions. */
function diffFieldLists(prev: FieldListData, next: FieldListData): Set<string> {
  const prevMap = new Map<string, string>();
  for (const b of prev.blocks) {
    for (const f of b.fields) {
      prevMap.set(`${b.name}:${f.name}`, `${f.data_type}|${f.hidden}`);
    }
  }
  const changed = new Set<string>();
  for (const b of next.blocks) {
    for (const f of b.fields) {
      const key = `${b.name}:${f.name}`;
      if (prevMap.get(key) !== `${f.data_type}|${f.hidden}`) changed.add(key);
    }
  }
  return changed;
}

export default function ReviewStep({ sessionId, parsed, initialMessage, initialFieldList, onGenerated }: Props) {
  const [fieldList, setFieldList] = useState<FieldListData>(initialFieldList);
  const [changedKeys, setChangedKeys] = useState<Set<string>>(new Set());
  const [manualEdits, setManualEdits] = useState(0);
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

  const totalFields = fieldList.blocks.reduce((n, b) => n + b.fields.length, 0);

  function handleManualChange(next: FieldListData) {
    setFieldList(next);
    setManualEdits(n => n + 1);
  }

  async function sendCorrection() {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setLoading(true);
    setError('');
    try {
      const res = await correctFieldList(sessionId, text, fieldList);
      setChangedKeys(diffFieldLists(fieldList, res.field_list));
      setFieldList(res.field_list);
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
      const res = await generateFiles(sessionId, fieldList);
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
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-950/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <img src={kaizensLogo} alt="Kaizens" className="h-7 w-auto" />
          <div>
            <p className="text-sm font-semibold text-slate-100">{parsed.report_name}</p>
            <p className="text-xs text-slate-500">
              {parsed.report_title} · {fieldList.blocks.length} block{fieldList.blocks.length !== 1 ? 's' : ''} · {totalFields} fields
            </p>
          </div>
        </div>
      </header>

      {/* Split view */}
      <div className="flex-1 grid grid-cols-5 min-h-0">
        {/* Field list — main work surface */}
        <div className="col-span-3 border-r border-slate-800 min-h-0">
          <FieldListPanel
            fieldList={fieldList}
            changedKeys={changedKeys}
            onChange={handleManualChange}
          />
        </div>

        {/* Chat assistant panel */}
        <div className="col-span-2 flex flex-col min-h-0">
          <div className="px-4 py-2.5 border-b border-slate-800 shrink-0">
            <p className="text-xs font-medium text-slate-400">AI assistant</p>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed
                    ${msg.role === 'assistant'
                      ? 'bg-slate-900 text-slate-100 rounded-tl-sm'
                      : 'bg-indigo-600 text-white rounded-tr-sm'
                    }`}
                >
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-slate-800 prose-p:my-1">
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
                <div className="bg-slate-900 rounded-2xl rounded-tl-sm px-3.5 py-2.5">
                  <TypingIndicator />
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-red-950/50 border border-red-800 text-red-300 text-xs px-3 py-2">
                {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="border-t border-slate-800 px-3 py-3 shrink-0">
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask for changes…"
                disabled={loading}
                className="flex-1 resize-none rounded-xl bg-slate-900 border border-slate-700 px-3 py-2
                           text-xs text-slate-100 placeholder-slate-500
                           focus:outline-none focus:ring-2 focus:ring-indigo-500
                           disabled:opacity-50 max-h-32"
              />
              <button
                onClick={sendCorrection}
                disabled={!input.trim() || loading}
                className="px-3 py-2 rounded-xl bg-slate-800 text-slate-300 text-xs font-medium
                           hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-end gap-4 px-6 py-3 border-t border-slate-800 bg-slate-950 shrink-0">
        <span className="text-xs text-slate-500">
          {manualEdits > 0 && `${manualEdits} manual edit${manualEdits !== 1 ? 's' : ''}`}
          {manualEdits > 0 && changedKeys.size > 0 && ' · '}
          {changedKeys.size > 0 && `${changedKeys.size} AI change${changedKeys.size !== 1 ? 's' : ''} highlighted`}
        </span>
        <button
          onClick={handleGenerate}
          disabled={loading || generating}
          className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold
                     disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {generating ? (
            <span className="flex items-center gap-2"><Spinner />Generating…</span>
          ) : (
            'Generate IFS Report Definition ▶'
          )}
        </button>
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
