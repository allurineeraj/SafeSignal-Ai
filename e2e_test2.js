async function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runTest() {
  try {
    console.log("1. Creating test report via /api/analyze...");
    const req1 = await fetch("http://localhost:3003/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: "Worker was seen doing maintenance on the rooftop without a harness. The edge had no guardrails, creating a severe fall hazard."
      })
    });
    const analyzeData = await req1.json();
    console.log("Analyze result:", analyzeData.report_id, analyzeData.sif_label, analyzeData.risk_level);
    
    if (analyzeData.error) {
       console.error("Failed to analyze", analyzeData.error);
       return;
    }

    const reportId = analyzeData.report_id;
    console.log("Generated Report ID:", reportId);

    console.log("2. Querying /api/queue...");
    const req2 = await fetch("http://localhost:3003/api/queue");
    const queueData = await req2.json();
    const reports = Array.isArray(queueData) ? queueData : queueData.reports || [];
    
    const ourReport = reports.find(r => r.report_id === reportId);
    if (!ourReport) {
       console.error("Report not found in Queue!");
       return;
    }

    console.log("Queue Report Found:", ourReport.report_id);
    console.log("- Status:", ourReport.report_status);

    console.log("3. Review action (Accept)...");
    const req3 = await fetch("http://localhost:3003/api/review", {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       body: JSON.stringify({
         report_id: reportId,
         reviewer_name: "TestUser",
         action: "Accept"
       })
    });
    const reviewData = await req3.json();
    console.log("Review result:", reviewData);

    console.log("4. Querying /api/analytics...");
    const req4 = await fetch("http://localhost:3003/api/analytics");
    const analyticsData = await req4.json();
    console.log("Analytics Total Reports:", analyticsData.total_reports);
    console.log("Analytics Hazards:", analyticsData.hazards);
    console.log("Analytics Risk Levels:", analyticsData.riskLevels);

  } catch (e) {
    console.error("Test Error:", e);
  }
}

runTest();
