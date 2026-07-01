import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type FieldMetadata = {
  name: string;
  inferred_type: string;
  non_empty_count: number;
  fill_rate?: number;
  pii_level?: string;
};

type ParsedFile = {
  filename: string;
  format: string;
  status: string;
  row_count: number;
  fields: FieldMetadata[];
  errors: string[];
};

type IngestResponse = {
  status: string;
  files: {
    file_a: ParsedFile;
    file_b: ParsedFile;
  };
  comparison?: ComparisonResult | null;
};

type Proposal = {
  proposal_id: string;
  canonical_field: string;
  trust_score: number;
  route: "auto_merge" | "review" | "separate";
  source_field_a: FieldMetadata;
  source_field_b: FieldMetadata;
  rationale: string;
  review_state: string;
  review_decision?: ReviewDecision | null;
  explanation: Explanation;
  concept?: string;
};

type UnmatchedField = {
  name: string;
  inferred_type: string;
  concept: string;
  sample_values: string[];
};

type ReviewDecision = {
  proposal_id: string;
  decision: "keep" | "discard";
  review_state: string;
  low_confidence_confirmed: boolean;
};

type DecisionToast = {
  text: string;
  tone: "success" | "danger" | "warning";
};

type Explanation = {
  status: "generated" | "fallback" | "not_required";
  text: string;
  model: string | null;
  recoverable_error?: string;
};

type ComparisonResult = {
  overall_trust_score: number;
  proposal_count: number;
  proposals: Proposal[];
  unmatched_fields_a?: UnmatchedField[];
  unmatched_fields_b?: UnmatchedField[];
};

type PreviewResult = {
  status: "ready" | "blocked";
  summary: {
    accepted_count: number;
    rejected_count: number;
    separated_count: number;
    unresolved_count: number;
    overall_trust_score: number;
  };
  field_preview: Array<{
    proposal_id: string;
    canonical_field: string;
    trust_score: number;
    route: string;
    decision_state: string;
    source_fields: {
      file_a: FieldMetadata;
      file_b: FieldMetadata;
    };
  }>;
  entity_preview: Array<{
    row_index: number;
    canonical_fields: string[];
  }>;
  export_blockers: string[];
};

type ExportResult = {
  status: "ready";
  canonical_mapping: {
    version: string;
    fields: Array<{
      canonical_field: string;
      trust_score: number;
      decision_state: string;
      source_fields: {
        file_a: FieldMetadata;
        file_b: FieldMetadata;
      };
    }>;
  };
  merged_output: {
    version: string;
    records: Array<Record<string, unknown>>;
  };
  preview: PreviewResult;
};

function App() {
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [result, setResult] = useState<IngestResponse | null>(null);
  const [message, setMessage] = useState("Select two peer company files to inspect their schemas.");
  const [isLoading, setIsLoading] = useState(false);
  const [step, setStep] = useState<number>(1); // 1 = Upload & Ingest, 2 = Review Schema proposals, 3 = Export & Preview

  async function submitFiles(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fileA || !fileB) {
      setMessage("Both File A and File B are required.");
      return;
    }

    const formData = new FormData();
    formData.append("file_a", fileA);
    formData.append("file_b", fileB);

    setIsLoading(true);
    setMessage("Parsing files and extracting schema metadata...");
    try {
      const response = await fetch(`${apiBaseUrl}/compare`, { method: "POST", body: formData });
      const payload = (await response.json()) as IngestResponse;
      setResult(payload);
      setMessage(payload.status === "valid" ? "Schema extraction and concept scoring complete." : "Schema extraction completed with validation errors.");
      if (payload.status === "valid" || payload.files) {
        setStep(2); // Auto-advance to Review step
      }
    } catch {
      setMessage("Backend ingestion service is not reachable.");
    } finally {
      setIsLoading(false);
    }
  }

  const overallProgress = result?.comparison?.proposal_count
    ? Math.round(100) // progress indicator placeholder or actual math
    : 0;

  return (
    <main className="app-shell">
      <section className="workspace" aria-labelledby="app-title">
        <h1 id="app-title">MergeWise AI</h1>
        <p className="subtitle">
          AI-orchestrated data readiness platform for aligning enterprise schemas,
          mitigating reporting risk, and validating compliance.
        </p>

        {/* Stepper Component */}
        <nav className="stepper" aria-label="Workflow progress">
          <button
            type="button"
            className={`step-item ${step === 1 ? "active" : ""} ${step > 1 ? "completed" : ""}`}
            onClick={() => setStep(1)}
          >
            <div className="step-num">1</div>
            <div className="step-label">File Ingestion</div>
          </button>
          <div className="step-connector"></div>
          <button
            type="button"
            className={`step-item ${step === 2 ? "active" : ""} ${step > 2 ? "completed" : ""}`}
            disabled={!result}
            onClick={() => setStep(2)}
          >
            <div className="step-num">2</div>
            <div className="step-label">Mapping Review</div>
          </button>
          <div className="step-connector"></div>
          <button
            type="button"
            className={`step-item ${step === 3 ? "active" : ""}`}
            disabled={!result}
            onClick={() => setStep(3)}
          >
            <div className="step-num">3</div>
            <div className="step-label">Merge Board & Export</div>
          </button>
        </nav>

        {isLoading && (
          <div className="stylish-loader-overlay">
            <div className="stylish-spinner"></div>
            <p className="stylish-loader-text">AI is parsing datasets, detecting PII levels, and executing fuzzy semantic match heuristics...</p>
          </div>
        )}

        {step === 1 && (
          <div className="step-container slide-in">
            <form className="upload-panel" onSubmit={submitFiles}>
              <div className={`dropzone ${fileA ? "has-file" : ""}`}>
                <span className="dropzone-title">Company A Source</span>
                <span className="file-info" title={fileA?.name}>
                  {fileA && <span className="file-selected-indicator" aria-hidden="true"></span>}
                  <span className="file-info-name">{fileA ? fileA.name : "No file chosen"}</span>
                </span>
                <input type="file" accept=".csv,.json,.xlsx" onChange={(event) => setFileA(event.target.files?.[0] ?? null)} />
                <button type="button" className="btn-browse">Browse File A</button>
              </div>

              <div className={`dropzone ${fileB ? "has-file" : ""}`}>
                <span className="dropzone-title">Company B Source</span>
                <span className="file-info" title={fileB?.name}>
                  {fileB && <span className="file-selected-indicator" aria-hidden="true"></span>}
                  <span className="file-info-name">{fileB ? fileB.name : "No file chosen"}</span>
                </span>
                <input type="file" accept=".csv,.json,.xlsx" onChange={(event) => setFileB(event.target.files?.[0] ?? null)} />
                <button type="button" className="btn-browse">Browse File B</button>
              </div>

              <div className="submit-panel">
                <button type="submit" className="btn-submit" disabled={isLoading || !fileA || !fileB}>
                  {isLoading ? "Analyzing..." : "Compare Schemas"}
                </button>
              </div>
            </form>

            {message && <output className="message">{message}</output>}

            {result && (
              <section className="results" aria-label="Schema extraction results">
                <SchemaSummary label="Company A Schema" file={result.files.file_a} />
                <SchemaSummary label="Company B Schema" file={result.files.file_b} />
              </section>
            )}
          </div>
        )}

        {step === 2 && result?.comparison && fileA && fileB && (
          <div className="step-container slide-in">
            <ProposalList
              comparison={result.comparison}
              fileA={fileA}
              fileB={fileB}
              onGoToNextStep={() => setStep(3)}
            />
          </div>
        )}

        {step === 3 && result?.comparison && fileA && fileB && (
          <div className="step-container slide-in">
            <ExportAndPreviewPanel
              comparison={result.comparison}
              fileA={fileA}
              fileB={fileB}
            />
          </div>
        )}
      </section>
    </main>
  );
}

function ProposalList({
  comparison,
  fileA,
  fileB,
  onGoToNextStep,
}: {
  readonly comparison: ComparisonResult;
  readonly fileA: File;
  readonly fileB: File;
  readonly onGoToNextStep: () => void;
}) {
  const [decisions, setDecisions] = useState<Record<string, ReviewDecision>>({});
  const [toast, setToast] = useState<DecisionToast | null>(null);
  const [activeTab, setActiveTab] = useState<"auto" | "review" | "separate" | "progress" | "unmatched">("review");

  // Local matching indices to support managing review progress easily
  const [currentProposalIndex, setCurrentProposalIndex] = useState<number>(0);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeoutId = window.setTimeout(() => setToast(null), 2500);
    return () => window.clearTimeout(timeoutId);
  }, [toast]);

  function showDecisionToast(text: string, tone: DecisionToast["tone"]) {
    setToast({ text, tone });
  }

  async function decide(proposal: Proposal, decision: "keep" | "discard", confirmLowConfidence = false) {
    if (proposal.route === "separate" && decision === "keep" && !confirmLowConfidence) {
      showDecisionToast("Low-confidence keep requires override confirmation.", "warning");
      return;
    }

    const response = await fetch(`${apiBaseUrl}/review/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        proposal_id: proposal.proposal_id,
        route: proposal.route,
        trust_score: proposal.trust_score,
        decision,
        confirm_low_confidence: confirmLowConfidence,
      }),
    });
    if (!response.ok) {
      showDecisionToast("Review decision was not saved.", "danger");
      return;
    }
    const payload = (await response.json()) as ReviewDecision;
    setDecisions((current) => ({ ...current, [proposal.proposal_id]: payload }));
    const decisionLabel = decision === "discard" ? "Rejected" : "Kept";
    showDecisionToast(`Decision saved: ${decisionLabel} [${proposal.canonical_field}]`, decision === "discard" ? "danger" : "success");
  }

  const filteredProposals = comparison.proposals.filter((p) => {
    if (activeTab === "progress") return true;
    if (activeTab === "auto") return p.route === "auto_merge";
    if (activeTab === "review") return p.route === "review";
    return p.route === "separate";
  });

  const totalReviewsNeeded = comparison.proposals.filter((p) => p.route === "review").length;
  const reviewsDecided = comparison.proposals.filter(
    (p) => p.route === "review" && (decisions[p.proposal_id] || p.review_decision)
  ).length;

  const currentProposal = filteredProposals[currentProposalIndex];

  function handleNext() {
    if (currentProposalIndex < filteredProposals.length - 1) {
      setCurrentProposalIndex(currentProposalIndex + 1);
    }
  }

  function handlePrev() {
    if (currentProposalIndex > 0) {
      setCurrentProposalIndex(currentProposalIndex - 1);
    }
  }

  return (
    <section className="proposal-panel" aria-label="Concept merge proposals">
      {toast && (
        <div className="toast-viewport" aria-live="polite">
          <output className={`decision-toast ${toast.tone}`} role={toast.tone === "danger" ? "alert" : "status"}>
            {toast.text}
          </output>
        </div>
      )}

      <header className="proposal-board-header">
        <div className="metric-badge">
          <span>Overall Trust Match</span>
          <strong>{comparison.overall_trust_score}%</strong>
        </div>
        <div className="metric-badge">
          <span>Total Schema Fields</span>
          <strong>{comparison.proposal_count}</strong>
        </div>
        <div className="metric-badge">
          <span>Review Completion Progress</span>
          <strong>
            {reviewsDecided} / {totalReviewsNeeded} Decided
          </strong>
        </div>
      </header>

      {/* Progress Bar inside Proposal view */}
      <div className="review-progress-track">
        <div className="progress-bg" style={{ width: "100%", height: "10px" }}>
          <div
            className="progress-fg"
            style={{
              height: "100%",
              width: `${totalReviewsNeeded > 0 ? (reviewsDecided / totalReviewsNeeded) * 100 : 100}%`,
              transition: "width 0.3s ease",
            }}
          ></div>
        </div>
      </div>

      <div className="proposals-hub">
        <div className="proposals-tabs-strip">
          <button
            type="button"
            className={`tab-btn ${activeTab === "review" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("review");
              setCurrentProposalIndex(0);
            }}
          >
            Needs Review ({comparison.proposals.filter((p) => p.route === "review").length})
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === "auto" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("auto");
              setCurrentProposalIndex(0);
            }}
          >
            Auto-Merged ({comparison.proposals.filter((p) => p.route === "auto_merge").length})
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === "separate" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("separate");
              setCurrentProposalIndex(0);
            }}
          >
            Separated / Weak ({comparison.proposals.filter((p) => p.route === "separate").length})
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === "progress" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("progress");
              setCurrentProposalIndex(0);
            }}
          >
            All Proposed Mappings ({comparison.proposals.length})
          </button>
          <button
            type="button"
            className={`tab-btn unmatched-tab ${activeTab === "unmatched" ? "active" : ""}`}
            onClick={() => setActiveTab("unmatched")}
          >
            Unmatched Fields ({(comparison.unmatched_fields_a?.length ?? 0) + (comparison.unmatched_fields_b?.length ?? 0)})
          </button>
        </div>

        {activeTab === "unmatched" ? (
          <div className="unmatched-panel">
            <div className="unmatched-columns">
              <div className="unmatched-col">
                <h4 className="unmatched-col-heading">Only in Company A</h4>
                {(comparison.unmatched_fields_a ?? []).length === 0 ? (
                  <p className="unmatched-empty">No unmatched fields.</p>
                ) : (
                  <ul className="unmatched-list">
                    {(comparison.unmatched_fields_a ?? []).map((f) => (
                      <li key={f.name} className="unmatched-item">
                        <code>{f.name}</code>
                        <span className="src-type">{f.inferred_type}</span>
                        <span className="concept-badge">{f.concept.replace(/_/g, " ")}</span>
                        {f.sample_values.length > 0 && (
                          <span className="unmatched-samples">e.g. {f.sample_values.join(", ")}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <div className="unmatched-col">
                <h4 className="unmatched-col-heading">Only in Company B</h4>
                {(comparison.unmatched_fields_b ?? []).length === 0 ? (
                  <p className="unmatched-empty">No unmatched fields.</p>
                ) : (
                  <ul className="unmatched-list">
                    {(comparison.unmatched_fields_b ?? []).map((f) => (
                      <li key={f.name} className="unmatched-item">
                        <code>{f.name}</code>
                        <span className="src-type">{f.inferred_type}</span>
                        <span className="concept-badge">{f.concept.replace(/_/g, " ")}</span>
                        {f.sample_values.length > 0 && (
                          <span className="unmatched-samples">e.g. {f.sample_values.join(", ")}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        ) : filteredProposals.length === 0 ? (
          <div className="empty-tab-state">No matching proposals in this category.</div>
        ) : (
          <div className="minimal-scroll-container">
            <div className="proposal-slider-header">
              <span>Proposal {currentProposalIndex + 1} of {filteredProposals.length}</span>
              <div className="slider-nav-btns">
                <button type="button" className="btn-action" onClick={handlePrev} disabled={currentProposalIndex === 0}>
                  ◀ Previous
                </button>
                <button type="button" className="btn-action" onClick={handleNext} disabled={currentProposalIndex === filteredProposals.length - 1}>
                  Next ▶
                </button>
              </div>
            </div>

            {(() => {
              const proposal = currentProposal;
              const currentDecision = decisions[proposal.proposal_id];
              return (
                <article className="proposal-card active-slider" key={proposal.proposal_id}>
                  <div className="proposal-heading-row">
                    <div className="canonical-col">
                      <span className="trace-tag">Canonical Field Target</span>
                      <strong>{proposal.canonical_field}</strong>
                    </div>
                    <div className={`route-score-badge ${proposal.route}`}>
                      {routeLabel(proposal.route)} · {proposal.trust_score}%
                    </div>
                  </div>

                  <div className="source-alignment-display">
                    <div className="src-field">
                      <span className="src-label">Company A Field</span>
                      <code>{proposal.source_field_a.name}</code>
                      <span className="src-type">{proposal.source_field_a.inferred_type}</span>
                    </div>
                    <div className="arrow-sep">↔</div>
                    <div className="src-field">
                      <span className="src-label">Company B Field</span>
                      <code>{proposal.source_field_b.name}</code>
                      <span className="src-type">{proposal.source_field_b.inferred_type}</span>
                    </div>
                  </div>

                  <div className="explanation-section">
                    <span className="expl-tag">{explanationLabel(proposal.explanation.status)}</span>
                    <div className="expl-text">
                      <ReactMarkdown>{proposal.explanation.text}</ReactMarkdown>
                    </div>
                    {proposal.explanation.recoverable_error && (
                      <span className="error-badge">{proposal.explanation.recoverable_error}</span>
                    )}
                  </div>

                  <div className="rationale-collapse">
                    <dt>Heuristic Rationale</dt>
                    <dd>{proposal.rationale}</dd>
                  </div>

                  <div className="review-action-row">
                    <div className="action-buttons-group">
                      <button type="button" className="btn-approve" onClick={() => decide(proposal, "keep")}>
                        Keep Mapping
                      </button>
                      <button type="button" className="btn-discard" onClick={() => decide(proposal, "discard")}>
                        Separate Fields
                      </button>
                      {proposal.route === "separate" && (
                        <button
                          type="button"
                          className="btn-warn-override"
                          onClick={() => decide(proposal, "keep", true)}
                        >
                          Low-Confidence Keep Override
                        </button>
                      )}
                    </div>
                    <div className="decision-status">
                      <span>Status</span>
                      <strong className={`status-val ${currentDecision?.review_state ?? proposal.review_state}`}>
                        {formatReviewState(currentDecision?.review_state ?? proposal.review_state)}
                      </strong>
                    </div>
                  </div>
                </article>
              );
            })()}
          </div>
        )}
      </div>

      <div className="bottom-next-step-row">
        <button type="button" className="btn-action btn-export" onClick={onGoToNextStep}>
          Proceed to Merge Board & Export ▶
        </button>
      </div>
    </section>
  );
}

function ExportAndPreviewPanel({
  comparison,
  fileA,
  fileB,
}: {
  readonly comparison: ComparisonResult;
  readonly fileA: File;
  readonly fileB: File;
}) {
  const [decisionMessage, setDecisionMessage] = useState("");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [exportResult, setExportResult] = useState<ExportResult | null>(null);
  const [loadingArtifact, setLoadingArtifact] = useState<"preview" | "export" | null>(null);
  const [downloadFormat, setDownloadFormat] = useState<"json" | "csv" | "txt">("json");

  function serializeExport(format: "json" | "csv" | "txt"): { content: string; mime: string; ext: string } {
    const { canonical_mapping, merged_output } = exportResult!;
    const records = merged_output.records;

    // Ordered column list: _source → accepted canonical fields → any extra/unmatched columns
    // Extra columns come from the actual record keys so nothing from the source files is dropped.
    const canonicalSet = new Set(canonical_mapping.fields.map((f) => f.canonical_field));
    const extraCols = Array.from(
      records.reduce((acc, row) => {
        Object.keys(row).forEach((k) => { if (k !== "_source" && !canonicalSet.has(k)) acc.add(k); });
        return acc;
      }, new Set<string>())
    );
    const allColumns = ["_source", ...canonical_mapping.fields.map((f) => f.canonical_field), ...extraCols];

    if (format === "json") {
      return {
        content: JSON.stringify(
          { version: merged_output.version, columns: allColumns.slice(1), records },
          null,
          2
        ),
        mime: "application/json",
        ext: "json",
      };
    }

    if (format === "csv") {
      const escape = (v: unknown) => {
        const s = v == null ? "" : String(v);
        return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
      };
      const header = allColumns.join(",");
      const rows = records.map((row) =>
        allColumns.map((f) => escape(row[f])).join(",")
      );
      return { content: [header, ...rows].join("\n"), mime: "text/csv", ext: "csv" };
    }

    // txt — human-readable report
    const line = "─".repeat(60);
    const acceptedSummary = canonical_mapping.fields
      .map((f) => `  ${f.canonical_field.padEnd(24)} ${f.source_fields.file_a.name} → ${f.source_fields.file_b.name}  [${f.trust_score}%]`)
      .join("\n");
    const extraSummary = extraCols.length
      ? "\nUNMATCHED / SEPARATED COLUMNS (kept with original name)\n" +
        extraCols.map((c) => `  ${c}`).join("\n")
      : "";
    const dataRows = records.map((row, i) => {
      const src = String(row["_source"] ?? "").replace("_", " ").toUpperCase();
      const values = allColumns
        .filter((c) => c !== "_source")
        .map((f) => `    ${f.padEnd(28)} ${row[f] ?? ""}`)
        .join("\n");
      return `[${i + 1}] ${src}\n${values}`;
    });
    const content = [
      "MERGEWISE AI — MERGED DATA EXPORT",
      `Generated : ${new Date().toISOString().slice(0, 10)}`,
      `Version   : ${merged_output.version}`,
      `Records   : ${records.length}  (${records.filter((r) => r._source === "company_a").length} Company A + ${records.filter((r) => r._source === "company_b").length} Company B)`,
      `Columns   : ${allColumns.length - 1} total  (${canonical_mapping.fields.length} canonical + ${extraCols.length} unmatched)`,
      line,
      "CANONICAL FIELD MAP",
      acceptedSummary,
      extraSummary,
      line,
      "MERGED RECORDS",
      dataRows.join("\n\n"),
      line,
    ].join("\n");
    return { content, mime: "text/plain", ext: "txt" };
  }

  function triggerDownload() {
    const { content, mime, ext } = serializeExport(downloadFormat);
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `canonical-mapping.${ext}`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function requestArtifact(path: "preview" | "export") {
    if (loadingArtifact) {
      return;
    }

    setPreview(null);
    setExportResult(null);
    setDecisionMessage("");
    setLoadingArtifact(path);

    try {
      const formData = new FormData();
      formData.append("file_a", fileA);
      formData.append("file_b", fileB);
      const response = await fetch(`${apiBaseUrl}/${path}`, { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok) {
        setDecisionMessage(payload.detail?.message ?? "Export is blocked until review decisions are complete.");
        return;
      }
      if (path === "preview") {
        setPreview(payload as PreviewResult);
      } else {
        const exportedArtifact = payload as ExportResult;
        setPreview(exportedArtifact.preview);
        setExportResult(exportedArtifact);
      }
    } catch {
      setDecisionMessage("Merge board service is not reachable.");
    } finally {
      setLoadingArtifact(null);
    }
  }

  const isLoadingArtifact = loadingArtifact !== null;

  return (
    <div className="export-and-preview-panel card">
      <div className="card-header">
        <span>Publish & Sync Workspace</span>
        <strong>Consolidated Merged Export Workspace</strong>
      </div>
      <div className="card-body">
        <p className="schema-quick-summary text-muted">
          Validate aligned variables, run live row synchronization previews, or emit standard compliance configuration artifacts.
        </p>

        {decisionMessage && <output className="decision-banner message">{decisionMessage}</output>}

        <div className="export-actions">
          <button
            type="button"
            className="btn-action btn-export"
            disabled={isLoadingArtifact}
            aria-busy={loadingArtifact === "preview"}
            onClick={() => requestArtifact("preview")}
          >
            {loadingArtifact === "preview" ? "Generating Preview..." : "Generate Merge Preview"}
          </button>
          <div className="export-format-group">
            <span className="export-format-label">Format</span>
            {(["json", "csv", "txt"] as const).map((fmt) => (
              <button
                key={fmt}
                type="button"
                className={`btn-format ${downloadFormat === fmt ? "active" : ""}`}
                onClick={() => setDownloadFormat(fmt)}
              >
                {fmt.toUpperCase()}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="btn-action"
            disabled={isLoadingArtifact}
            aria-busy={loadingArtifact === "export"}
            onClick={() => requestArtifact("export")}
          >
            {loadingArtifact === "export" ? "Exporting Mapping..." : "Export Canonical Mapping"}
          </button>
        </div>

        {isLoadingArtifact && (
          <div className="stylish-loader-overlay artifact-loader" role="status" aria-live="polite">
            <div className="stylish-spinner"></div>
            <p className="stylish-loader-text">
              {loadingArtifact === "preview"
                ? "Generating merge preview..."
                : "Preparing canonical mapping and merge preview..."}
            </p>
          </div>
        )}

        {preview && <MergeBoard title="Interactive Merge Preview Board" preview={preview} />}
        {exportResult && (
          <section className="artifact-summary text-left" aria-label="Export metadata info">
            <div className="artifact-header-row">
              <div>
                <h2>✔ Canonical Export Ready</h2>
                <p className="export-sub text-muted">
                  {exportResult.merged_output.records.length} merged rows · {exportResult.canonical_mapping.fields.length} canonical fields · version {exportResult.canonical_mapping.version}
                </p>
              </div>
              <div className="artifact-download-group">
                <span className="export-format-label">Download as</span>
                {(["json", "csv", "txt"] as const).map((fmt) => (
                  <button
                    key={fmt}
                    type="button"
                    className={`btn-format ${downloadFormat === fmt ? "active" : ""}`}
                    onClick={() => setDownloadFormat(fmt)}
                  >
                    {fmt.toUpperCase()}
                  </button>
                ))}
                <button type="button" className="btn-action btn-download" onClick={triggerDownload}>
                  ⬇ Download canonical-mapping.{downloadFormat}
                </button>
              </div>
            </div>
            <pre className="export-preview-pre">{serializeExport(downloadFormat).content}</pre>
          </section>
        )}
      </div>
    </div>
  );
}

function MergeBoard({ title, preview }: { readonly title: string; readonly preview: PreviewResult }) {
  return (
    <section className="unified-merge-board" aria-label="Interactive Merge Grid">
      <h3>{title}</h3>
      <div className="board-grid-metrics">
        <div className="board-mini-tag alert-emerald">Accepted: {preview.summary.accepted_count}</div>
        <div className="board-mini-tag alert-crimson">Rejected: {preview.summary.rejected_count}</div>
        <div className="board-mini-tag alert-amber">Separated: {preview.summary.separated_count}</div>
        {preview.summary.unresolved_count > 0 && (
          <div className="board-mini-tag alert-unresolved">Unresolved Blockers: {preview.summary.unresolved_count}</div>
        )}
      </div>

      <div className="board-scrollable-table">
        <table>
          <thead>
            <tr>
              <th>Merged Column</th>
              <th>Merge Trust Category</th>
              <th>Company A Source</th>
              <th>Company B Source</th>
              <th>Decision State</th>
            </tr>
          </thead>
          <tbody>
            {preview.field_preview.map((fp) => (
              <tr key={fp.proposal_id}>
                <td>
                  <strong>{fp.canonical_field}</strong>
                </td>
                <td>
                  <span className={`route-score-badge ${fp.route}`}>{routeLabel(fp.route as any)} · {fp.trust_score}%</span>
                </td>
                <td>
                  <code>{fp.source_fields.file_a.name}</code>{" "}
                  <span className="type-badge">{fp.source_fields.file_a.inferred_type}</span>
                </td>
                <td>
                  <code>{fp.source_fields.file_b.name}</code>{" "}
                  <span className="type-badge">{fp.source_fields.file_b.inferred_type}</span>
                </td>
                <td>
                  <span className={`decision-badge ${fp.decision_state}`}>
                    {fp.decision_state.toUpperCase().replace("_", " ")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function explanationLabel(status: Explanation["status"]) {
  if (status === "generated") {
    return "AI-ORCHESTRATED EXPLANATION";
  }
  if (status === "fallback") {
    return "EVALUATOR RATIONALE (MODEL DETECTED)";
  }
  return "AUTO-VERIFIED METRIC";
}

function routeLabel(route: Proposal["route"]) {
  if (route === "auto_merge") {
    return "AUTO-MERGE";
  }
  if (route === "review") {
    return "NEEDS MANUAL REVIEW";
  }
  return "SEPARATE / WEAK MATCH";
}

function formatReviewState(state: string) {
  return state.toUpperCase().replace(/_/g, " ");
}

function SchemaSummary({ label, file }: { label: string; file: ParsedFile }) {
  return (
    <article className="schema-summary card">
      <header className="card-header">
        <span>{label}</span>
        <strong>{file.filename}</strong>
      </header>
      {file.errors.length > 0 ? (
        <ul className="errors m-0">
          {file.errors.map((error) => <li key={error}>{error}</li>)}
        </ul>
      ) : (
        <div className="card-body">
          <div className="schema-quick-summary text-muted">
            {file.row_count} rows | {file.fields.length} columns | {file.format.toUpperCase()} format
          </div>
          <table className="schema-table">
            <thead>
              <tr>
                <th>Column Name</th>
                <th>Inferred Type</th>
                <th>Fill density</th>
                <th>Security Risk</th>
              </tr>
            </thead>
            <tbody>
              {file.fields.map((field) => (
                <tr key={field.name}>
                  <td>
                    <code>{field.name}</code>
                  </td>
                  <td>
                    <span className="type-badge">{field.inferred_type}</span>
                  </td>
                  <td>
                    <div className="fill-progress-block">
                      <span className="rate-num">{field.fill_rate ?? 100}%</span>
                      <div className="progress-bg">
                        <div
                          className="progress-fg"
                          style={{ width: `${field.fill_rate ?? 100}%` }}
                        ></div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`pii-tag pii-${field.pii_level ?? "None"}`}>
                      {field.pii_level ?? "None"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

export default App;
