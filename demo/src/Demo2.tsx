import React from 'react';
import {
  AnnotatedVideo,
  annotatedDuration,
  Caption,
  Callout,
  Chapter,
} from './AnnotatedVideo';

const PROPS = {
  videoFile: 'recording2.mp4',
  trimSeconds: 102,
  introSeconds: 5,
  introSubtitle: 'A multi-block invoice report — from .rep layout to PL/SQL in 100 seconds',
  outroSeconds: 5,
};

export const TOTAL_DURATION_2 = annotatedDuration(PROPS);

const CAPTIONS: Caption[] = [
  {from: 5, to: 12.5, text: 'Drop in the .rep layout and add the report metadata'},
  {from: 13.5, to: 17.5, text: 'AI analyses the layout against the indexed IFS codebase…'},
  {from: 18, to: 24, text: 'Three nested blocks detected — INVOICE → CUSTOMER → DETAIL'},
  {from: 24.5, to: 30, text: 'Hidden linking fields were inferred — keys the layout never shows'},
  {from: 30.5, to: 36, text: 'Ask for changes in plain English…'},
  {from: 36.5, to: 43.5, text: 'CUSTOMER_NO is now a visible column — source mapping kept'},
  {from: 44.5, to: 55.5, text: 'Every field maps to a real column in the IFS codebase'},
  {from: 56.5, to: 64.5, text: 'Fields can be hidden from the layout just as easily'},
  {from: 65.5, to: 70.5, text: 'Flipped to hidden — the change is highlighted'},
  {from: 71.5, to: 77, text: 'Generating the complete PL/SQL Report Definition Package…'},
  {from: 78, to: 88.5, text: 'Cursors, joins and parameter passing — written with real IFS API calls'},
  {from: 89.5, to: 96.5, text: 'RPT table, REP view, registration, Execute_Report and Test — all included'},
  {from: 97.5, to: 101.5, text: 'Download the .rdf — ready to deploy', top: true},
];

const CALLOUTS: Callout[] = [
  {from: 5.5, to: 12, x: 590, y: 345, w: 740, h: 555, label: 'One form, three fields'},
  {from: 18.5, to: 24, x: 80, y: 185, w: 1050, h: 590, label: 'Nested block hierarchy', labelBelow: true},
  {from: 25, to: 30, x: 80, y: 240, w: 1050, h: 200, label: 'hidden · inferred', labelBelow: true},
  {from: 31, to: 35.5, x: 1140, y: 880, w: 640, h: 70, label: 'AI assistant'},
  {from: 37, to: 43, x: 1150, y: 555, w: 620, h: 110, label: 'Applied instantly', labelBelow: true},
  {from: 66, to: 70.5, x: 80, y: 475, w: 1050, h: 60, label: 'hidden · added by AI'},
  {from: 72, to: 76.5, x: 1620, y: 955, w: 215, h: 70, label: 'Claude writes the PL/SQL'},
  {from: 98, to: 101.5, x: 1690, y: 175, w: 165, h: 65, label: 'Ready to deploy', labelBelow: true},
];

const CHAPTERS: Chapter[] = [
  {from: 4.5, to: 13, text: '1 · Upload the layout'},
  {from: 17.5, to: 71, text: '2 · Review the field list'},
  {from: 75, to: 102, text: '3 · Generated package'},
];

export const Demo2: React.FC = () => (
  <AnnotatedVideo {...PROPS} captions={CAPTIONS} callouts={CALLOUTS} chapters={CHAPTERS} />
);
