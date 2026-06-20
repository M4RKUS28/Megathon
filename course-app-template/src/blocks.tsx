import { type ReactNode, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
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
import type {
  Block,
  ConversationTurn,
  MinigameData,
  MinigamePair,
  MinigameQuestion,
  MinigameSortItem,
  Persona,
} from "./types";

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

// â”€â”€ Conversation (avatars left/right, click-through bubbles, per-bubble TTS) â”€â”€

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
                  {p?.role ? <span className="font-normal opacity-70">Â· {p.role}</span> : null}
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
                    <span aria-hidden="true">ðŸ”Š</span> Replay
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
            â†» Replay conversation
          </button>
        ) : (
          <button
            type="button"
            onClick={advance}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white"
          >
            Next â–¶
          </button>
        )}
      </div>
    </div>
  );
}

function shuffle<T>(items: T[]): T[] {
  return [...items]
    .map((value) => ({ value, order: Math.random() }))
    .sort((a, b) => a.order - b.order)
    .map(({ value }) => value);
}

function GameShell({
  title,
  prompt,
  score,
  total,
  onReset,
  children,
}: {
  title: string;
  prompt?: string;
  score: number;
  total: number;
  onReset: () => void;
  children: ReactNode;
}) {
  const pct = total ? Math.round((score / total) * 100) : 0;
  return (
    <div className="overflow-hidden rounded-2xl border border-black/5 bg-white shadow-sm">
      <div className="border-b border-black/5 bg-[var(--brand)]/5 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">
              Minigame
            </div>
            <h4 className="mt-0.5 text-base font-bold text-gray-900">{title}</h4>
            {prompt ? <p className="mt-1 text-sm text-gray-600">{prompt}</p> : null}
          </div>
          <div className="rounded-xl border border-black/5 bg-white px-3 py-2 text-right shadow-sm">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
              Score
            </div>
            <div className="text-lg font-bold text-[var(--brand)]">
              {score}/{total}
            </div>
          </div>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-black/10">
          <motion.div
            animate={{ width: `${pct}%` }}
            className="h-full rounded-full bg-[var(--brand)]"
          />
        </div>
      </div>
      <div className="p-4">{children}</div>
      <div className="flex justify-end border-t border-black/5 bg-gray-50 px-4 py-3">
        <button
          type="button"
          onClick={onReset}
          className="rounded-lg border border-black/10 bg-white px-3 py-1.5 text-xs font-medium"
        >
          Replay
        </button>
      </div>
    </div>
  );
}

function QuizMinigame({ data }: { data: MinigameData }) {
  const questions = data.questions ?? [];
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const score = questions.reduce(
    (sum, q, i) => sum + (answers[i] === q.answerIndex ? 1 : 0),
    0,
  );

  return (
    <GameShell
      title={data.title ?? "Quick challenge"}
      prompt={data.prompt}
      score={score}
      total={questions.length}
      onReset={() => setAnswers({})}
    >
      <div className="space-y-4">
        {questions.map((q: MinigameQuestion, qi) => {
          const picked = answers[qi];
          const answered = picked !== undefined;
          return (
            <div key={qi} className="rounded-xl border border-black/5 bg-gray-50 p-3">
              <div className="text-sm font-semibold text-gray-900">{q.question}</div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {q.options.map((option, oi) => {
                  const correct = oi === q.answerIndex;
                  const active = picked === oi;
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setAnswers((s) => ({ ...s, [qi]: oi }))}
                      className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                        answered && correct
                          ? "border-emerald-500 bg-emerald-50"
                          : active
                            ? "border-red-400 bg-red-50"
                            : "border-black/10 bg-white hover:border-[var(--brand)]"
                      }`}
                    >
                      <span className="mr-2 font-bold">
                        {answered && correct ? "OK" : answered && active ? "X" : ""}
                      </span>
                      {option}
                    </button>
                  );
                })}
              </div>
              {answered && q.explanation ? (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 rounded-lg bg-white p-2 text-xs text-gray-600"
                >
                  {q.explanation}
                </motion.div>
              ) : null}
            </div>
          );
        })}
      </div>
    </GameShell>
  );
}

function OrderMinigame({ data }: { data: MinigameData }) {
  const steps = data.steps ?? [];
  const [order, setOrder] = useState<string[]>(() => shuffle(steps));
  const score = order.reduce((sum, step, i) => sum + (step === steps[i] ? 1 : 0), 0);

  const move = (from: number, to: number) => {
    if (to < 0 || to >= order.length) return;
    setOrder((current) => {
      const next = [...current];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  };

  return (
    <GameShell
      title={data.title ?? "Put it in order"}
      prompt={data.prompt}
      score={score}
      total={steps.length}
      onReset={() => setOrder(shuffle(steps))}
    >
      <div className="space-y-2">
        {order.map((step, i) => {
          const correct = step === steps[i];
          return (
            <motion.div
              layout
              key={step}
              className={`flex items-center gap-2 rounded-xl border p-2 ${
                correct ? "border-emerald-500 bg-emerald-50" : "border-black/10 bg-gray-50"
              }`}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-sm font-bold">
                {i + 1}
              </div>
              <div className="flex-1 text-sm">{step}</div>
              <button
                type="button"
                onClick={() => move(i, i - 1)}
                className="rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
              >
                Up
              </button>
              <button
                type="button"
                onClick={() => move(i, i + 1)}
                className="rounded-lg border border-black/10 bg-white px-2 py-1 text-xs"
              >
                Down
              </button>
            </motion.div>
          );
        })}
      </div>
    </GameShell>
  );
}

function SortMinigame({ data }: { data: MinigameData }) {
  const items = data.items ?? [];
  const categories =
    data.categories && data.categories.length
      ? data.categories
      : Array.from(new Set(items.map((item) => item.category)));
  const [picks, setPicks] = useState<Record<number, string>>({});
  const score = items.reduce((sum, item, i) => sum + (picks[i] === item.category ? 1 : 0), 0);

  return (
    <GameShell
      title={data.title ?? "Sort the cards"}
      prompt={data.prompt}
      score={score}
      total={items.length}
      onReset={() => setPicks({})}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        {items.map((item: MinigameSortItem, i) => {
          const picked = picks[i];
          const correct = picked === item.category;
          return (
            <div
              key={`${item.text}-${i}`}
              className={`rounded-xl border p-3 ${
                picked
                  ? correct
                    ? "border-emerald-500 bg-emerald-50"
                    : "border-red-400 bg-red-50"
                  : "border-black/10 bg-gray-50"
              }`}
            >
              <div className="text-sm font-medium">{item.text}</div>
              <select
                value={picked ?? ""}
                onChange={(e) => setPicks((s) => ({ ...s, [i]: e.target.value }))}
                className="mt-2 w-full rounded-lg border border-black/10 bg-white px-2 py-1.5 text-sm"
              >
                <option value="">Choose category</option>
                {categories.map((category) => (
                  <option key={category} value={category}>
                    {category}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>
    </GameShell>
  );
}

type MemoryCard = {
  id: string;
  pair: number;
  text: string;
};

function MemoryMinigame({ data }: { data: MinigameData }) {
  const pairs = data.pairs ?? [];
  const [cards, setCards] = useState<MemoryCard[]>(() =>
    shuffle(
      pairs.flatMap((pair: MinigamePair, i) => [
        { id: `${i}-a`, pair: i, text: pair.a },
        { id: `${i}-b`, pair: i, text: pair.b },
      ]),
    ),
  );
  const [open, setOpen] = useState<string[]>([]);
  const [matched, setMatched] = useState<Record<number, boolean>>({});
  const score = Object.values(matched).filter(Boolean).length;

  const reset = () => {
    setCards(
      shuffle(
        pairs.flatMap((pair: MinigamePair, i) => [
          { id: `${i}-a`, pair: i, text: pair.a },
          { id: `${i}-b`, pair: i, text: pair.b },
        ]),
      ),
    );
    setOpen([]);
    setMatched({});
  };

  const flip = (card: MemoryCard) => {
    if (matched[card.pair] || open.includes(card.id) || open.length >= 2) return;
    const nextOpen = [...open, card.id];
    setOpen(nextOpen);
    if (nextOpen.length === 2) {
      const first = cards.find((c) => c.id === nextOpen[0]);
      if (first?.pair === card.pair) {
        setMatched((s) => ({ ...s, [card.pair]: true }));
        setOpen([]);
      } else {
        window.setTimeout(() => setOpen([]), 800);
      }
    }
  };

  return (
    <GameShell
      title={data.title ?? "Memory match"}
      prompt={data.prompt}
      score={score}
      total={pairs.length}
      onReset={reset}
    >
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {cards.map((card) => {
          const visible = matched[card.pair] || open.includes(card.id);
          return (
            <button
              key={card.id}
              type="button"
              onClick={() => flip(card)}
              className={`min-h-[82px] rounded-xl border p-3 text-sm font-medium transition ${
                matched[card.pair]
                  ? "border-emerald-500 bg-emerald-50"
                  : visible
                    ? "border-[var(--brand)] bg-[var(--brand)]/5"
                    : "border-black/10 bg-gray-100"
              }`}
            >
              {visible ? card.text : "?"}
            </button>
          );
        })}
      </div>
    </GameShell>
  );
}

function Minigame({ data }: { data?: Record<string, unknown> }) {
  const game = (data ?? {}) as unknown as MinigameData;
  switch (game.game) {
    case "quiz":
      return <QuizMinigame data={game} />;
    case "order":
      return <OrderMinigame data={game} />;
    case "sort":
      return <SortMinigame data={game} />;
    case "memory":
      return <MemoryMinigame data={game} />;
    default:
      return (
        <GameShell
          title={game.title ?? "Practice challenge"}
          prompt={game.prompt ?? "This minigame type is not supported by the fallback renderer yet."}
          score={0}
          total={0}
          onReset={() => {}}
        >
          <div className="rounded-xl bg-gray-50 p-3 text-sm text-gray-600">
            Custom game: {game.game || "unknown"}
          </div>
        </GameShell>
      );
  }
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
                <option value="">Selectâ€¦</option>
                {rights.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {picks[i] ? <span>{correct ? "âœ“" : "âœ—"}</span> : null}
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
            <span>{open === i ? "âˆ’" : "+"}</span>
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

function AudioBlock({ block, resolve }: { block: Block; resolve: Resolve }) {
  const src = resolve(block.asset);
  const [open, setOpen] = useState(false);
  if (!src) return null;

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-black/5 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-[var(--brand)]">
          <span aria-hidden="true">AUDIO</span>
          Listen to this page
        </div>
        {block.text ? (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="flex h-7 w-7 items-center justify-center rounded-full border border-black/10 bg-gray-50 text-xs font-bold text-gray-700"
            aria-label="Show spoken text"
            title="Show spoken text"
          >
            i
          </button>
        ) : null}
      </div>
      <audio controls className="w-full" src={src} />
      {open && block.text ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            className="max-h-[80vh] w-full max-w-lg overflow-auto rounded-2xl bg-white p-5 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-label="Spoken text"
          >
            <div className="flex items-start justify-between gap-3">
              <h4 className="text-base font-bold text-gray-900">Spoken text</h4>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg border border-black/10 px-2 py-1 text-xs font-medium"
              >
                Close
              </button>
            </div>
            <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
              {block.text}
            </p>
          </motion.div>
        </div>
      ) : null}
    </div>
  );
}

function labelize(key: string): string {
  return key
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function StructuredValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <span>{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="list-disc space-y-1 pl-5">
        {value.map((item, i) => (
          <li key={i}>
            <StructuredValue value={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return (
      <div className="space-y-2">
        {Object.entries(value as Record<string, unknown>).map(([key, item]) => (
          <div key={key}>
            <span className="font-semibold text-gray-800">{labelize(key)}: </span>
            <StructuredValue value={item} />
          </div>
        ))}
      </div>
    );
  }
  return null;
}

function StructuredData({ data }: { data?: Record<string, unknown> }) {
  if (!data || !Object.keys(data).length) return null;
  return (
    <div className="rounded-xl border border-black/5 bg-gray-50 p-3 text-sm leading-relaxed text-gray-700">
      <StructuredValue value={data} />
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
      return <AudioBlock block={block} resolve={resolve} />;
    }
    case "conversation":
    case "dialogue":
      return <Conversation data={block.data} resolve={resolve} />;
    case "minigame":
      return <Minigame data={block.data} />;
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
      // items, data and any referenced image). This is the fallback renderer used when
      // the implementation agent isn't building a bespoke app.
      const img = resolve(block.asset);
      if (!block.text && !(block.items && block.items.length) && !block.data && !img) return null;
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
          <StructuredData data={block.data} />
          {img ? <MediaImage src={img} alt={block.text} /> : null}
        </div>
      );
    }
  }
}
