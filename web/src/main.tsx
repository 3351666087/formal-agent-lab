import { lazy, StrictMode, Suspense, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { createBrowserRouter, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router";
import { RouterProvider } from "react-router/dom";
import { get, type Meta, type Project } from "./api";
import { ToastProvider } from "./ui";
import "./styles.css";

// one chunk per area: the first screen loads only the shell and the page it shows (P2-095)
const ProjectsPage = lazy(() => import("./pages/Projects").then((m) => ({ default: m.ProjectsPage })));
const ModelWorkbench = lazy(() => import("./pages/ModelWorkbench").then((m) => ({ default: m.ModelWorkbench })));
const ScenariosPage = lazy(() => import("./pages/Scenarios").then((m) => ({ default: m.ScenariosPage })));
const StrategiesPage = lazy(() => import("./pages/Strategies").then((m) => ({ default: m.StrategiesPage })));
const RunsPage = lazy(() => import("./pages/Runs").then((m) => ({ default: m.RunsPage })));
const RunConsole = lazy(() => import("./pages/RunConsole").then((m) => ({ default: m.RunConsole })));
const EvidencePage = lazy(() => import("./pages/Evidence").then((m) => ({ default: m.EvidencePage })));
const BenchmarksPage = lazy(() => import("./pages/Benchmarks").then((m) => ({ default: m.BenchmarksPage })));

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 5_000 } } });

const AREAS = [
  { to: "models", label: "模型工作台", icon: "◇" },
  { to: "scenarios", label: "场景管理", icon: "▤" },
  { to: "strategies", label: "策略注册表", icon: "⚙" },
  { to: "runs", label: "实验运行台", icon: "▶" },
  { to: "evidence", label: "证据与回放", icon: "⟲" },
  { to: "benchmarks", label: "基准对比", icon: "▦" },
];

function Shell() {
  const { pid } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [menu, setMenu] = useState(false);
  useEffect(() => setMenu(false), [location.pathname]);
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => get<Project[]>("/projects") });
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => get<Meta>("/meta"), staleTime: 60_000 });
  const ready = useQuery({ queryKey: ["ready"], queryFn: () => get<{ ready: boolean }>("/health/ready"),
    refetchInterval: 15_000, retry: 0 });
  const current = projects.data?.find((p) => p.id === pid);
  return (
    <div className={`shell ${menu ? "menu-open" : ""}`}>
      <div className="topbar">
        <button className="btn sm" aria-label="打开导航" aria-expanded={menu} onClick={() => setMenu(true)}>☰</button>
        <strong className="ellipsis">{current?.name ?? "formal-agent-lab"}</strong>
      </div>
      {menu && <div className="scrim" onClick={() => setMenu(false)} />}
      <aside className="sidebar" aria-label="导航">
        <div className="brand"><span className="brand-mark">F</span>formal-agent-lab</div>
        <label className="field" style={{ padding: "0 8px" }}>
          <span>项目</span>
          <select value={pid ?? ""} onChange={(e) => navigate(e.target.value ? `/p/${e.target.value}/models` : "/")}>
            <option value="">— 全部项目 —</option>
            {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>
        {pid ? (
          <nav className="nav" aria-label="功能区">
            <div className="nav-label">功能区</div>
            {AREAS.map((a) => (
              <NavLink key={a.to} to={`/p/${pid}/${a.to}`}>
                <span aria-hidden>{a.icon}</span>{a.label}
                {a.to === "runs" && current?.counts ? <span className="num">{current.counts.runs}</span> : null}
              </NavLink>
            ))}
          </nav>
        ) : (
          <nav className="nav"><NavLink to="/" end>项目列表</NavLink></nav>
        )}
        <div className="sidebar-foot">
          <span><span className={`dot ${ready.data?.ready ? "live" : ""}`} aria-hidden />{" "}
            {ready.isError ? "服务未就绪" : ready.data?.ready ? "服务就绪" : "检查中…"}</span>
          {meta.data && <>
            <span title={meta.data.capability_level}>配置：{meta.data.deployment_profile}</span>
            <span className="mono" title={meta.data.contract_digest}>{meta.data.contract_version} · {meta.data.contract_digest.slice(0, 8)}</span>
            <span>LLM：{meta.data.llm.configured ? meta.data.llm.model : "未配置（可用替身）"}</span>
          </>}
        </div>
      </aside>
      <main className="main" id="main">
        <Suspense fallback={<div className="muted pad" role="status" aria-live="polite">加载页面…</div>}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <ProjectsPage /> },
      { path: "p/:pid", element: <Navigate to="models" replace /> },
      { path: "p/:pid/models", element: <ModelWorkbench /> },
      { path: "p/:pid/models/:modelId", element: <ModelWorkbench /> },
      { path: "p/:pid/scenarios", element: <ScenariosPage /> },
      { path: "p/:pid/scenarios/:sid", element: <ScenariosPage /> },
      { path: "p/:pid/strategies", element: <StrategiesPage /> },
      { path: "p/:pid/runs", element: <RunsPage /> },
      { path: "p/:pid/runs/:runId", element: <RunConsole /> },
      { path: "p/:pid/evidence", element: <EvidencePage /> },
      { path: "p/:pid/evidence/:runId", element: <EvidencePage /> },
      { path: "p/:pid/benchmarks", element: <BenchmarksPage /> },
      { path: "p/:pid/benchmarks/:mid", element: <BenchmarksPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
);
