type Props = {
  progress: number;
};

export default function ScrollProgressBar({ progress }: Props) {
  return (
    <div className="scroll-progress-shell" aria-hidden="true">
      <div
        className="scroll-progress-bar"
        style={{ transform: `scaleX(${Math.max(0, Math.min(1, progress))})` }}
      />
    </div>
  );
}
