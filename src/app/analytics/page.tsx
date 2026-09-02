"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Activity, ShieldAlert, CheckCircle2, AlertTriangle, ArrowLeft } from "lucide-react";

export default function AnalyticsDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`/api/analytics?t=${Date.now()}`, {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            Pragma: "no-cache",
          },
        });
        const data = await res.json();
        setStats(data);
      } catch (e) {
        console.error("Failed to load analytics", e);
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) return <div className="p-12 text-center text-slate-400">Loading HSE analytics...</div>;
  if (!stats) return <div className="p-12 text-center text-red-400">Failed to load analytics dashboard.</div>;

  const renderBarChart = (title: string, dataObj: Record<string, number>, colorClass: string) => {
    const entries = Object.entries(dataObj || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const max = Math.max(...entries.map(e => e[1]), 1);
    
    return (
      <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-6 shadow-xl">
        <h3 className="text-lg font-bold text-slate-200 mb-6">{title}</h3>
        {entries.length === 0 ? (
          <p className="text-sm text-slate-500 italic">No data available yet.</p>
        ) : (
          <div className="space-y-4">
            {entries.map(([label, count]) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-300">{label}</span>
                  <span className="font-bold text-slate-200">{count}</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2">
                  <div className={`${colorClass} h-2 rounded-full`} style={{ width: `${(count / max) * 100}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-8 animate-in fade-in pb-12">
      <div className="flex items-center gap-4 border-b border-slate-700 pb-4 mt-8">
        <button onClick={() => router.push('/hse')} className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-slate-300">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-3xl font-bold">HSE Analytics Dashboard</h1>
          <p className="text-sm text-slate-400">Real-time Safety Intelligence & Precursor Tracking</p>
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Reports" value={stats.total_reports} icon={<Activity className="w-6 h-6 text-blue-400" />} />
        <StatCard title="Critical/High Priority" value={stats.critical_count} icon={<AlertTriangle className="w-6 h-6 text-orange-400" />} />
        <StatCard title="Closed Reports" value={stats.closed_count} icon={<CheckCircle2 className="w-6 h-6 text-emerald-400" />} />
        <StatCard title="SIF Potential" value={stats.sif_count} subtitle={`${stats.sif_percentage}% of total`} icon={<ShieldAlert className="w-6 h-6 text-red-400" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 pt-4">
        {renderBarChart("Risk Distribution", stats.riskLevels, "bg-red-500")}
        {renderBarChart("Report Types", stats.reportTypes, "bg-blue-500")}
        {renderBarChart("Life-Saving Rules Triggered", stats.lifeSavingRules, "bg-emerald-500")}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {renderBarChart("Top Hazards Identified", stats.hazards, "bg-orange-500")}
        
        {/* AI Insights Section */}
        <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-6 shadow-xl relative overflow-hidden">
          <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500"></div>
          <h3 className="text-lg font-bold text-indigo-400 mb-6 flex items-center gap-2">
            AI Safety Insights
          </h3>
          
          {stats.topPrecursor && stats.topPrecursor !== "None" ? (
            <div className="space-y-4">
              <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
                <p className="text-sm text-slate-300">
                  <strong className="text-indigo-300 block mb-1">Key Observation</strong>
                  The system has identified a recurring precursor pattern: <span className="font-semibold text-white">{stats.topPrecursor}</span>. 
                  This pattern has appeared in {stats.topPrecursorCount} recent report(s).
                </p>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg">
                <p className="text-sm text-slate-300">
                  <strong className="text-amber-400 block mb-1">Recommended HSE Action</strong>
                  Investigate the root cause of this recurring pattern to prevent a potential incident. Review the locations where this precursor is most frequently observed and implement targeted controls.
                </p>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center text-slate-400 border border-dashed border-slate-700 rounded-lg">
              Submit more reports to generate AI precursor insights.
            </div>
          )}
        </div>
      </div>

      {/* CLOSED REPORTS & PROJECTS SECTION */}
      <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-slate-200 flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400" /> Closed Reports & Projects ({stats.closed_count || 0})
          </h3>
          <span className="text-xs text-slate-400">
            Reports resolved and closed by the HSE team
          </span>
        </div>

        {(!stats.closed_reports || stats.closed_reports.length === 0) ? (
          <div className="p-8 text-center text-slate-500 border border-dashed border-slate-800 rounded-lg">
            No closed reports yet. Reports closed in the HSE Review Queue will appear here.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="text-xs uppercase bg-slate-800/60 text-slate-400 border-b border-slate-700">
                <tr>
                  <th className="px-4 py-3">Report ID</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Summary / Description</th>
                  <th className="px-4 py-3">Priority</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Closed / Reviewed Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {stats.closed_reports.map((cr: any) => (
                  <tr key={cr.id || cr.report_id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 font-semibold text-white">{cr.report_id}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-300 border border-slate-700">
                        {cr.report_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-200 max-w-md truncate">
                      {cr.report_summary}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                          cr.review_priority === "Critical"
                            ? "bg-red-500/20 text-red-400 border-red-500/50"
                            : cr.review_priority === "High"
                            ? "bg-orange-500/20 text-orange-400 border-orange-500/50"
                            : cr.review_priority === "Medium"
                            ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/50"
                            : "bg-blue-500/20 text-blue-400 border-blue-500/50"
                        }`}
                      >
                        {cr.review_priority}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {cr.report_status || "Closed"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-400">
                      {cr.reviewed_at ? new Date(cr.reviewed_at).toLocaleDateString() : (cr.created_at ? new Date(cr.created_at).toLocaleDateString() : "—")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ title, value, subtitle, icon }: any) {
  return (
    <div className="bg-slate-900/80 border border-slate-700 rounded-xl p-6 flex flex-col justify-between shadow-xl">
      <div className="flex justify-between items-start mb-4">
        <p className="text-sm font-medium text-slate-400">{title}</p>
        <div className="p-2 bg-slate-800 rounded-lg border border-slate-700">{icon}</div>
      </div>
      <div>
        <h4 className="text-3xl font-bold text-white">{value}</h4>
        {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
      </div>
    </div>
  );
}
