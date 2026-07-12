import React from 'react';
import {
  AbsoluteFill,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';

export const FPS = 30;
const VIDEO_TRIM_SECONDS = 196; // drop the static "Applying…" tail
const OUTRO_SECONDS = 5;
export const TOTAL_DURATION = (VIDEO_TRIM_SECONDS + OUTRO_SECONDS) * FPS;

const INDIGO = '#818CF8';
const INDIGO_DEEP = '#4F46E5';

// ---------------------------------------------------------------------------
// Timed content definitions (all times in source-video seconds)
// ---------------------------------------------------------------------------

interface Caption {
  from: number;
  to: number;
  text: string;
  top?: boolean; // render at top-center instead of bottom (when bottom UI is in use)
}

interface Callout {
  from: number;
  to: number;
  // Box in 1920x1080 coordinates
  x: number;
  y: number;
  w: number;
  h: number;
  label?: string;
  labelBelow?: boolean;
}

interface Chapter {
  from: number;
  to: number;
  text: string;
}

const CAPTIONS: Caption[] = [
  {from: 9, to: 16, text: 'Drop in an IFS Report Studio (.rep) layout file'},
  {from: 17, to: 28.5, text: 'Add the LU name, module and a short description'},
  {from: 29, to: 37.5, text: 'AI reads the layout and proposes the complete field list'},
  {from: 38.5, to: 46, text: 'SQL types, source columns and parameters — extracted automatically'},
  {from: 47, to: 62, text: 'Ask for changes in plain English…'},
  {from: 63, to: 74, text: 'TEST_NUM appears under report parameters — instantly'},
  {from: 78, to: 108, text: 'Add fields the same way — type, length and placement are inferred'},
  {from: 109, to: 118, text: 'AI changes are highlighted in the field list'},
  {from: 119.5, to: 134, text: 'Or edit any field inline — no AI round-trip needed'},
  {from: 136.5, to: 147, text: 'One click generates the complete PL/SQL Report Definition Package'},
  {from: 148, to: 158, text: 'RPT table, REP view, registration and package body — IFS conventions built in'},
  {from: 159.5, to: 186, text: 'Need a SQL tweak? Request corrections in plain English', top: true},
  {from: 187, to: 195.5, text: 'The .rdf is rewritten in place — download when ready', top: true},
];

const CALLOUTS: Callout[] = [
  {from: 9, to: 15, x: 590, y: 345, w: 740, h: 250, label: '.rdl and .rep supported'},
  {from: 17, to: 28, x: 590, y: 590, w: 740, h: 310, label: 'Report metadata', labelBelow: true},
  {from: 29.5, to: 33, x: 590, y: 900, w: 740, h: 85, label: 'Claude Sonnet under the hood', labelBelow: true},
  {from: 39, to: 45.5, x: 80, y: 185, w: 1050, h: 530},
  {from: 47.5, to: 55, x: 1140, y: 880, w: 640, h: 70, label: 'AI assistant', labelBelow: false},
  {from: 63.5, to: 73, x: 80, y: 600, w: 1050, h: 155, label: 'Applied instantly', labelBelow: true},
  {from: 110, to: 117.5, x: 80, y: 540, w: 1050, h: 65, label: 'Highlighted change'},
  {from: 120.5, to: 133, x: 80, y: 545, w: 1050, h: 70, label: 'Inline editing'},
  {from: 137, to: 144, x: 85, y: 175, w: 400, h: 65, label: 'Both files generated', labelBelow: true},
  {from: 160.5, to: 185, x: 470, y: 950, w: 890, h: 70, label: 'SQL correction loop'},
  {from: 188, to: 195, x: 1690, y: 175, w: 165, h: 65, label: 'Ready to deploy', labelBelow: true},
];

const CHAPTERS: Chapter[] = [
  {from: 8, to: 37.5, text: '1 · Upload the layout'},
  {from: 38.5, to: 135, text: '2 · Review the field list'},
  {from: 136, to: 196, text: '3 · Generate & refine'},
];

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

const CaptionBar: React.FC<{caption: Caption}> = ({caption}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const start = caption.from * fps;
  const end = caption.to * fps;
  const appear = spring({frame: frame - start, fps, config: {damping: 200}});
  const fadeOut = interpolate(frame, [end - 8, end], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = Math.min(appear, fadeOut);
  const translate = interpolate(appear, [0, 1], [caption.top ? -24 : 24, 0]);

  return (
    <div
      style={{
        position: 'absolute',
        ...(caption.top ? {top: 110} : {bottom: 34}),
        left: 0,
        right: 0,
        display: 'flex',
        justifyContent: 'center',
        opacity,
        transform: `translateY(${translate}px)`,
      }}
    >
      <div
        style={{
          background: 'rgba(10, 12, 24, 0.88)',
          border: `1.5px solid rgba(129, 140, 248, 0.45)`,
          borderRadius: 16,
          padding: '16px 34px',
          maxWidth: 1500,
          fontFamily: 'Helvetica, Arial, sans-serif',
          fontSize: 34,
          fontWeight: 500,
          color: '#F1F5F9',
          textAlign: 'center',
          boxShadow: '0 8px 40px rgba(0,0,0,0.55)',
          letterSpacing: 0.2,
        }}
      >
        {caption.text}
      </div>
    </div>
  );
};

const CalloutBox: React.FC<{callout: Callout}> = ({callout}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const start = callout.from * fps;
  const end = callout.to * fps;
  const appear = spring({frame: frame - start, fps, config: {damping: 14, mass: 0.6}});
  const fadeOut = interpolate(frame, [end - 8, end], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = Math.min(appear, fadeOut);
  const scale = interpolate(appear, [0, 1], [1.06, 1]);
  // Gentle breathing pulse on the ring
  const pulse = 1 + 0.012 * Math.sin(((frame - start) / fps) * Math.PI * 2);

  const labelStyle: React.CSSProperties = {
    position: 'absolute',
    left: 0,
    ...(callout.labelBelow ? {top: '100%', marginTop: 12} : {bottom: '100%', marginBottom: 12}),
    background: INDIGO_DEEP,
    color: 'white',
    fontFamily: 'Helvetica, Arial, sans-serif',
    fontSize: 26,
    fontWeight: 600,
    padding: '8px 20px',
    borderRadius: 999,
    whiteSpace: 'nowrap',
    boxShadow: '0 4px 24px rgba(79, 70, 229, 0.5)',
  };

  return (
    <div
      style={{
        position: 'absolute',
        left: callout.x,
        top: callout.y,
        width: callout.w,
        height: callout.h,
        opacity,
        transform: `scale(${scale * pulse})`,
        transformOrigin: 'center',
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          border: `3.5px solid ${INDIGO}`,
          borderRadius: 14,
          boxShadow: `0 0 0 6px rgba(129, 140, 248, 0.18), 0 0 34px rgba(129, 140, 248, 0.35)`,
        }}
      />
      {callout.label ? <div style={labelStyle}>{callout.label}</div> : null}
    </div>
  );
};

const ChapterBadge: React.FC<{chapter: Chapter}> = ({chapter}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const start = chapter.from * fps;
  const end = chapter.to * fps;
  const appear = spring({frame: frame - start, fps, config: {damping: 200}});
  const fadeOut = interpolate(frame, [end - 10, end], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = Math.min(appear, fadeOut);
  const translate = interpolate(appear, [0, 1], [-30, 0]);

  return (
    <div
      style={{
        position: 'absolute',
        top: 28,
        right: 40,
        opacity,
        transform: `translateY(${translate}px)`,
        background: 'rgba(10, 12, 24, 0.85)',
        border: '1.5px solid rgba(129, 140, 248, 0.4)',
        borderRadius: 999,
        padding: '10px 26px',
        fontFamily: 'Helvetica, Arial, sans-serif',
        fontSize: 26,
        fontWeight: 600,
        color: INDIGO,
        letterSpacing: 0.5,
        boxShadow: '0 6px 30px rgba(0,0,0,0.5)',
      }}
    >
      {chapter.text}
    </div>
  );
};

const IntroOverlay: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const appear = spring({frame, fps, config: {damping: 200}});
  const fadeOut = interpolate(frame, [6.2 * fps, 7.5 * fps], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const opacity = Math.min(appear, fadeOut);

  return (
    <AbsoluteFill
      style={{
        background: `rgba(5, 6, 15, ${0.82 * opacity})`,
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: 'Helvetica, Arial, sans-serif',
      }}
    >
      <div style={{opacity, textAlign: 'center', transform: `translateY(${interpolate(appear, [0, 1], [30, 0])}px)`}}>
        <div style={{display: 'flex', gap: 14, justifyContent: 'center', marginBottom: 38}}>
          <div style={{width: 150, height: 26, borderRadius: 13, background: '#8B00FF'}} />
          <div style={{width: 100, height: 26, borderRadius: 13, background: '#9B59D0'}} />
          <div style={{width: 60, height: 26, borderRadius: 13, background: '#C8A0E8'}} />
        </div>
        <div style={{fontSize: 84, fontWeight: 700, color: 'white', letterSpacing: -1}}>RepDefGen</div>
        <div style={{fontSize: 38, fontWeight: 400, color: '#94A3B8', marginTop: 18}}>
          AI-generated IFS Report Definitions — from layout to PL/SQL in minutes
        </div>
        <div style={{fontSize: 28, fontWeight: 600, color: INDIGO, marginTop: 34, letterSpacing: 2}}>
          KAIZENS GROUP
        </div>
      </div>
    </AbsoluteFill>
  );
};

const OutroCard: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const appear = spring({frame, fps, config: {damping: 200}});

  return (
    <AbsoluteFill
      style={{
        background: '#05060F',
        justifyContent: 'center',
        alignItems: 'center',
        fontFamily: 'Helvetica, Arial, sans-serif',
        opacity: appear,
      }}
    >
      <div style={{textAlign: 'center'}}>
        <div style={{display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 34}}>
          <div style={{width: 130, height: 22, borderRadius: 11, background: '#8B00FF'}} />
          <div style={{width: 88, height: 22, borderRadius: 11, background: '#9B59D0'}} />
          <div style={{width: 52, height: 22, borderRadius: 11, background: '#C8A0E8'}} />
        </div>
        <div style={{fontSize: 66, fontWeight: 700, color: 'white'}}>RepDefGen</div>
        <div style={{fontSize: 32, color: '#94A3B8', marginTop: 16}}>
          Upload a layout · Review the fields · Ship the report
        </div>
        <div style={{fontSize: 26, fontWeight: 600, color: INDIGO, marginTop: 40, letterSpacing: 2}}>
          KAIZENS GROUP
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------------------
// Main composition
// ---------------------------------------------------------------------------

export const Demo: React.FC = () => {
  const {fps} = useVideoConfig();
  const videoDuration = VIDEO_TRIM_SECONDS * fps;

  return (
    <AbsoluteFill style={{background: '#05060F'}}>
      <Sequence durationInFrames={videoDuration}>
        <OffthreadVideo src={staticFile('recording.mp4')} muted />

        {CHAPTERS.map((c, i) => (
          <ChapterBadge key={`ch-${i}`} chapter={c} />
        ))}
        {CALLOUTS.map((c, i) => (
          <CalloutBox key={`co-${i}`} callout={c} />
        ))}
        {CAPTIONS.map((c, i) => (
          <CaptionBar key={`ca-${i}`} caption={c} />
        ))}

        <IntroOverlay />
      </Sequence>

      <Sequence from={videoDuration} durationInFrames={OUTRO_SECONDS * fps}>
        <OutroCard />
      </Sequence>
    </AbsoluteFill>
  );
};
