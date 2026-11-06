import { useMemo, useRef } from 'react'
import { MINUTES } from './trips'

const H = 44

type Props = { active: Int32Array; waymo: Int32Array; minute: number; onSeek: (minute: number) => void }

/** Trips in motion across the day, with the Waymo portion on top. Click or drag to scrub. */
export function DayTimeline({ active, waymo, minute, onSeek }: Props) {
  const ref = useRef<SVGSVGElement>(null)
  const dragging = useRef(false)
  const [all, robo] = useMemo(() => {
    const peak = Math.max(...active, 1)
    const path = (a: Int32Array) => {
      let d = `M0,${H}`
      a.forEach((v, m) => (d += `L${m},${(H - (v / peak) * (H - 4)).toFixed(1)}`))
      return `${d}L${MINUTES},${H}Z`
    }
    return [path(active), path(waymo)]
  }, [active, waymo])
  const seek = (clientX: number) => {
    const r = ref.current!.getBoundingClientRect()
    onSeek(Math.min(Math.max((clientX - r.left) / r.width, 0), 0.9995) * MINUTES)
  }
  return (
    <div className="timeline">
      <svg
        ref={ref}
        viewBox={`0 0 ${MINUTES} ${H}`}
        preserveAspectRatio="none"
        role="slider"
        aria-label="Time of day"
        aria-valuemin={0}
        aria-valuemax={MINUTES}
        aria-valuenow={Math.round(minute)}
        onPointerDown={(e) => {
          dragging.current = true
          e.currentTarget.setPointerCapture(e.pointerId)
          seek(e.clientX)
        }}
        onPointerMove={(e) => dragging.current && seek(e.clientX)}
        onPointerUp={() => (dragging.current = false)}
      >
        <path d={all} fill="var(--human)" opacity={0.3} />
        <path d={robo} fill="var(--waymo)" opacity={0.9} />
        <line x1={minute} x2={minute} y1={0} y2={H} stroke="#fff" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      </svg>
      <div className="timeline-axis">
        {[0, 3, 6, 9, 12, 15, 18, 21].map((h) => (
          <span key={h} style={{ left: `${(h / 24) * 100}%` }}>
            {String(h).padStart(2, '0')}:00
          </span>
        ))}
      </div>
    </div>
  )
}
