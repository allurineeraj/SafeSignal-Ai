"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle,
  FileX,
  Shield,
  RefreshCw,
  AlertTriangle,
  X,
  CheckCircle2,
  AlertCircle,
  Calendar,
  User,
  Building2,
  Edit3,
  Loader2,
  ClipboardCheck,
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

function getSifLabel(report: any, ai: any): string {
  const value =
    ai?.sif_label ??
    report?.ai_sif_label ??
    "Non-SIF";

  const text = String(value).trim();
  if (text === "SIF-potential" || text === "Non-SIF") {
    return text;
  }
  return "Non-SIF";
}

export default function HSEQueue() {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Review & Action Modal State
  const [reviewModalReport, setReviewModalReport] = useState<any | null>(null);
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  // Review form fields
  const [formPriority, setFormPriority] = useState("Medium");
  const [formSif, setFormSif] = useState("Non-SIF");
  const [formHazard, setFormHazard] = useState("");
  const [formPrecursor, setFormPrecursor] = useState("");
  const [formRules, setFormRules] = useState("");
  const [formSummary, setFormSummary] = useState("");
  const [formComments, setFormComments] = useState("");

  // Corrective action fields
  const [formActionPlan, setFormActionPlan] = useState("");
  const [formResponsibleDept, setFormResponsibleDept] = useState("Safety & HSE");
  const [formAssignedTo, setFormAssignedTo] = useState("");
  const [formActionPriority, setFormActionPriority] = useState("Medium");
  const [formTargetDate, setFormTargetDate] = useState("");

  // Close report loading state per report
  const [closingReportId, setClosingReportId] = useState<string | null>(null);

  const router = useRouter();

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const fetchQueue = useCallback(async () => {
    try {
      setRefreshing(true);
      setErrorMsg(null);

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

  // Open Review & Action Modal and pre-populate all values
  const handleOpenReview = (report: any) => {
    const ai = getAiPrediction(report);
    const risk = getRiskLevel(report, ai);
    const sif = getSifLabel(report, ai);
    const hazard = getHazard(ai);
    const precursor = getPrecursor(ai);
    const rulesList = parseRules(ai?.life_saving_rules || report?.life_saving_rules);
    const summary = getSummary(report, ai);

    setReviewModalReport(report);
    setFormPriority(risk);
    setFormSif(sif);
    setFormHazard(hazard !== "None" ? hazard : "");
    setFormPrecursor(precursor !== "None" ? precursor : "");
    setFormRules(rulesList.join(", "));
    setFormSummary(summary !== "No summary available" ? summary : "");
    setFormComments("");

    // Reset corrective action fields
    setFormActionPlan("");
    setFormResponsibleDept("Safety & HSE");
    setFormAssignedTo("");
    setFormActionPriority(risk);
    
    // Default target date: 7 days from today
    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 7);
    setFormTargetDate(nextWeek.toISOString().split("T")[0]);
  };

  // Submit Review / Action Assignment
  const handleSaveReview = async (actionType: "Assign Action" | "Accept" | "Correct") => {
    if (!reviewModalReport) return;

    try {
      setIsSubmittingReview(true);
      const user = localStorage.getItem("user") || "HSE001";

      const parsedRulesArray = formRules
        ? formRules.split(",").map((r) => r.trim()).filter(Boolean)
        : [];

      const payload: any = {
        report_id: reviewModalReport.report_id,
        reviewer_name: user,
        action: actionType,
        comments: formComments.trim() || `Report ${actionType === "Assign Action" ? "action assigned" : actionType.toLowerCase()} by ${user}`,
        corrections: {
          priority: formPriority,
          sif_label: formSif,
          hazard: formHazard.trim() || "Not identified",
          precursor_pattern: formPrecursor.trim() || "Not identified",
          life_saving_rules: parsedRulesArray,
          summary: formSummary.trim(),
        },
      };

      // If assigning action or action plan is entered, attach corrective action
      if (formActionPlan.trim()) {
        payload.corrective_action = {
          action_plan: formActionPlan.trim(),
          responsible_department: formResponsibleDept,
          assigned_to: formAssignedTo.trim() || "Unassigned",
          priority: formActionPriority,
          target_date: formTargetDate || new Date().toISOString().split("T")[0],
          status: "Assigned",
        };
      }

      const res = await fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to submit review.");
      }

      setToast({
        type: "success",
        message: `Report #${reviewModalReport.report_id} successfully updated (${data.new_status || actionType}).`,
      });

      setReviewModalReport(null);
      await fetchQueue();
    } catch (error: any) {
      console.error("[HSE Queue] Review submission error:", error);
      setToast({
        type: "error",
        message: error.message || "Failed to save review. Please try again.",
      });
    } finally {
      setIsSubmittingReview(false);
    }
  };

  // Close Report Handler
  const handleCloseReport = async (reportId: string) => {
    try {
      setClosingReportId(reportId);
      const user = localStorage.getItem("user") || "HSE001";

      const res = await fetch("/api/review", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          report_id: reportId,
          reviewer_name: user,
          action: "Close",
          comments: `Report marked as Closed by ${user}`,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to close report");
      }

      setToast({
        type: "success",
        message: `Report #${reportId} has been successfully closed.`,
      });

      await fetchQueue();
    } catch (error: any) {
      console.error("[HSE Queue] Close report error:", error);
      setToast({
        type: "error",
        message: error.message || "Failed to close report. Please try again.",
      });
    } finally {
      setClosingReportId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-12 text-center text-slate-400 flex items-center justify-center gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        Loading review queue...
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* HEADER */}
      <div className="flex justify-between items-center border-b border-slate-700 pb-4 mt-8">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Shield className="w-8 h-8 text-blue-500" /> HSE Review Queue
        </h1>
        <div className="flex items-center gap-4">
          {refreshing && <span className="text-sm text-slate-500 flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Refreshing...</span>}
          <button
            onClick={() => router.push("/analytics")}
            className="text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors"
          >
            Analytics Dashboard
          </button>
          
          <button
            onClick={() => fetchQueue()}
            disabled={refreshing}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-white disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>

          <button
            onClick={() => {
              localStorage.clear();
              router.push("/login");
            }}
            className="text-sm text-slate-400 hover:text-white transition-colors"
          >
            Logout
          </button>
        </div>
      </div>

      {/* TOAST FEEDBACK */}
      {toast && (
        <div
          className={`p-4 rounded-xl flex items-center justify-between border shadow-lg animate-in fade-in slide-in-from-top-2 ${
            toast.type === "success"
              ? "bg-emerald-950/80 border-emerald-800 text-emerald-200"
              : "bg-red-950/80 border-red-800 text-red-200"
          }`}
        >
          <div className="flex items-center gap-3">
            {toast.type === "success" ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-400 shrink-0" />
            )}
            <p className="text-sm font-medium">{toast.message}</p>
          </div>
          <button
            onClick={() => setToast(null)}
            className="text-slate-400 hover:text-white p-1"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* QUEUE CONTENT */}
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
            className="mt-6 px-5 py-2 rounded-lg bg-blue-600/20 border border-blue-500/30 text-blue-400 hover:bg-blue-600/30 transition-colors"
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
            const riskLevel = getRiskLevel(report, ai);
            const sifLabel = getSifLabel(report, ai);
            const summary = getSummary(report, ai);
            const precursor = getPrecursor(ai);
            const hazard = getHazard(ai);
            const isClosing = closingReportId === report.report_id;

            return (
              <div
                key={report.id ?? report.report_id}
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
                      {sifLabel === "SIF-potential" && (
                        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-950 text-red-300 border border-red-800">
                          SIF-potential
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-400">
                      {report.created_at
                        ? new Date(report.created_at).toLocaleString()
                        : "Date unavailable"}
                    </p>
                  </div>

                  {/* RISK BADGE */}
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
                  <p className="text-slate-100">{summary}</p>
                </div>

                {/* AI DATA GRID */}
                <div className="grid md:grid-cols-4 gap-4 text-sm">
                  {/* HAZARD */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Hazard
                    </p>
                    <p className="font-medium text-slate-200">{hazard}</p>
                  </div>

                  {/* PRECURSOR */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Precursor Pattern
                    </p>
                    <p className="font-medium text-amber-400">{precursor}</p>
                  </div>

                  {/* LIFE SAVING RULE */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Life-Saving Rule
                    </p>
                    <p className="font-medium text-blue-400">
                      {lifeSavingRules.length > 0 ? lifeSavingRules.join(", ") : "None"}
                    </p>
                  </div>

                  {/* STATUS */}
                  <div className="bg-slate-800/50 p-3 rounded-lg border border-slate-700/50">
                    <p className="text-slate-400 text-xs uppercase tracking-wider mb-1">
                      Status
                    </p>
                    <p className="font-medium text-slate-200">
                      {report.report_status ?? "Pending HSE Review"}
                    </p>
                  </div>
                </div>

                {/* ACTIONS */}
                <div className="pt-4 flex flex-wrap gap-3 border-t border-slate-700/50 items-center">
                  <button
                    onClick={() => handleOpenReview(report)}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600/20 text-emerald-400 border border-emerald-600/30 hover:bg-emerald-600/30 rounded-lg transition-colors text-sm font-medium"
                  >
                    <CheckCircle className="w-4 h-4" />
                    Review & Assign Action
                  </button>

                  <button
                    onClick={() => handleOpenReview(report)}
                    className="flex items-center gap-2 px-3 py-2 bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 rounded-lg transition-colors text-sm font-medium"
                  >
                    <Edit3 className="w-4 h-4" />
                    Edit / Review
                  </button>

                  <button
                    onClick={() => handleCloseReport(report.report_id)}
                    disabled={isClosing}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600/20 text-red-400 border border-red-600/30 hover:bg-red-600/30 disabled:opacity-50 rounded-lg transition-colors text-sm font-medium ml-auto"
                  >
                    {isClosing ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <FileX className="w-4 h-4" />
                    )}
                    {isClosing ? "Closing..." : "Close Report"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* REVIEW & ASSIGN ACTION MODAL */}
      {reviewModalReport && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-6 my-8 max-h-[92vh] overflow-y-auto">
            {/* MODAL HEADER */}
            <div className="flex justify-between items-start border-b border-slate-800 pb-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <Shield className="w-5 h-5 text-blue-500" /> HSE Review & Action Assignment
                  </h2>
                  <span className="px-2 py-0.5 rounded text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/30">
                    {reviewModalReport.report_id}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Review AI classifications, adjust parameters, and assign corrective actions.
                </p>
              </div>
              <button
                onClick={() => setReviewModalReport(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* MODAL FORM CONTENT */}
            <div className="space-y-6">
              {/* SECTION 1: REPORT CLASSIFICATION & CORRECTIONS */}
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-4">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-blue-400" /> Report Classification & Review
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">
                      Risk Priority Level
                    </label>
                    <select
                      value={formPriority}
                      onChange={(e) => {
                        setFormPriority(e.target.value);
                        setFormActionPriority(e.target.value);
                      }}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500"
                    >
                      <option value="Critical">Critical Risk</option>
                      <option value="High">High Risk</option>
                      <option value="Medium">Medium Risk</option>
                      <option value="Low">Low Risk</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">
                      SIF Classification
                    </label>
                    <select
                      value={formSif}
                      onChange={(e) => setFormSif(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500"
                    >
                      <option value="SIF-potential">SIF-potential (Serious Injury / Fatality)</option>
                      <option value="Non-SIF">Non-SIF</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">
                      Primary Hazard
                    </label>
                    <input
                      type="text"
                      value={formHazard}
                      onChange={(e) => setFormHazard(e.target.value)}
                      placeholder="e.g., Working at Height, Electrical, Chemical Spill"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1">
                      Precursor Pattern
                    </label>
                    <input
                      type="text"
                      value={formPrecursor}
                      onChange={(e) => setFormPrecursor(e.target.value)}
                      placeholder="e.g., Unprotected exposure to fall-from-height"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    Life-Saving Rules (comma separated)
                  </label>
                  <input
                    type="text"
                    value={formRules}
                    onChange={(e) => setFormRules(e.target.value)}
                    placeholder="e.g., Working at Height, Line of Fire, Control of Hazardous Energy"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    Report Summary / Description
                  </label>
                  <textarea
                    value={formSummary}
                    onChange={(e) => setFormSummary(e.target.value)}
                    rows={2}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500 resize-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    HSE Officer Comments / Review Notes
                  </label>
                  <textarea
                    value={formComments}
                    onChange={(e) => setFormComments(e.target.value)}
                    placeholder="Add any specific observations or review decisions..."
                    rows={2}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-blue-500 resize-none"
                  />
                </div>
              </div>

              {/* SECTION 2: CORRECTIVE ACTION ASSIGNMENT */}
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-4">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-emerald-400" /> Assign Corrective Action
                </h3>

                <div>
                  <label className="block text-xs font-semibold text-slate-400 mb-1">
                    Corrective Action Plan / Remediation
                  </label>
                  <textarea
                    value={formActionPlan}
                    onChange={(e) => setFormActionPlan(e.target.value)}
                    placeholder="e.g., Inspect scaffolding, install edge guardrails, and mandate 100% tie-off before work resumes..."
                    rows={3}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-emerald-500 resize-none"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1 flex items-center gap-1">
                      <Building2 className="w-3.5 h-3.5" /> Department
                    </label>
                    <select
                      value={formResponsibleDept}
                      onChange={(e) => setFormResponsibleDept(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-emerald-500"
                    >
                      <option value="Safety & HSE">Safety & HSE</option>
                      <option value="Maintenance">Maintenance</option>
                      <option value="Operations">Operations</option>
                      <option value="Electrical">Electrical</option>
                      <option value="Civil / Structural">Civil / Structural</option>
                      <option value="Logistics">Logistics</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1 flex items-center gap-1">
                      <User className="w-3.5 h-3.5" /> Assigned To
                    </label>
                    <input
                      type="text"
                      value={formAssignedTo}
                      onChange={(e) => setFormAssignedTo(e.target.value)}
                      placeholder="e.g., Site Supervisor / Safety Lead"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 mb-1 flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" /> Target Date
                    </label>
                    <input
                      type="date"
                      value={formTargetDate}
                      onChange={(e) => setFormTargetDate(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2.5 text-white text-sm outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* MODAL FOOTER BUTTONS */}
            <div className="flex flex-wrap items-center justify-end gap-3 pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setReviewModalReport(null)}
                disabled={isSubmittingReview}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={() => handleSaveReview("Accept")}
                disabled={isSubmittingReview}
                className="px-4 py-2 bg-blue-600/20 text-blue-400 border border-blue-500/30 hover:bg-blue-600/30 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                Save Review (Accepted)
              </button>

              <button
                type="button"
                onClick={() => handleSaveReview("Assign Action")}
                disabled={isSubmittingReview}
                className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-bold shadow-lg shadow-emerald-900/30 transition-all disabled:opacity-50"
              >
                {isSubmittingReview && <Loader2 className="w-4 h-4 animate-spin" />}
                {isSubmittingReview ? "Saving..." : "Save & Assign Action"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}