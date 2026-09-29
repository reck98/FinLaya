import React, { useState, useRef } from "react";
import type { PnLPoint } from "../types/dashboard";
import { formatCurrency } from "../utils/formatters";

interface Props {
  history: PnLPoint[];
  currentPnl: number;
}

export const PnLChart: React.FC<Props> = ({ history, currentPnl }) => {
  const [hoveredPoint, setHoveredPoint] = useState<PnLPoint | null>(null);
  const [hoverX, setHoverX] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const points =
    history.length >= 2
      ? history
      : [
          { timestamp: "09:27:00", pnl: 0 },
          { timestamp: "15:13:00", pnl: currentPnl },
        ];

  // Calculate bounds
  const pnlValues = points.map((p) => p.pnl);
  let min = Math.min(0, ...pnlValues);
  let max = Math.max(0, ...pnlValues);

  // Add margin
  const spread = max - min || 1000;
  const padding = spread * 0.15;
  min -= padding;
  max += padding;

  const width = 800;
  const height = 180;
  const marginLeft = 60;
  const marginRight = 20;
  const marginTop = 20;
  const marginBottom = 25;

  const chartWidth = width - marginLeft - marginRight;
  const chartHeight = height - marginTop - marginBottom;

  const getY = (val: number) => {
    return marginTop + chartHeight - ((val - min) / (max - min)) * chartHeight;
  };

  const getX = (idx: number) => {
    return marginLeft + (idx / (points.length - 1)) * chartWidth;
  };

  const yZero = getY(0);

  // Build path
  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${getX(i).toFixed(1)} ${getY(p.pnl).toFixed(1)}`)
    .join(" ");

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const scaledX = (clientX / rect.width) * width;

    if (scaledX >= marginLeft && scaledX <= width - marginRight) {
      const pct = (scaledX - marginLeft) / chartWidth;
      const idx = Math.min(
        points.length - 1,
        Math.max(0, Math.round(pct * (points.length - 1)))
      );
      setHoveredPoint(points[idx]);
      setHoverX(getX(idx));
    }
  };

  const handleMouseLeave = () => {
    setHoveredPoint(null);
    setHoverX(null);
  };

  const isCurrentPositive = currentPnl >= 0;
  const strokeColor = isCurrentPositive ? "#34d399" : "#fb7185";

  return (
    <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3.5 flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-2 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium tracking-wider text-zinc-400 uppercase">
            Intraday Cumulative P&L
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">09:27 → 15:13</span>
        </div>
        <div className="font-mono text-xs font-semibold tabular-nums">
          <span className={isCurrentPositive ? "text-emerald-400" : "text-rose-400"}>
            {formatCurrency(currentPnl)}
          </span>
        </div>
      </div>

      <div className="relative flex-1 w-full min-h-[160px]">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full cursor-crosshair overflow-visible select-none"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Y Axis Grid Lines */}
          <line
            x1={marginLeft}
            y1={marginTop}
            x2={width - marginRight}
            y2={marginTop}
            stroke="#27272a"
            strokeDasharray="2 2"
          />
          <text
            x={marginLeft - 8}
            y={marginTop + 4}
            textAnchor="end"
            fontSize="10"
            className="fill-zinc-500 font-mono"
          >
            {formatCurrency(max, false)}
          </text>

          {/* Zero Line (Dashed) */}
          <line
            x1={marginLeft}
            y1={yZero}
            x2={width - marginRight}
            y2={yZero}
            stroke="#52525b"
            strokeDasharray="4 3"
            strokeWidth="1.2"
          />
          <text
            x={marginLeft - 8}
            y={yZero + 3}
            textAnchor="end"
            fontSize="10"
            className="fill-zinc-400 font-mono font-medium"
          >
            ₹0.00
          </text>

          <line
            x1={marginLeft}
            y1={height - marginBottom}
            x2={width - marginRight}
            y2={height - marginBottom}
            stroke="#27272a"
            strokeDasharray="2 2"
          />
          <text
            x={marginLeft - 8}
            y={height - marginBottom + 3}
            textAnchor="end"
            fontSize="10"
            className="fill-zinc-500 font-mono"
          >
            {formatCurrency(min, false)}
          </text>

          {/* P&L Polyline */}
          <path
            d={pathD}
            fill="none"
            stroke={strokeColor}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* X Axis Time Labels */}
          <text
            x={marginLeft}
            y={height - 6}
            textAnchor="start"
            fontSize="10"
            className="fill-zinc-500 font-mono"
          >
            {points[0]?.timestamp.substring(0, 5) || "09:27"}
          </text>
          <text
            x={width - marginRight}
            y={height - 6}
            textAnchor="end"
            fontSize="10"
            className="fill-zinc-500 font-mono"
          >
            {points[points.length - 1]?.timestamp.substring(0, 5) || "15:13"}
          </text>

          {/* Hover Crosshair */}
          {hoverX !== null && hoveredPoint && (
            <g>
              <line
                x1={hoverX}
                y1={marginTop}
                x2={hoverX}
                y2={height - marginBottom}
                stroke="#a1a1aa"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <circle
                cx={hoverX}
                cy={getY(hoveredPoint.pnl)}
                r="3.5"
                fill={hoveredPoint.pnl >= 0 ? "#34d399" : "#fb7185"}
                stroke="#09090b"
                strokeWidth="1.5"
              />
            </g>
          )}
        </svg>

        {/* Floating Tooltip */}
        {hoveredPoint && (
          <div
            className="absolute top-2 right-4 bg-zinc-950/95 border border-zinc-700/80 rounded px-2.5 py-1 text-[11px] font-mono shadow-lg pointer-events-none"
          >
            <span className="text-zinc-400 mr-2">{hoveredPoint.timestamp}</span>
            <span
              className={`font-semibold tabular-nums ${
                hoveredPoint.pnl >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {formatCurrency(hoveredPoint.pnl)}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
