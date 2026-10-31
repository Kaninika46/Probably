/**
 * web/src/components/ParseStrip.tsx
 * Signature component #2: Re-renders the user's question with recognized NLP spans
 * from `/api/ask` (`tokens`: text, label, start, end, canonical, detail).
 * - SEGMENT: underline in segment colour
 * - COUNTRY: dotted underline
 * - HEDGE: inline pill such as `probably → P ≥ 0.66`
 * - NUMBER / LAPSE / BOUNDARY / EXP_SIZE / EXP_REV: subtle surface-2 highlight
 */

import React from "react";
import {
  RecognizedToken,
  SegmentColorInfo,
  segmentCssColor,
} from "../lib/api";

interface ParseStripProps {
  question: string;
  tokens: RecognizedToken[];
  segmentsMeta?: SegmentColorInfo[];
}

export const ParseStrip: React.FC<ParseStripProps> = ({
  question,
  tokens,
  segmentsMeta,
}) => {
  if (!question) return null;

  const sorted = [...tokens].sort((a, b) => a.start - b.start);
  const pieces: React.ReactNode[] = [];
  let cursor = 0;

  sorted.forEach((tok, idx) => {
    if (tok.start > cursor) {
      pieces.push(
        <span key={`plain-${idx}`}>
          {question.slice(cursor, tok.start)}
        </span>
      );
    }

    const label = tok.label;
    const tooltip = tok.detail || `${tok.label}: ${tok.canonical || tok.text}`;

    if (label === "SEGMENT") {
      const segColor = segmentCssColor(tok.canonical || tok.text, segmentsMeta);
      pieces.push(
        <span
          key={`tok-${idx}`}
          title={tooltip}
          className="font-semibold pb-0.5 cursor-help"
          style={{
            borderBottom: `2.5px solid ${segColor}`,
            color: "var(--ink)",
          }}
        >
          {tok.text}
        </span>
      );
    } else if (label === "COUNTRY") {
      pieces.push(
        <span
          key={`tok-${idx}`}
          title={tooltip}
          className="font-medium pb-0.5 cursor-help"
          style={{
            borderBottom: "2px dotted var(--ink-2)",
            color: "var(--ink)",
          }}
        >
          {tok.text}
        </span>
      );
    } else if (label === "HEDGE") {
      pieces.push(
        <span
          key={`tok-${idx}`}
          title={tooltip}
          className="inline-flex items-center gap-1.5 px-2.5 py-0.5 mx-0.5 rounded-full text-small font-medium cursor-help align-baseline"
          style={{
            backgroundColor: "var(--surface-2)",
            border: "1px solid var(--line)",
            color: "var(--ink)",
          }}
        >
          <span>{tok.text}</span>
          <span className="text-code" style={{ color: "var(--ink-2)" }}>
            {tok.detail ? tok.detail.replace(/^.*→\s*/, "→ ") : ""}
          </span>
        </span>
      );
    } else {
      pieces.push(
        <span
          key={`tok-${idx}`}
          title={tooltip}
          className="px-1.5 py-0.5 rounded text-small font-medium cursor-help"
          style={{
            backgroundColor: "var(--surface-2)",
            color: "var(--ink)",
          }}
        >
          {tok.text}
        </span>
      );
    }

    cursor = Math.max(cursor, tok.end);
  });

  if (cursor < question.length) {
    pieces.push(<span key="plain-end">{question.slice(cursor)}</span>);
  }

  return (
    <div
      className="flex flex-wrap items-center gap-y-2 px-4 py-3 rounded-input"
      style={{
        backgroundColor: "var(--surface)",
        border: "1px solid var(--line)",
      }}
      aria-label="Parsed natural language tokens"
    >
      <span className="label-caps mr-3 select-none">NLP Parse</span>
      <div className="text-body leading-relaxed">{pieces}</div>
    </div>
  );
};
