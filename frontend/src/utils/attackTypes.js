// The attack-type labels the backend can put on an incident, in display order.
// Source: AttackType in backend/app/models/schemas.py. The label comes from a
// port/volume heuristic (backend/app/services/threat_analyzer.py
// infer_attack_type), not from either model.
//
// Pages used to hard-code a shorter list, so DoSHulk and Manual alerts were
// reachable only under "All" and never counted (FE-11, FE-13, FE-26).
export const ATTACK_TYPES = ['DDoS', 'PortScan', 'SSHBrute', 'DoSHulk', 'Botnet', 'Manual', 'Heuristic', 'Unknown']

// Shown only while some record actually carries them.
const RARE = new Set(['Heuristic', 'Unknown'])

/** Filter options for the records present: every common type, a rare one only
 *  when it occurs, and any label the backend sends that this list lacks. */
export function attackTypeOptions(presentTypes = []) {
  const present = new Set(presentTypes.filter(Boolean))
  const known = ATTACK_TYPES.filter((t) => !RARE.has(t) || present.has(t))
  const unknown = [...present].filter((t) => !ATTACK_TYPES.includes(t)).sort()
  return [...known, ...unknown]
}
