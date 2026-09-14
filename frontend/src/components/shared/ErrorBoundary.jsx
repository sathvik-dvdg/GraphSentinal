// [Windows] GraphSentinel — Susheep
// Error.md U10 — react-force-graph-3d (three.js) and cytoscape can throw on
// unexpected node shapes (null id, circular refs from the physics engine).
// Without a boundary a single bad node blanks the whole page. This catches
// the render error, shows a recoverable message, and offers a retry that
// remounts the subtree.
import { Component } from 'react'
import { AlertTriangle } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', this.props.label || '', error, info)
  }

  retry = () => this.setState({ error: null })

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, textAlign: 'center',
          }}
        >
          <AlertTriangle size={28} style={{ color: '#E03C3C', opacity: 0.7 }} />
          <div style={{ color: '#1b1f27', fontFamily: "'Plus Jakarta Sans', sans-serif", fontWeight: 600, fontSize: 14 }}>
            {this.props.label || 'This view'} hit a render error
          </div>
          <div style={{ color: '#727a86', fontFamily: "'DM Mono', monospace", fontSize: 11, maxWidth: 340, lineHeight: 1.6 }}>
            {String(this.state.error?.message || this.state.error).slice(0, 200)}
          </div>
          <button
            onClick={this.retry}
            style={{
              padding: '6px 16px', borderRadius: 6, cursor: 'pointer',
              border: '1px solid rgba(79,110,247,0.3)', background: 'rgba(79,110,247,0.08)',
              color: '#3b56d9', fontSize: 12, fontFamily: "'DM Mono', monospace",
            }}
          >
            Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
