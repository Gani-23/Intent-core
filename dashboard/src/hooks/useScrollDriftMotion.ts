import { useEffect } from "react";

export function useScrollDriftMotion(scope = "global") {
  useEffect(() => {
    let frame = 0;

    const root = document.documentElement;

    const update = () => {
      frame = 0;
      const scrollTop = window.scrollY || window.pageYOffset;
      const maxScroll = Math.max(document.body.scrollHeight - window.innerHeight, 1);
      const progress = Math.min(scrollTop / maxScroll, 1);
      const driftY = scrollTop * 0.16;
      const driftX = Math.sin(scrollTop * 0.0028) * 18;
      const orbit = Math.cos(scrollTop * 0.0017) * 24;

      root.style.setProperty("--scroll-progress-live", progress.toFixed(4));
      root.style.setProperty("--scroll-drift-y", `${driftY.toFixed(2)}px`);
      root.style.setProperty("--scroll-drift-x", `${driftX.toFixed(2)}px`);
      root.style.setProperty("--scroll-orbit", `${orbit.toFixed(2)}px`);
      root.setAttribute("data-scroll-scope", scope);
    };

    const onScroll = () => {
      if (frame) {
        return;
      }
      frame = window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);

    return () => {
      if (frame) {
        window.cancelAnimationFrame(frame);
      }
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      root.removeAttribute("data-scroll-scope");
    };
  }, [scope]);
}
