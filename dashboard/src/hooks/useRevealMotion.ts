import { useEffect } from "react";
import { animate, stagger } from "animejs";

export function useRevealMotion(scopeSelector: string, deps: unknown[] = []) {
  useEffect(() => {
    const root = document.querySelector(scopeSelector);
    if (!root) {
      return;
    }

    const htmlRoot = root as HTMLElement;
    if (htmlRoot.dataset.motionBound === "true") {
      return;
    }
    htmlRoot.dataset.motionBound = "true";

    const elements = Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]"));

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }
          const target = entry.target as HTMLElement;
          if (target.dataset.revealed === "true") {
            observer.unobserve(target);
            return;
          }
          target.dataset.revealed = "true";
          animate(target, {
            opacity: [0, 1],
            translateY: [40, 0],
            scale: [0.98, 1],
            ease: "outExpo",
            duration: 1100,
          });
          observer.unobserve(target);
        });
      },
      { threshold: 0.18 },
    );

    elements.forEach((element) => {
      if (element.dataset.revealed !== "true") {
        observer.observe(element);
      }
    });

    const staggerGroup = root.querySelectorAll<HTMLElement>("[data-stagger-group] > *");
    if (staggerGroup.length) {
      animate(staggerGroup, {
        opacity: [0, 1],
        translateY: [28, 0],
        delay: stagger(85),
        duration: 900,
        ease: "outQuad",
      });
      staggerGroup.forEach((element) => {
        element.dataset.revealed = "true";
      });
    }

    return () => observer.disconnect();
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
}
