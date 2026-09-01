"use client";

import { useState } from "react";
import {
  FileText,
  UploadCloud,
  FileType,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";
import Papa from "papaparse";

type Tab = "manual" | "csv" | "pdf";
type ProcessingStage = "idle" | "processing" | "success" | "error";

/*
 * Safely converts life_saving_rules into a string array.
 *
 * Handles:
 * - null / undefined
 * - empty strings
 * - already parsed arrays
 * - JSON strings such as '["Rule 1","Rule 2"]'
 * - plain text
 * - malformed JSON
 */
function parseRules(value: any): string[] {
  if (!value) {
    return [];
  }

  // Already an array
  if (Array.isArray(value)) {
    return value.filter(Boolean).map(String);
  }

  // Anything other than a string is not useful here
  if (typeof value !== "string") {
    return [];
  }

  const trimmed = value.trim();

  // Empty string
  if (!trimmed) {
    return [];
  }

  try {
    const parsed = JSON.parse(trimmed);

    if (Array.isArray(parsed)) {
      return parsed.filter(Boolean).map(String);
    }

    if (parsed) {
      return [String(parsed)];
    }

    return [];
  } catch {
    // If database contains plain text instead of JSON,
    // display the text instead of crashing the page.
    return [trimmed];
  }
}

export default function WorkerPortal() {
  const [activeTab, setActiveTab] = useState<Tab>("manual");
  const [stage, setStage] = useState<ProcessingStage>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [results, setResults] = useState<any[]>([]);

  // Manual Input State
  const [manualText, setManualText] = useState("");

  const submitManual = async () => {
    if (!manualText.trim()) return;

    setStage("processing");
    setErrorMsg("");
    setResults([]);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: manualText,
        }),
      });

      let data: any;

      try {
        data = await res.json();
      } catch {
        throw new Error("Server returned an invalid response.");
      }

      if (!res.ok) {
        throw new Error(
          data?.error || "Unable to analyze the report. Please try again."
        );
      }

      setResults([data]);
      setStage("success");
    } catch (err: any) {
      console.error("[Worker Portal] Manual submission error:", err);
      setStage("error");
      setErrorMsg(
        err?.message || "Unable to analyze the report. Please try again."
      );
    }
  };

  const submitCSV = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];

    if (!file) return;

    setStage("processing");
    setErrorMsg("");
    setResults([]);

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,

      complete: async (results) => {
        try {
          const rows = results.data as any[];

          if (rows.length === 0) {
            throw new Error("CSV is empty or invalid.");
          }

          const processedResults: any[] = [];

          for (const row of rows) {
            // Use report_text when available.
            // Otherwise combine all CSV columns.
            const text =
              row.report_text || Object.values(row).join(" | ");

            if (!String(text || "").trim()) {
              continue;
            }

            const res = await fetch("/api/analyze", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                text,
              }),
            });

            let data: any;

            try {
              data = await res.json();
            } catch {
              console.error(
                "[Worker Portal] Invalid JSON response for CSV row"
              );
              continue;
            }

            if (res.ok && data) {
              processedResults.push(data);
            } else {
              console.error(
                "[Worker Portal] CSV row analysis failed:",
                data?.error
              );
            }
          }

          if (processedResults.length === 0) {
            throw new Error("CSV contains invalid rows.");
          }

          setResults(processedResults);
          setStage("success");
        } catch (err: any) {
          console.error("[Worker Portal] CSV submission error:", err);
          setStage("error");
          setErrorMsg(
            err?.message || "Failed to process CSV file."
          );
        }
      },

      error: (error) => {
        console.error("[Worker Portal] CSV parse error:", error);
        setStage("error");
        setErrorMsg("Failed to parse CSV file.");
      },
    });
  };

  const submitPDF = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];

    if (!file) return;

    if (file.type !== "application/pdf") {
      setStage("error");
      setErrorMsg("Please upload a valid PDF file.");
      return;
    }

    setStage("processing");
    setErrorMsg("");
    setResults([]);

    const reader = new FileReader();

    reader.onload = async (event) => {
      try {
        const result = event.target?.result;

        if (typeof result !== "string") {
          throw new Error("Unable to read the PDF file.");
        }

        const parts = result.split(",");

        if (parts.length < 2 || !parts[1]) {
          throw new Error("Unable to extract PDF data.");
        }

        const base64 = parts[1];

        const res = await fetch("/api/analyze", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            fileData: {
              data: base64,
              mimeType: "application/pdf",
            },
          }),
        });

        let data: any;

        try {
          data = await res.json();
        } catch {
          throw new Error("Server returned an invalid PDF response.");
        }

        if (!res.ok) {
          throw new Error(
            data?.error || "PDF could not be read or analyzed."
          );
        }

        setResults([data]);
        setStage("success");
      } catch (err: any) {
        console.error("[Worker Portal] PDF submission error:", err);
        setStage("error");
        setErrorMsg(
          err?.message || "PDF could not be read or analyzed."
        );
      }
    };

    reader.onerror = () => {
      setStage("error");
      setErrorMsg("Failed to read the PDF file.");
    };

    reader.readAsDataURL(file);
  };

  const renderResult = (res: any) => {
    const rules = parseRules(res?.life_saving_rules);

    const riskLevel =
      res?.risk_level ||
      res?.review_priority ||
      "Medium";

    const hazard =
      res?.hazard ||
      "Hazard not identified";

    const reportSummary =
      res?.report_summary ||
      res?.explanation ||
      "No summary available.";

    const precursorPattern =
      res?.precursor_pattern &&
      res.precursor_pattern !== "Not identified"
        ? res.precursor_pattern
        : "";

    return (
      <div
        key={res?.report_id || Math.random()}
        className="bg-slate-800 border border-slate-700 rounded-lg p-5 mb-4 text-left"
      >
        <div className="flex justify-between items-start mb-2">
          <h3 className="text-lg font-bold text-white">
            Report #{res?.report_id || "Unknown"}
          </h3>

          <span
            className={`px-3 py-1 rounded-full text-xs font-bold ${
              riskLevel === "Critical"
                ? "bg-red-500/20 text-red-400 border border-red-500/50"
                : riskLevel === "High"
                ? "bg-orange-500/20 text-orange-400 border border-orange-500/50"
                : riskLevel === "Medium"
                ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/50"
                : "bg-blue-500/20 text-blue-400 border border-blue-500/50"
            }`}
          >
            {riskLevel} Risk
          </span>
        </div>

        <p className="text-sm text-slate-300 mb-4">
          {reportSummary}
        </p>

        <div className="grid grid-cols-2 gap-4 text-sm bg-slate-900 p-4 rounded-lg mb-4">
          <div>
            <span className="text-slate-500 block text-xs">
              Hazard
            </span>

            <span className="font-medium text-slate-200">
              {hazard}
            </span>
          </div>

          <div>
            <span className="text-slate-500 block text-xs">
              Life-Saving Rule
            </span>

            <span className="font-medium text-slate-200">
              {rules.length > 0
                ? rules.join(", ")
                : "None"}
            </span>
          </div>
        </div>

        {precursorPattern && (
          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex gap-3 items-start">
            <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />

            <div>
              <p className="text-sm font-bold text-amber-400">
                Precursor Pattern Detected
              </p>

              <p className="text-xs text-amber-200/80 mt-1">
                {precursorPattern}
              </p>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 pb-12">
      <div className="text-center space-y-4 pt-12">
        <h1 className="text-4xl font-extrabold tracking-tight text-white">
          SafeSignal AI
        </h1>

        <p className="text-slate-400 text-lg">
          Submit safety reports for automated AI analysis and
          precursor detection.
        </p>
      </div>

      <div className="bg-slate-900/50 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl backdrop-blur-xl">
        {/* Tabs */}
        <div className="flex border-b border-slate-800">
          <TabButton
            active={activeTab === "manual"}
            onClick={() => {
              setActiveTab("manual");
              setStage("idle");
              setResults([]);
              setErrorMsg("");
            }}
            icon={<FileText className="w-4 h-4" />}
            label="Manual Report"
          />

          <TabButton
            active={activeTab === "csv"}
            onClick={() => {
              setActiveTab("csv");
              setStage("idle");
              setResults([]);
              setErrorMsg("");
            }}
            icon={<FileType className="w-4 h-4" />}
            label="CSV Upload"
          />

          <TabButton
            active={activeTab === "pdf"}
            onClick={() => {
              setActiveTab("pdf");
              setStage("idle");
              setResults([]);
              setErrorMsg("");
            }}
            icon={<UploadCloud className="w-4 h-4" />}
            label="PDF Upload"
          />
        </div>

        {/* Content */}
        <div className="p-8 min-h-[300px] flex flex-col items-center justify-center">
          {stage === "processing" ? (
            <div className="flex flex-col items-center text-blue-400 space-y-4 animate-in fade-in">
              <Loader2 className="w-12 h-12 animate-spin" />

              <p className="font-medium">
                Analyzing safety report data...
              </p>
            </div>
          ) : stage === "success" && results.length > 0 ? (
            <div className="w-full animate-in fade-in slide-in-from-bottom-4">
              <div className="flex items-center gap-2 text-emerald-400 mb-6 justify-center">
                <CheckCircle2 className="w-6 h-6" />

                <h2 className="text-xl font-bold">
                  Successfully Processed {results.length} Report(s)
                </h2>
              </div>

              <div className="max-h-[500px] overflow-y-auto pr-2">
                {results.map(renderResult)}
              </div>

              <div className="mt-6 flex justify-center">
                <button
                  onClick={() => {
                    setStage("idle");
                    setResults([]);
                    setErrorMsg("");
                  }}
                  className="px-6 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors font-medium"
                >
                  Submit Another
                </button>
              </div>
            </div>
          ) : (
            <div className="w-full animate-in fade-in flex flex-col items-center max-w-2xl text-center space-y-6">
              {/* Manual */}
              {activeTab === "manual" && (
                <>
                  <p className="text-slate-400">
                    Describe the safety incident, near miss, or
                    unsafe condition.
                  </p>

                  <textarea
                    value={manualText}
                    onChange={(e) =>
                      setManualText(e.target.value)
                    }
                    placeholder="e.g. There is an oil leak near the main pump in the production area. The floor is slippery..."
                    className="w-full h-40 bg-slate-950 border border-slate-800 rounded-xl p-4 text-white placeholder-slate-600 focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                  />

                  <button
                    onClick={submitManual}
                    disabled={!manualText.trim()}
                    className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl font-bold text-white shadow-lg shadow-blue-900/20 transition-all"
                  >
                    Analyze Safety Report
                  </button>
                </>
              )}

              {/* CSV */}
              {activeTab === "csv" && (
                <>
                  <p className="text-slate-400">
                    Upload a CSV file containing multiple safety
                    reports to process them in bulk.
                  </p>

                  <label className="w-full h-40 border-2 border-dashed border-slate-700 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:border-blue-500 hover:bg-slate-800/50 transition-colors">
                    <UploadCloud className="w-10 h-10 text-slate-500 mb-3" />

                    <span className="text-slate-300 font-medium">
                      Click to select CSV file
                    </span>

                    <input
                      type="file"
                      accept=".csv"
                      className="hidden"
                      onChange={submitCSV}
                    />
                  </label>
                </>
              )}

              {/* PDF */}
              {activeTab === "pdf" && (
                <>
                  <p className="text-slate-400">
                    Upload an incident report or safety document
                    in PDF format.
                  </p>

                  <label className="w-full h-40 border-2 border-dashed border-slate-700 rounded-xl flex flex-col items-center justify-center cursor-pointer hover:border-blue-500 hover:bg-slate-800/50 transition-colors">
                    <FileText className="w-10 h-10 text-slate-500 mb-3" />

                    <span className="text-slate-300 font-medium">
                      Click to select PDF file
                    </span>

                    <input
                      type="file"
                      accept="application/pdf"
                      className="hidden"
                      onChange={submitPDF}
                    />
                  </label>
                </>
              )}
            </div>
          )}

          {/* Error */}
          {errorMsg && stage === "error" && (
            <div className="mt-8 w-full max-w-2xl p-4 bg-red-500/10 border border-red-500/20 rounded-lg flex items-start gap-3 text-red-200 text-left animate-in fade-in">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-red-400" />

              <p>{errorMsg}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 flex items-center justify-center gap-2 py-4 font-medium text-sm transition-all border-b-2 ${
        active
          ? "border-blue-500 text-white bg-blue-500/5"
          : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}