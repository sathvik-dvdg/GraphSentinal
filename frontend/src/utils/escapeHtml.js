// Escape a value for interpolation into an HTML string. react-force-graph
// renders `nodeLabel` as HTML, and the label is built from server data.
// Today every host id/label is a validated IPv4 address, so nothing in it can
// be markup -- this keeps that true whatever the backend sends later.
const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export function escapeHtml(value) {
  if (value == null) return ''
  return String(value).replace(/[&<>"']/g, (c) => ENTITIES[c])
}
