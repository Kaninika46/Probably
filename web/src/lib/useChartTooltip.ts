/**
 * web/src/lib/useChartTooltip.ts
 * Keeps Recharts tooltips from getting stuck on screen.
 *
 * Recharts hides its tooltip on mouse-leave. When the page is scrolled with the wheel, the
 * content moves under a pointer that has not moved, so no mouse-leave fires and the tooltip
 * stays drawn over the chart. This hook tracks which chart on a page is hovered and forces
 * every tooltip hidden as soon as anything scrolls.
 */

import { useEffect, useState } from "react";

export function useChartTooltip() {
  const [hoveredChart, setHoveredChart] = useState<string | null>(null);

  useEffect(() => {
    const hide = () => setHoveredChart(null);
    // capture: true also catches scrolling inside nested scroll containers
    window.addEventListener("scroll", hide, { capture: true, passive: true });
    return () => window.removeEventListener("scroll", hide, { capture: true });
  }, []);

  return {
    /** Spread onto a Recharts chart: <BarChart {...tooltip.bind("sizes")} …> */
    bind: (chartId: string) => ({
      onMouseMove: () => setHoveredChart(chartId),
      onMouseLeave: () => setHoveredChart(null),
    }),
    /** Pass to <Tooltip active={…}>: false forces it hidden, undefined lets Recharts decide. */
    activeFor: (chartId: string) => (hoveredChart === chartId ? undefined : false),
  };
}
