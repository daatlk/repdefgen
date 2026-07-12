import React from 'react';
import {
  AnnotatedVideo,
  annotatedDuration,
  Caption,
  Callout,
  Chapter,
} from './AnnotatedVideo';

export {FPS} from './AnnotatedVideo';

const PROPS = {
  videoFile: 'recording.mp4',
  trimSeconds: 196, // drop the static "Applying…" tail
  introSeconds: 7.5,
  introSubtitle: 'AI-generated IFS Report Definitions — from layout to PL/SQL in minutes',
  outroSeconds: 5,
};

export const TOTAL_DURATION = annotatedDuration(PROPS);

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

export const Demo: React.FC = () => (
  <AnnotatedVideo {...PROPS} captions={CAPTIONS} callouts={CALLOUTS} chapters={CHAPTERS} />
);
