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

const INDIGO = '#818CF8';
const INDIGO_DEEP = '#4F46E5';

// ---------------------------------------------------------------------------
// Data types (all times in source-video seconds)
// ---------------------------------------------------------------------------

export interface Caption {
  from: number;
  to: number;
  text: string;
  top?: boolean; // render at top-center instead of bottom (when bottom UI is in use)
}

export interface Callout {
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

export interface Chapter {
  from: number;
  to: number;
  text: string;
}

export interface AnnotatedVideoProps {
  videoFile: string; // filename inside public/
  trimSeconds: number; // cut the source video here
  introSeconds: number; // when the intro overlay has fully faded
  introSubtitle: string;
  outroSeconds: number;
  captions: Caption[];
  callouts: Callout[];
  chapters: Chapter[];
}

export const annotatedDuration = (p: {trimSeconds: number; outroSeconds: number}) =>
  Math.round((p.trimSeconds + p.outroSeconds) * FPS);

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

const KaizensBars: React.FC<{scale?: number}> = ({scale = 1}) => (
  <div style={{display: 'flex', gap: 14 * scale, justifyContent: 'center'}}>
    <div style={{width: 150 * scale, height: 26 * scale, borderRadius: 13 * scale, background: '#8B00FF'}} />
    <div style={{width: 100 * scale, height: 26 * scale, borderRadius: 13 * scale, background: '#9B59D0'}} />
    <div style={{width: 60 * scale, height: 26 * scale, borderRadius: 13 * scale, background: '#C8A0E8'}} />
  </div>
);

const IntroOverlay: React.FC<{subtitle: string; untilSeconds: number}> = ({subtitle, untilSeconds}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const appear = spring({frame, fps, config: {damping: 200}});
  const fadeOut = interpolate(
    frame,
    [(untilSeconds - 1.3) * fps, untilSeconds * fps],
    [1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
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
        <div style={{marginBottom: 38}}>
          <KaizensBars />
        </div>
        <div style={{fontSize: 84, fontWeight: 700, color: 'white', letterSpacing: -1}}>RepDefGen</div>
        <div style={{fontSize: 38, fontWeight: 400, color: '#94A3B8', marginTop: 18}}>{subtitle}</div>
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
        <div style={{marginBottom: 34}}>
          <KaizensBars scale={0.85} />
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
// Main component
// ---------------------------------------------------------------------------

export const AnnotatedVideo: React.FC<AnnotatedVideoProps> = ({
  videoFile,
  trimSeconds,
  introSeconds,
  introSubtitle,
  outroSeconds,
  captions,
  callouts,
  chapters,
}) => {
  const {fps} = useVideoConfig();
  const videoDuration = trimSeconds * fps;

  return (
    <AbsoluteFill style={{background: '#05060F'}}>
      <Sequence durationInFrames={videoDuration}>
        <OffthreadVideo src={staticFile(videoFile)} muted />

        {chapters.map((c, i) => (
          <ChapterBadge key={`ch-${i}`} chapter={c} />
        ))}
        {callouts.map((c, i) => (
          <CalloutBox key={`co-${i}`} callout={c} />
        ))}
        {captions.map((c, i) => (
          <CaptionBar key={`ca-${i}`} caption={c} />
        ))}

        <IntroOverlay subtitle={introSubtitle} untilSeconds={introSeconds} />
      </Sequence>

      <Sequence from={videoDuration} durationInFrames={outroSeconds * fps}>
        <OutroCard />
      </Sequence>
    </AbsoluteFill>
  );
};
