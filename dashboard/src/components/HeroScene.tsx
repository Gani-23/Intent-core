import { useEffect, useRef } from "react";

type Star = {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  speed: number;
};

function seedStars(width: number, height: number, count: number): Star[] {
  return Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    radius: 0.6 + Math.random() * 2.1,
    alpha: 0.15 + Math.random() * 0.75,
    speed: 0.12 + Math.random() * 0.45,
  }));
}

export default function HeroScene() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }
    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    let animationFrame = 0;
    let disposed = false;
    let stars: Star[] = [];

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      canvas.width = Math.max(1, Math.floor(bounds.width * dpr));
      canvas.height = Math.max(1, Math.floor(bounds.height * dpr));
      context.setTransform(1, 0, 0, 1, 0, 0);
      context.scale(dpr, dpr);
      stars = seedStars(bounds.width, bounds.height, Math.max(32, Math.floor(bounds.width / 10)));
    };

    const draw = (time: number) => {
      if (disposed) {
        return;
      }
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const t = time * 0.001;

      context.clearRect(0, 0, width, height);

      const background = context.createLinearGradient(0, 0, width, height);
      background.addColorStop(0, "#050816");
      background.addColorStop(0.55, "#081126");
      background.addColorStop(1, "#0f1630");
      context.fillStyle = background;
      context.fillRect(0, 0, width, height);

      for (const star of stars) {
        const pulse = 0.4 + Math.sin(t * star.speed * 3 + star.x * 0.015 + star.y * 0.009) * 0.3;
        context.beginPath();
        context.fillStyle = `rgba(226, 245, 255, ${Math.max(0.12, star.alpha * pulse)})`;
        context.arc(star.x, star.y, star.radius * (0.9 + pulse * 0.4), 0, Math.PI * 2);
        context.fill();
      }

      const glow = context.createRadialGradient(width * 0.54, height * 0.45, 10, width * 0.54, height * 0.45, width * 0.3);
      glow.addColorStop(0, "rgba(145, 244, 255, 0.88)");
      glow.addColorStop(0.25, "rgba(129, 205, 255, 0.32)");
      glow.addColorStop(1, "rgba(129, 205, 255, 0)");
      context.fillStyle = glow;
      context.fillRect(0, 0, width, height);

      const centerX = width * 0.53;
      const centerY = height * 0.49;
      const mainRadius = Math.min(width, height) * 0.17;
      context.save();
      context.translate(centerX, centerY);
      context.rotate(t * 0.18);
      context.beginPath();
      for (let step = 0; step <= 120; step += 1) {
        const angle = (step / 120) * Math.PI * 2;
        const wave = 1 + Math.sin(angle * 3 + t * 1.4) * 0.14 + Math.cos(angle * 5 - t) * 0.06;
        const x = Math.cos(angle) * mainRadius * wave;
        const y = Math.sin(angle) * mainRadius * wave;
        if (step === 0) {
          context.moveTo(x, y);
        } else {
          context.lineTo(x, y);
        }
      }
      context.closePath();
      const orbGradient = context.createLinearGradient(-mainRadius, -mainRadius, mainRadius, mainRadius);
      orbGradient.addColorStop(0, "rgba(139, 242, 255, 0.92)");
      orbGradient.addColorStop(1, "rgba(184, 235, 255, 0.72)");
      context.fillStyle = orbGradient;
      context.fill();
      context.restore();

      const rings = [
        { rx: width * 0.33, ry: height * 0.13, rotation: t * 0.45, color: "rgba(223, 247, 244, 0.95)", lineWidth: 6 },
        { rx: width * 0.18, ry: height * 0.31, rotation: t * -0.35 + 0.8, color: "rgba(229, 182, 245, 0.92)", lineWidth: 7 },
        { rx: width * 0.22, ry: height * 0.41, rotation: t * 0.24 + 1.6, color: "rgba(218, 255, 246, 0.88)", lineWidth: 5 },
      ];

      for (const ring of rings) {
        context.save();
        context.translate(centerX, centerY);
        context.rotate(ring.rotation);
        context.beginPath();
        context.ellipse(0, 0, ring.rx, ring.ry, 0, 0, Math.PI * 2);
        context.strokeStyle = ring.color;
        context.lineWidth = ring.lineWidth;
        context.shadowColor = ring.color;
        context.shadowBlur = 18;
        context.stroke();
        context.restore();
      }

      const lineGradient = context.createLinearGradient(width * 0.08, height * 0.66, width * 0.92, height * 0.34);
      lineGradient.addColorStop(0, "rgba(221, 250, 255, 0)");
      lineGradient.addColorStop(0.18, "rgba(221, 250, 255, 0.98)");
      lineGradient.addColorStop(0.82, "rgba(221, 250, 255, 0.98)");
      lineGradient.addColorStop(1, "rgba(221, 250, 255, 0)");
      context.strokeStyle = lineGradient;
      context.lineWidth = 7;
      context.beginPath();
      context.moveTo(width * 0.06, height * 0.67);
      context.quadraticCurveTo(width * 0.46, height * 0.51, width * 0.94, height * 0.36);
      context.stroke();

      animationFrame = window.requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    animationFrame = window.requestAnimationFrame(draw);

    return () => {
      disposed = true;
      window.removeEventListener("resize", resize);
      window.cancelAnimationFrame(animationFrame);
    };
  }, []);

  return (
    <div className="hero-canvas hero-lite-scene">
      <canvas aria-hidden="true" className="hero-lite-canvas" ref={canvasRef} />
      <div className="hero-lite-grid" />
      <div className="hero-lite-vignette" />
    </div>
  );
}
