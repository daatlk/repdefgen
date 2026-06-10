import { useState } from 'react';
import './index.css';
import LoginStep from './components/LoginStep';
import UploadStep from './components/UploadStep';
import ReviewStep from './components/ReviewStep';
import PreviewStep from './components/PreviewStep';
import { getToken } from './api';
import type { FieldListData, SessionCreatedResponse } from './api';

type Step = 'login' | 'upload' | 'review' | 'preview';

export default function App() {
  const [step, setStep] = useState<Step>(() => getToken() ? 'upload' : 'login');
  const [sessionId, setSessionId] = useState('');
  const [parsed, setParsed] = useState<SessionCreatedResponse | null>(null);
  const [initialMessage, setInitialMessage] = useState('');
  const [fieldList, setFieldList] = useState<FieldListData | null>(null);
  const [generatedFiles, setGeneratedFiles] = useState<Record<string, string>>({});

  function handleUploaded(id: string, p: SessionCreatedResponse, msg: string, fl: FieldListData) {
    setSessionId(id);
    setParsed(p);
    setInitialMessage(msg);
    setFieldList(fl);
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
    setFieldList(null);
    setGeneratedFiles({});
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {step === 'login' && (
        <LoginStep onLogin={() => setStep('upload')} />
      )}
      {step === 'upload' && (
        <UploadStep onDone={handleUploaded} />
      )}
      {step === 'review' && parsed && fieldList && (
        <ReviewStep
          sessionId={sessionId}
          parsed={parsed}
          initialMessage={initialMessage}
          initialFieldList={fieldList}
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
