/**
 * web/src/pages/AboutPage.tsx
 * Page 6 (`/about`): Architecture, methodology, and dataset citation (`FRONTEND.md` section 4.6).
 * Displays `docs/architecture.png` (`/api/assets/architecture.png`), the S1–S3 snapshot timeline,
 * how each part maps to Course Topics 3, 1, and 2, key limitations, and dataset licence/citation
 * from `/api/meta`.
 */

import React from "react";
import { MetaResponse, formatNumber } from "../lib/api";

interface AboutPageProps {
  meta: MetaResponse | null;
}

export const AboutPage: React.FC<AboutPageProps> = ({ meta }) => {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <span className="label-caps">
          ABAI2009L · Data Management and AI Integration · Bennett University
        </span>
        <h1 className="text-h1 mt-1">
          About Probably · System Architecture, Methodology &amp; Limitations
        </h1>
      </div>

      {/* Architecture Diagram (`docs/architecture.png`) */}
      <section className="card-surface flex flex-col gap-3">
        <div>
          <span className="label-caps">System Architecture</span>
          <h2 className="text-h2 mt-0.5">
            Offline Python KDD pipeline → DuckDB probabilistic tables → Read-only FastAPI + React web app
          </h2>
        </div>
        <div
          className="p-3 rounded-input overflow-hidden"
          style={{
            backgroundColor: "var(--bg)",
            border: "1px solid var(--line)",
          }}
        >
          <img
            src="/api/assets/architecture.png"
            alt="Probably system architecture diagram showing offline Python pipeline, DuckDB probabilistic database, and React + FastAPI web application"
            className="w-full h-auto rounded"
          />
        </div>
      </section>

      {/* Mapping to Course Topics 3, 1 and 2 */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card-surface flex flex-col gap-2">
          <span className="label-caps">Topic 3 (Core) · Data Mining &amp; KDD</span>
          <h2 className="text-h2">Knowledge Discovery Pipeline</h2>
          <p className="text-small" style={{ color: "var(--ink-2)" }}>
            Six-step SQL cleaning funnel (<code>sql/02_clean_views.sql</code>), leak-free temporal snapshots S1–S3 (<code>sql/03_features.sql</code>), 99th-percentile capping + <code>log1p</code> + <code>StandardScaler</code> preprocessing, K-Means and spherical GMM (K = 5, provisional) segmentation, depth-4 decision-tree surrogate rules, and Platt-calibrated logistic regression for 90-day lapse risk.
          </p>
        </div>

        <div className="card-surface flex flex-col gap-2">
          <span className="label-caps">
            Topic 1 · Probabilistic &amp; Uncertain Databases
          </span>
          <h2 className="text-h2">BID &amp; Tuple-Independent Relations</h2>
          <p className="text-small" style={{ color: "var(--ink-2)" }}>
            Stores cluster posteriors and B=100 bootstrap co-assignments in a formal <strong>Block-Independent-Disjoint (BID)</strong> relation <code>segment_membership</code> (block key <code>(customer_id, snapshot, method)</code>, Σp = 1.0) and calibrated 90-day lapse probabilities in a <strong>tuple-independent</strong> table <code>lapse_risk</code>, queried via templates Q1–Q6 and verified by a 10,000-world Monte Carlo sampler.
          </p>
        </div>

        <div className="card-surface flex flex-col gap-2">
          <span className="label-caps">Topic 2 · NLP for Database Interaction</span>
          <h2 className="text-h2">Deterministic spaCy + Hedge Lexicon</h2>
          <p className="text-small" style={{ color: "var(--ink-2)" }}>
            Uses <code>en_core_web_sm</code> + custom <code>EntityRuler</code> patterns to recognise segments, countries, intents, and verbal probability hedges (<em>possibly</em> ≥ 0.33, <em>probably</em> ≥ 0.66, <em>very likely</em> ≥ 0.90, <em>almost certainly</em> ≥ 0.95 from IPCC AR5 &amp; Sherman Kent), binding only allow-listed typed parameters to SQL templates Q1–Q6.
          </p>
        </div>
      </section>

      {/* S1-S3 Snapshot Timeline */}
      <section className="card-surface flex flex-col gap-4">
        <div>
          <span className="label-caps">Zero-Leakage Temporal Design</span>
          <h2 className="text-h2 mt-0.5">
            Snapshots S1, S2 and S3 (strictly disjoint feature and outcome windows)
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            className="p-4 rounded-input"
            style={{
              backgroundColor: "var(--bg)",
              border: "1px solid var(--line)",
            }}
          >
            <span className="label-caps">Snapshot S1 · Train Lapse Model</span>
            <div className="text-h2 mt-1 text-code">2010-09-10</div>
            <p className="text-small mt-1" style={{ color: "var(--ink-2)" }}>
              <strong>Features:</strong> 2009-12-10 to 2010-09-09 (3,256 customers)
              <br />
              <strong>Outcome:</strong> 2010-09-10 to 2010-12-09 (base 90d lapse rate 41.40%)
            </p>
          </div>

          <div
            className="p-4 rounded-input"
            style={{
              backgroundColor: "var(--bg)",
              border: "1px solid var(--line)",
            }}
          >
            <span className="label-caps">Snapshot S2 · Held-Out Test (Used Once)</span>
            <div className="text-h2 mt-1 text-code">2011-09-10</div>
            <p className="text-small mt-1" style={{ color: "var(--ink-2)" }}>
              <strong>Features:</strong> 2010-12-10 to 2011-09-09 (3,247 customers)
              <br />
              <strong>Outcome:</strong> 2011-09-10 to 2011-12-09 (base 90d lapse rate 42.38%)
            </p>
          </div>

          <div
            className="p-4 rounded-input"
            style={{
              backgroundColor: "var(--bg)",
              border: "1px solid var(--line)",
            }}
          >
            <span className="label-caps">Snapshot S3 · Live App Cohort</span>
            <div className="text-h2 mt-1 text-code">2011-12-10</div>
            <p className="text-small mt-1" style={{ color: "var(--ink-2)" }}>
              <strong>Features:</strong> 2011-03-10 to 2011-12-09 ({meta ? formatNumber(meta.customer_count) : "3,961"} customers)
              <br />
              <strong>Outcome:</strong> Future window (segmented &amp; scored into <code>app.duckdb</code>)
            </p>
          </div>
        </div>
      </section>

      {/* Limitations & Dataset Citation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="card-surface flex flex-col gap-2">
          <span className="label-caps">Methodological Limitations</span>
          <h2 className="text-h2">Honest Scope &amp; Approximations</h2>
          <ul className="mt-1 space-y-2 text-small list-disc list-inside" style={{ color: "var(--ink-2)" }}>
            <li>
              <strong>Tree explanations are approximations:</strong> Our depth-4 decision tree makes axis-aligned cuts in original R/F/M units and agrees with the log-scaled spherical GMM on 86.80% of held-out test customers.
            </li>
            <li>
              <strong>Segment + lapse dependence in Q6:</strong> Because both segment membership and 90-day lapse risk depend on <code>recency_days</code> and <code>frequency</code>, Q6 filters on two separate thresholds (<code>p ≥ τ1 AND p_lapse_90d ≥ τ2</code>) and never multiplies them.
            </li>
            <li>
              <strong>Template-bounded NL interface:</strong> The spaCy parser guarantees SQL safety by mapping questions strictly to templates Q1–Q6; open-ended ad-hoc SQL joins are politely refused.
            </li>
            <li>
              <strong>Provisional checkpoints:</strong> Spherical K=5 and the GMM default are recorded as provisional in <code>docs/DECISIONS.md</code> so alternatives (K=4 or bootstrap default) remain one config switch away.
            </li>
          </ul>
        </section>

        <section className="card-surface flex flex-col justify-between gap-4">
          <div>
            <span className="label-caps">Dataset Licence &amp; Citation</span>
            <h2 className="text-h2 mt-0.5">
              {meta?.dataset_name || "UCI Online Retail II"} (ID {meta?.dataset_id || 502})
            </h2>
            <p className="text-small mt-2" style={{ color: "var(--ink-2)" }}>
              <strong>Creator:</strong> Daqing Chen (2019), UCI Machine Learning Repository.
              <br />
              <strong>DOI:</strong>{" "}
              <code className="text-code">{meta?.doi || "10.24432/C5CG6D"}</code> ·{" "}
              <strong>Licence:</strong> {meta?.licence || "CC BY 4.0"}.
            </p>
            <p className="text-small mt-2" style={{ color: "var(--muted)" }}>
              Raw workbook rows (1,067,371 transactions from 01 Dec 2009 to 09 Dec 2011) are loaded unchanged into <code>raw_transactions</code> and never committed to git.
            </p>
          </div>
          <div
            className="p-3 rounded-input text-code text-xs"
            style={{
              backgroundColor: "var(--surface-2)",
              color: "var(--ink-2)",
            }}
          >
            Chen, D. (2019). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D
          </div>
        </section>
      </div>
    </div>
  );
};
