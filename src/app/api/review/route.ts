import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { report_id, reviewer_name, action, comments, corrections, corrective_action } = body;

    if (!report_id) {
      return NextResponse.json({ error: "Missing required field: report_id" }, { status: 400 });
    }

    const statusMap: Record<string, string> = {
      "Accept": "Accepted",
      "Assign Action": "Action Assigned",
      "Action Assigned": "Action Assigned",
      "Correct": "Corrected",
      "Close": "Closed",
      "Reject": "Closed",
      "Duplicate": "Closed",
    };
    
    // If corrective action details are supplied with Accept, map to Action Assigned
    let newStatus = statusMap[action] || "Pending HSE Review";
    if (action === "Accept" && corrective_action?.action_plan?.trim()) {
      newStatus = "Action Assigned";
    }

    const c = corrections || {};

    // 1. Update report status and any corrected priority on reports table
    const reportUpdates: Record<string, any> = { report_status: newStatus };
    if (c.priority) {
      reportUpdates.review_priority = c.priority;
    }

    const { error: updateErr } = await supabase
      .from("reports")
      .update(reportUpdates)
      .eq("report_id", report_id);

    if (updateErr) {
      console.error("[POST /api/review] Update report failed:", updateErr.message);
      return NextResponse.json({ error: updateErr.message }, { status: 500 });
    }

    // 2. Format life saving rules if provided
    let rulesStr: string | null = null;
    if (c.life_saving_rules) {
      if (Array.isArray(c.life_saving_rules)) {
        rulesStr = JSON.stringify(c.life_saving_rules);
      } else if (typeof c.life_saving_rules === "string") {
        rulesStr = c.life_saving_rules.startsWith("[") ? c.life_saving_rules : JSON.stringify([c.life_saving_rules]);
      }
    }

    // 3. Upsert HSE Review record
    const reviewData: Record<string, any> = {
      report_id,
      reviewer_name: reviewer_name || "HSE Officer",
      review_status: newStatus,
      hse_comments: comments || (action === "Close" ? "Report closed by HSE Officer" : ""),
      final_sif_label: c.sif_label || "Non-SIF",
      final_priority: c.priority || "Medium",
    };

    if (c.hazard) reviewData.final_hazard = c.hazard;
    if (c.precursor_pattern || c.potential_consequence) {
      reviewData.final_potential_consequence = c.precursor_pattern || c.potential_consequence;
    }
    if (rulesStr) reviewData.final_life_saving_rules = rulesStr;

    const { error: reviewErr } = await supabase
      .from("hse_reviews")
      .upsert(reviewData, { onConflict: "report_id" });

    if (reviewErr) {
      console.error("[POST /api/review] Upsert review log error:", reviewErr.message);
    }

    // 4. Update AI predictions table if corrections are provided
    if (c.hazard || c.priority || c.sif_label || c.precursor_pattern || rulesStr || c.summary) {
      const predUpdates: Record<string, any> = {};
      if (c.hazard) predUpdates.hazard = c.hazard;
      if (c.priority) predUpdates.priority = c.priority;
      if (c.sif_label) predUpdates.sif_label = c.sif_label;
      if (c.precursor_pattern) predUpdates.potential_consequence = c.precursor_pattern;
      if (rulesStr) predUpdates.life_saving_rules = rulesStr;
      if (c.summary) predUpdates.explanation = c.summary;

      const { error: predErr } = await supabase
        .from("ai_predictions")
        .update(predUpdates)
        .eq("report_id", report_id);

      if (predErr) {
        console.warn("[POST /api/review] ai_predictions update warning:", predErr.message);
      }
    }

    // 5. Insert Corrective Action if provided
    if (corrective_action?.action_plan?.trim()) {
      const { error: caErr } = await supabase
        .from("corrective_actions")
        .insert({
          report_id,
          action_plan: corrective_action.action_plan.trim(),
          responsible_department: corrective_action.responsible_department?.trim() || "Safety & HSE",
          assigned_to: corrective_action.assigned_to?.trim() || "Unassigned",
          priority: corrective_action.priority || c.priority || "Medium",
          target_date: corrective_action.target_date || new Date().toISOString().split("T")[0],
          status: corrective_action.status || "Assigned",
        });

      if (caErr) {
        console.error("[POST /api/review] Insert corrective action error:", caErr.message);
      }
    }

    return NextResponse.json({
      success: true,
      report_id,
      new_status: newStatus,
      message: `Report ${report_id} successfully updated to ${newStatus}`,
    });
  } catch (err: any) {
    console.error("[POST /api/review] Unexpected error:", err);
    return NextResponse.json({ error: err?.message || String(err) }, { status: 500 });
  }
}

