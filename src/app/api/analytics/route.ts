import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // Fetch reports with joined AI predictions and HSE reviews for exact relational accuracy
    const { data: reports, error: reportsErr } = await supabase
      .from("reports")
      .select("*, ai_predictions(*), hse_reviews(*)")
      .order("created_at", { ascending: false });

    if (reportsErr) {
      console.error("[GET /api/analytics] Supabase error:", reportsErr.message);
      return NextResponse.json({ error: reportsErr.message }, { status: 500 });
    }

    const allReports = reports || [];
    const total = allReports.length;

    let critical_count = 0;
    let closed_count = 0;
    let sif_count = 0;

    const hazards: Record<string, number> = {};
    const precursors: Record<string, number> = {};
    const riskLevels: Record<string, number> = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    const reportTypes: Record<string, number> = {};
    const lifeSavingRules: Record<string, number> = {};

    const closedReportsList: any[] = [];

    allReports.forEach((r: any) => {
      const ai = Array.isArray(r.ai_predictions) ? r.ai_predictions[0] : r.ai_predictions;
      const rev = Array.isArray(r.hse_reviews) ? r.hse_reviews[0] : r.hse_reviews;

      // Status
      const status = r.report_status || "Submitted";
      if (status === "Closed") {
        closed_count++;
        closedReportsList.push({
          id: r.id,
          report_id: r.report_id,
          report_type: r.report_type || "Report",
          report_summary: ai?.explanation || r.report_summary || r.original_text || "No summary available",
          original_text: r.original_text,
          review_priority: rev?.final_priority || r.review_priority || ai?.priority || "Low",
          report_status: status,
          reviewer_name: rev?.reviewer_name || "HSE Officer",
          hse_comments: rev?.hse_comments || "",
          created_at: r.created_at,
          reviewed_at: rev?.reviewed_at || r.created_at,
        });
      }

      // Priority / Risk Level
      const priority = rev?.final_priority || r.review_priority || ai?.priority || "Low";
      if (priority === "Critical" || priority === "High") {
        critical_count++;
      }
      if (riskLevels[priority] !== undefined) {
        riskLevels[priority]++;
      } else {
        riskLevels["Low"] = (riskLevels["Low"] || 0) + 1;
      }

      // SIF Potential
      const sifLabel = rev?.final_sif_label || ai?.sif_label;
      if (sifLabel === "SIF-potential") {
        sif_count++;
      }

      // Report Type
      const type = r.report_type || "Manual/CSV Input";
      reportTypes[type] = (reportTypes[type] || 0) + 1;

      // Hazard
      const hazard = rev?.final_hazard || ai?.hazard;
      if (hazard && hazard !== "Not identified" && hazard !== "None" && hazard !== "Hazard not identified") {
        hazards[hazard] = (hazards[hazard] || 0) + 1;
      }

      // Precursor
      const precursor = rev?.final_potential_consequence || ai?.potential_consequence || ai?.precursor_pattern;
      if (precursor && precursor !== "Not identified" && precursor !== "None") {
        precursors[precursor] = (precursors[precursor] || 0) + 1;
      }

      // Life-Saving Rules
      const rawRules = rev?.final_life_saving_rules || ai?.life_saving_rules;
      if (rawRules) {
        let rules: string[] = [];
        if (Array.isArray(rawRules)) {
          rules = rawRules;
        } else if (typeof rawRules === "string") {
          const trimmed = rawRules.trim();
          if (trimmed) {
            try {
              const parsed = JSON.parse(trimmed);
              if (Array.isArray(parsed)) {
                rules = parsed;
              } else if (typeof parsed === "string") {
                rules = [parsed];
              }
            } catch {
              rules = [trimmed];
            }
          }
        }

        rules.forEach((rule: any) => {
          const ruleStr = String(rule).trim();
          if (ruleStr && ruleStr !== "No applicable rule" && ruleStr !== "[]" && ruleStr !== "None" && ruleStr !== "null") {
            lifeSavingRules[ruleStr] = (lifeSavingRules[ruleStr] || 0) + 1;
          }
        });
      }
    });

    let topPrecursor = "None";
    let topPrecursorCount = 0;
    for (const [k, v] of Object.entries(precursors)) {
      if (v > topPrecursorCount) {
        topPrecursor = k;
        topPrecursorCount = v;
      }
    }

    const sif_percentage = total > 0 ? parseFloat(((sif_count / total) * 100).toFixed(1)) : 0;

    return NextResponse.json({
      total_reports: total,
      sif_count,
      critical_count,
      closed_count,
      sif_percentage,
      hazards,
      precursors,
      riskLevels,
      reportTypes,
      lifeSavingRules,
      topPrecursor,
      topPrecursorCount,
      closed_reports: closedReportsList,
    });
  } catch (err: any) {
    console.error("[GET /api/analytics] Exception:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
