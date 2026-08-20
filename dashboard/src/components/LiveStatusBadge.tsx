type Props = {
  loading: boolean;
  actionState?: string | null;
  idleLabel?: string;
};

export default function LiveStatusBadge({
  loading,
  actionState,
  idleLabel = "Live polling every 15s",
}: Props) {
  const live = !loading && !actionState;
  return (
    <span className={`live-status-badge ${live ? "is-live" : "is-busy"}`}>
      <span className="live-status-pulse" />
      <span>{actionState || (loading ? "Loading live surface..." : idleLabel)}</span>
    </span>
  );
}
