// How a graph payload lands on the graph already on screen, kept free of React
// and the store so it can be tested with `node --test`
// (frontend/tests/unit/graphMerge.test.js).
//
// Two payloads arrive: the REST poll's full graph every 10 s, and socket
// pushes that the server caps at 50 nodes / 100 links (`truncated: true`,
// backend/app/websocket/events.py), keeping the most dangerous ones.
//   * A full graph replaces what is on screen (hosts that left go away).
//   * A capped push is MERGED: its nodes update (or add to) the ones on
//     screen, its links update (or add to) theirs, and everything it left out
//     stays. Replacing made the graph flip between the full and the capped
//     version every few seconds; ignoring it (FE-10's first fix) delayed the
//     newest scores of exactly the hosts that matter by up to a poll.
// Node objects are updated in place so react-force-graph keeps their x/y/z.

const endpointId = (end) => (end && typeof end === 'object' ? end.id : end)
const linkKey = (l) => `${endpointId(l.source)}->${endpointId(l.target)}`

export function mergeGraph(current, incoming) {
  const existing = new Map((current?.nodes || []).map((n) => [n.id, n]))
  const update = (n) => {
    const node = existing.get(n.id)
    return node ? Object.assign(node, n) : n
  }

  if (!incoming?.truncated) {
    return { nodes: (incoming?.nodes || []).map(update), links: incoming?.links || [] }
  }

  const nodes = [...(current?.nodes || [])]
  for (const n of incoming.nodes || []) {
    if (existing.has(n.id)) update(n)
    else nodes.push(n)
  }
  const links = new Map((current?.links || []).map((l) => [linkKey(l), l]))
  for (const l of incoming.links || []) {
    const old = links.get(linkKey(l))
    // Keep the old link object (the renderer may have swapped its ends for
    // node objects); take the new values.
    links.set(linkKey(l), old ? Object.assign(old, { ...l, source: old.source, target: old.target }) : l)
  }
  return { nodes, links: [...links.values()] }
}
