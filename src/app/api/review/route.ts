import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { report_id, reviewer_name, action, comments, corrections } = body;

    const statusMap: Record<string, string> = {
      Accept: "Action Assigned", // or "Reviewed" depending on workflow. Let's use "Reviewed" if no action, else "Action Assigned"
      Correct: "Corrected",
      Reject: "Closed", // or "Rejected"
      Duplicate: "Closed",
    };
    
    const newStatus = statusMap[action] || "Pending HSE Review";

    // 1. Update report status
    await supabase.from("reports").update({ report_status: newStatus }).eq("report_id", report_id);

    // 2. Insert HSE Review log
    const c = corrections || {};
    await supabase.from("hse_reviews").insert({
      report_id,
      reviewer_name: reviewer_name || "HSE User",
      review_status: newStatus,
      hse_comments: comments || "",
      final_sif_label: c.sif_label || "Unknown",
      final_priority: c.priority || "Unknown",
    });

    return NextResponse.json({ success: true, new_status: newStatus });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
