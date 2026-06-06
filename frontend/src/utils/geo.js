export function haversineKm(lat1, lng1, lat2, lng2) {
  const R = 6371
  const toRad = d => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export const MOVEMENT_RATES = {
  Infantry: 4,
  Armor: 25,
  Artillery: 20,
  Aviation: 150,
  Logistics: 35,
  SF: 6,
  EW: 25,
  Cyber: 0,
  Naval: 30,
  'Air Defense': 20,
  'Mechanized Infantry': 30,
}
