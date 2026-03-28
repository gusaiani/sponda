"use client";

import { useState } from "react";
import { useCompanyAnalysis, type AnalysisVersion } from "../hooks/useCompanyAnalysis";
import "../styles/analysis.css";

interface CompanyAnalysisProps {
  ticker: string;
}

function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
  return date.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatQuarter(dataQuarter: string): string {
  const [year, quarter] = dataQuarter.split("-");
  return `${quarter.replace("Q", "")}T ${year}`;
}

function renderContent(content: string): string {
  return content
    .split("\n\n")
    .map((paragraph) => {
      const trimmed = paragraph.trim();
      if (!trimmed) return "";

      // Headings
      if (trimmed.startsWith("### ")) {
        return `<h4 class="analysis-heading-3">${trimmed.slice(4)}</h4>`;
      }
      if (trimmed.startsWith("## ")) {
        return `<h3 class="analysis-heading-2">${trimmed.slice(3)}</h3>`;
      }

      // Apply inline formatting
      let html = trimmed
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");

      return `<p>${html}</p>`;
    })
    .join("");
}

function VersionSelector({
  versions,
  currentId,
  onSelect,
}: {
  versions: AnalysisVersion[];
  currentId: number;
  onSelect: (version: AnalysisVersion) => void;
}) {
  if (versions.length <= 1) return null;

  return (
    <div className="analysis-versions">
      <label className="analysis-versions-label">Versões anteriores</label>
      <select
        className="analysis-versions-select"
        value={currentId}
        onChange={(event) => {
          const selected = versions.find(
            (version) => version.id === Number(event.target.value)
          );
          if (selected) onSelect(selected);
        }}
      >
        {versions.map((version) => (
          <option key={version.id} value={version.id}>
            {formatQuarter(version.dataQuarter)} · {formatDate(version.generatedAt)}
          </option>
        ))}
      </select>
    </div>
  );
}

export function CompanyAnalysis({ ticker }: CompanyAnalysisProps) {
  const { data, isLoading, error } = useCompanyAnalysis(ticker, true);
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null);

  if (isLoading || error || !data) return null;

  const currentVersionId = selectedVersionId ?? data.versions[0]?.id;

  return (
    <div className="pe10-card">
      <div className="analysis-container">
        <div className="analysis-header">
          <div className="analysis-badge">
            <svg className="analysis-badge-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
              <path d="M18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
            </svg>
            Análise de longo prazo
          </div>
          <span className="analysis-quarter">{formatQuarter(data.dataQuarter)}</span>
        </div>

        <div
          className="analysis-body"
          dangerouslySetInnerHTML={{ __html: renderContent(data.content) }}
        />

        <div className="analysis-footer">
          <div className="analysis-attribution">
            Análise por Claude · Dados: BRAPI · {formatDate(data.generatedAt)}
          </div>
          <VersionSelector
            versions={data.versions}
            currentId={currentVersionId}
            onSelect={(version) => setSelectedVersionId(version.id)}
          />
        </div>
      </div>
    </div>
  );
}
