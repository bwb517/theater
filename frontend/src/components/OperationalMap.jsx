import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet default icon path issue with Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const SIDE_COLORS = { Blue: '#3b82f6', Red: '#ef4444', Green: '#22c55e', White: '#9ca3af' }

// Range ring data by unit type — returns { radius (m), color, label } or null
function unitRangeInfo(unit) {
  const t = (unit.type || '').toLowerCase()
  const n = (unit.name || '').toLowerCase()
  // Artillery / fires
  if (n.includes('himars') || n.includes('atacms'))       return { radius: 80000,  color: null, label: 'FIRES' }
  if (n.includes('mlrs') || t.includes('rocket'))         return { radius: 70000,  color: null, label: 'FIRES' }
  if (t.includes('naval'))                                 return { radius: 50000,  color: null, label: 'FIRES' }
  if (t.includes('artillery'))                             return { radius: 28000,  color: null, label: 'FIRES' }
  if (t.includes('mortar'))                                return { radius: 7000,   color: null, label: 'FIRES' }
  // SAM / air defense — color always orange regardless of faction
  if (n.includes('s-400') || n.includes('sa-21'))         return { radius: 400000, color: '#f97316', label: 'SAM' }
  if (n.includes('s-300') || n.includes('sa-20'))         return { radius: 200000, color: '#f97316', label: 'SAM' }
  if (n.includes('patriot') || n.includes('pac-') || n.includes('thaad')) return { radius: 160000, color: '#f97316', label: 'SAM' }
  if (n.includes('hawk') || n.includes('iris-t') || n.includes('nasams')) return { radius: 40000,  color: '#f97316', label: 'SAM' }
  if (n.includes('shorad') || n.includes('manpads') || n.includes('stinger')) return { radius: 8000, color: '#f97316', label: 'SAM' }
  if (t.includes('air defense') || t.includes('sam'))     return { radius: 40000,  color: '#f97316', label: 'SAM' }
  // Fighter / strike aircraft — purple
  if (t.includes('fighter') || t.includes('strike') || t.includes('aircraft') || t.includes('aviation')) return { radius: 150000, color: '#a855f7', label: 'CAP' }
  if (n.includes('f-35') || n.includes('f-16') || n.includes('f-15') || n.includes('su-') || n.includes('mig-')) return { radius: 150000, color: '#a855f7', label: 'CAP' }
  return null
}

function createUnitIcon(side, label, strength, selected, highlighted, wtfOpacity) {
  const color   = SIDE_COLORS[side] || '#9ca3af'
  const opacity = wtfOpacity ?? (strength === 'Critical' ? 0.55 : strength === 'Degraded' ? 0.8 : 1)
  const border  = selected     ? `3px solid #fff`
                : highlighted  ? `3px solid #fbbf24`
                : `2px solid ${color}`
  const shadow  = selected
    ? `0 0 0 3px ${color}60, 0 2px 12px rgba(0,0,0,0.8)`
    : highlighted
    ? `0 0 0 3px #fbbf2460, 0 2px 12px rgba(0,0,0,0.8)`
    : `0 2px 8px rgba(0,0,0,0.6)`

  const html = `
    <div style="
      background: ${color}${Math.round(opacity * 255).toString(16).padStart(2,'0')};
      border: ${border};
      border-radius: 2px;
      color: white;
      font-family: 'JetBrains Mono', monospace;
      font-size: 9px;
      font-weight: 700;
      padding: 2px 5px;
      white-space: nowrap;
      min-width: 28px;
      text-align: center;
      box-shadow: ${shadow};
      cursor: pointer;
      transform: ${selected ? 'scale(1.15)' : 'scale(1)'};
      transition: transform 0.15s;
    ">${label}</div>`
  return L.divIcon({ html, className: '', iconAnchor: [14, 14] })
}

function AutoFitBounds({ units }) {
  const map = useMap()
  const fitted = useRef(false)
  useEffect(() => {
    if (fitted.current) return
    if (!units || units.length === 0) return
    const valid = units.filter(u => u.location?.lat && u.location?.lng)
    if (valid.length === 0) return
    const bounds = L.latLngBounds(valid.map(u => [u.location.lat, u.location.lng]))
    map.fitBounds(bounds, { padding: [40, 40] })
    fitted.current = true
  }, [units, map]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

// Calls invalidateSize() whenever the map container is resized (e.g. side panel open/close)
function MapResizer() {
  const map = useMap()
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return null
}

// Handles map clicks (pick mode) and right-clicks (context menu)
function MapEventHandler({ enabled, onMapClick, onMapRightClick }) {
  useMapEvents({
    click(e) {
      if (enabled) onMapClick(e.latlng.lat, e.latlng.lng)
    },
    contextmenu(e) {
      L.DomEvent.preventDefault(e)
      // Suppress context menu while in destination / fires-target pick mode
      if (!enabled && onMapRightClick) {
        onMapRightClick(
          e.latlng.lat, e.latlng.lng,
          e.originalEvent.clientX, e.originalEvent.clientY
        )
      }
    },
  })
  return null
}

// ─── Main map component ───────────────────────────────────────────────────────

export default function OperationalMap({
  units          = [],
  factions       = [],
  center         = [54.1, 22.9],
  zoom           = 8,
  height         = '100%',
  // Interactivity
  onUnitClick    = null,
  selectedUnit   = null,
  // Movement arrows from pending orders
  pendingOrders  = [],
  // Destination pick mode
  pickingDestination = false,
  onMapClick     = null,
  onMapRightClick = null,
  // Post-adjudication highlighting (array of unit_ids)
  highlightedUnits = [],
  // Scenario geography
  keyTerrain     = [],
  // FOW: if set, units not in detected_by for this faction show as "?"
  viewingFactionId = null,
  // Previous turn ghost overlay
  previousUnits = [],
}) {
  const [sideFilter, setSideFilter] = useState({ Blue: true, Red: true, Green: true, White: true })
  const [gmView, setGmView] = useState(false)

  const factionMap = useMemo(() => {
    const m = {}
    factions.forEach(f => { m[f.faction_id] = f })
    return m
  }, [factions])

  // Unit positions keyed by unit_id for drawing movement arrows
  const unitPositions = useMemo(() => {
    const m = {}
    units.forEach(u => { if (u.location?.lat) m[u.unit_id] = [u.location.lat, u.location.lng] })
    return m
  }, [units])

  // Maneuver orders that have both a source unit position and a destination coord
  const movementArrows = useMemo(() =>
    pendingOrders
      .filter(o => o.wff === 'maneuver' && o.unit_id && o.to_lat && o.to_lng && unitPositions[o.unit_id])
      .map(o => ({
        id: o.id,
        from: unitPositions[o.unit_id],
        to: [o.to_lat, o.to_lng],
        label: `${o.unit_id} → ${o.to_location || 'Destination'}`,
      })),
  [pendingOrders, unitPositions])

  const ghostMarkers = useMemo(() => {
    if (!previousUnits.length) return []
    const currPos = Object.fromEntries(
      units.filter(u => u.location?.lat).map(u => [u.unit_id, [u.location.lat, u.location.lng]])
    )
    return previousUnits
      .filter(u => u.location?.lat && u.location?.lng && u.strength !== 'Destroyed')
      .map(u => ({
        unit_id: u.unit_id,
        faction_id: u.faction_id,
        prevPos: [u.location.lat, u.location.lng],
        currPos: currPos[u.unit_id] || null,
      }))
  }, [previousUnits, units])

  const isVisible = (unit) => {
    if (!viewingFactionId || gmView) return true
    if (unit.faction_id === viewingFactionId) return true
    return (unit.detected_by || []).includes(viewingFactionId)
  }

  const allPositionedUnits = units.filter(u =>
    u.location?.lat && u.location?.lng &&
    u.strength !== 'Destroyed' &&
    sideFilter[factionMap[u.faction_id]?.side || 'White']
  )
  const validUnits   = allPositionedUnits.filter(u => isVisible(u))
  const fowUnits     = allPositionedUnits.filter(u => !isVisible(u))

  const handleUnitClick = useCallback((unit, e) => {
    if (onUnitClick) {
      L.DomEvent.stopPropagation(e)
      onUnitClick(unit)
    }
  }, [onUnitClick])

  return (
    <div style={{ height, width: '100%', position: 'relative', zIndex: 0 }}>
      {/* Destination-pick mode banner */}
      {pickingDestination && (
        <div style={{
          position: 'absolute', top: 0, left: 0, right: 0, zIndex: 2000,
          background: 'rgba(251,191,36,0.15)', borderBottom: '2px solid #fbbf24',
          padding: '6px 16px', display: 'flex', alignItems: 'center', gap: 8,
          fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#fbbf24',
        }}>
          <span style={{ fontSize: 14 }}>⊕</span>
          CLICK MAP TO SET DESTINATION — click the unit again or press Escape to cancel
        </div>
      )}

      <MapContainer
        center={center}
        zoom={zoom}
        style={{
          height: '100%', width: '100%', background: '#0a0f1e',
          cursor: pickingDestination ? 'crosshair' : 'grab',
        }}
        zoomControl={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://carto.com/">CARTO</a>'
          subdomains="abcd"
          maxZoom={19}
        />

        <AutoFitBounds units={validUnits} />
        <MapResizer />
        <MapEventHandler enabled={pickingDestination} onMapClick={onMapClick} onMapRightClick={onMapRightClick} />

        {/* Movement arrows (pending maneuver orders with map destinations) */}
        {movementArrows.map(arrow => (
          <Polyline
            key={arrow.id}
            positions={[arrow.from, arrow.to]}
            pathOptions={{ color: '#3b82f6', weight: 2.5, dashArray: '8 5', opacity: 0.9 }}
          >
            <Tooltip sticky>{arrow.label}</Tooltip>
          </Polyline>
        ))}

        {/* Destination pins */}
        {movementArrows.map(arrow => (
          <Circle
            key={`dest-${arrow.id}`}
            center={arrow.to}
            radius={400}
            pathOptions={{ color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.4, weight: 2 }}
          />
        ))}

        {/* Previous turn ghost markers */}
        {ghostMarkers.map(g => {
          const side = factionMap[g.faction_id]?.side || 'White'
          const color = SIDE_COLORS[side] || '#9ca3af'
          const ghostIcon = L.divIcon({
            html: `<div style="background:${color}22;border:2px dashed ${color}66;border-radius:2px;color:${color}88;font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:700;padding:2px 5px;white-space:nowrap;opacity:0.6;">${g.unit_id.split('-')[0]}</div>`,
            className: '', iconAnchor: [14, 14],
          })
          return (
            <Marker key={`ghost-${g.unit_id}`} position={g.prevPos} icon={ghostIcon} interactive={false}>
              <Tooltip>Prev: {g.unit_id}</Tooltip>
            </Marker>
          )
        })}
        {ghostMarkers.filter(g => g.currPos).map(g => {
          const side = factionMap[g.faction_id]?.side || 'White'
          const color = SIDE_COLORS[side] || '#9ca3af'
          return (
            <Polyline
              key={`trail-${g.unit_id}`}
              positions={[g.prevPos, g.currPos]}
              pathOptions={{ color, weight: 1.5, dashArray: '4 4', opacity: 0.35 }}
            />
          )
        })}

        {/* FOW "?" markers for undetected enemy units */}
        {fowUnits.map(unit => {
          const fowIcon = L.divIcon({
            html: `<div style="
              background: #374151; border: 2px solid #6b7280; border-radius: 2px;
              color: #9ca3af; font-family: 'JetBrains Mono',monospace; font-size: 11px;
              font-weight: 700; padding: 2px 6px; opacity: 0.6;
            ">?</div>`,
            className: '', iconAnchor: [10, 10],
          })
          return (
            <Marker key={`fow-${unit.unit_id}`} position={[unit.location.lat, unit.location.lng]} icon={fowIcon}>
              <Tooltip>Undetected unit</Tooltip>
            </Marker>
          )
        })}

        {/* Unit markers */}
        {validUnits.map(unit => {
          const faction   = factionMap[unit.faction_id]
          const side      = faction?.side || 'White'
          const isSelected    = selectedUnit?.unit_id === unit.unit_id
          const isHighlighted = highlightedUnits.includes(unit.unit_id)
          const shortName = unit.name?.split(' ').slice(0, 2).join('-').toUpperCase().substring(0, 10) || unit.unit_id
          // WTF Broken units get 40% opacity
          const wtfOpacity = unit.will_to_fight === 'Broken' ? 0.4 : undefined
          const icon      = createUnitIcon(side, shortName, unit.strength, isSelected, isHighlighted, wtfOpacity)
          const rangeInfo = unitRangeInfo(unit)
          const supply    = unit.supply || {}
          const munitions = supply.munitions
          const wtfColors = { High: '#22c55e', Moderate: '#fbbf24', Low: '#f97316', Broken: '#ef4444' }
          const c2Colors  = { Nominal: '#22c55e', Degraded: '#fbbf24', Lost: '#ef4444' }

          return (
            <Marker
              key={unit.unit_id}
              position={[unit.location.lat, unit.location.lng]}
              icon={icon}
              eventHandlers={{ click: (e) => handleUnitClick(unit, e.originalEvent) }}
              zIndexOffset={isSelected ? 1000 : 0}
            >
              {/* Range ring — artillery (faction color), SAM (orange), CAP (purple) */}
              {rangeInfo && (
                <Circle
                  center={[unit.location.lat, unit.location.lng]}
                  radius={rangeInfo.radius}
                  pathOptions={{
                    color: rangeInfo.color ?? (side === 'Blue' ? '#3b82f6' : '#ef4444'),
                    weight: 1,
                    dashArray: rangeInfo.label === 'SAM' ? '2 6' : rangeInfo.label === 'CAP' ? '6 4' : '4 6',
                    fillOpacity: 0.03,
                    opacity: isSelected ? 0.7 : 0.3,
                    interactive: false,
                  }}
                />
              )}

              {!onUnitClick && (
                <Popup>
                  <div style={{ background: '#111827', color: '#f9fafb', minWidth: 210, fontFamily: 'Inter, sans-serif' }}>
                    <div style={{ borderBottom: '1px solid #1f2937', padding: '8px 12px', marginBottom: 8 }}>
                      <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: '#9ca3af' }}>{unit.unit_id}</div>
                      <div style={{ fontWeight: 700, fontSize: 14 }}>{unit.name}</div>
                      {faction && <div style={{ fontSize: 11, color: SIDE_COLORS[side] }}>{faction.name}</div>}
                    </div>
                    <div style={{ padding: '0 12px 8px', fontSize: 11 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                        <span style={{ color: '#9ca3af' }}>Type:</span><span>{unit.type}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                        <span style={{ color: '#9ca3af' }}>Echelon:</span><span>{unit.echelon}</span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                        <span style={{ color: '#9ca3af' }}>Strength:</span>
                        <span style={{ color: unit.strength === 'Full' ? '#22c55e' : unit.strength === 'Degraded' ? '#fbbf24' : '#ef4444', fontWeight: 700 }}>{unit.strength}</span>
                      </div>
                      {unit.will_to_fight && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                          <span style={{ color: '#9ca3af' }}>Will-to-Fight:</span>
                          <span style={{ color: wtfColors[unit.will_to_fight] || '#9ca3af', fontWeight: 700 }}>{unit.will_to_fight}</span>
                        </div>
                      )}
                      {unit.c2_status && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                          <span style={{ color: '#9ca3af' }}>C2:</span>
                          <span style={{ color: c2Colors[unit.c2_status] || '#9ca3af', fontWeight: 700 }}>{unit.c2_status}</span>
                        </div>
                      )}
                      {supply.ammo != null && (
                        <div style={{ marginTop: 6, borderTop: '1px solid #1f2937', paddingTop: 6 }}>
                          {munitions != null ? (
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                              <span style={{ color: '#9ca3af' }}>{munitions.type}:</span>
                              <span style={{ color: munitions.count === 0 ? '#ef4444' : munitions.count < munitions.max * 0.25 ? '#f97316' : '#22c55e', fontWeight: 700 }}>
                                {munitions.count}/{munitions.max}
                              </span>
                            </div>
                          ) : (
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                              <span style={{ color: '#9ca3af' }}>Ammo:</span>
                              <span style={{ color: supply.ammo < 20 ? '#ef4444' : supply.ammo < 50 ? '#fbbf24' : '#22c55e' }}>{supply.ammo}/100</span>
                            </div>
                          )}
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                            <span style={{ color: '#9ca3af' }}>Fuel:</span>
                            <span style={{ color: supply.fuel < 20 ? '#ef4444' : supply.fuel < 50 ? '#fbbf24' : '#22c55e' }}>{supply.fuel}/100</span>
                          </div>
                        </div>
                      )}
                      {unit.location?.grid_reference && (
                        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, color: '#6b7280', marginTop: 6, borderTop: '1px solid #1f2937', paddingTop: 6 }}>
                          GRID: {unit.location.grid_reference}
                        </div>
                      )}
                    </div>
                  </div>
                </Popup>
              )}
            </Marker>
          )
        })}
      </MapContainer>

      {/* Map legend + faction filter */}
      <div style={{
        position: 'absolute', bottom: 24, left: 12, zIndex: 1000,
        background: 'rgba(17,24,39,0.92)', border: '1px solid #1f2937',
        borderRadius: 6, padding: '8px 12px', backdropFilter: 'blur(4px)',
        userSelect: 'none',
      }}>
        <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#6b7280', marginBottom: 6 }}>FORCE FILTER</div>
        {[['Blue','#3b82f6','BLUE'], ['Red','#ef4444','RED'], ['Green','#22c55e','GREEN']].map(([side, color, label]) => (
          <div
            key={side}
            onClick={() => setSideFilter(p => ({ ...p, [side]: !p[side] }))}
            style={{
              display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3,
              cursor: 'pointer', opacity: sideFilter[side] ? 1 : 0.35,
              transition: 'opacity 0.15s',
            }}
          >
            <div style={{ width: 12, height: 12, background: sideFilter[side] ? color : 'transparent', borderRadius: 2, border: `2px solid ${color}`, transition: 'background 0.15s' }} />
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#9ca3af' }}>{label}</span>
          </div>
        ))}
        {movementArrows.length > 0 && (
          <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px solid #1f2937' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 18, height: 2, borderTop: '2px dashed #3b82f6' }} />
              <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#9ca3af' }}>PENDING MOVE</span>
            </div>
          </div>
        )}
        {viewingFactionId && (
          <div
            onClick={() => setGmView(p => !p)}
            style={{
              marginTop: 8, paddingTop: 6, borderTop: '1px solid #1f2937',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            <div style={{ width: 12, height: 12, background: gmView ? '#fbbf24' : 'transparent', borderRadius: 2, border: '2px solid #fbbf24', transition: 'background 0.15s' }} />
            <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, color: '#fbbf24' }}>GM VIEW</span>
          </div>
        )}
      </div>

    </div>
  )
}
