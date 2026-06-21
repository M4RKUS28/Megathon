import { type ReactNode, useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
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

function speakWithBrowser(text?: string): boolean {
  if (!text || typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = document.documentElement.lang || navigator.language || "en";
  utterance.rate = 1;
  window.speechSynthesis.speak(utterance);
  return true;
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

// --- Dialogue Graph types (real shape for conversation/dialogue blocks) ---

interface DialogueChoice {
  text: string;
  next_node: string | null;
}

interface DialogueNode {
  id: string;
  text: string;
  choices?: DialogueChoice[];
}

interface DialogueGraphData {
  speaker?: string;
  dialogue_nodes: DialogueNode[];
}

function isDialogueGraph(d: Record<string, unknown>): boolean {
  return Array.isArray(d.dialogue_nodes);
}

function DialogueGraph({ data }: { data: Record<string, unknown> }) {
  const reduced = useReducedMotion();
  const raw = data as unknown as DialogueGraphData;
  const nodes = raw.dialogue_nodes;
  const speakerName = typeof raw.speaker === "string" ? raw.speaker : "Speaker";
  const nodeMap = useMemo(() => {
    const m = new Map<string, DialogueNode>();
    for (const n of nodes) m.set(n.id, n);
    return m;
  }, [nodes]);

  const firstNode = nodes[0];
  const [transcript, setTranscript] = useState<{ role: "speaker" | "learner"; text: string }[]>(
    firstNode ? [{ role: "speaker", text: firstNode.text }] : [],
  );
  const [currentNodeId, setCurrentNodeId] = useState<string | null>(firstNode?.id ?? null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const currentNode = currentNodeId ? nodeMap.get(currentNodeId) : undefined;
  const choices = currentNode?.choices ?? [];
  const isTerminal = !currentNode || choices.length === 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
  }, [transcript.length, reduced]);

  const pickChoice = useCallback((choice: DialogueChoice) => {
    setTranscript((prev) => [...prev, { role: "learner", text: choice.text }]);
    if (choice.next_node && nodeMap.has(choice.next_node)) {
      const nextNode = nodeMap.get(choice.next_node)!;
      setCurrentNodeId(choice.next_node);
      setTranscript((prev) => [...prev, { role: "speaker", text: nextNode.text }]);
    } else {
      setCurrentNodeId(null);
    }
  }, [nodeMap]);

  const restart = useCallback(() => {
    setTranscript(firstNode ? [{ role: "speaker", text: firstNode.text }] : []);
    setCurrentNodeId(firstNode?.id ?? null);
  }, [firstNode]);

  if (!nodes.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No dialogue available.
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-black/5 bg-gradient-to-b from-gray-50 to-white" role="region" aria-label="Interactive dialogue">
      <div className="border-b border-black/5 px-4 py-3">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">Dialogue</span>
        <div className="text-sm font-semibold text-gray-700">{speakerName}</div>
      </div>

      <div className="max-h-[400px] overflow-y-auto p-4">
        <div className="space-y-2.5" role="log" aria-label="Conversation transcript" aria-live="polite">
          {transcript.map((entry, i) => {
            const isLearner = entry.role === "learner";
            return (
              <motion.div
                key={i}
                initial={reduced ? { opacity: 1 } : { opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${isLearner ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-sm ${
                    isLearner
                      ? "bg-[var(--brand)] text-white"
                      : "border border-black/5 bg-white"
                  }`}
                >
                  <div className={`mb-0.5 text-[11px] font-semibold ${isLearner ? "text-white/85" : "opacity-70"}`}>
                    {isLearner ? "You" : speakerName}
                  </div>
                  <div>{entry.text}</div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* Choice buttons */}
        {!isTerminal && choices.length > 0 ? (
          <div className="mt-3 space-y-1.5">
            {choices.map((choice, ci) => (
              <button
                key={ci}
                type="button"
                onClick={() => pickChoice(choice)}
                className="block w-full rounded-xl border border-[var(--brand)]/30 bg-[var(--brand)]/5 px-3 py-2 text-left text-sm font-medium text-[var(--brand)] transition hover:bg-[var(--brand)]/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
              >
                {choice.text}
              </button>
            ))}
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      <div className="flex items-center justify-between border-t border-black/5 px-4 py-3">
        <span className="text-xs text-gray-400">
          {isTerminal && transcript.length > 0 ? "Conversation complete" : `${transcript.length} messages`}
        </span>
        <button
          type="button"
          onClick={restart}
          className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
        >
          Restart
        </button>
      </div>
    </div>
  );
}

function Conversation({ data, resolve }: { data?: Record<string, unknown>; resolve: Resolve }) {
  // Real shape: dialogue_nodes graph
  if (data && isDialogueGraph(data)) {
    return <DialogueGraph data={data} />;
  }

  // Legacy shape: linear turns + personas
  const { personas, turns } = useMemo(() => normalizeConversation(data), [data]);
  const [shown, setShown] = useState(1);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const fallbackSpeechRef = useRef<string>("");

  const left = personas.find((p) => p.side !== "right") ?? personas[0];
  const right = personas.find((p) => p.side === "right") ?? personas[1] ?? personas[0];

  const play = useCallback(
    (link?: string, text?: string) => {
      const src = resolve(link);
      const el = audioRef.current;
      fallbackSpeechRef.current = text ?? "";
      if (!src || !el) {
        speakWithBrowser(text);
        return;
      }
      el.src = src;
      el.currentTime = 0;
      void el.play().catch(() => {});
    },
    [resolve],
  );

  useEffect(() => {
    if (!turns.length) return;
    const turn = turns[shown - 1];
    play(turn?.audio, turn?.text);
  }, [shown, turns, play]);

  if (!turns.length) return null;

  const active = personaOf(turns[shown - 1] ?? {}, personas);
  const done = shown >= turns.length;
  const advance = () => setShown((s) => Math.min(s + 1, turns.length));

  return (
    <div className="rounded-2xl border border-black/5 bg-gradient-to-b from-gray-50 to-white p-4" role="region" aria-label="Conversation">
      <audio
        ref={audioRef}
        className="hidden"
        onLoadedMetadata={(e) => {
          if (fallbackSpeechRef.current && e.currentTarget.duration <= 3.2) {
            e.currentTarget.pause();
            speakWithBrowser(fallbackSpeechRef.current);
          }
        }}
        onError={() => speakWithBrowser(fallbackSpeechRef.current)}
      />
      <div className="mb-4 flex items-end justify-between gap-2">
        <PersonaStage persona={left} active={left === active} resolve={resolve} />
        <span className="pb-7 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
          Conversation
        </span>
        <PersonaStage persona={right} active={right === active} resolve={resolve} />
      </div>

      <div className="space-y-2.5" role="log" aria-label="Conversation transcript" aria-live="polite">
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
                  {p?.role ? <span className="font-normal opacity-70">{String.fromCharCode(183)} {p.role}</span> : null}
                </div>
                <div>{t.text}</div>
                {t.audio ? (
                  <button
                    type="button"
                    onClick={() => play(t.audio, t.text)}
                    className={`mt-1 inline-flex items-center gap-1 text-[11px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)] ${
                      mine ? "text-white/85" : "text-[var(--brand)]"
                    }`}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 8.5v7a4.49 4.49 0 002.5-3.5z"/>
                    </svg>
                    Replay
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
            className="rounded-lg border border-black/10 px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
          >
            Replay conversation
          </button>
        ) : (
          <button
            type="button"
            onClick={advance}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Next
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

// --- DragDrop types ---

interface DragDropItemReal {
  id: string;
  text: string;
  category: string;
}

interface DragDropCategoryReal {
  id: string;
  title: string;
}

interface DragDropNormalized {
  prompt?: string;
  items: { id: string; text: string; correctBin: string }[];
  bins: { id: string; title: string }[];
}

function normalizeDragDropData(data?: Record<string, unknown>): DragDropNormalized {
  if (!data) return { items: [], bins: [] };
  // Real shape: { items, categories }
  if (Array.isArray(data.items) && Array.isArray(data.categories)) {
    const rawItems = data.items as DragDropItemReal[];
    const rawCats = data.categories as DragDropCategoryReal[];
    return {
      prompt: typeof data.prompt === "string" ? data.prompt : undefined,
      items: rawItems.map((it, i) => ({
        id: it.id ?? `item-${i}`,
        text: it.text,
        correctBin: it.category,
      })),
      bins: rawCats.map((c) => ({ id: c.id, title: c.title })),
    };
  }
  // Legacy shape: { prompt, pairs: [{ left, right }] }
  const pairs = (data.pairs as { left: string; right: string }[]) ?? [];
  const uniqueRights = Array.from(new Set(pairs.map((p) => p.right)));
  return {
    prompt: typeof data.prompt === "string" ? data.prompt : undefined,
    items: pairs.map((p, i) => ({
      id: `item-${i}`,
      text: p.left,
      correctBin: p.right,
    })),
    bins: uniqueRights.map((r) => ({ id: r, title: r })),
  };
}

function DragDrop({ data }: { data?: Record<string, unknown> }) {
  const reduced = useReducedMotion();
  const normalized = useMemo(() => normalizeDragDropData(data), [data]);
  const { prompt, items, bins } = normalized;

  // Shuffled pool of items
  const shuffledItems = useMemo(() => {
    const arr = [...items];
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.map((it) => it.id).join(",")]);

  // Placements: itemId -> binId
  const [placements, setPlacements] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false);
  const [selectedItem, setSelectedItem] = useState<string | null>(null);
  const [dragOverBin, setDragOverBin] = useState<string | null>(null);

  const unplaced = shuffledItems.filter((it) => !placements[it.id]);
  const allPlaced = items.length > 0 && unplaced.length === 0;
  const score = checked
    ? items.reduce((sum, it) => sum + (placements[it.id] === it.correctBin ? 1 : 0), 0)
    : 0;

  const placeItem = useCallback((itemId: string, binId: string) => {
    setPlacements((prev) => ({ ...prev, [itemId]: binId }));
    setSelectedItem(null);
    setChecked(false);
  }, []);

  const removeItem = useCallback((itemId: string) => {
    setPlacements((prev) => {
      const next = { ...prev };
      delete next[itemId];
      return next;
    });
    setChecked(false);
  }, []);

  const reset = useCallback(() => {
    setPlacements({});
    setChecked(false);
    setSelectedItem(null);
  }, []);

  const handleDragStart = useCallback((e: React.DragEvent, itemId: string) => {
    e.dataTransfer.setData("text/plain", itemId);
    e.dataTransfer.effectAllowed = "move";
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, binId: string) => {
    e.preventDefault();
    const itemId = e.dataTransfer.getData("text/plain");
    if (itemId) placeItem(itemId, binId);
    setDragOverBin(null);
  }, [placeItem]);

  const handleBinClick = useCallback((binId: string) => {
    if (selectedItem) {
      placeItem(selectedItem, binId);
    }
  }, [selectedItem, placeItem]);

  const handleItemKeyDown = useCallback((e: React.KeyboardEvent, itemId: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setSelectedItem((prev) => (prev === itemId ? null : itemId));
    }
  }, []);

  const handleBinKeyDown = useCallback((e: React.KeyboardEvent, binId: string) => {
    if ((e.key === "Enter" || e.key === " ") && selectedItem) {
      e.preventDefault();
      placeItem(selectedItem, binId);
    }
  }, [selectedItem, placeItem]);

  if (!items.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No items to sort.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Drag and drop sorting activity">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">Sort Items</div>
          {prompt ? <p className="mt-0.5 text-sm text-gray-600">{prompt}</p> : null}
        </div>
        {checked ? (
          <div className="rounded-lg border border-black/5 bg-white px-3 py-1.5 text-sm font-bold text-[var(--brand)]">
            {score}/{items.length}
          </div>
        ) : null}
      </div>

      <div className="p-4">
        {/* Item pool */}
        {unplaced.length > 0 ? (
          <div className="mb-4">
            <div className="mb-2 text-xs font-medium text-gray-500">Items to sort:</div>
            <div className="flex flex-wrap gap-2" role="list" aria-label="Items to place">
              {unplaced.map((item) => (
                <motion.button
                  key={item.id}
                  type="button"
                  layout={!reduced}
                  draggable
                  onDragStart={(e) => handleDragStart(e as unknown as React.DragEvent, item.id)}
                  onClick={() => setSelectedItem((prev) => (prev === item.id ? null : item.id))}
                  onKeyDown={(e) => handleItemKeyDown(e, item.id)}
                  className={`cursor-grab rounded-lg border px-3 py-1.5 text-sm font-medium transition active:cursor-grabbing ${
                    selectedItem === item.id
                      ? "border-[var(--brand)] bg-[var(--brand)]/10 text-[var(--brand)]"
                      : "border-black/10 bg-white hover:border-[var(--brand)]/50"
                  } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]`}
                  role="listitem"
                  aria-label={`${item.text}${selectedItem === item.id ? " (selected)" : ""}`}
                  aria-pressed={selectedItem === item.id}
                >
                  {item.text}
                </motion.button>
              ))}
            </div>
          </div>
        ) : null}

        {/* Category bins */}
        <div className={`grid gap-3 ${bins.length <= 2 ? "sm:grid-cols-2" : "sm:grid-cols-3"}`}>
          {bins.map((bin) => {
            const binItems = items.filter((it) => placements[it.id] === bin.id);
            const isOver = dragOverBin === bin.id;
            return (
              <div
                key={bin.id}
                onDragOver={handleDragOver}
                onDragEnter={() => setDragOverBin(bin.id)}
                onDragLeave={() => setDragOverBin(null)}
                onDrop={(e) => handleDrop(e, bin.id)}
                onClick={() => handleBinClick(bin.id)}
                onKeyDown={(e) => handleBinKeyDown(e, bin.id)}
                tabIndex={selectedItem ? 0 : -1}
                role="group"
                aria-label={`Category: ${bin.title}`}
                className={`min-h-[80px] rounded-xl border-2 border-dashed p-3 transition ${
                  isOver
                    ? "border-[var(--brand)] bg-[var(--brand)]/5"
                    : selectedItem
                      ? "border-[var(--brand)]/30 bg-[var(--brand)]/5 cursor-pointer"
                      : "border-black/10 bg-gray-50"
                } focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]`}
              >
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  {bin.title}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {binItems.map((item) => {
                    const isCorrect = checked && placements[item.id] === item.correctBin;
                    const isWrong = checked && placements[item.id] !== item.correctBin;
                    return (
                      <span
                        key={item.id}
                        className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium ${
                          isCorrect
                            ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                            : isWrong
                              ? "border-red-300 bg-red-50 text-red-700"
                              : "border-black/10 bg-white"
                        }`}
                      >
                        {item.text}
                        {!checked ? (
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); removeItem(item.id); }}
                            className="ml-0.5 text-gray-400 hover:text-gray-600 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--brand)]"
                            aria-label={`Remove ${item.text}`}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                              <path d="M18 6L6 18M6 6l12 12" />
                            </svg>
                          </button>
                        ) : null}
                        {isCorrect ? (
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                            <path d="M20 6L9 17l-5-5" />
                          </svg>
                        ) : null}
                        {isWrong ? (
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden="true">
                            <path d="M18 6L6 18M6 6l12 12" />
                          </svg>
                        ) : null}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between border-t border-black/5 bg-gray-50 px-4 py-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-lg border border-black/10 bg-white px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
        >
          Reset
        </button>
        {allPlaced && !checked ? (
          <button
            type="button"
            onClick={() => setChecked(true)}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Check
          </button>
        ) : null}
        {checked ? (
          <span className="text-sm font-medium" role="status" aria-live="polite">
            {score === items.length ? (
              <span className="text-emerald-600">All correct!</span>
            ) : (
              <span className="text-gray-600">{score} of {items.length} correct</span>
            )}
          </span>
        ) : null}
      </div>
    </div>
  );
}


// --- Hotspot types ---

interface HotspotSpotNormalized {
  id: string;
  x: number;
  y: number;
  radius: number;
  title: string;
  description: string;
}

function normalizeHotspotData(
  data: Record<string, unknown> | undefined,
  resolve: Resolve,
): { imageUrl: string | undefined; spots: HotspotSpotNormalized[] } {
  if (!data) return { imageUrl: undefined, spots: [] };
  // Real shape: { image_url, hotspots: [...] }
  if (Array.isArray(data.hotspots)) {
    const hotspots = data.hotspots as { id?: string; x: number; y: number; radius?: number; title?: string; description?: string }[];
    return {
      imageUrl: resolve(data.image_url as string | undefined),
      spots: hotspots.map((h, i) => ({
        id: typeof h.id === "string" ? h.id : `spot-${i}`,
        x: h.x,
        y: h.y,
        radius: typeof h.radius === "number" ? h.radius : 3,
        title: typeof h.title === "string" ? h.title : `Spot ${i + 1}`,
        description: typeof h.description === "string" ? h.description : "",
      })),
    };
  }
  // Legacy shape: { asset, spots: [{ x, y, label }] }
  const legacySpots = (data.spots as { x: number; y: number; label: string }[]) ?? [];
  return {
    imageUrl: resolve(data.asset as string | undefined),
    spots: legacySpots.map((s, i) => ({
      id: `spot-${i}`,
      x: s.x,
      y: s.y,
      radius: 3,
      title: s.label,
      description: "",
    })),
  };
}

function Hotspot({ data, resolve }: { data?: Record<string, unknown>; resolve: Resolve }) {
  const reduced = useReducedMotion();
  const { imageUrl, spots } = useMemo(() => normalizeHotspotData(data, resolve), [data, resolve]);
  const [discovered, setDiscovered] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const hintTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const total = spots.length;
  const found = discovered.size;
  const done = total > 0 && found >= total;

  const clearHint = useCallback(() => {
    if (hintTimer.current) clearTimeout(hintTimer.current);
    setHint(null);
  }, []);

  const handleSpotClick = useCallback(
    (spot: HotspotSpotNormalized) => {
      clearHint();
      setDiscovered((prev) => new Set(prev).add(spot.id));
      setActiveId((prev) => (prev === spot.id ? null : spot.id));
    },
    [clearHint],
  );

  const handleImageClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if ((e.target as HTMLElement).closest("button")) return;
      clearHint();
      const rect = e.currentTarget.getBoundingClientRect();
      const clickX = ((e.clientX - rect.left) / rect.width) * 100;
      const clickY = ((e.clientY - rect.top) / rect.height) * 100;
      const hit = spots.find((s) => {
        const dx = clickX - s.x;
        const dy = clickY - s.y;
        return Math.sqrt(dx * dx + dy * dy) <= s.radius + 2;
      });
      if (hit) {
        handleSpotClick(hit);
      } else {
        setHint("Try clicking on a highlighted region");
        hintTimer.current = setTimeout(() => setHint(null), 2000);
      }
    },
    [spots, handleSpotClick, clearHint],
  );

  const reset = useCallback(() => {
    setDiscovered(new Set());
    setActiveId(null);
    clearHint();
  }, [clearHint]);

  useEffect(() => {
    return () => { if (hintTimer.current) clearTimeout(hintTimer.current); };
  }, []);

  if (!spots.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No hotspots available.
      </div>
    );
  }

  const activeSpot = spots.find((s) => s.id === activeId);

  return (
    <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Interactive hotspot image">
      {/* Progress */}
      <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-2">
        <span className="text-xs font-medium text-gray-500" role="status" aria-live="polite">
          Discovered {found}/{total}
        </span>
        {found > 0 ? (
          <button
            type="button"
            onClick={reset}
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--brand)] hover:bg-[var(--brand)]/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
          >
            Reset
          </button>
        ) : null}
      </div>

      <div className="h-1 bg-gray-100">
        <motion.div
          className="h-full bg-[var(--brand)]"
          animate={{ width: `${total ? (found / total) * 100 : 0}%` }}
          transition={{ duration: reduced ? 0 : 0.4 }}
        />
      </div>

      {/* Image + spots */}
      <div
        className="relative cursor-crosshair select-none"
        onClick={handleImageClick}
        role="img"
        aria-label="Hotspot image with clickable regions"
      >
        {imageUrl ? (
          <img src={imageUrl} alt="" className="block w-full" draggable={false} />
        ) : (
          <div className="flex h-48 items-center justify-center bg-gray-100 text-sm text-gray-400">
            No image provided
          </div>
        )}

        {spots.map((spot) => {
          const isDiscovered = discovered.has(spot.id);
          const isActive = activeId === spot.id;
          return (
            <button
              key={spot.id}
              type="button"
              onClick={(e) => { e.stopPropagation(); handleSpotClick(spot); }}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); e.stopPropagation(); handleSpotClick(spot); } }}
              style={{ left: `${spot.x}%`, top: `${spot.y}%` }}
              className={`absolute flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full text-xs font-bold shadow-md transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)] ${
                isDiscovered
                  ? "bg-emerald-500 text-white"
                  : "bg-[var(--brand)] text-white"
              } ${isActive ? "ring-4 ring-[var(--brand)]/30" : ""}`}
              aria-label={isDiscovered ? `${spot.title} (discovered)` : `Undiscovered spot`}
              aria-pressed={isActive}
            >
              {isDiscovered ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              ) : (
                <motion.span
                  animate={reduced ? {} : { scale: [1, 1.3, 1] }}
                  transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                  className="block h-2.5 w-2.5 rounded-full bg-white/80"
                  aria-hidden="true"
                />
              )}
            </button>
          );
        })}

        <AnimatePresence>
          {hint ? (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-lg bg-gray-900/90 px-3 py-1.5 text-xs text-white shadow-lg"
              role="alert"
            >
              {hint}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      {/* Detail panel */}
      <AnimatePresence>
        {activeSpot ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.25 }}
            className="overflow-hidden border-t border-black/5"
          >
            <div className="bg-gray-50 p-4">
              <div className="text-sm font-semibold text-gray-900">{activeSpot.title}</div>
              {activeSpot.description ? (
                <div className="mt-1 text-sm text-gray-600">{activeSpot.description}</div>
              ) : null}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {/* Completion */}
      <AnimatePresence>
        {done ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="border-t border-emerald-200 bg-emerald-50 p-3 text-center text-sm font-medium text-emerald-700"
            role="status"
            aria-live="polite"
          >
            All {total} hotspots discovered!
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}


// --- Timeline types ---

interface TimelineStepNormalized {
  id: string;
  title: string;
  description: string;
}

function normalizeTimelineData(data?: Record<string, unknown>): TimelineStepNormalized[] {
  if (!data) return [];
  // Real shape: { steps: [{ id, title, description }] }
  if (Array.isArray(data.steps)) {
    return (data.steps as { id?: string; title?: string; description?: string }[]).map((s, i) => ({
      id: typeof s.id === "string" ? s.id : `step-${i}`,
      title: typeof s.title === "string" ? s.title : `Step ${i + 1}`,
      description: typeof s.description === "string" ? s.description : "",
    }));
  }
  // Legacy shape: { events: [{ date, text }] }
  const events = (data.events as { date: string; text: string }[]) ?? [];
  return events.map((ev, i) => ({
    id: `event-${i}`,
    title: ev.date,
    description: ev.text,
  }));
}

function Timeline({ data }: { data?: Record<string, unknown> }) {
  const reduced = useReducedMotion();
  const authoredSteps = useMemo(() => normalizeTimelineData(data), [data]);
  const [interactive, setInteractive] = useState(false);
  const [userOrder, setUserOrder] = useState<TimelineStepNormalized[]>([]);
  const [validated, setValidated] = useState(false);

  const startInteractive = useCallback(() => {
    const shuffled = [...authoredSteps];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    setUserOrder(shuffled);
    setValidated(false);
    setInteractive(true);
  }, [authoredSteps]);

  const moveStep = useCallback((from: number, direction: -1 | 1) => {
    const to = from + direction;
    setUserOrder((prev) => {
      if (to < 0 || to >= prev.length) return prev;
      const next = [...prev];
      [next[from], next[to]] = [next[to], next[from]];
      return next;
    });
    setValidated(false);
  }, []);

  const checkOrder = useCallback(() => setValidated(true), []);

  const exitInteractive = useCallback(() => {
    setInteractive(false);
    setValidated(false);
  }, []);

  if (!authoredSteps.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No timeline data available.
      </div>
    );
  }

  if (interactive) {
    const allCorrect = userOrder.every((s, i) => s.id === authoredSteps[i].id);
    return (
      <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Interactive timeline reorder">
        <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">Reorder the steps</span>
          <button
            type="button"
            onClick={exitInteractive}
            className="text-xs font-medium text-gray-500 hover:text-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
          >
            Back to timeline
          </button>
        </div>

        <div className="space-y-2 p-4" role="list" aria-label="Reorderable steps">
          {userOrder.map((step, i) => {
            const isCorrect = validated && step.id === authoredSteps[i].id;
            const isWrong = validated && step.id !== authoredSteps[i].id;
            return (
              <motion.div
                layout={!reduced}
                key={step.id}
                className={`flex items-center gap-2 rounded-xl border p-3 ${
                  isCorrect
                    ? "border-emerald-300 bg-emerald-50"
                    : isWrong
                      ? "border-red-300 bg-red-50"
                      : "border-black/10 bg-gray-50"
                }`}
                role="listitem"
              >
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white text-xs font-bold text-gray-700 shadow-sm">
                  {i + 1}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium">{step.title}</div>
                  {step.description ? <div className="text-xs text-gray-500">{step.description}</div> : null}
                </div>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => moveStep(i, -1)}
                    disabled={i === 0}
                    className="rounded-md border border-black/10 bg-white px-2 py-1 text-xs disabled:opacity-30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
                    aria-label={`Move ${step.title} up`}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M18 15l-6-6-6 6" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    onClick={() => moveStep(i, 1)}
                    disabled={i === userOrder.length - 1}
                    className="rounded-md border border-black/10 bg-white px-2 py-1 text-xs disabled:opacity-30 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
                    aria-label={`Move ${step.title} down`}
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M6 9l6 6 6-6" />
                    </svg>
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>

        <div className="flex items-center justify-between border-t border-black/5 bg-gray-50 px-4 py-3">
          <span className="text-xs text-gray-500" role="status" aria-live="polite">
            {validated ? (allCorrect ? "Correct order!" : "Some steps are out of order") : `${userOrder.length} steps`}
          </span>
          {!validated ? (
            <button
              type="button"
              onClick={checkOrder}
              className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              Check Order
            </button>
          ) : !allCorrect ? (
            <button
              type="button"
              onClick={() => setValidated(false)}
              className="rounded-lg border border-black/10 bg-white px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
            >
              Try Again
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  // Default: vertical animated timeline
  return (
    <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Timeline">
      <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">Timeline</span>
        {authoredSteps.length > 1 ? (
          <button
            type="button"
            onClick={startInteractive}
            className="rounded-md px-2 py-1 text-xs font-medium text-[var(--brand)] hover:bg-[var(--brand)]/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
          >
            Try reordering
          </button>
        ) : null}
      </div>

      <ol className="relative space-y-0 border-l-2 border-[var(--brand)]/20 py-4 pl-8 pr-4 ml-4" aria-label="Timeline steps">
        {authoredSteps.map((step, i) => (
          <motion.li
            key={step.id}
            initial={reduced ? { opacity: 1 } : { opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1, duration: 0.3 }}
            className="relative pb-6 last:pb-0"
          >
            <span className="absolute -left-[33px] top-0.5 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--brand)] text-[10px] font-bold text-white shadow-sm">
              {i + 1}
            </span>
            <div className="text-sm font-semibold text-gray-900">{step.title}</div>
            {step.description ? (
              <div className="mt-0.5 text-sm text-gray-600">{step.description}</div>
            ) : null}
          </motion.li>
        ))}
      </ol>
    </div>
  );
}


// --- Accordion types ---

interface AccordionSectionNormalized {
  title: string;
  content: string;
}

function normalizeAccordionData(data?: Record<string, unknown>): AccordionSectionNormalized[] {
  if (!data) return [];
  // Real shape: { sections: [{ title, content }] }
  if (Array.isArray(data.sections)) {
    return (data.sections as { title?: string; content?: string }[]).map((s, i) => ({
      title: typeof s.title === "string" ? s.title : `Section ${i + 1}`,
      content: typeof s.content === "string" ? s.content : "",
    }));
  }
  // Legacy shape: { items: [{ title, body }] }
  const items = (data.items as { title: string; body: string }[]) ?? [];
  return items.map((it) => ({
    title: it.title,
    content: it.body,
  }));
}

function Accordion({ data }: { data?: Record<string, unknown> }) {
  const reduced = useReducedMotion();
  const sections = useMemo(() => normalizeAccordionData(data), [data]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [explored, setExplored] = useState<Set<number>>(new Set());

  const total = sections.length;
  const exploredCount = explored.size;
  const allExplored = total > 0 && exploredCount >= total;

  const toggle = useCallback((i: number) => {
    setOpenIndex((prev) => {
      const next = prev === i ? null : i;
      if (next !== null) {
        setExplored((prev) => new Set(prev).add(next));
      }
      return next;
    });
  }, []);

  const collapseAll = useCallback(() => setOpenIndex(null), []);

  const resetProgress = useCallback(() => {
    setOpenIndex(null);
    setExplored(new Set());
  }, []);

  if (!sections.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No sections available.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Accordion">
      {/* Progress header */}
      <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-2">
        <span className="text-xs font-medium text-gray-500" role="status" aria-live="polite">
          {allExplored ? (
            <span className="text-emerald-600">All sections explored!</span>
          ) : (
            `Explored ${exploredCount}/${total}`
          )}
        </span>
        <div className="flex gap-2">
          {openIndex !== null ? (
            <button
              type="button"
              onClick={collapseAll}
              className="text-xs font-medium text-gray-500 hover:text-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
            >
              Collapse all
            </button>
          ) : null}
          {exploredCount > 0 ? (
            <button
              type="button"
              onClick={resetProgress}
              className="text-xs font-medium text-[var(--brand)] hover:text-[var(--brand)]/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
            >
              Reset
            </button>
          ) : null}
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-gray-100">
        <motion.div
          className="h-full bg-[var(--brand)]"
          animate={{ width: `${total ? (exploredCount / total) * 100 : 0}%` }}
          transition={{ duration: reduced ? 0 : 0.3 }}
        />
      </div>

      {/* Sections */}
      <div className="divide-y divide-black/5" role="list">
        {sections.map((section, i) => {
          const isOpen = openIndex === i;
          const wasExplored = explored.has(i);
          return (
            <div key={i} role="listitem">
              <button
                type="button"
                onClick={() => toggle(i)}
                className="flex w-full items-center justify-between px-4 py-3.5 text-left text-sm font-medium text-gray-900 transition hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--brand)]"
                aria-expanded={isOpen}
              >
                <span className="flex items-center gap-2">
                  {wasExplored ? (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    </span>
                  ) : (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full border border-black/10" aria-hidden="true" />
                  )}
                  {section.title}
                </span>
                <motion.span
                  animate={{ rotate: isOpen ? 180 : 0 }}
                  transition={{ duration: reduced ? 0 : 0.2 }}
                  aria-hidden="true"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen ? (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: reduced ? 0 : 0.25 }}
                    className="overflow-hidden"
                  >
                    <div className="px-4 pb-4 pl-10 text-sm leading-relaxed text-gray-600">{section.content}</div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </div>
  );
}


// --- Scenario types ---

interface ScenarioOption {
  text: string;
  feedback: string;
  next_step?: string | null;
  correct?: boolean;
}

interface ScenarioStep {
  id: string;
  question: string;
  options: ScenarioOption[];
}

interface ScenarioNormalized {
  prompt?: string;
  steps: ScenarioStep[];
}

function normalizeScenarioData(data?: Record<string, unknown>): ScenarioNormalized {
  if (!data) return { steps: [] };
  // Real shape: { steps: [{ id, question, options: [{ text, feedback, next_step }] }] }
  if (Array.isArray(data.steps)) {
    const steps = (data.steps as { id?: string; question?: string; options?: { text: string; feedback?: string; next_step?: string | null; correct?: boolean }[] }[]).map(
      (s, i) => ({
        id: typeof s.id === "string" ? s.id : `step-${i}`,
        question: typeof s.question === "string" ? s.question : `Decision ${i + 1}`,
        options: (s.options ?? []).map((o) => ({
          text: o.text,
          feedback: typeof o.feedback === "string" ? o.feedback : "",
          next_step: o.next_step ?? null,
          correct: typeof o.correct === "boolean" ? o.correct : undefined,
        })),
      }),
    );
    return { prompt: typeof data.prompt === "string" ? data.prompt : undefined, steps };
  }
  // Legacy shape: { prompt, branches: [{ choice, outcome }] }
  const branches = (data.branches as { choice: string; outcome: string }[]) ?? [];
  const singleStep: ScenarioStep = {
    id: "step-0",
    question: typeof data.prompt === "string" ? data.prompt : "Make your choice:",
    options: branches.map((b) => ({
      text: b.choice,
      feedback: b.outcome,
      next_step: null,
    })),
  };
  return { prompt: undefined, steps: branches.length ? [singleStep] : [] };
}

function Scenario({ data }: { data?: Record<string, unknown> }) {
  const reduced = useReducedMotion();
  const { prompt, steps } = useMemo(() => normalizeScenarioData(data), [data]);
  const stepMap = useMemo(() => {
    const m = new Map<string, ScenarioStep>();
    for (const s of steps) m.set(s.id, s);
    return m;
  }, [steps]);

  const [currentStepId, setCurrentStepId] = useState<string>(steps[0]?.id ?? "");
  const [chosenOption, setChosenOption] = useState<ScenarioOption | null>(null);
  const [history, setHistory] = useState<{ stepId: string; option: ScenarioOption }[]>([]);
  const [complete, setComplete] = useState(false);

  const currentStep = stepMap.get(currentStepId);

  const pickOption = useCallback(
    (option: ScenarioOption) => {
      setChosenOption(option);
    },
    [],
  );

  const advance = useCallback(() => {
    if (!chosenOption || !currentStepId) return;
    setHistory((prev) => [...prev, { stepId: currentStepId, option: chosenOption }]);
    if (chosenOption.next_step && stepMap.has(chosenOption.next_step)) {
      setCurrentStepId(chosenOption.next_step);
      setChosenOption(null);
    } else {
      setComplete(true);
    }
  }, [chosenOption, currentStepId, stepMap]);

  const reset = useCallback(() => {
    setCurrentStepId(steps[0]?.id ?? "");
    setChosenOption(null);
    setHistory([]);
    setComplete(false);
  }, [steps]);

  if (!steps.length) {
    return (
      <div className="rounded-xl border border-black/5 bg-gray-50 p-6 text-center text-sm text-gray-400">
        No scenario data available.
      </div>
    );
  }

  const totalSteps = steps.length;
  const completedSteps = history.length;
  const correctCount = history.filter((h) => h.option.correct === true).length;
  const hasCorrectness = history.some((h) => h.option.correct !== undefined);

  return (
    <div className="overflow-hidden rounded-xl border border-black/5 bg-white" role="region" aria-label="Decision scenario">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-black/5 bg-gray-50 px-4 py-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[var(--brand)]">Scenario</div>
          {prompt ? <p className="mt-0.5 text-sm text-gray-600">{prompt}</p> : null}
        </div>
        <span className="text-xs text-gray-400">
          Step {Math.min(completedSteps + 1, totalSteps)}/{totalSteps}
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-gray-100">
        <motion.div
          className="h-full bg-[var(--brand)]"
          animate={{ width: `${totalSteps ? ((complete ? totalSteps : completedSteps) / totalSteps) * 100 : 0}%` }}
          transition={{ duration: reduced ? 0 : 0.3 }}
        />
      </div>

      <div className="p-4">
        {/* History */}
        {history.length > 0 ? (
          <div className="mb-4 space-y-2">
            {history.map((h, i) => {
              const step = stepMap.get(h.stepId);
              const isCorrect = h.option.correct === true;
              const isWrong = h.option.correct === false;
              return (
                <motion.div
                  key={i}
                  initial={reduced ? { opacity: 1 } : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="rounded-lg bg-gray-50 p-3"
                >
                  <div className="text-xs font-medium text-gray-500">{step?.question}</div>
                  <div className={`mt-1 text-sm font-medium ${isCorrect ? "text-emerald-700" : isWrong ? "text-red-600" : "text-gray-900"}`}>
                    {isCorrect ? (
                      <svg className="mr-1 inline h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20 6L9 17l-5-5" /></svg>
                    ) : isWrong ? (
                      <svg className="mr-1 inline h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12" /></svg>
                    ) : null}
                    {h.option.text}
                  </div>
                  {h.option.feedback ? (
                    <div className="mt-1 text-xs text-gray-500">{h.option.feedback}</div>
                  ) : null}
                </motion.div>
              );
            })}
          </div>
        ) : null}

        {/* Current step or completion */}
        {complete ? (
          <motion.div
            initial={reduced ? { opacity: 1 } : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-center"
            role="status"
            aria-live="polite"
          >
            <div className="text-sm font-semibold text-emerald-700">Scenario Complete</div>
            {hasCorrectness ? (
              <div className="mt-1 text-xs text-emerald-600">
                {correctCount} of {history.length} decisions correct
              </div>
            ) : (
              <div className="mt-1 text-xs text-emerald-600">
                You completed all {history.length} decision{history.length !== 1 ? "s" : ""}
              </div>
            )}
          </motion.div>
        ) : currentStep ? (
          <div>
            <div className="mb-3 text-sm font-semibold text-gray-900">{currentStep.question}</div>
            <div className="space-y-2">
              {currentStep.options.map((option, oi) => {
                const isChosen = chosenOption === option;
                const showFeedback = isChosen && option.feedback;
                const isCorrect = isChosen && option.correct === true;
                const isWrong = isChosen && option.correct === false;
                return (
                  <div key={oi}>
                    <button
                      type="button"
                      onClick={() => pickOption(option)}
                      disabled={chosenOption !== null && chosenOption !== option}
                      className={`w-full rounded-xl border px-4 py-2.5 text-left text-sm font-medium transition ${
                        isCorrect
                          ? "border-emerald-400 bg-emerald-50 text-emerald-700"
                          : isWrong
                            ? "border-red-300 bg-red-50 text-red-700"
                            : isChosen
                              ? "border-[var(--brand)] bg-[var(--brand)]/10 text-[var(--brand)]"
                              : "border-black/10 hover:border-[var(--brand)]/50"
                      } disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]`}
                      aria-pressed={isChosen}
                    >
                      {option.text}
                    </button>
                    <AnimatePresence>
                      {showFeedback ? (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: reduced ? 0 : 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="mt-1.5 rounded-lg bg-gray-50 p-2.5 text-xs text-gray-600" role="alert">
                            {option.feedback}
                          </div>
                        </motion.div>
                      ) : null}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-black/5 bg-gray-50 px-4 py-3">
        <button
          type="button"
          onClick={reset}
          className="rounded-lg border border-black/10 bg-white px-3 py-1.5 text-xs font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
        >
          Restart
        </button>
        {chosenOption && !complete ? (
          <button
            type="button"
            onClick={advance}
            className="rounded-lg bg-[var(--brand)] px-4 py-1.5 text-sm font-medium text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Continue
          </button>
        ) : null}
      </div>
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
  const [useBrowserVoice, setUseBrowserVoice] = useState(!src && !!block.text);
  if (!src && !block.text) return null;

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
      {src && !useBrowserVoice ? (
        <audio
          controls
          className="w-full"
          src={src}
          onLoadedMetadata={(e) => {
            if (block.text && e.currentTarget.duration <= 3.2) {
              e.currentTarget.pause();
              setUseBrowserVoice(true);
            }
          }}
          onError={() => {
            if (block.text) setUseBrowserVoice(true);
          }}
        />
      ) : null}
      {block.text && useBrowserVoice ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="text-xs text-amber-800">
            Generated audio is unavailable. Using your browser voice for this transcript.
          </div>
          <button
            type="button"
            onClick={() => speakWithBrowser(block.text)}
            className="mt-2 rounded-lg bg-[var(--brand)] px-3 py-1.5 text-sm font-medium text-white"
          >
            Play spoken text
          </button>
        </div>
      ) : null}
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
