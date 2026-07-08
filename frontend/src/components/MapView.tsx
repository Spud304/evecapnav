import { useEffect, useRef, useState } from 'react';
import { select } from 'd3-selection';
import 'd3-transition'; // extends Selection.prototype with .transition()
import { zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior } from 'd3-zoom';
import { quadtree, type Quadtree } from 'd3-quadtree';
import { getMapData } from '../api';
import { getSovColor as sovColor } from '../utils/sovColors';
import type { MapData, MapSystem, RouteStep } from '../types';

interface Props {
  route?: RouteStep[];
  /** Pan/zoom to this system when the value changes (e.g. on origin/dest pick). */
  focusSystemId?: number | null;
}

const CANVAS_W = 1040;
const CANVAS_H = 700;
const PADDING = 24;

function secColor(sec: number): string {
  if (sec >= 0.45) return '#4f8df0';
  if (sec >= 0.0) return '#e5b03d';
  return '#c14343';
}

interface Projection {
  scale: number;
  offsetX: number;
  offsetY: number;
}

function computeProjection(systems: MapSystem[]): Projection {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const s of systems) {
    if (s.x < minX) minX = s.x;
    if (s.x > maxX) maxX = s.x;
    if (s.y < minY) minY = s.y;
    if (s.y > maxY) maxY = s.y;
  }
  const spanX = maxX - minX || 1;
  const spanY = maxY - minY || 1;
  const scale = Math.min(
    (CANVAS_W - PADDING * 2) / spanX,
    (CANVAS_H - PADDING * 2) / spanY,
  );
  return {
    scale,
    offsetX: (CANVAS_W - spanX * scale) / 2 - minX * scale,
    offsetY: (CANVAS_H - spanY * scale) / 2 - minY * scale,
  };
}

/** Compute the dominant sov holder name per region from the system list. */
function computeDominantSovByRegion(systems: MapSystem[]): Map<number, string> {
  const counts = new Map<number, Map<string, number>>();
  for (const s of systems) {
    if (!s.region_id || !s.sov) continue;
    let inner = counts.get(s.region_id);
    if (!inner) {
      inner = new Map();
      counts.set(s.region_id, inner);
    }
    inner.set(s.sov, (inner.get(s.sov) || 0) + 1);
  }
  const out = new Map<number, string>();
  for (const [rid, inner] of counts) {
    let best = '';
    let bestCount = 0;
    for (const [sov, c] of inner) {
      if (c > bestCount) {
        best = sov;
        bestCount = c;
      }
    }
    if (best) out.set(rid, best);
  }
  return out;
}

/** Compute a zoom transform that fits the given canvas-space bbox. */
function fitTransform(
  minX: number,
  maxX: number,
  minY: number,
  maxY: number,
  paddingPx: number,
  maxScale: number,
): { k: number; tx: number; ty: number } {
  const w = Math.max(maxX - minX, 1);
  const h = Math.max(maxY - minY, 1);
  const k = Math.min(
    (CANVAS_W - paddingPx * 2) / w,
    (CANVAS_H - paddingPx * 2) / h,
    maxScale,
  );
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  return {
    k,
    tx: CANVAS_W / 2 - cx * k,
    ty: CANVAS_H / 2 - cy * k,
  };
}

export default function MapView({ route, focusSystemId }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [data, setData] = useState<MapData | null>(null);
  const [error, setError] = useState('');
  const [hovered, setHovered] = useState<MapSystem | null>(null);
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });

  // Refs that don't trigger re-render — render() reads them on each frame.
  const transformRef = useRef({ k: 1, x: 0, y: 0 });
  const projectionRef = useRef<Projection | null>(null);
  const quadtreeRef = useRef<Quadtree<MapSystem> | null>(null);
  const systemByIdRef = useRef<Map<number, MapSystem> | null>(null);
  const regionSovColorRef = useRef<Map<number, string>>(new Map());
  const zoomBehaviorRef = useRef<ZoomBehavior<HTMLCanvasElement, unknown> | null>(
    null,
  );
  // Props that may change mid-zoom: route the d3-zoom callback through this
  // ref so it always reads the latest values instead of a stale closure.
  // (Fixes: route line vanished while panning/zooming until you un-hovered.)
  const routeRef = useRef(route);
  const hoveredRef = useRef(hovered);
  useEffect(() => {
    routeRef.current = route;
  }, [route]);
  useEffect(() => {
    hoveredRef.current = hovered;
  }, [hovered]);

  // Fetch map data once.
  useEffect(() => {
    let cancelled = false;
    getMapData()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e) => {
        if (!cancelled) setError(`Failed to load map data: ${e}`);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Set up projection, quadtree, dominant-sov, and d3-zoom once data arrives.
  useEffect(() => {
    if (!data || !canvasRef.current) return;
    const canvas = canvasRef.current;

    const projection = computeProjection(data.systems);
    projectionRef.current = projection;

    const tree = quadtree<MapSystem>()
      .x((s) => s.x * projection.scale + projection.offsetX)
      .y((s) => s.y * projection.scale + projection.offsetY)
      .addAll(data.systems);
    quadtreeRef.current = tree;
    systemByIdRef.current = new Map(data.systems.map((s) => [s.id, s]));

    // Region-label tint = color of dominant sov holder in that region.
    const dominantSov = computeDominantSovByRegion(data.systems);
    const tints = new Map<number, string>();
    for (const [rid, name] of dominantSov) {
      const c = sovColor(name);
      if (c) tints.set(rid, c);
    }
    regionSovColorRef.current = tints;

    transformRef.current = { k: 1, x: 0, y: 0 };

    const zoomBehavior = zoom<HTMLCanvasElement, unknown>()
      .scaleExtent([0.5, 60])
      .on('zoom', (event: D3ZoomEvent<HTMLCanvasElement, unknown>) => {
        const t = event.transform;
        transformRef.current = { k: t.k, x: t.x, y: t.y };
        render();
      });
    zoomBehaviorRef.current = zoomBehavior;

    select(canvas as HTMLCanvasElement).call(zoomBehavior as never);

    render();

    return () => {
      select(canvas as HTMLCanvasElement).on('.zoom', null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);

  function render() {
    const canvas = canvasRef.current;
    const proj = projectionRef.current;
    if (!canvas || !proj || !data) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const t = transformRef.current;
    const currentRoute = routeRef.current;
    const currentHovered = hoveredRef.current;

    ctx.fillStyle = '#0b0d12';
    ctx.fillRect(0, 0, CANVAS_W, CANVAS_H);

    ctx.save();
    ctx.translate(t.x, t.y);
    ctx.scale(t.k, t.k);

    // Stargate edges.
    ctx.lineWidth = 0.5 / t.k;
    const systemById = systemByIdRef.current!;
    for (const [src, dst, crossRegion] of data.gate_edges) {
      const a = systemById.get(src);
      const b = systemById.get(dst);
      if (!a || !b) continue;
      const ax = a.x * proj.scale + proj.offsetX;
      const ay = a.y * proj.scale + proj.offsetY;
      const bx = b.x * proj.scale + proj.offsetX;
      const by = b.y * proj.scale + proj.offsetY;
      ctx.strokeStyle = crossRegion
        ? 'rgba(170, 130, 220, 0.55)'
        : 'rgba(85, 110, 170, 0.4)';
      ctx.beginPath();
      ctx.moveTo(ax, ay);
      ctx.lineTo(bx, by);
      ctx.stroke();
    }

    // System dots. Fill = sov color (or sec color if no sov). When sov
    // is present, add a thin sec-band ring around it so both signals are
    // visible at once (especially when zoomed in).
    const dotR = 1.4 / t.k;
    const ringR = 2.2 / t.k;
    const ringLW = 0.6 / t.k;
    for (const s of data.systems) {
      const px = s.x * proj.scale + proj.offsetX;
      const py = s.y * proj.scale + proj.offsetY;
      const sov = sovColor(s.sov);
      ctx.fillStyle = sov ?? secColor(s.sec);
      ctx.beginPath();
      ctx.arc(px, py, dotR, 0, Math.PI * 2);
      ctx.fill();
      if (sov) {
        ctx.strokeStyle = secColor(s.sec);
        ctx.lineWidth = ringLW;
        ctx.beginPath();
        ctx.arc(px, py, ringR, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    // Route overlay.
    if (currentRoute && currentRoute.length > 1) {
      const routeCoords: Array<{ x: number; y: number }> = [];
      for (const step of currentRoute) {
        const sys = systemById.get(step.system_id);
        if (!sys) {
          routeCoords.push({ x: NaN, y: NaN });
          continue;
        }
        routeCoords.push({
          x: sys.x * proj.scale + proj.offsetX,
          y: sys.y * proj.scale + proj.offsetY,
        });
      }
      ctx.lineWidth = 2.5 / t.k;
      ctx.lineCap = 'round';
      for (let i = 1; i < routeCoords.length; i++) {
        const a = routeCoords[i - 1];
        const b = routeCoords[i];
        if (
          Number.isNaN(a.x) ||
          Number.isNaN(a.y) ||
          Number.isNaN(b.x) ||
          Number.isNaN(b.y)
        ) {
          continue;
        }
        const edgeType = currentRoute[i].edge_type || 'jump';
        ctx.strokeStyle =
          edgeType === 'gate'
            ? 'rgba(120, 220, 240, 0.95)'
            : 'rgba(120, 250, 140, 0.95)';
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      const routeR = 3.5 / t.k;
      const routeRing = 5.0 / t.k;
      for (let i = 0; i < routeCoords.length; i++) {
        const c = routeCoords[i];
        if (Number.isNaN(c.x)) continue;
        const isEndpoint = i === 0 || i === routeCoords.length - 1;
        ctx.fillStyle = isEndpoint ? '#ffffff' : '#74e094';
        if (isEndpoint) {
          ctx.strokeStyle = i === 0 ? '#74e094' : '#ffd06b';
          ctx.lineWidth = 2 / t.k;
          ctx.beginPath();
          ctx.arc(c.x, c.y, routeRing, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.beginPath();
        ctx.arc(c.x, c.y, routeR, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Region labels at centroids, tinted by dominant sov.
    const fontPx = 11 / t.k;
    ctx.font = `${fontPx}px system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    const minSystemsForLabel = t.k < 1.5 ? 3 : 1;
    const tints = regionSovColorRef.current;
    for (const r of data.regions) {
      if (r.system_count < minSystemsForLabel) continue;
      const px = r.x * proj.scale + proj.offsetX;
      const py = r.y * proj.scale + proj.offsetY;
      const tint = tints.get(r.id);
      // 0xCC ≈ 80% alpha — bright enough to read on dark, recognizable
      // as the sov color of the territory.
      ctx.fillStyle = tint ? `${tint}cc` : 'rgba(220, 225, 240, 0.9)';
      ctx.fillText(r.name, px, py);
    }

    // Hover halo on top of everything.
    if (currentHovered) {
      const px = currentHovered.x * proj.scale + proj.offsetX;
      const py = currentHovered.y * proj.scale + proj.offsetY;
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5 / t.k;
      ctx.beginPath();
      ctx.arc(px, py, 4 / t.k, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.restore();
  }

  // Render whenever hovered changes (route already triggers via the
  // auto-zoom effect below, which re-applies a transform).
  useEffect(() => {
    render();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hovered]);

  // Auto-fit zoom to the route whenever a new route is provided. Triggering
  // d3-zoom's `.transform()` also re-renders via the zoom callback.
  useEffect(() => {
    if (!route || route.length < 1) {
      render();
      return;
    }
    const proj = projectionRef.current;
    const systemById = systemByIdRef.current;
    const canvas = canvasRef.current;
    const zb = zoomBehaviorRef.current;
    if (!proj || !systemById || !canvas || !zb) return;

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    let any = false;
    for (const step of route) {
      const sys = systemById.get(step.system_id);
      if (!sys) continue;
      const px = sys.x * proj.scale + proj.offsetX;
      const py = sys.y * proj.scale + proj.offsetY;
      if (px < minX) minX = px;
      if (px > maxX) maxX = px;
      if (py < minY) minY = py;
      if (py > maxY) maxY = py;
      any = true;
    }
    if (!any) {
      render();
      return;
    }
    const { k, tx, ty } = fitTransform(minX, maxX, minY, maxY, 80, 20);
    const t = zoomIdentity.translate(tx, ty).scale(k);
    select(canvas as HTMLCanvasElement)
      .transition()
      .duration(600)
      .call(zb.transform as never, t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [route]);

  // Pan/zoom to a single system when focusSystemId changes (search-and-go).
  useEffect(() => {
    if (focusSystemId == null) return;
    const proj = projectionRef.current;
    const systemById = systemByIdRef.current;
    const canvas = canvasRef.current;
    const zb = zoomBehaviorRef.current;
    if (!proj || !systemById || !canvas || !zb) return;
    const sys = systemById.get(focusSystemId);
    if (!sys) return;
    const px = sys.x * proj.scale + proj.offsetX;
    const py = sys.y * proj.scale + proj.offsetY;
    // Center on the system at a zoom level that shows ~the surrounding region.
    const k = Math.max(transformRef.current.k, 6);
    const t = zoomIdentity
      .translate(CANVAS_W / 2 - px * k, CANVAS_H / 2 - py * k)
      .scale(k);
    select(canvas as HTMLCanvasElement)
      .transition()
      .duration(450)
      .call(zb.transform as never, t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusSystemId]);

  function onMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    const tree = quadtreeRef.current;
    if (!canvas || !tree) return;
    const rect = canvas.getBoundingClientRect();
    const cx = ((e.clientX - rect.left) / rect.width) * CANVAS_W;
    const cy = ((e.clientY - rect.top) / rect.height) * CANVAS_H;

    const t = transformRef.current;
    const qx = (cx - t.x) / t.k;
    const qy = (cy - t.y) / t.k;

    const radius = 8 / t.k;
    const hit = tree.find(qx, qy, radius);
    setHovered(hit ?? null);
    setCursorPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }

  function onMouseLeave() {
    setHovered(null);
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Star map</h2>
        <span className="help">
          {data
            ? `${data.systems.length} systems · scroll to zoom · drag to pan`
            : 'Loading...'}
        </span>
      </div>
      <div className="card-body">
        {error && (
          <div className="px-4 py-2 rounded-lg border border-[rgba(248,81,73,0.4)] bg-[rgba(248,81,73,0.10)] text-[var(--color-bad)] text-[13px]">
            {error}
          </div>
        )}
        <div style={{ position: 'relative' }}>
          <canvas
            ref={canvasRef}
            width={CANVAS_W}
            height={CANVAS_H}
            onMouseMove={onMouseMove}
            onMouseLeave={onMouseLeave}
            style={{
              width: '100%',
              height: 'auto',
              display: 'block',
              borderRadius: 6,
              cursor: hovered ? 'pointer' : 'grab',
            }}
          />
          {hovered && (
            <div
              style={{
                position: 'absolute',
                left: Math.min(cursorPos.x + 12, CANVAS_W - 200),
                top: cursorPos.y + 12,
                background: 'rgba(20, 25, 40, 0.95)',
                color: '#e5e8f0',
                padding: '6px 10px',
                borderRadius: 4,
                fontSize: 12,
                lineHeight: 1.4,
                pointerEvents: 'none',
                whiteSpace: 'nowrap',
                boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
              }}
            >
              <div style={{ fontWeight: 600 }}>{hovered.name}</div>
              <div>
                Sec:{' '}
                <span style={{ color: secColor(hovered.sec) }}>
                  {hovered.sec.toFixed(2)}
                </span>
              </div>
              {hovered.sov && (
                <div style={{ opacity: 0.85 }}>{hovered.sov}</div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
