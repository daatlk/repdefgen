# RepDefGen Demo Video

Remotion project that overlays the RepDefGen screen recording
(`public/recording.mp4`) with captions, animated callouts, chapter badges,
and branded intro/outro cards.

## Edit

All captions, callouts, and their timings live in `src/Demo.tsx`
(`CAPTIONS`, `CALLOUTS`, `CHAPTERS` arrays — times are in source-video
seconds; callout boxes are 1920x1080 coordinates).

## Preview

```console
npm i
npx remotion studio
```

## Render

```console
npx remotion render Demo out/RepDefGen-demo.mp4
```
