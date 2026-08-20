type Props = {
  tone?: "landing" | "command";
};

export default function ScrollMotionLayer({ tone = "landing" }: Props) {
  return (
    <div className={`scroll-motion-layer ${tone}`} aria-hidden="true">
      <span className="drift-orb orb-a" />
      <span className="drift-orb orb-b" />
      <span className="drift-orb orb-c" />
      <span className="drift-ring ring-a" />
      <span className="drift-ring ring-b" />
      <span className="drift-line line-a" />
      <span className="drift-line line-b" />
      <span className="drift-grid-blur" />
    </div>
  );
}
