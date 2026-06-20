import { useEffect, useMemo, useRef, useState } from "react";
import { Chart, registerables } from "chart.js";
import type {
  Block,
  ChartSeries,
  DialogueSpeaker,
  DragPair,
  FlipCard,
  Hotspot,
} from "./types";

Chart.register(...registerables);

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w.charAt(0))
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function Avatar({ speaker, active }: { speaker: DialogueSpeaker; active: boolean }) {
  return (
    <div className={`avatar${active ? " active" : ""}`}>
      {speaker.avatarUrl ? (
        <img src={speaker.avatarUrl} alt={speaker.name} />
      ) : (
        <span>{initials(speaker.name)}</span>
      )}
    </div>
  );
}

/** Click-to-reveal conversation: each click reveals the next line; new speakers
 * fade in as they enter the conversation. */
function DialogueBlock({
  speakers,
  steps,
  title,
}: {
  speakers: DialogueSpeaker[];
  steps: { speaker: string; text: string }[];
  title?: string;
}) {
  const [revealed, setRevealed] = useState(1);
  const byName = useMemo(() => {
    const m: Record<string, DialogueSpeaker> = {};
    speakers.forEach((s) => (m[s.name] = s));
    return m;
  }, [speakers]);
  const shown = steps.slice(0, revealed);
  const done = revealed >= steps.length;

  return (
    <div className="dialogue">
      {title ? <div className="dialogue-title">{title}</div> : null}
      <div className="dialogue-stage">
        {shown.map((step, i) => {
          const sp = byName[step.speaker] || { name: step.speaker };
          const isLast = i === shown.length - 1;
          return (
            <div key={i} className={`dialogue-row${i % 2 ? " right" : ""}`}>
              <Avatar speaker={sp} active={isLast} />
              <div className="bubble">
                <span className="bubble-name">{sp.name}</span>
                {step.text}
              </div>
            </div>
          );
        })}
      </div>
      {!done ? (
        <button className="btn-soft pulse" onClick={() => setRevealed((r) => r + 1)}>
          {revealed === 0 ? "Start conversation" : "Tap to continue ›"}
        </button>
      ) : (
        <div className="dialogue-end">End of conversation ✓</div>
      )}
    </div>
  );
}

/** Drag a definition onto its matching term. */
function DragDropBlock({ pairs, instructions }: { pairs: DragPair[]; instructions?: string }) {
  const matches = useMemo(() => shuffle(pairs.map((p) => p.match)), [pairs]);
  const [placed, setPlaced] = useState<Record<string, string>>({});
  const [dragging, setDragging] = useState<string | null>(null);

  const usedMatches = new Set(Object.values(placed));
  const allCorrect =
    pairs.length > 0 && pairs.every((p) => placed[p.term] === p.match);

  const drop = (term: string) => {
    if (!dragging) return;
    setPlaced((prev) => {
      const next = { ...prev };
      for (const k of Object.keys(next)) if (next[k] === dragging) delete next[k];
      next[term] = dragging;
      return next;
    });
    setDragging(null);
  };

  return (
    <div className="exercise">
      {instructions ? <p className="exercise-instr">{instructions}</p> : null}
      <div className="dragdrop">
        <div className="drop-col">
          {pairs.map((p) => {
            const val = placed[p.term];
            const state = val ? (val === p.match ? " ok" : " bad") : "";
            return (
              <div key={p.term} className="drop-row">
                <span className="term">{p.term}</span>
                <div
                  className={`drop-zone${state}`}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => drop(p.term)}
                  onClick={() => val && setPlaced((pr) => {
                    const n = { ...pr };
                    delete n[p.term];
                    return n;
                  })}
                >
                  {val || "Drop here"}
                </div>
              </div>
            );
          })}
        </div>
        <div className="bank">
          {matches.map((m) => (
            <div
              key={m}
              className={`chip${usedMatches.has(m) ? " used" : ""}`}
              draggable={!usedMatches.has(m)}
              onDragStart={() => setDragging(m)}
            >
              {m}
            </div>
          ))}
        </div>
      </div>
      {allCorrect ? <div className="exercise-done">Nice — all matched! ✓</div> : null}
    </div>
  );
}

/** Drag items into the correct sequence. */
function OrderingBlock({ items, instructions }: { items: string[]; instructions?: string }) {
  const [order, setOrder] = useState<string[]>(() => shuffle(items));
  const [drag, setDrag] = useState<number | null>(null);
  const correct = order.every((it, i) => it === items[i]);

  const onDrop = (target: number) => {
    if (drag === null || drag === target) return;
    setOrder((prev) => {
      const next = [...prev];
      const [moved] = next.splice(drag, 1);
      next.splice(target, 0, moved);
      return next;
    });
    setDrag(null);
  };

  return (
    <div className="exercise">
      {instructions ? <p className="exercise-instr">{instructions}</p> : null}
      <ol className="ordering">
        {order.map((it, i) => (
          <li
            key={it}
            draggable
            onDragStart={() => setDrag(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => onDrop(i)}
            className={correct ? "ok" : ""}
          >
            <span className="grip">⋮⋮</span>
            {it}
          </li>
        ))}
      </ol>
      {correct ? <div className="exercise-done">Correct order! ✓</div> : null}
    </div>
  );
}

/** Clickable markers over an image reveal explanatory text. */
function HotspotBlock({
  spots,
  imageUrl,
  instructions,
}: {
  spots: Hotspot[];
  imageUrl?: string;
  instructions?: string;
}) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <div className="exercise">
      {instructions ? <p className="exercise-instr">{instructions}</p> : null}
      <div className="hotspot">
        {imageUrl ? (
          <img src={imageUrl} alt="" />
        ) : (
          <div className="hotspot-placeholder">Diagram</div>
        )}
        {spots.map((s, i) => (
          <button
            key={i}
            className={`spot${open === i ? " open" : ""}`}
            style={{ left: `${s.x}%`, top: `${s.y}%` }}
            onClick={() => setOpen(open === i ? null : i)}
          >
            {i + 1}
            {open === i ? (
              <span className="spot-pop">
                <strong>{s.label}</strong>
                {s.text}
              </span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}

function FlipCardsBlock({ cards, title }: { cards: FlipCard[]; title?: string }) {
  const [flipped, setFlipped] = useState<Set<number>>(new Set());
  const toggle = (i: number) =>
    setFlipped((prev) => {
      const n = new Set(prev);
      n.has(i) ? n.delete(i) : n.add(i);
      return n;
    });
  return (
    <div className="exercise">
      {title ? <p className="exercise-instr">{title}</p> : null}
      <div className="flipcards">
        {cards.map((c, i) => (
          <button
            key={i}
            className={`flipcard${flipped.has(i) ? " flipped" : ""}`}
            onClick={() => toggle(i)}
          >
            <span className="flip-inner">
              <span className="flip-front">{c.front}</span>
              <span className="flip-back">{c.back}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

const CHART_PALETTE = [
  "#5145E5",
  "#FF5C38",
  "#10B981",
  "#F59E0B",
  "#3B82F6",
  "#EC4899",
];

function ChartBlock({
  chartType,
  labels,
  series,
  title,
}: {
  chartType?: string;
  labels: string[];
  series: ChartSeries[];
  title?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!canvasRef.current) return;
    const type = (chartType || "bar") as "bar" | "line" | "pie" | "doughnut" | "radar";
    const pie = type === "pie" || type === "doughnut";
    const chart = new Chart(canvasRef.current, {
      type,
      data: {
        labels,
        datasets: series.map((s, i) => ({
          label: s.label,
          data: s.data,
          backgroundColor: pie
            ? labels.map((_, j) => CHART_PALETTE[j % CHART_PALETTE.length])
            : CHART_PALETTE[i % CHART_PALETTE.length],
          borderColor: CHART_PALETTE[i % CHART_PALETTE.length],
          borderWidth: 2,
          fill: type === "radar" || type === "line" ? false : undefined,
          tension: 0.3,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: series.length > 1 || pie } },
      },
    });
    return () => chart.destroy();
  }, [chartType, labels, series]);

  return (
    <div className="chart-block">
      {title ? <p className="exercise-instr">{title}</p> : null}
      <div className="chart-canvas-wrap">
        <canvas ref={canvasRef} />
      </div>
    </div>
  );
}

function ImagePlaceholder({ alt }: { alt?: string }) {
  return (
    <div className="img-placeholder" role="img" aria-label={alt || "illustration"}>
      <svg viewBox="0 0 64 64" width="48" height="48" aria-hidden="true">
        <rect x="6" y="10" width="52" height="40" rx="4" fill="none" stroke="currentColor" strokeWidth="3" />
        <circle cx="22" cy="26" r="5" fill="currentColor" />
        <path d="M12 46l14-14 10 10 8-7 8 11z" fill="currentColor" />
      </svg>
      <span>{alt || "Illustration"}</span>
    </div>
  );
}

export function BlockView({ block, id }: { block: Block; id: string }) {
  switch (block.type) {
    case "heading":
      return <h2 data-block-id={id} style={{ marginTop: 28 }}>{block.text}</h2>;
    case "paragraph":
      return <p data-block-id={id} className="block-p">{block.text}</p>;
    case "list":
      return (
        <ul data-block-id={id} className="block-list">
          {block.items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      );
    case "callout":
      return (
        <div data-block-id={id} className={`callout ${block.variant || "info"}`}>
          {block.text}
        </div>
      );
    case "code":
      return <pre data-block-id={id} className="code">{block.text}</pre>;
    case "image":
      return (
        <figure data-block-id={id} className="media-figure">
          {block.url ? (
            <img src={block.url} alt={block.alt || ""} loading="lazy" />
          ) : (
            <ImagePlaceholder alt={block.alt} />
          )}
          {block.caption ? <figcaption>{block.caption}</figcaption> : null}
        </figure>
      );
    case "video":
      return (
        <figure data-block-id={id} className="media-figure">
          {block.url ? (
            <video src={block.url} poster={block.poster} controls playsInline />
          ) : (
            <ImagePlaceholder alt={block.caption || "Video"} />
          )}
          {block.caption ? <figcaption>{block.caption}</figcaption> : null}
        </figure>
      );
    case "audio":
      return (
        <div data-block-id={id} className="audio-block">
          <span className="audio-icon" aria-hidden="true">►</span>
          <div className="audio-body">
            {block.caption ? <span className="audio-caption">{block.caption}</span> : null}
            {block.url ? (
              <audio src={block.url} controls />
            ) : (
              <span className="audio-pending">{block.say}</span>
            )}
          </div>
        </div>
      );
    case "dialogue":
      return (
        <div data-block-id={id}>
          <DialogueBlock title={block.title} speakers={block.speakers} steps={block.steps} />
        </div>
      );
    case "dragdrop":
      return (
        <div data-block-id={id}>
          <DragDropBlock pairs={block.pairs} instructions={block.instructions} />
        </div>
      );
    case "ordering":
      return (
        <div data-block-id={id}>
          <OrderingBlock items={block.items} instructions={block.instructions} />
        </div>
      );
    case "hotspot":
      return (
        <div data-block-id={id}>
          <HotspotBlock
            spots={block.spots}
            imageUrl={block.imageUrl}
            instructions={block.instructions}
          />
        </div>
      );
    case "flipcards":
      return (
        <div data-block-id={id}>
          <FlipCardsBlock cards={block.cards} title={block.title} />
        </div>
      );
    case "chart":
      return (
        <div data-block-id={id}>
          <ChartBlock
            chartType={block.chartType}
            labels={block.labels}
            series={block.series}
            title={block.title}
          />
        </div>
      );
    default:
      return null;
  }
}
