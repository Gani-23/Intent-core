import { statusTone, titleCase } from "../lib/format";

type Props = {
  label: string;
  value?: string | boolean | null;
};

export default function StatusPill({ label, value }: Props) {
  const text =
    typeof value === "boolean"
      ? value
        ? "passed"
        : "blocked"
      : value
        ? titleCase(String(value))
        : "Unknown";

  return (
    <div className={`status-pill tone-${statusTone(String(value ?? ""))}`}>
      <span>{label}</span>
      <strong>{text}</strong>
    </div>
  );
}
