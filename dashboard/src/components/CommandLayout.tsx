import type { PropsWithChildren, ReactNode } from "react";
import { Link } from "react-router-dom";

import ApiConfigSheet from "./ApiConfigSheet";
import NavBar from "./NavBar";
import ScrollMotionLayer from "./ScrollMotionLayer";
import { useScrollDriftMotion } from "../hooks/useScrollDriftMotion";

type Props = PropsWithChildren<{
  title: string;
  eyebrow: string;
  description: string;
  configOpen: boolean;
  onOpenConfig: () => void;
  onCloseConfig: () => void;
  actions?: ReactNode;
  meta?: ReactNode;
}>;

export default function CommandLayout({
  title,
  eyebrow,
  description,
  configOpen,
  onOpenConfig,
  onCloseConfig,
  actions,
  meta,
  children,
}: Props) {
  useScrollDriftMotion("command");

  return (
    <div className="app-shell command-page">
      <div className="ambient-background command" />
      <ScrollMotionLayer tone="command" />
      <NavBar onOpenConfig={onOpenConfig} />
      <main>
        <section className="subpage-hero" data-reveal>
          <div className="subpage-copy">
            <span className="eyebrow">{eyebrow}</span>
            <h1>{title}</h1>
            <p>{description}</p>
            <div className="hero-actions">
              <Link className="ghost-button" to="/command">
                Back to Command Center
              </Link>
              {actions}
            </div>
            {meta ? <div className="command-meta">{meta}</div> : null}
          </div>
        </section>
        {children}
      </main>
      <ApiConfigSheet open={configOpen} onClose={onCloseConfig} />
    </div>
  );
}
