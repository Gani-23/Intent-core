import { useEffect, useRef, useState } from "react";
import { animate } from "animejs";

type Props = {
  label: string;
  value: number | string;
  caption?: string;
  tone?: "good" | "warn" | "bad" | "neutral";
};

export default function MetricCard({ label, value, caption, tone = "neutral" }: Props) {
  const numberRef = useRef<HTMLDivElement | null>(null);
  const [renderValue, setRenderValue] = useState(typeof value === "number" ? 0 : value);

  useEffect(() => {
    if (typeof value !== "number" || !numberRef.current) {
      setRenderValue(value);
      return;
    }
    const state = { value: 0 };
    const animation = animate(state, {
      value,
      duration: 1200,
      ease: "outExpo",
      onUpdate: () => setRenderValue(Math.round(state.value)),
    });
    return () => {
      animation.cancel();
    };
  }, [value]);

  return (
    <article className={`metric-card tone-${tone}`} data-reveal>
      <span className="metric-label">{label}</span>
      <div className="metric-value" ref={numberRef}>
        {renderValue}
      </div>
      {caption ? <p className="metric-caption">{caption}</p> : null}
    </article>
  );
}
