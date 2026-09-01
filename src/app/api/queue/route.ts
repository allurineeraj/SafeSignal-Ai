import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const { data, error } = await supabase
      .from("reports")
      .select("*, ai_predictions(*)")
      .eq("report_status", "Pending HSE Review")
      .order("created_at", { ascending: false });

    if (error) {
      console.error("[GET /api/queue] Database query failed:", error.message);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    
    return NextResponse.json(data || []);
  } catch (err: any) {
    console.error("[GET /api/queue] Unexpected error:", err);
    return NextResponse.json({ error: err?.message || String(err) }, { status: 500 });
  }
}

