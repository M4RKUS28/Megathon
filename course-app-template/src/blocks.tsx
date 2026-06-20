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
import type {
  Block,
  ConversationTurn,
  FillInBlankData,
  MatchingGameData,
  Persona,
  SortingChallengeData,
  WordCloudData,
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
  const allCards = useMemo(() => (data?.cards as { front: string; back: string }[]) ?? [], [data]);
  const [order, setOrder] = useState<number[]>(() => allCards.map((_, i) => i));
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  const [firstFlipCorrect, setFirstFlipCorrect] = useState<Set<number>>(new Set());
  const [showCelebration, setShowCelebration] = useState(false);

  const cards = useMemo(() => order.map((i) => ({ ...allCards[i], _idx: i })), [order, allCards]);
  const revealed = Object.keys(flipped).filter((k) => flipped[Number(k)]).length;
  const total = allCards.length;

  const shuffle = useCallback(() => {
    setOrder((prev) => {
      const next = [...prev];
      for (let i = next.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [next[i], next[j]] = [next[j], next[i]];
      }
      return next;
    });
    setFlipped({});
  }, []);

  const flip = (idx: number) => {
    const wasFlipped = !!flipped[idx];
    setFlipped((f) => ({ ...f, [idx]: !f[idx] }));
    if (!wasFlipped) {
      setFirstFlipCorrect((s) => new Set(s).add(idx));
      if (revealed + 1 === total && !showCelebration) {
        setShowCelebration(true);
        setTimeout(() => setShowCelebration(false), 2500);
      }
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500">
          {revealed} / {total} revealed
        </span>
        <button
          type="button"
          onClick={shuffle}
          className="rounded-lg border border-black/10 px-3 py-1 text-xs font-medium hover:bg-black/5"
        >
          Shuffle
        </button>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-[var(--brand)] transition-all"
          style={{ width: `${total ? (revealed / total) * 100 : 0}%` }}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {cards.map((c) => (
          <button
            key={c._idx}
            onClick={() => flip(c._idx)}
            className={`min-h-[96px] rounded-xl border p-4 text-left shadow-sm transition hover:shadow-md ${
              flipped[c._idx]
                ? "border-[var(--brand)]/30 bg-[var(--brand)]/5"
                : "border-black/5 bg-white"
            }`}
          >
            <div className="text-[11px] font-semibold uppercase tracking-wide text-[var(--brand)]">
              {flipped[c._idx] ? "Answer" : "Card"}
            </div>
            <div className="mt-1 text-sm">{flipped[c._idx] ? c.back : c.front}</div>
          </button>
        ))}
      </div>
      {showCelebration && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-center"
        >
          <div className="text-lg font-bold text-emerald-700">All cards revealed!</div>
          <div className="text-sm text-emerald-600">
            {firstFlipCorrect.size} / {total} seen on first pass
          </div>
        </motion.div>
      )}
    </div>
  );
}

function DragDrop({ data }: { data?: Record<string, unknown> }) {
  const pairs = (data?.pairs as { left: string; right: string }[]) ?? [];
  const rights = useMemo(() => pairs.map((p) => p.right).sort(), [pairs]);
  const [picks, setPicks] = useState<Record<number, string>>({});
  const [checked, setChecked] = useState(false);
  const [shakeIdx, setShakeIdx] = useState<number | null>(null);

  const allFilled = pairs.every((_, i) => !!picks[i]);
  const correctCount = pairs.filter((p, i) => picks[i] === p.right).length;
  const allCorrect = checked && correctCount === pairs.length;

  const checkAll = () => {
    setChecked(true);
    // Shake the first wrong answer
    const wrongIdx = pairs.findIndex((p, i) => picks[i] !== p.right);
    if (wrongIdx >= 0) {
      setShakeIdx(wrongIdx);
      setTimeout(() => setShakeIdx(null), 600);
    }
  };

  const reset = () => {
    setPicks({});
    setChecked(false);
    setShakeIdx(null);
  };

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.prompt ? <p className="mb-3 text-sm font-medium">{String(data.prompt)}</p> : null}
      <div className="space-y-2">
        {pairs.map((p, i) => {
          const correct = picks[i] === p.right;
          const isShaking = shakeIdx === i;
          return (
            <motion.div
              key={i}
              animate={isShaking ? { x: [0, -6, 6, -4, 4, 0] } : {}}
              transition={{ duration: 0.4 }}
              className="flex items-center gap-3"
            >
              <span className="w-28 shrink-0 text-sm font-medium">{p.left}</span>
              <select
                value={picks[i] ?? ""}
                disabled={checked && correct}
                onChange={(e) => {
                  setPicks((s) => ({ ...s, [i]: e.target.value }));
                  setChecked(false);
                }}
                className={`flex-1 rounded-lg border px-2 py-1.5 text-sm transition-all ${
                  checked
                    ? correct
                      ? "border-emerald-500 bg-emerald-50"
                      : "border-red-400 bg-red-50"
                    : picks[i]
                      ? "border-[var(--brand)] bg-[var(--brand)]/5"
                      : "border-black/10"
                }`}
              >
                <option value="">Select…</option>
                {rights.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {checked && (
                <span className={`text-sm font-bold ${correct ? "text-emerald-600" : "text-red-500"}`}>
                  {correct ? "✓" : "✗"}
                </span>
              )}
            </motion.div>
          );
        })}
      </div>
      <div className="mt-4 flex items-center gap-3">
        {!checked ? (
          <button
            type="button"
            disabled={!allFilled}
            onClick={checkAll}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            Check All
          </button>
        ) : allCorrect ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 text-sm font-medium text-emerald-600"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white text-xs">✓</span>
            All correct!
          </motion.div>
        ) : (
          <>
            <span className="text-sm font-medium text-red-600">
              {correctCount} / {pairs.length} correct
            </span>
            <button
              type="button"
              onClick={reset}
              className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
            >
              Try again
            </button>
          </>
        )}
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
  const branches = (data?.branches as { choice: string; outcome: string; explanation?: string }[]) ?? [];
  const [picked, setPicked] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {data?.prompt ? <p className="mb-3 text-sm font-medium">{String(data.prompt)}</p> : null}
      <div className="flex flex-wrap gap-2">
        {branches.map((b, i) => (
          <button
            key={i}
            onClick={() => { setPicked(i); setShowAll(false); }}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-all ${
              picked === i
                ? "border-[var(--brand)] bg-[var(--brand)]/10 font-medium"
                : picked !== null
                  ? "border-black/5 opacity-60"
                  : "border-black/10 hover:border-[var(--brand)]/50"
            }`}
          >
            {b.choice}
          </button>
        ))}
      </div>
      {picked !== null && branches[picked] ? (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-3 space-y-2"
        >
          <div className="rounded-lg bg-[var(--brand)]/5 border border-[var(--brand)]/10 p-3 text-sm">
            <div className="font-medium text-[var(--brand)] mb-1">Your choice: {branches[picked].choice}</div>
            {branches[picked].outcome}
          </div>
          {!showAll && branches.some((b) => b.explanation) && (
            <button
              type="button"
              onClick={() => setShowAll(true)}
              className="text-xs font-medium text-[var(--brand)] hover:underline"
            >
              Why were the other options different?
            </button>
          )}
          {showAll && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-1.5"
            >
              {branches.map((b, i) => {
                if (i === picked || !b.explanation) return null;
                return (
                  <div key={i} className="rounded-lg bg-gray-50 p-2.5 text-sm">
                    <span className="font-medium text-gray-700">{b.choice}:</span>{" "}
                    <span className="text-gray-500">{b.explanation}</span>
                  </div>
                );
              })}
            </motion.div>
          )}
        </motion.div>
      ) : null}
    </div>
  );
}

// ── New interactive block types ───────────────────────────────────────────────

function MatchingGame({ data }: { data?: Record<string, unknown> }) {
  const pairs = ((data as MatchingGameData | undefined)?.pairs) ?? [];
  const total = pairs.length;

  // Build a grid of 2*N cards (term + definition), shuffled once
  const gridCards = useMemo(() => {
    const cards: { id: number; text: string; pairIdx: number; kind: "term" | "def" }[] = [];
    pairs.forEach((p, i) => {
      cards.push({ id: i * 2, text: p.term, pairIdx: i, kind: "term" });
      cards.push({ id: i * 2 + 1, text: p.definition, pairIdx: i, kind: "def" });
    });
    for (let i = cards.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [cards[i], cards[j]] = [cards[j], cards[i]];
    }
    return cards;
  }, [pairs]);

  const [flipped, setFlipped] = useState<Set<number>>(new Set());
  const [matched, setMatched] = useState<Set<number>>(new Set());
  const [selected, setSelected] = useState<number | null>(null);
  const [wrong, setWrong] = useState<Set<number>>(new Set());
  const [moves, setMoves] = useState(0);

  const handleClick = (cardId: number) => {
    if (matched.has(cardId) || flipped.has(cardId) || wrong.size > 0) return;
    const card = gridCards.find((c) => c.id === cardId);
    if (!card) return;

    if (selected === null) {
      setSelected(cardId);
      setFlipped((s) => new Set(s).add(cardId));
      return;
    }

    const prev = gridCards.find((c) => c.id === selected);
    if (!prev) return;
    setFlipped((s) => new Set(s).add(cardId));
    setMoves((m) => m + 1);

    if (prev.pairIdx === card.pairIdx && prev.kind !== card.kind) {
      // Match!
      setMatched((s) => { const n = new Set(s); n.add(prev.id); n.add(card.id); return n; });
      setSelected(null);
    } else {
      // No match — briefly show both, then hide
      setWrong(new Set([prev.id, card.id]));
      setTimeout(() => {
        setFlipped((s) => { const n = new Set(s); n.delete(prev.id); n.delete(card.id); return n; });
        setWrong(new Set());
        setSelected(null);
      }, 800);
    }
  };

  const allMatched = matched.size === gridCards.length && gridCards.length > 0;
  const cols = total <= 3 ? "grid-cols-3" : total <= 4 ? "grid-cols-4" : "grid-cols-4";

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold">Memory Match</h4>
        <span className="text-xs text-gray-400">{matched.size / 2} / {total} matched · {moves} moves</span>
      </div>
      <div className={`grid ${cols} gap-2`}>
        {gridCards.map((card) => {
          const isFlipped = flipped.has(card.id) || matched.has(card.id);
          const isMatched = matched.has(card.id);
          const isWrong = wrong.has(card.id);
          return (
            <button
              key={card.id}
              onClick={() => handleClick(card.id)}
              disabled={isMatched}
              className={`min-h-[72px] rounded-lg border p-2.5 text-xs text-center transition-all ${
                isMatched
                  ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                  : isWrong
                    ? "border-red-400 bg-red-50"
                    : isFlipped
                      ? "border-[var(--brand)] bg-[var(--brand)]/5"
                      : "border-black/10 bg-gray-50 hover:bg-gray-100 cursor-pointer"
              }`}
            >
              {isFlipped ? (
                <span>{card.text}</span>
              ) : (
                <span className="text-gray-400 text-lg">?</span>
              )}
            </button>
          );
        })}
      </div>
      {allMatched && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mt-3 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-center"
        >
          <div className="font-bold text-emerald-700">All pairs matched!</div>
          <div className="text-xs text-emerald-600">Completed in {moves} moves</div>
        </motion.div>
      )}
    </div>
  );
}

function SortingChallenge({ data }: { data?: Record<string, unknown> }) {
  const raw = data as SortingChallengeData | undefined;
  const prompt = raw?.prompt ?? "Put these items in the correct order:";
  const items = useMemo(() => raw?.items ?? [], [raw]);
  const correctOrder = useMemo(() => raw?.correctOrder ?? items.map((_, i) => i), [raw, items]);

  const [order, setOrder] = useState<number[]>(() => {
    const indices = items.map((_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices;
  });
  const [checked, setChecked] = useState(false);

  const moveUp = (pos: number) => {
    if (pos === 0) return;
    setOrder((o) => { const n = [...o]; [n[pos], n[pos - 1]] = [n[pos - 1], n[pos]]; return n; });
    setChecked(false);
  };

  const moveDown = (pos: number) => {
    if (pos >= order.length - 1) return;
    setOrder((o) => { const n = [...o]; [n[pos], n[pos + 1]] = [n[pos + 1], n[pos]]; return n; });
    setChecked(false);
  };

  const isCorrect = order.every((idx, pos) => idx === correctOrder[pos]);

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      <p className="mb-3 text-sm font-medium">{prompt}</p>
      <div className="space-y-1.5">
        {order.map((itemIdx, pos) => {
          const posCorrect = checked && itemIdx === correctOrder[pos];
          const posWrong = checked && itemIdx !== correctOrder[pos];
          return (
            <motion.div
              key={itemIdx}
              layout
              className={`flex items-center gap-2 rounded-lg border p-2.5 text-sm transition-all ${
                posCorrect
                  ? "border-emerald-300 bg-emerald-50"
                  : posWrong
                    ? "border-red-300 bg-red-50"
                    : "border-black/10 bg-white"
              }`}
            >
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gray-100 text-xs font-bold text-gray-500">
                {pos + 1}
              </span>
              <span className="flex-1">{items[itemIdx]}</span>
              <div className="flex gap-1">
                <button
                  type="button"
                  onClick={() => moveUp(pos)}
                  disabled={pos === 0 || (checked && isCorrect)}
                  className="rounded px-1.5 py-0.5 text-xs hover:bg-black/5 disabled:opacity-30"
                >
                  ▲
                </button>
                <button
                  type="button"
                  onClick={() => moveDown(pos)}
                  disabled={pos >= order.length - 1 || (checked && isCorrect)}
                  className="rounded px-1.5 py-0.5 text-xs hover:bg-black/5 disabled:opacity-30"
                >
                  ▼
                </button>
              </div>
              {checked && (
                <span className={`text-sm font-bold ${posCorrect ? "text-emerald-600" : "text-red-500"}`}>
                  {posCorrect ? "✓" : "✗"}
                </span>
              )}
            </motion.div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center gap-3">
        {!checked ? (
          <button
            type="button"
            onClick={() => setChecked(true)}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white"
          >
            Check Order
          </button>
        ) : isCorrect ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 text-sm font-medium text-emerald-600"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white text-xs">✓</span>
            Correct order!
          </motion.div>
        ) : (
          <button
            type="button"
            onClick={() => setChecked(false)}
            className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
          >
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

function FillInBlank({ data }: { data?: Record<string, unknown> }) {
  const raw = data as FillInBlankData | undefined;
  const sentences = raw?.sentences ?? [];
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);

  let totalBlanks = 0;
  let correctBlanks = 0;
  sentences.forEach((s, si) =>
    s.blanks.forEach((b, bi) => {
      totalBlanks++;
      if (answers[`${si}-${bi}`] === b.answer) correctBlanks++;
    }),
  );
  const allFilled = Object.keys(answers).length >= totalBlanks;
  const allCorrect = checked && correctBlanks === totalBlanks;

  return (
    <div className="rounded-xl border border-black/5 bg-white p-4 space-y-4">
      <h4 className="text-sm font-semibold">Fill in the blanks</h4>
      {sentences.map((s, si) => {
        // Split text at blank positions and interleave with dropdowns
        const parts: (string | { blankIdx: number })[] = [];
        let lastPos = 0;
        const sortedBlanks = [...s.blanks].sort((a, b) => a.position - b.position);
        sortedBlanks.forEach((blank, bi) => {
          if (blank.position > lastPos) {
            parts.push(s.text.slice(lastPos, blank.position));
          }
          parts.push({ blankIdx: bi });
          // Skip past the blank placeholder (assume "___" or similar)
          const afterBlank = s.text.indexOf(" ", blank.position + 1);
          lastPos = afterBlank > blank.position ? afterBlank : blank.position + 3;
        });
        if (lastPos < s.text.length) parts.push(s.text.slice(lastPos));

        return (
          <div key={si} className="text-sm leading-loose flex flex-wrap items-center gap-1">
            {parts.map((part, pi) => {
              if (typeof part === "string") {
                return <span key={pi}>{part}</span>;
              }
              const blank = s.blanks[part.blankIdx];
              const key = `${si}-${part.blankIdx}`;
              const val = answers[key];
              const correct = val === blank.answer;
              return (
                <select
                  key={pi}
                  value={val ?? ""}
                  disabled={checked && correct}
                  onChange={(e) => {
                    setAnswers((a) => ({ ...a, [key]: e.target.value }));
                    setChecked(false);
                  }}
                  className={`inline-block rounded-md border px-2 py-1 text-sm min-w-[120px] ${
                    checked
                      ? correct
                        ? "border-emerald-500 bg-emerald-50"
                        : "border-red-400 bg-red-50"
                      : val
                        ? "border-[var(--brand)] bg-[var(--brand)]/5"
                        : "border-black/10"
                  }`}
                >
                  <option value="">Choose…</option>
                  {blank.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              );
            })}
          </div>
        );
      })}
      <div className="flex items-center gap-3">
        {!checked ? (
          <button
            type="button"
            disabled={!allFilled}
            onClick={() => setChecked(true)}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          >
            Check Answers
          </button>
        ) : allCorrect ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 text-sm font-medium text-emerald-600"
          >
            <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-500 text-white text-xs">✓</span>
            All blanks correct!
          </motion.div>
        ) : (
          <>
            <span className="text-sm text-red-600 font-medium">{correctBlanks} / {totalBlanks} correct</span>
            <button
              type="button"
              onClick={() => setChecked(false)}
              className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium"
            >
              Try again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function WordCloud({ data }: { data?: Record<string, unknown> }) {
  const raw = data as WordCloudData | undefined;
  const words = raw?.words ?? [];
  const maxWeight = Math.max(...words.map((w) => w.weight), 1);

  return (
    <div className="rounded-xl border border-black/5 bg-gradient-to-br from-gray-50 to-white p-5">
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
        {words.map((w, i) => {
          const ratio = w.weight / maxWeight;
          const size = 12 + ratio * 24; // 12px to 36px
          const opacity = 0.4 + ratio * 0.6;
          return (
            <motion.span
              key={i}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity, scale: 1 }}
              transition={{ delay: i * 0.04 }}
              style={{ fontSize: `${size}px` }}
              className="font-semibold text-[var(--brand)] cursor-default select-none"
              title={`Weight: ${w.weight}`}
            >
              {w.text}
            </motion.span>
          );
        })}
      </div>
    </div>
  );
}

// Detect fabricated / placeholder chart data that shouldn't be rendered as a
// real chart. Generic quarter labels with linearly increasing values are a
// strong signal that the data is filler, not meaningful metrics.
function looksLikePlaceholder(labels: string[], datasets: { data: number[] }[]): boolean {
  const GENERIC = /^(q[1-4]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|month\s*\d|week\s*\d|step\s*\d|year\s*\d)/i;
  const genericCount = labels.filter((l) => GENERIC.test(l.trim())).length;
  if (genericCount < labels.length * 0.6) return false;
  for (const ds of datasets) {
    if (!ds.data || ds.data.length < 3) continue;
    let monotone = true;
    for (let i = 1; i < ds.data.length; i++) {
      if (ds.data[i] < ds.data[i - 1]) { monotone = false; break; }
    }
    if (monotone) return true;
  }
  return false;
}

function ChartBlock({ data }: { data?: Record<string, unknown> }) {
  const chartType = (data?.chartType as string) ?? "bar";
  const labels = (data?.labels as string[]) ?? [];
  const datasets = (data?.datasets as { label: string; data: number[] }[]) ?? [];
  const title = data?.title ? String(data.title) : undefined;

  // If the data looks fabricated, render a styled info card instead of a chart
  if (looksLikePlaceholder(labels, datasets)) {
    return (
      <div className="rounded-xl border border-black/5 bg-gradient-to-br from-[var(--brand)]/5 to-transparent p-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-[var(--brand)]/10 text-[var(--brand)] text-sm">
            📊
          </span>
          {title ? (
            <h4 className="text-sm font-semibold">{title}</h4>
          ) : (
            <h4 className="text-sm font-semibold">Data Visualization</h4>
          )}
        </div>
        <p className="text-sm text-gray-500">
          This visualization will be populated with real metrics once data is available.
        </p>
        {datasets.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {datasets.map((ds, i) => (
              <span
                key={i}
                className="rounded-full bg-white px-3 py-1 text-xs font-medium text-gray-600 border border-black/5"
              >
                {ds.label}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  const coloredDatasets = datasets.map((d, i) => ({
    ...d,
    backgroundColor: ["#5145E5", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"][i % 5],
    borderColor: "#5145E5",
  }));
  const chartData = { labels, datasets: coloredDatasets };
  const opts = { responsive: true, plugins: { legend: { position: "bottom" as const } } };
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4">
      {title ? <h4 className="mb-2 text-sm font-semibold">{title}</h4> : null}
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
    case "matching_game":
      return <MatchingGame data={block.data} />;
    case "sorting_challenge":
      return <SortingChallenge data={block.data} />;
    case "fill_in_blank":
      return <FillInBlank data={block.data} />;
    case "word_cloud":
      return <WordCloud data={block.data} />;
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
