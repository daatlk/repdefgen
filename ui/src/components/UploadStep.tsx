import { useCallback, useState } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { createSession, proposeFieldList, type SessionCreatedResponse } from '../api';

interface Props {
  onDone: (sessionId: string, parsed: SessionCreatedResponse, firstMessage: string) => void;
}

export default function UploadStep({ onDone }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [luName, setLuName] = useState('');
  const [module, setModule] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onDrop = useCallback((accepted: File[], rejected: FileRejection[]) => {
    if (rejected.length > 0) {
      setError('Only .rdl files are supported.');
      return;
    }
    setFile(accepted[0]);
    setError('');
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/octet-stream': ['.rdl'] },
    maxFiles: 1,
  });

  const canSubmit = file && luName.trim() && module.trim() && description.trim() && !loading;

  async function handleSubmit() {
    if (!canSubmit) return;
    setLoading(true);
    setError('');
    try {
      const session = await createSession(file!);
      const proposal = await proposeFieldList(session.session_id, luName, module, description);
      onDone(session.session_id, session, proposal.message);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 py-12">
      {/* Header */}
      <div className="mb-10 text-center">
        <div className="inline-flex items-center gap-2 mb-3">
          <span className="text-2xl">⚙️</span>
          <span className="text-xl font-semibold text-slate-100 tracking-tight">RepDefGen</span>
        </div>
        <h1 className="text-4xl font-bold text-slate-100 tracking-tight">Generate RDF</h1>
        <p className="mt-2 text-slate-400 text-base">Upload a Report Layout and let Claude write the Report Definition Package.</p>
      </div>

      <div className="w-full max-w-xl space-y-5">
        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={`relative cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors
            ${isDragActive ? 'border-indigo-400 bg-indigo-950/30' : 'border-slate-700 bg-slate-900/60 hover:border-slate-500'}`}
        >
          <input {...getInputProps()} />
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <span className="text-3xl">📄</span>
              <span className="text-slate-100 font-medium">{file.name}</span>
              <span className="text-xs text-slate-500">Click or drag to replace</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <span className="text-3xl">📂</span>
              <p className="text-slate-300 font-medium">
                {isDragActive ? 'Drop it here…' : 'Drag & drop your .rdl file here'}
              </p>
              <p className="text-sm text-slate-500">or click to browse</p>
            </div>
          )}
        </div>

        {/* Metadata fields */}
        <div className="space-y-3">
          <Field label="LU Name" placeholder="e.g. JobQuote" value={luName} onChange={setLuName} />
          <Field label="Module" placeholder="e.g. SRVQUO" value={module} onChange={setModule} />
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Description</label>
            <textarea
              rows={2}
              placeholder="Brief description of what this report covers…"
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-sm text-slate-100
                         placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
        </div>

        {error && (
          <div className="rounded-lg bg-red-950/50 border border-red-800 text-red-300 text-sm px-4 py-3">
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="w-full py-3 rounded-xl font-semibold text-sm tracking-wide transition-all
            bg-indigo-600 hover:bg-indigo-500 text-white
            disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <Spinner /> Proposing Field List…
            </span>
          ) : (
            'Propose Field List →'
          )}
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1">{label}</label>
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-sm text-slate-100
                   placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
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
