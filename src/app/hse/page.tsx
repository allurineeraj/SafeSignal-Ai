"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle,
  FileX,
  Shield,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";

function parseRules(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String).filter((x) => x.trim() !== "");
  }

  if (typeof value === "string") {
    const trimmed = value.trim();

    if (!trimmed) {
      return [];
    }

    try {
      const parsed = JSON.parse(trimmed);

      if (Array.isArray(parsed)) {
        return parsed.map(String).filter((x) => x.trim() !== "");
      }

      if (typeof parsed === "string" && parsed.trim()) {
        return [parsed.trim()];
      }
    } catch {
      // Stored as normal text instead of JSON.
    }

    return [trimmed];
  }

  return [];
}

function getAiPrediction(report: any) {
  if (!report) {
    return null;
  }

  const raw = report.ai_predictions;

  if (Array.isArray(raw)) {
    return raw[0] ?? null;
  }

  if (raw && typeof raw === "object") {
    return raw;
  }

  // Fallback in case /api/queue returns flattened AI fields.
  if (
    report.ai_hazard ||
    report.ai_life_saving_rules ||
    report.ai_potential_consequence ||
    report.ai_priority ||
    report.ai_explanation
  ) {
    return {
      hazard: report.ai_hazard,
      life_saving_rules: report.ai_life_saving_rules,
      potential_consequence: report.ai_potential_consequence,
      priority: report.ai_priority,
      explanation: report.ai_explanation,
      sif_label: report.ai_sif_label,
    };
  }

  return null;
}

function getPrecursor(ai: any): string {
  if (!ai) {
    return "None";
  }

  const value =
    ai.potential_consequence ??
    ai.precursor_pattern ??
    ai.ai_potential_consequence ??
    "";

  if (value === null || value === undefined) {
    return "None";
  }

  const text = String(value).trim();

  if (
    !text ||
    text.toLowerCase() === "none" ||
    text.toLowerCase() === "not identified"
  ) {
    return "None";
  }

  return text;
}

function getHazard(ai: any): string {
  if (!ai) {
    return "None";
  }

  const value = ai.hazard ?? ai.ai_hazard ?? "";

  if (value === null || value === undefined) {
    return "None";
  }

  const text = String(value).trim();

  return text || "None";
}

function getSummary(report: any, ai: any): string {
  const value =
    ai?.explanation ??
    ai?.report_summary ??
    report?.report_summary ??
    report?.original_text ??
    "No summary available";

  const text = String(value).trim();

  return text || "No summary available";
}

function getRiskLevel(report: any, ai: any): string {
  const value =
    ai?.priority ??
    ai?.risk_level ??
    report?.review_priority ??
    "Low";

  const text = String(value).trim();

  if (
    text === "Critical" ||
    text === "High" ||
    text === "Medium" ||
    text === "Low"
  ) {
    return text;
  }

  return "Low";
}

export default function HSEQueue() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const router = useRouter();

  const fetchQueue = useCallback(async () => {
    try {
      setRefreshing(true);
      setErrorMsg(null);

      /*
       * IMPORTANT:
       * Add a timestamp and no-store so the HSE queue always
       * requests the latest reports instead of an old cached response.
       */
      const res = await fetch(`/api/queue?t=${Date.now()}`, {
        method: "GET",
        cache: "no-store",
        headers: {
          "Cache-Control": "no-cache",
        },
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Queue request failed: ${res.status}`);
      }

      const data = await res.json();

      console.log("[HSE Queue] Fresh API response:", data);

      /*
       * Support both:
       *   [report, report, ...]
       *
       * and:
       *   { reports: [...] }
       */
      if (Array.isArray(data)) {
        setReports(data);
      } else if (Array.isArray(data?.reports)) {
        setReports(data.reports);
      } else {
        console.error("[HSE Queue] Unexpected API response:", data);
        setReports([]);
      }
    } catch (error: any) {
      console.error("[HSE Queue] Failed to fetch queue:", error);
      setErrorMsg(error.message || "Failed to connect to the backend.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("token");

    if (!token) {
      router.push("/login");
      return;
    }

    fetchQueue();
  }, [router, fetchQueue]);

  const handleAction = async (
    reportId: string,
    action: string
  ) => {
    try {
      const user =
        localStorage.getItem("user") || "HSE001";

      const res = await fetch("/api/review", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          report_id: reportId,
          reviewer_name: user,
          action,
          comments: `Report marked as ${action}`,
        }),
      });

      if (!res.ok) {
        throw new Error("Review action failed");
      }

      await fetchQueue();
    } catch (error) {
      console.error(error);
      alert("Action failed");
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-400">
        Loading review queue...
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">

      <div className="flex justify-between items-center border-b border-slate-700 pb-4 mt-8">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Shield className="w-8 h-8 text-blue-500" /> HSE Review Queue
        </h1>
        <div className="flex items-center gap-4">
          {refreshing && <span className="text-sm text-slate-500">Refreshing...</span>}
          <button
            onClick={() => router.push("/analytics")}
            className="text-sm text-blue-400 hover:text-blue-300 font-medium"
          >
            Analytics Dashboard
          </button>
          
          <button
            onClick={() => fetchQueue()}
            disabled={refreshing}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white disabled:opacity-50"
          >
            Refresh
          </button>

          <button
            onClick={() => {
              localStorage.clear();
              router.push("/login");
            }}
            className="text-sm text-slate-400 hover:text-white"
          >
            Logout
          </button>
        </div>
      </div>

      {errorMsg ? (
        <div className="bg-red-900/50 border border-red-800 rounded-xl p-8 text-center text-red-200 shadow-xl">
          <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-red-500 opacity-80" />
          <p className="text-lg font-bold mb-2">Error Loading Queue</p>
          <p className="text-sm opacity-80">{errorMsg}</p>
        </div>
      ) : reports.length === 0 ? (

        <div className="bg-slate-900/50 border border-slate-800 rounded-xl p-16 text-center text-slate-400 shadow-xl">

          <CheckCircle className="w-16 h-16 mx-auto mb-4 text-emerald-500 opacity-50" />

          <p className="text-xl">
            All caught up! No pending reports to review.
          </p>

          <button
            onClick={() => fetchQueue()}
            className="mt-6 px-5 py-2 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30"
          >
            Refresh Queue
          </button>

        </div>

      ) : (

        <div className="space-y-6">

          {reports.map((report) => {

            const ai = getAiPrediction(report);

            const lifeSavingRules = parseRules(
              ai?.life_saving_rules ??
              ai?.lifeSavingRules ??
              report?.ai_life_saving_rules ??
              report?.life_saving_rules
            );

            const riskLevel = getRiskLevel(
              report,
              ai
            );

            const summary = getSummary(
              report,
              ai
            );

            const precursor = getPrecursor(ai);

            const hazard = getHazard(ai);

            return (

              <div
                key={
                  report.id ??
                  report.report_id
                }
                className="bg-slate-900/80 border border-slate-700 rounded-xl p-6 shadow-xl space-y-5"
              >

                {/* REPORT HEADER */}
                <div className="flex justify-between items-start">

                  <div>

                    <div className="flex items-center gap-3 mb-1">

                      <h3 className="text-xl font-bold text-white">
                        {report.report_id}
                      </h3>

                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                        {report.report_type}
                      </span>

                    </div>

                    <p className="text-sm text-slate-400">
                      {report.created_at
                        ? new Date(
                            report.created_at
                          ).toLocaleString()
                        : "Date unavailable"}
                    </p>

                  </div>

                  {/* RISK */}
                  <div>

                    <span
                      className={`px-3 py-1 rounded-full text-xs font-bold border ${
                        riskLevel === "Critical"
                          ? "bg-red-500/20 text-red-400 border-red-500/50"
                          : riskLevel === "High"
                          ? "bg-orange-500/20 text-orange-400 border-orange-500/50"
                          : riskLevel === "Medium"
                          ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/50"
                          : "bg-blue-500/20 text-blue-400 border-blue-500/50"
                      }`}
                    >
                      {riskLevel} Risk
                    </span>

                  </div>

                </div>

                {/* SUMMARY */}
                <div className="bg-slate-950 p-4 rounded-lg border border-slate-800">

                  <p className="text-sm font-medium text-slate-300 mb-2">
                    Report Summary
                  </p>

                  <p className="text-slate-100">
                    {summary}
                  </p>

                </div>

                {/* AI DATA */}
                <div className="grid md:grid-cols-4 gap-4 text-sm">

                  {/* HAZARD */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">

                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Hazard
                    </p>

                    <p className="font-medium text-slate-200">
                      {hazard}
                    </p>

                  </div>

                  {/* PRECURSOR */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">

                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Precursor Pattern
                    </p>

                    <p className="font-medium text-amber-400">
                      {precursor}
                    </p>

                  </div>

                  {/* LIFE SAVING RULE */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">

                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Life-Saving Rule
                    </p>

                    <p className="font-medium text-blue-400">
                      {lifeSavingRules.length > 0
                        ? lifeSavingRules.join(", ")
                        : "None"}
                    </p>

                  </div>

                  {/* STATUS */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">

                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Status
                    </p>

                    <p className="font-medium text-slate-200">
                      {report.report_status ??
                        "Pending HSE Review"}
                    </p>

                  </div>

                </div>

                {/* ACTIONS */}
                <div className="pt-4 flex flex-wrap gap-3 border-t border-slate-700/50">

                  <button
                    onClick={() =>
                      handleAction(
                        report.report_id,
                        "Accept"
                      )
                    }
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600/20 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/30 rounded-lg transition-colors text-sm font-medium"
                  >
                    <CheckCircle className="w-4 h-4" />
                    Review & Assign Action
                  </button>

                  <button
                    onClick={() =>
                      handleAction(
                        report.report_id,
                        "Reject"
                      )
                    }
                    className="flex items-center gap-2 px-4 py-2 bg-red-600/20 text-red-400 border border-red-600/30 hover:bg-red-600/30 rounded-lg transition-colors text-sm font-medium ml-auto"
                  >
                    <FileX className="w-4 h-4" />
                    Close Report
                  </button>

                </div>

              </div>

            );
          })}

        </div>

      )}

    </div>
  );
}