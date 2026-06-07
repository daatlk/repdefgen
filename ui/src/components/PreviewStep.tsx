import { useState } from 'react';
import kaizensLogo from '../assets/kaizens-logo.webp';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { applyCorrection, downloadUrl } from '../api';

interface Props {
  sessionId: string;
  files: Record<string, string>;
  onRestart: () => void;
}

export default function PreviewStep({ sessionId, files: initialFiles, onRestart }: Props) {
  const [files, setFiles] = useState(initialFiles);
  const filenames = Object.keys(files);
  const [activeTab, setActiveTab] = useState(filenames[0] ?? '');
  const [correction, setCorrection] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const rdfFile = filenames.find(f => f.endsWith('.rdf')) ?? activeTab;

  async function handleApply() {
    if (!correction.trim()) return;
    setLoading(true);
    setError('');
    try {
      const res = await applyCorrection(sessionId, correction);
      setFiles(res.files);
      setCorrection('');
      showToast('Correction applied ✓');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(''), 3000);
  }

  function handleCopy() {
    navigator.clipboard.writeText(files[activeTab] ?? '');
    showToast('Copied to clipboard ✓');
  }

  const ext = activeTab.endsWith('.rdf') ? 'sql' : 'xml';

  return (
    <div className="flex flex-col h-screen bg-slate-950">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-slate-950/80 backdrop-blur shrink-0">
        <div className="flex items-center gap-3">
          <img src={kaizensLogo} alt="Kaizens" className="h-7 w-auto" />
        </div>
        <button
          onClick={onRestart}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-3 py-1 rounded-lg hover:bg-slate-800"
        >
          ← New report
        </button>
      </header>

      {/* Tabs + actions */}
      <div className="flex items-center justify-between px-4 pt-4 pb-0 shrink-0">
        <div className="flex gap-1 bg-slate-900 rounded-lg p-1">
          {filenames.map(name => (
            <button
              key={name}
              onClick={() => setActiveTab(name)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors
                ${activeTab === name
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 transition-colors"
          >
            Copy
          </button>
          <a
            href={downloadUrl(sessionId, activeTab)}
            download={activeTab}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium transition-colors"
          >
            ↓ Download
          </a>
        </div>
      </div>

      {/* Code viewer */}
      <div className="flex-1 overflow-auto px-4 py-3">
        <div className="rounded-xl overflow-hidden border border-slate-800 h-full">
          <SyntaxHighlighter
            language={ext}
            style={vscDarkPlus}
            customStyle={{
              margin: 0,
              borderRadius: 0,
              fontSize: '12.5px',
              lineHeight: '1.6',
              height: '100%',
              background: '#0f172a',
            }}
            showLineNumbers
            lineNumberStyle={{ color: '#475569', minWidth: '3em' }}
          >
            {files[activeTab] ?? ''}
          </SyntaxHighlighter>
        </div>
      </div>

      {/* Correction bar */}
      <div className="border-t border-slate-800 bg-slate-950 px-4 py-3 shrink-0">
        <div className="max-w-3xl mx-auto">
          <p className="text-xs text-slate-500 mb-2">
            Request a SQL correction — only <span className="text-slate-400 font-mono">{rdfFile}</span> is rewritten
          </p>
          <div className="flex gap-2 items-center">
            <input
              type="text"
              value={correction}
              onChange={e => setCorrection(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleApply()}
              placeholder="e.g. fix GROUP BY in header cursor, add LEFT JOIN customer_info_address"
              disabled={loading}
              className="flex-1 rounded-xl bg-slate-900 border border-slate-700 px-4 py-2.5
                         text-sm text-slate-100 placeholder-slate-500
                         focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
            />
            <button
              onClick={handleApply}
              disabled={!correction.trim() || loading}
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold
                         disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              {loading ? 'Applying…' : 'Apply'}
            </button>
          </div>
          {error && (
            <p className="mt-2 text-xs text-red-400">{error}</p>
          )}
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 -translate-x-1/2 bg-slate-800 text-slate-100 text-sm
                        px-4 py-2 rounded-full shadow-lg border border-slate-700 pointer-events-none">
          {toast}
        </div>
      )}
    </div>
  );
}
