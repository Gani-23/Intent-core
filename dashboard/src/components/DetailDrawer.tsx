import type { ReactNode } from "react";

type Props = {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
};

export default function DetailDrawer({ open, title, subtitle, onClose, children }: Props) {
  return (
    <div className={`sheet-backdrop ${open ? "open" : ""}`} onClick={onClose}>
      <aside className={`detail-drawer ${open ? "open" : ""}`} onClick={(event) => event.stopPropagation()}>
        <div className="sheet-header">
          <div>
            {subtitle ? <span className="eyebrow">{subtitle}</span> : null}
            <h3>{title}</h3>
          </div>
          <button className="ghost-button" onClick={onClose} type="button">
            Close
          </button>
        </div>
        <div className="detail-drawer-body">{children}</div>
      </aside>
    </div>
  );
}
