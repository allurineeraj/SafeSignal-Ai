import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { report_id, reviewer_name, action, comments, corrections } = body;

    const statusMap: Record<string, string> = {
      Accept: "Action Assigned",
      Correct: "Corrected",
      Reject: "Closed",
      Duplicate: "Closed",
    };
    
    const newStatus = statusMap[action] || "Pending HSE Review";

    // 1. Update report status
    const { error: updateErr } = await supabase
      .from("reports")
      .update({ report_status: newStatus })
      .eq("report_id", report_id);

    if (updateErr) {
      console.error("[POST /api/review] Update status failed:", updateErr.message);
      return NextResponse.json({ error: updateErr.message }, { status: 500 });
    }

    // 2. Insert HSE Review log
    const c = corrections || {};
    const { error: reviewErr } = await supabase.from("hse_reviews").insert({
      report_id,
      reviewer_name: reviewer_name || "HSE User",
      review_status: newStatus,
      hse_comments: comments || "",
      final_sif_label: c.sif_label || "Unknown",
      final_priority: c.priority || "Unknown",
    });

    if (reviewErr) {
      console.error("[POST /api/review] Insert review log error:", reviewErr.message);
    }

    return NextResponse.json({ success: true, new_status: newStatus });
  } catch (err: any) {
    console.error("[POST /api/review] Unexpected error:", err);
    return NextResponse.json({ error: err?.message || String(err) }, { status: 500 });
  }
}

