import { NextResponse } from "next/server";
import { supabase } from "@/lib/supabase";

export const maxDuration = 60;
export const dynamic = 'force-dynamic';

export async function POST(req: Request) {
  try {
    console.log("[POST /api/analyze] Request received");

    const apiKey = (
      process.env.GROQ_API_KEY ||
      process.env.GROQ_KEY ||
      process.env.NEXT_PUBLIC_GROQ_API_KEY ||
      ""
    )
      .trim()
      .replace(/^["']|["']$/g, "");

    if (!apiKey) {
      console.error(
        "[POST /api/analyze] Missing GROQ_API_KEY in environment variables"
      );

      return NextResponse.json(
        {
          error:
            "Missing GROQ_API_KEY environment variable in Vercel settings. Please configure GROQ_API_KEY in your Vercel Project Settings.",
        },
        { status: 500 }
      );
    }

    let body: any;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { error: "Invalid JSON request body." },
        { status: 400 }
      );
    }

    let text = body?.text;

    // ---------------------------------------------------------
    // PDF PROCESSING
    // ---------------------------------------------------------

    if (body?.fileData) {
      console.log("[POST /api/analyze] Processing PDF extraction");
      try {
        const buffer = Buffer.from(body.fileData.data, "base64");
        const pdfModule: any = await import("pdf-parse");
        let extractedText = "";

        if (typeof pdfModule.PDFParse === "function") {
          const parser = new pdfModule.PDFParse({ data: buffer });
          const res = await parser.getText();
          extractedText = typeof res === "string" ? res : (res?.text || "");
        } else if (typeof pdfModule.default === "function") {
          const res = await pdfModule.default(buffer);
          extractedText = res?.text || "";
        } else if (typeof pdfModule === "function") {
          const res = await pdfModule(buffer);
          extractedText = res?.text || "";
        } else {
          throw new Error("Unable to locate PDF parser function in module.");
        }

        text = (extractedText || "").trim();
        
        if (!text) {
          throw new Error("Extracted PDF text is empty.");
        }
      } catch (err: any) {
        console.error("[POST /api/analyze] PDF Extraction error:", err?.message || err);
        return NextResponse.json(
          {
            error: "Failed to extract text from PDF: " + (err?.message || String(err)),
          },
          { status: 400 }
        );
      }
    }

    // ---------------------------------------------------------
    // TEXT VALIDATION
    // ---------------------------------------------------------

    if (!text || typeof text !== "string" || !text.trim()) {
      return NextResponse.json(
        { error: "Missing text or fileData in request body." },
        { status: 400 }
      );
    }

    text = text.trim();

    // ---------------------------------------------------------
    // GROQ PROMPT
    // ---------------------------------------------------------

    const prompt = `
You are the AI safety-analysis engine for SafeSignalAI.

Analyze the following safety incident, near miss, unsafe condition, or observation report.

Identify:

- Report summary
- Primary hazard
- Risk level
- Precursor pattern
- SIF classification
- Applicable Life-Saving Rules
- Important extracted entities

IMPORTANT RULES:

1. Return ONLY a valid JSON object.
2. Never invent facts that are not supported by the report.
3. If the report clearly describes an unsafe condition that could lead to an incident, identify it as the precursor pattern.
4. Do NOT return "None", null, or an empty string for precursor_pattern when an unsafe precursor is clearly described.
5. If no meaningful precursor exists, use exactly:
   "Not identified"
6. For life_saving_rules:
   - Identify applicable safety-critical rules.
   - If a recognized Life-Saving Rule is clearly triggered, return it as an array of strings.
   - Do not unnecessarily return an empty array.
7. Use concise professional terminology.
8. Risk level must be exactly:
   Critical
   High
   Medium
   Low
9. sif_label must be exactly:
   SIF-potential
   Non-SIF

The JSON MUST match exactly this structure:
{
  "report_summary": "string",
  "hazard": "string",
  "risk_level": "string",
  "precursor_pattern": "string",
  "sif_label": "string",
  "life_saving_rules": ["string"],
  "extracted_entities": ["string"]
}

Examples:

- Uncontrolled oil/chemical/gas leak with worker exposure:
  identify the uncontrolled release/exposure as the precursor.

- Slip/trip hazard caused by an unresolved spill:
  identify the unresolved spill/exposure condition.

- Working at height without fall protection:
  identify the fall-from-height precursor and applicable rule.

- Electrical exposure:
  identify the uncontrolled electrical-energy exposure and applicable rule.

- Moving machinery or vehicle exposure:
  identify the line-of-fire or uncontrolled-energy exposure where applicable.

- Confined-space exposure:
  identify the confined-space hazard and applicable rule.

- Lifting operation with people exposed below:
  identify the dropped-object/line-of-fire precursor where applicable.

SAFETY REPORT:

${text}
`;

    console.log("[POST /api/analyze] Calling Groq");

    // ---------------------------------------------------------
    // GROQ API
    // ---------------------------------------------------------

    let result;

    try {
      const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        cache: "no-store",
        headers: {
          "Authorization": `Bearer ${apiKey}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          model: "openai/gpt-oss-120b",
          messages: [{ role: "user", content: prompt }],
          response_format: { type: "json_object" }
        })
      });

      if (!response.ok) {
         const errData = await response.json().catch(() => ({}));
         throw new Error(errData.error?.message || `Groq API error ${response.status}`);
      }

      result = await response.json();
      console.log(
        "[POST /api/analyze] Groq request succeeded"
      );
    } catch (err: any) {
      console.error(
        "[POST /api/analyze] Groq API error:",
        err
      );

      return NextResponse.json(
        {
          error:
            "AI API Request failed: " + err.message,
        },
        { status: 500 }
      );
    }

    // ---------------------------------------------------------
    // PARSE GROQ RESPONSE
    // ---------------------------------------------------------

    let prediction: any;

    try {
      const rawText = result.choices[0].message.content;

      console.log(
        "[POST /api/analyze] Raw AI response:",
        rawText
      );

      prediction = JSON.parse(rawText);

      console.log(
        "[POST /api/analyze] Parsed AI prediction:",
        JSON.stringify(prediction, null, 2)
      );
    } catch (err: any) {
      console.error(
        "[POST /api/analyze] JSON parsing error:",
        err
      );

      return NextResponse.json(
        {
          error:
            "Failed to parse AI response: " +
            err.message,
        },
        { status: 500 }
      );
    }

    return await processPrediction(
      prediction,
      text,
      body.fileData ? "PDF Upload" : "Manual/CSV Input"
    );
  } catch (err: any) {
    console.error(
      "[POST /api/analyze] Unexpected error:",
      err
    );

    return NextResponse.json(
      {
        error:
          "Unexpected runtime error: " + err.message,
      },
      { status: 500 }
    );
  }
}

// ============================================================
// PROCESS AND SAVE GEMINI PREDICTION
// ============================================================

async function processPrediction(
  prediction: any,
  originalText: string,
  type: string
) {
  console.log(
    "[POST /api/analyze] processPrediction started"
  );

  // ---------------------------------------------------------
  // REPORT ID
  // ---------------------------------------------------------

  const report_id =
    "REP-" + Math.floor(Math.random() * 10000000);

  // ---------------------------------------------------------
  // NORMALIZE VALUES
  // ---------------------------------------------------------

  const reportSummary =
    typeof prediction?.report_summary === "string" &&
    prediction.report_summary.trim()
      ? prediction.report_summary.trim()
      : "No summary available";

  const hazard =
    typeof prediction?.hazard === "string" &&
    prediction.hazard.trim()
      ? prediction.hazard.trim()
      : "Hazard not identified";

  // ---------------------------------------------------------
  // RISK LEVEL
  // ---------------------------------------------------------

  const validRiskLevels = [
    "Critical",
    "High",
    "Medium",
    "Low",
  ];

  const rawRisk =
    prediction?.risk_level != null
      ? String(prediction.risk_level).trim()
      : "";

  const riskLevel = validRiskLevels.includes(rawRisk)
    ? rawRisk
    : "Medium";

  // ---------------------------------------------------------
  // PRECURSOR PATTERN
  // ---------------------------------------------------------

  let precursorPattern =
    typeof prediction?.precursor_pattern === "string"
      ? prediction.precursor_pattern.trim()
      : "";

  const invalidPrecursorValues = [
    "",
    "none",
    "null",
    "n/a",
    "na",
    "not identified",
    "not identified.",
    "unknown",
  ];

  if (
    invalidPrecursorValues.includes(
      precursorPattern.toLowerCase()
    )
  ) {
    precursorPattern = "Not identified";
  }

  // ---------------------------------------------------------
  // PRECURSOR FALLBACK
  // ---------------------------------------------------------

  const lowerText = originalText.toLowerCase();

  if (precursorPattern === "Not identified") {
    if (
      lowerText.includes("oil leak") ||
      lowerText.includes("oil spill") ||
      lowerText.includes("fluid leak") ||
      lowerText.includes("chemical leak") ||
      lowerText.includes("chemical spill") ||
      lowerText.includes("gas leak")
    ) {
      precursorPattern =
        "Uncontrolled leak or spill creating an unresolved worker exposure";
    } else if (
      lowerText.includes("slippery") ||
      lowerText.includes("slip hazard") ||
      lowerText.includes("slip and fall")
    ) {
      precursorPattern =
        "Uncontrolled slip hazard in an active worker area";
    } else if (
      lowerText.includes("working at height") ||
      lowerText.includes("fall protection") ||
      lowerText.includes("no harness") ||
      lowerText.includes("without harness")
    ) {
      precursorPattern =
        "Unprotected exposure to a fall-from-height hazard";
    } else if (
      lowerText.includes("electrical") ||
      lowerText.includes("live wire") ||
      lowerText.includes("live electrical")
    ) {
      precursorPattern =
        "Uncontrolled exposure to electrical energy";
    } else if (
      lowerText.includes("moving machinery") ||
      lowerText.includes("unguarded") ||
      lowerText.includes("machine guard")
    ) {
      precursorPattern =
        "Exposure to uncontrolled moving machinery energy";
    } else if (
      lowerText.includes("confined space")
    ) {
      precursorPattern =
        "Potential uncontrolled exposure associated with confined-space entry";
    } else if (
      lowerText.includes("forklift") ||
      lowerText.includes("vehicle")
    ) {
      precursorPattern =
        "Potential worker exposure to moving vehicle or mobile equipment";
    }
  }

  // ---------------------------------------------------------
  // SIF LABEL
  // ---------------------------------------------------------

  const validSifLabels = [
    "SIF-potential",
    "Non-SIF",
  ];

  const rawSif =
    prediction?.sif_label != null
      ? String(prediction.sif_label).trim()
      : "";

  const sifLabel = validSifLabels.includes(rawSif)
    ? rawSif
    : "Non-SIF";

  // ---------------------------------------------------------
  // LIFE-SAVING RULES
  // ---------------------------------------------------------

  let lifeSavingRules: string[] = [];

  if (Array.isArray(prediction?.life_saving_rules)) {
    lifeSavingRules = prediction.life_saving_rules
      .map((rule: any) => String(rule).trim())
      .filter(
        (rule: string) =>
          rule &&
          rule.toLowerCase() !== "none" &&
          rule.toLowerCase() !== "null" &&
          rule.toLowerCase() !== "n/a"
      );
  } else if (
    prediction?.life_saving_rules != null &&
    String(prediction.life_saving_rules).trim()
  ) {
    const rule = String(
      prediction.life_saving_rules
    ).trim();

    if (
      rule.toLowerCase() !== "none" &&
      rule.toLowerCase() !== "null" &&
      rule.toLowerCase() !== "n/a"
    ) {
      lifeSavingRules = [rule];
    }
  }

  // ---------------------------------------------------------
  // LIFE-SAVING RULE FALLBACKS
  // ---------------------------------------------------------

  if (lifeSavingRules.length === 0) {
    if (
      lowerText.includes("working at height") ||
      lowerText.includes("fall protection") ||
      lowerText.includes("no harness") ||
      lowerText.includes("without harness")
    ) {
      lifeSavingRules.push(
        "Working at Height"
      );
    }

    if (
      lowerText.includes("electrical") ||
      lowerText.includes("live wire") ||
      lowerText.includes("live electrical")
    ) {
      lifeSavingRules.push(
        "Control of Hazardous Energy"
      );
    }

    if (
      lowerText.includes("confined space")
    ) {
      lifeSavingRules.push(
        "Confined Space"
      );
    }

    if (
      lowerText.includes("forklift") ||
      lowerText.includes("vehicle") ||
      lowerText.includes("mobile equipment")
    ) {
      lifeSavingRules.push(
        "Line of Fire"
      );
    }

    if (
      lowerText.includes("moving machinery") ||
      lowerText.includes("unguarded") ||
      lowerText.includes("machine guard")
    ) {
      lifeSavingRules.push(
        "Control of Hazardous Energy"
      );
    }

    if (
      lowerText.includes("lifting") ||
      lowerText.includes("crane") ||
      lowerText.includes("suspended load") ||
      lowerText.includes("dropped object")
    ) {
      lifeSavingRules.push(
        "Lifting Operations"
      );
    }

    if (
      lowerText.includes("chemical") ||
      lowerText.includes("hazardous material") ||
      lowerText.includes("gas leak")
    ) {
      lifeSavingRules.push(
        "Hazardous Substances"
      );
    }
  }

  // ---------------------------------------------------------
  // REMOVE DUPLICATES
  // ---------------------------------------------------------

  lifeSavingRules = Array.from(
    new Set(lifeSavingRules)
  );

  // ---------------------------------------------------------
  // EXTRACTED ENTITIES
  // ---------------------------------------------------------

  let extractedEntities: string[] = [];

  if (Array.isArray(prediction?.extracted_entities)) {
    extractedEntities =
      prediction.extracted_entities
        .map((entity: any) =>
          String(entity).trim()
        )
        .filter(Boolean);
  } else if (
    prediction?.extracted_entities != null &&
    String(prediction.extracted_entities).trim()
  ) {
    extractedEntities = [
      String(
        prediction.extracted_entities
      ).trim(),
    ];
  }

  // ---------------------------------------------------------
  // LOG FINAL VALUES
  // ---------------------------------------------------------

  console.log(
    "[POST /api/analyze] FINAL NORMALIZED PREDICTION:",
    JSON.stringify(
      {
        report_id,
        reportSummary,
        hazard,
        riskLevel,
        precursorPattern,
        sifLabel,
        lifeSavingRules,
        extractedEntities,
      },
      null,
      2
    )
  );

  // ---------------------------------------------------------
  // INSERT REPORT
  // ---------------------------------------------------------

  const {
    data: reportData,
    error: reportError,
  } = await supabase
    .from("reports")
    .insert({
      report_id,
      original_text: originalText,
      report_type: type,
      site: "Main Site",
      location: "Production Area",
      report_status: "Pending HSE Review",
      review_priority: riskLevel,
    })
    .select("*")
    .single();

  if (reportError) {
    console.error(
      "[POST /api/analyze] reports insert failed:",
      reportError
    );

    return NextResponse.json(
      {
        error:
          "Supabase reports insert failed: " +
          reportError.message,
      },
      { status: 500 }
    );
  }

  // ---------------------------------------------------------
  // INSERT AI PREDICTION
  // ---------------------------------------------------------

  const {
    data: aiData,
    error: aiError,
  } = await supabase
    .from("ai_predictions")
    .insert({
      report_id,

      hazard,

      sif_label: sifLabel,

      life_saving_rules:
        JSON.stringify(lifeSavingRules),

      evidence_phrases:
        JSON.stringify(extractedEntities),

      // Existing live DB columns used as aliases
      explanation:
        reportSummary,

      priority:
        riskLevel,

      potential_consequence:
        precursorPattern,
    })
    .select("*")
    .single();

  if (aiError) {
    console.error(
      "[POST /api/analyze] ai_predictions insert failed:",
      aiError
    );

    return NextResponse.json(
      {
        error:
          "Supabase ai_predictions insert failed: " +
          aiError.message,
      },
      { status: 500 }
    );
  }

  // ---------------------------------------------------------
  // FINAL FRONTEND DATA
  // ---------------------------------------------------------

  const finalAiData = {
    ...aiData,

    report_summary:
      reportSummary,

    risk_level:
      riskLevel,

    precursor_pattern:
      precursorPattern,

    life_saving_rules:
      lifeSavingRules,

    extracted_entities:
      extractedEntities,

    sif_label:
      sifLabel,

    hazard:
      hazard,
  };

  console.log(
    "[POST /api/analyze] SUCCESS:",
    JSON.stringify(
      finalAiData,
      null,
      2
    )
  );

  // ---------------------------------------------------------
  // RETURN
  // ---------------------------------------------------------

  return NextResponse.json({
    ...reportData,

    ...finalAiData,

    ai_predictions:
      finalAiData,
  });
}