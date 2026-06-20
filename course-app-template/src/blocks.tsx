import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
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
import type { Block, ConversationTurn, Persona } from "./types";

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

// ── Conversation (avatars left/right, click-through bubbles, per-bubble TTS) ──

// Local "cartoon avatar library": a parametric flat-illustration person, drawn
// deterministically from a seed string so each persona keeps the same face. A
// persona `avatar` like "f-2"/"m-5" is the seed; a "/..." or "http..." value is
// treated as a real image instead.
const SKIN = ["#F8D2B0", "#F0C09A", "#E0A878", "#C68A5E", "#9C6B43", "#6F4A2E"];
const HAIR = ["#2B1B12", "#5A3825", "#8A5A2B", "#C99B4B", "#9AA0A6", "#1F2937", "#D14B3D", "#E6E0D4"];
const SHIRT = ["#5145E5", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4", "#8b5cf6", "#ec4899", "#0ea5e9"];

function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return Math.abs(h);
}

function isAssetRef(v?: string): boolean {
  return !!v && (v.startsWith("/") || v.startsWith("http"));
}

function HairStyle({ kind, hair }: { kind: number; hair: string }) {
  // A crown/cap that covers the forehead, plus per-style extras.
  const cap = "M27,42 Q27,16 50,16 Q73,16 73,42 Q73,28 50,28 Q27,28 27,42 Z";
  switch (kind) {
    case 1: // long: side panels down to the shoulders
      return (
        <>
          <rect x="26" y="34" width="9" height="34" rx="4" fill={hair} />
          <rect x="65" y="34" width="9" height="34" rx="4" fill={hair} />
          <path d={cap} fill={hair} />
        </>
      );
    case 2: // bun on top
      return (
        <>
          <circle cx="50" cy="14" r="7" fill={hair} />
          <path d={cap} fill={hair} />
        </>
      );
    case 3: // short / buzz: thinner cap
      return <path d="M29,40 Q29,22 50,22 Q71,22 71,40 Q71,31 50,31 Q29,31 29,40 Z" fill={hair} />;
    default: // tidy short
      return <path d={cap} fill={hair} />;
  }
}

function Avatar({ seed, size = 56 }: { seed: string; size?: number }) {
  const clip = useId();
  const h = hashSeed(seed || "x");
  const skin = SKIN[h % SKIN.length];
  const hair = HAIR[(h >> 3) % HAIR.length];
  const shirt = SHIRT[(h >> 6) % SHIRT.length];
  const style = (h >> 9) % 4;
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label="avatar">
      <defs>
        <clipPath id={clip}>
          <circle cx="50" cy="50" r="50" />
        </clipPath>
      </defs>
      <g clipPath={`url(#${clip})`}>
        <rect width="100" height="100" fill="#eef2f7" />
        <path d="M12,100 Q14,68 50,68 Q86,68 88,100 Z" fill={shirt} />
        <rect x="44" y="56" width="12" height="14" rx="5" fill={skin} />
        <circle cx="50" cy="40" r="22" fill={skin} />
        <HairStyle kind={style} hair={hair} />
        <circle cx="42.5" cy="41" r="2.1" fill="#1f2937" />
        <circle cx="57.5" cy="41" r="2.1" fill="#1f2937" />
        <path
          d="M43,48 Q50,53 57,48"
          stroke="#1f2937"
          strokeWidth="1.7"
          fill="none"
          strokeLinecap="round"
        />
      </g>
    </svg>
  );
}

function PersonaAvatar({
  persona,
  size,
  resolve,
}: {
  persona?: Persona;
  size: number;
  resolve: Resolve;
}) {
  const av = persona?.avatar;
  if (isAssetRef(av)) {
    const src = resolve(av);
    if (src)
      return (
        <img
          src={src}
          alt={persona?.name ?? ""}
          style={{ width: size, height: size }}
          className="rounded-full object-cover"
        />
      );
  }
  return <Avatar seed={av || persona?.id || persona?.name || "x"} size={size} />;
}

function PersonaStage({
  persona,
  active,
  resolve,
}: {
  persona?: Persona;
  active: boolean;
  resolve: Resolve;
}) {
  return (
    <div
      className={`flex flex-col items-center text-center transition-all duration-300 ${
        active ? "opacity-100" : "opacity-40 grayscale"
      }`}
    >
      <motion.div
        animate={{ scale: active ? 1.06 : 0.94 }}
        className={`rounded-full ${active ? "ring-4 ring-[var(--brand)]/30" : ""}`}
      >
        <PersonaAvatar persona={persona} size={64} resolve={resolve} />
      </motion.div>
      <div className="mt-1.5 text-xs font-semibold">{persona?.name}</div>
      {persona?.role ? <div className="text-[10px] text-gray-400">{persona.role}</div> : null}
    </div>
  );
}

function normalizeConversation(data?: Record<string, unknown>): {
  personas: Persona[];
  turns: ConversationTurn[];
} {
  const turns = (data?.turns as ConversationTurn[]) ?? [];
  let personas = (data?.personas as Persona[]) ?? [];
  if (!personas.length) {
    // Legacy `dialogue` shape: derive personas from distinct speakers.
    const names = Array.from(
      new Set(turns.map((t) => t.speaker || t.persona || "Speaker")),
    );
    personas = names.map((n, i): Persona => ({
      id: n,
      name: n,
      side: i % 2 === 0 ? "left" : "right",
    }));
  }
  return { personas, turns };
}

function personaOf(turn: ConversationTurn, personas: Persona[]): Persona {
  const key = turn.persona ?? turn.speaker;
  return (
    personas.find((p) => p.id === key || p.name === key) ??
    personas[0] ?? { name: turn.speaker, side: "left" }
  );
}

function Conversation({ data, resolve }: { data?: Record<string, unknown>; resolve: Resolve }) {
  const { personas, turns } = useMemo(() => normalizeConversation(data), [data]);
  const [shown, setShown] = useState(1);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const left = personas.find((p) => p.side !== "right") ?? personas[0];
  const right = personas.find((p) => p.side === "right") ?? personas[1] ?? personas[0];

  const play = useCallback(
    (link?: string) => {
      const src = resolve(link);
      const el = audioRef.current;
      if (!src || !el) return;
      el.src = src;
      el.currentTime = 0;
      void el.play().catch(() => {});
    },
    [resolve],
  );

  // Auto-play the most recently revealed bubble.
  useEffect(() => {
    if (!turns.length) return;
    play(turns[shown - 1]?.audio);
  }, [shown, turns, play]);

  if (!turns.length) return null;

  const active = personaOf(turns[shown - 1] ?? {}, personas);
  const done = shown >= turns.length;
  const advance = () => setShown((s) => Math.min(s + 1, turns.length));

  return (
    <div className="rounded-2xl border border-black/5 bg-gradient-to-b from-gray-50 to-white p-4">
      <audio ref={audioRef} className="hidden" />
      <div className="mb-4 flex items-end justify-between gap-2">
        <PersonaStage persona={left} active={left === active} resolve={resolve} />
        <span className="pb-7 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
          Conversation
        </span>
        <PersonaStage persona={right} active={right === active} resolve={resolve} />
      </div>

      <div className="space-y-2.5">
        {turns.slice(0, shown).map((t, i) => {
          const p = personaOf(t, personas);
          const mine = p?.side === "right";
          const isLast = i === shown - 1;
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex items-end gap-2 ${mine ? "flex-row-reverse" : ""}`}
            >
              <PersonaAvatar persona={p} size={30} resolve={resolve} />
              <div
                className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-sm ${
                  mine ? "bg-[var(--brand)] text-white" : "border border-black/5 bg-white"
                } ${isLast ? "ring-2 ring-[var(--brand)]/30" : ""}`}
              >
                <div
                  className={`mb-0.5 flex items-center gap-1.5 text-[11px] font-semibold ${
                    mine ? "text-white/85" : "opacity-70"
                  }`}
                >
                  {p?.name}
                  {p?.role ? <span className="font-normal opacity-70">· {p.role}</span> : null}
                </div>
                <div>{t.text}</div>
                {t.audio ? (
                  <button
                    type="button"
                    onClick={() => play(t.audio)}
                    className={`mt-1 inline-flex items-center gap-1 text-[11px] ${
                      mine ? "text-white/85" : "text-[var(--brand)]"
                    }`}
                  >
                    <span aria-hidden="true">🔊</span> Replay
                  </button>
                ) : null}
              </div>
            </motion.div>
          );
        })}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-xs text-gray-400">
          {Math.min(shown, turns.length)} / {turns.length}
        </span>
        {done ? (
          <button
            type="button"
            onClick={() => setShown(1)}
            className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
          >
            ↻ Replay conversation
          </button>
        ) : (
          <button
            type="button"
            onClick={advance}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white"
          >
            Next ▶
          </button>
        )}
      </div>
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
      if (!src) return null;
      return (
        <div className="flex flex-col gap-2 rounded-xl border border-black/5 bg-white p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--brand)]">
            <span aria-hidden="true">🔊</span>
            Listen to this page
          </div>
          <audio controls className="w-full" src={src} />
        </div>
      );
    }
    case "conversation":
    case "dialogue":
      return <Conversation data={block.data} resolve={resolve} />;
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
