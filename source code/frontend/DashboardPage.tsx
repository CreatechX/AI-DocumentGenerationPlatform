import { motion } from "framer-motion";
import { FileText, History, MessageSquare, Settings, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/context/AuthContext";
import { api, type DocumentRecord } from "@/lib/api";
import { getUploadActivities } from "@/lib/storage";
import { displayNameFromEmail, formatRelativeDate } from "@/lib/utils";

const quickLinks = [
  { to: "/upload", icon: Upload, label: "Upload Documents", color: "from-violet-500/20 to-purple-500/10" },
  { to: "/chat", icon: MessageSquare, label: "AI Chat", color: "from-cyan-500/20 to-blue-500/10" },
  { to: "/generate", icon: FileText, label: "Generate Documents", color: "from-emerald-500/20 to-teal-500/10" },
  { to: "/history", icon: History, label: "History", color: "from-amber-500/20 to-orange-500/10" },
  { to: "/settings", icon: Settings, label: "Settings", color: "from-slate-500/20 to-zinc-500/10" },
];

export function DashboardPage() {
  const { email } = useAuth();
  const name = displayNameFromEmail(email);
  const [generated, setGenerated] = useState<DocumentRecord[]>([]);
  const uploads = getUploadActivities().slice(0, 3);

  useEffect(() => {
    api.history().then(setGenerated).catch(() => setGenerated([]));
  }, []);

  return (
    <div className="space-y-8">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-3xl font-bold">
          Hello {name} <span className="inline-block animate-[wave_2s_ease-in-out_infinite]">👋</span>
        </h1>
        <p className="mt-1 text-muted">Welcome back.</p>
      </motion.div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {quickLinks.map(({ to, icon: Icon, label, color }, i) => (
          <motion.div
            key={to}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <Link to={to}>
              <Card className={`group h-full bg-gradient-to-br ${color} transition hover:border-primary/40 hover:glow-primary`}>
                <CardContent className="flex items-center gap-4 p-6">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/10 group-hover:scale-110 transition">
                    <Icon className="h-6 w-6 text-primary-glow" />
                  </div>
                  <span className="font-medium">{label}</span>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>Your uploads and generated documents</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {uploads.length === 0 && generated.length === 0 ? (
            <p className="text-sm text-muted">No activity yet. Upload a document or start a chat!</p>
          ) : null}
          {uploads.map((u) => (
            <div key={u.id} className="flex items-center justify-between rounded-xl border border-border/40 bg-white/5 px-4 py-3 text-sm">
              <div>
                <p className="font-medium">Uploaded: {u.filename}</p>
                <p className="text-muted">{formatRelativeDate(u.created_at)} · {u.chunks_indexed} chunks</p>
              </div>
            </div>
          ))}
          {generated.slice(0, 3).map((g) => (
            <div key={g.id} className="flex items-center justify-between rounded-xl border border-border/40 bg-white/5 px-4 py-3 text-sm">
              <div>
                <p className="font-medium">Generated: {g.title}.{g.output_type}</p>
                <p className="text-muted">{formatRelativeDate(g.created_at)}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
