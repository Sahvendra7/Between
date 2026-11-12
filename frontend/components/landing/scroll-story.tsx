"use client";
import { useEffect, useRef, useState } from "react";
import { STAGES, StageVisual } from "./stages";

/**
 * The signature moment: one clause travelling from the agreement to a verified payment as you scroll.
 * Native scroll only: an IntersectionObserver picks the step in the middle of the screen, CSS does the crossfade.
 */
export function ScrollStory() {
  const [active, setActive] = useState(0);
  const steps = useRef<(HTMLLIElement | null)[]>([]);
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setActive(Number((e.target as HTMLElement).dataset.i))),
      { rootMargin: "-45% 0px -45% 0px" },
    );
    steps.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);
  return (
    <div className="story relative grid gap-10 lg:grid-cols-[1fr_1.05fr] lg:gap-16">
      <ol className="m-0 list-none p-0">
        {STAGES.map((s, i) => (
          <li key={s.key} data-i={i} ref={(el) => { steps.current[i] = el; }} className="grid content-center gap-3 py-6 lg:min-h-[78vh] lg:py-0">
            <p className="m-0 text-sm font-bold text-act">{i + 1} of 4</p>
            <h3 className="display m-0 text-[clamp(1.9rem,3.4vw,2.8rem)]">{s.title}</h3>
            <p className="lede m-0">{s.body}</p>
            <div className="mt-4 lg:hidden"><StageVisual stage={i} /></div>
          </li>
        ))}
      </ol>
      <div className="hidden lg:block">
        <div className="sticky top-[14vh] grid gap-6">
          <div className="flex items-center gap-3" aria-hidden>
            {STAGES.map((s, i) => <span key={s.key} className={`h-1.5 flex-1 rounded-full transition-colors duration-300 ${i <= active ? "bg-act" : "bg-sunk"}`} />)}
          </div>
          <div className="min-h-[420px]">
            <div key={active} className="story-stage"><StageVisual stage={active} /></div>
          </div>
          <p className="m-0 text-sm text-ink-2" aria-live="polite">Illustration with the synthetic sample agreement. {STAGES[active].title}.</p>
        </div>
      </div>
      <div aria-hidden className="story-progress absolute top-0 bottom-0 -left-5 hidden w-px origin-top bg-act/50 lg:block" />
    </div>
  );
}
