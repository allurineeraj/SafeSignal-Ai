import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const { data: reports, error: reportsErr } = await supabase.from("reports").select("report_status, review_priority, id, created_at, report_type");
    const { data: preds, error: predsErr } = await supabase.from("ai_predictions").select("sif_label, priority, potential_consequence, hazard, life_saving_rules");

    if (reportsErr || predsErr) {
      const errMessage = reportsErr?.message || predsErr?.message || "Failed to fetch analytics from database";
      console.error("[GET /api/analytics] Supabase error:", errMessage);
      return NextResponse.json({ error: errMessage }, { status: 500 });
    }

    const total = reports?.length || 0;
    const critical = reports?.filter((r: any) => r.review_priority === "Critical" || r.review_priority === "High").length || 0;
    const closed = reports?.filter((r: any) => r.report_status === "Closed").length || 0;
    const sif_count = preds?.filter((p: any) => p.sif_label === "SIF-potential").length || 0;
    
    const hazards: Record<string, number> = {};
    const precursors: Record<string, number> = {};
    const riskLevels = { Critical: 0, High: 0, Medium: 0, Low: 0 };
    const reportTypes: Record<string, number> = {};
    const lifeSavingRules: Record<string, number> = {};

    reports?.forEach((r: any) => {
      reportTypes[r.report_type] = (reportTypes[r.report_type] || 0) + 1;
    });

    preds?.forEach((p: any) => {
      if (p.hazard && p.hazard !== "Not identified") hazards[p.hazard] = (hazards[p.hazard] || 0) + 1;
      
      const precursor = p.potential_consequence;
      if (precursor && precursor !== "Not identified") {
        precursors[precursor] = (precursors[precursor] || 0) + 1;
      }
      
      const riskLevel = p.priority;
      if (riskLevel && riskLevels[riskLevel as keyof typeof riskLevels] !== undefined) {
        riskLevels[riskLevel as keyof typeof riskLevels]++;
      }

      if (p.life_saving_rules) {
        try {
          // Use safe parse logic
          let rules = [];
          if (Array.isArray(p.life_saving_rules)) {
            rules = p.life_saving_rules;
          } else if (typeof p.life_saving_rules === "string") {
             const trimmed = p.life_saving_rules.trim();
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
            if (ruleStr && ruleStr !== "No applicable rule" && ruleStr !== "[]") {
              lifeSavingRules[ruleStr] = (lifeSavingRules[ruleStr] || 0) + 1;
            }
          });
        } catch(e){}
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

    return NextResponse.json({
      total_reports: total,
      sif_count,
      critical_count: critical,
      closed_count: closed,
      sif_percentage: total > 0 ? ((sif_count / total) * 100).toFixed(1) : 0,
      hazards,
      precursors,
      riskLevels,
      reportTypes,
      lifeSavingRules,
      topPrecursor,
      topPrecursorCount
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
