import { useState } from 'react';
import './index.css';
import UploadStep from './components/UploadStep';
import ReviewStep from './components/ReviewStep';
import PreviewStep from './components/PreviewStep';
import type { SessionCreatedResponse } from './api';

type Step = 'upload' | 'review' | 'preview';

export default function App() {
  const [step, setStep] = useState<Step>('upload');
  const [sessionId, setSessionId] = useState('');
  const [parsed, setParsed] = useState<SessionCreatedResponse | null>(null);
  const [initialMessage, setInitialMessage] = useState('');
  const [generatedFiles, setGeneratedFiles] = useState<Record<string, string>>({});

  function handleUploaded(id: string, p: SessionCreatedResponse, msg: string) {
    setSessionId(id);
    setParsed(p);
    setInitialMessage(msg);
    setStep('review');
  }

  function handleGenerated(files: Record<string, string>) {
    setGeneratedFiles(files);
    setStep('preview');
  }

  function handleRestart() {
    setStep('upload');
    setSessionId('');
    setParsed(null);
    setInitialMessage('');
    setGeneratedFiles({});
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {step === 'upload' && (
        <UploadStep onDone={handleUploaded} />
      )}
      {step === 'review' && parsed && (
        <ReviewStep
          sessionId={sessionId}
          parsed={parsed}
          initialMessage={initialMessage}
          onGenerated={handleGenerated}
        />
      )}
      {step === 'preview' && (
        <PreviewStep
          sessionId={sessionId}
          files={generatedFiles}
          onRestart={handleRestart}
        />
      )}
    </div>
  );
}
