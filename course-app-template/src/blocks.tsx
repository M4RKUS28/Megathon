import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Bar, Line, Pie } from "react-chartjs-2";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import type { Block } from "./types";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Tooltip,
  Legend,
);

type Resolve = (link?: string) => string | undefined;

function MediaImage({ src, alt }: { src?: string; alt?: string }) {
  if (!src) return null;
  return (
    <motion.img
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      src={src}
      alt={alt ?? ""}
      className="w-full rounded-xl border border-black/5 shadow-sm"
    />
  );
}

function Dialogue({ data }: { data?: Record<string, unknown> }) {
  const turns = (data?.turns as { speaker: string; text: string }[]) ?? [];
  return (
    <div className="space-y-3">
      {turns.map((t, i) => {
        const mine = /you|du|ich/i.test(t.speaker);
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: mine ? 20 : -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.08 }}
            className={`flex ${mine ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm ${
                mine ? "bg-[var(--brand)] text-white" : "bg-white border border-black/5"
              }`}
            >
              <div className="mb-0.5 text-[11px] font-semibold opacity-70">{t.speaker}</div>
              {t.text}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

function Flashcards({ data }: { data?: Record<string, unknown> }) {
  const cards = (data?.cards as { front: string; back: string }[]) ?? [];
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {cards.map((c, i) => (
        <button
          key={i}
          onClick={() => setFlipped((f) => ({ ...f, [i]: !f[i] }))}
          className="min-h-[96px] rounded-xl border border-black/5 bg-white p-4 text-left shadow-sm transition hover:shadow-md"
        >
          <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--brand)]">
            {flipped[i] ? "Answer" : "Card"}
          </div>
          <div className="mt-1 text-sm">{flipped[i] ? c.back : c.front}</div>
        </button>
      ))}
    </div>
  );
}

function DragDrop({ data }: { data?: Record<string, unknown> }) {
  const pairs = (data?.pairs as { left: string; right: string }[]) ?? [];
  const rights = useMemo(() => pairs.map((p) => p.right).sort(), [pairs]);
  const [picks, setPicks] = useState<Record<number, string>>({});
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.prompt ? <p className="mb-3 text-sm font-medium">{String(data.prompt)}</p> : null}
      <div className="space-y-2">
        {pairs.map((p, i) => {
          const correct = picks[i] === p.right;
          return (
            <div key={i} className="flex items-center gap-3">
              <span className="w-28 shrink-0 text-sm font-medium">{p.left}</span>
              <select
                value={picks[i] ?? ""}
                onChange={(e) => setPicks((s) => ({ ...s, [i]: e.target.value }))}
                className={`flex-1 rounded-lg border px-2 py-1.5 text-sm ${
                  picks[i] ? (correct ? "border-emerald-500" : "border-red-400") : "border-black/10"
                }`}
              >
                <option value="">Select…</option>
                {rights.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {picks[i] ? <span>{correct ? "✓" : "✗"}</span> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Hotspot({ data, resolve }: { data?: Record<string, unknown>; resolve: Resolve }) {
  const spots = (data?.spots as { x: number; y: number; label: string }[]) ?? [];
  const [active, setActive] = useState<number | null>(null);
  const img = resolve(data?.asset as string | undefined);
  return (
    <div className="relative overflow-hidden rounded-xl border border-black/5 bg-white">
      {img ? <img src={img} alt="" className="w-full" /> : <div className="h-48 bg-gray-100" />}
      {spots.map((s, i) => (
        <button
          key={i}
          onClick={() => setActive(active === i ? null : i)}
          style={{ left: `${s.x}%`, top: `${s.y}%` }}
          className="absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--brand)] text-xs font-bold text-white shadow"
        >
          {i + 1}
        </button>
      ))}
      {active !== null && spots[active] ? (
        <div className="border-t border-black/5 bg-gray-50 p-3 text-sm">{spots[active].label}</div>
      ) : null}
    </div>
  );
}

function Timeline({ data }: { data?: Record<string, unknown> }) {
  const items = (data?.events as { date: string; text: string }[]) ?? [];
  return (
    <ol className="relative space-y-4 border-l-2 border-[var(--brand)]/30 pl-5">
      {items.map((it, i) => (
        <motion.li
          key={i}
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          className="relative"
        >
          <span className="absolute -left-[27px] top-1 h-3 w-3 rounded-full bg-[var(--brand)]" />
          <div className="text-xs font-semibold text-[var(--brand)]">{it.date}</div>
          <div className="text-sm">{it.text}</div>
        </motion.li>
      ))}
    </ol>
  );
}

function Accordion({ data }: { data?: Record<string, unknown> }) {
  const items = (data?.items as { title: string; body: string }[]) ?? [];
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-black/5 overflow-hidden rounded-xl border border-black/5 bg-white">
      {items.map((it, i) => (
        <div key={i}>
          <button
            onClick={() => setOpen(open === i ? null : i)}
            className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-medium"
          >
            {it.title}
            <span>{open === i ? "−" : "+"}</span>
          </button>
          {open === i ? <div className="px-4 pb-4 text-sm text-gray-600">{it.body}</div> : null}
        </div>
      ))}
    </div>
  );
}

function Scenario({ data }: { data?: Record<string, unknown> }) {
  const branches = (data?.branches as { choice: string; outcome: string }[]) ?? [];
  const [picked, setPicked] = useState<number | null>(null);
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.prompt ? <p className="mb-3 text-sm font-medium">{String(data.prompt)}</p> : null}
      <div className="flex flex-wrap gap-2">
        {branches.map((b, i) => (
          <button
            key={i}
            onClick={() => setPicked(i)}
            className={`rounded-lg border px-3 py-1.5 text-sm ${
              picked === i ? "border-[var(--brand)] bg-[var(--brand)]/10" : "border-black/10"
            }`}
          >
            {b.choice}
          </button>
        ))}
      </div>
      {picked !== null && branches[picked] ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mt-3 rounded-lg bg-gray-50 p-3 text-sm"
        >
          {branches[picked].outcome}
        </motion.div>
      ) : null}
    </div>
  );
}

function ChartBlock({ data }: { data?: Record<string, unknown> }) {
  const chartType = (data?.chartType as string) ?? "bar";
  const labels = (data?.labels as string[]) ?? [];
  const datasets = ((data?.datasets as { label: string; data: number[] }[]) ?? []).map((d, i) => ({
    ...d,
    backgroundColor: ["#5145E5", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"][i % 5],
    borderColor: "#5145E5",
  }));
  const chartData = { labels, datasets };
  const opts = { responsive: true, plugins: { legend: { position: "bottom" as const } } };
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.title ? <h4 className="mb-2 text-sm font-semibold">{String(data.title)}</h4> : null}
      {chartType === "line" ? (
        <Line data={chartData} options={opts} />
      ) : chartType === "pie" ? (
        <Pie data={chartData} options={opts} />
      ) : (
        <Bar data={chartData} options={opts} />
      )}
    </div>
  );
}

export function BlockView({ block, resolve }: { block: Block; resolve: Resolve }) {
  switch (block.type) {
    case "heading":
      return <h3 className="mt-2 text-xl font-bold">{block.text}</h3>;
    case "paragraph":
      return <p className="text-[15px] leading-relaxed text-gray-700">{block.text}</p>;
    case "list":
      return (
        <ul className="list-disc space-y-1 pl-5 text-[15px] text-gray-700">
          {(block.items ?? []).map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      );
    case "callout":
      return (
        <div className="rounded-xl border-l-4 border-[var(--brand)] bg-[var(--brand)]/5 p-4 text-sm">
          {block.text}
        </div>
      );
    case "image":
      return <MediaImage src={resolve(block.asset)} alt={block.text} />;
    case "video": {
      const src = resolve(block.asset);
      return src ? (
        <video controls className="w-full rounded-xl border border-black/5">
          <source src={src} />
        </video>
      ) : null;
    }
    case "audio": {
      const src = resolve(block.asset);
      return src ? <audio controls className="w-full" src={src} /> : null;
    }
    case "dialogue":
      return <Dialogue data={block.data} />;
    case "flashcards":
      return <Flashcards data={block.data} />;
    case "dragdrop":
      return <DragDrop data={block.data} />;
    case "hotspot":
      return <Hotspot data={block.data} resolve={resolve} />;
    case "timeline":
      return <Timeline data={block.data} />;
    case "accordion":
      return <Accordion data={block.data} />;
    case "scenario":
      return <Scenario data={block.data} />;
    case "chart":
      return <ChartBlock data={block.data} />;
    default: {
      // Unknown / custom block type. The design is intentionally free, so rather
      // than dropping the block, surface whatever content it carries (text, list
      // items and any referenced image). This is the fallback renderer used when
      // the implementation agent isn't building a bespoke app.
      const img = resolve(block.asset);
      if (!block.text && !(block.items && block.items.length) && !img) return null;
      return (
        <div className="space-y-2">
          {block.text ? (
            <p className="text-[15px] leading-relaxed text-gray-700">{block.text}</p>
          ) : null}
          {block.items && block.items.length ? (
            <ul className="list-disc space-y-1 pl-5 text-[15px] text-gray-700">
              {block.items.map((it, i) => (
                <li key={i}>{it}</li>
              ))}
            </ul>
          ) : null}
          {img ? <MediaImage src={img} alt={block.text} /> : null}
        </div>
      );
    }
  }
}
