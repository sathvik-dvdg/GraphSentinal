// [Windows] GraphSentinel — Susheep
// Sidebar — collapsible icon navigation with per-route accent colours
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Network, ShieldAlert, Search,
  Link2, TrendingUp, Zap, Bell, Settings, ChevronRight, Pin,
} from 'lucide-react'
import useGraphStore from '../../store/useGraphStore'
import useAuthStore from '../../store/useAuthStore'

const NAV_ITEMS = [
  { path: '/dashboard',  Icon: LayoutDashboard, label: 'Dashboard',         color: '#5a616e' },
  { path: '/network',    Icon: Network,          label: 'Network Topology',  color: '#1D9E75' },
  { path: '/threats',    Icon: ShieldAlert,      label: 'Threat Feed',       color: '#E03C3C' },
  { path: '/forensics',  Icon: Search,           label: 'Forensics',         color: '#3b56d9' },
  { path: '/blockchain', Icon: Link2,            label: 'Audit & Ledger',    color: '#7c3aed' },
  { path: '/timeline',   Icon: TrendingUp,       label: 'Timeline',          color: '#1D9E75' },
  { path: '/healing',    Icon: Zap,              label: 'Self-Healing',      color: '#12a672' },
  { path: '/alerts',     Icon: Bell,             label: 'Alert Centre',      color: '#b7791f' },
]

export default function Sidebar({ expanded, pinned, onPinToggle, onHoverChange }) {
  const unread = useGraphStore((s) => 
    s.alerts.filter((a) => !a.is_blocked && !a.acknowledged).length
  )

  return (
    <aside
      style={{
        height: '100%',
        background: '#ffffff',
        borderRight: '1px solid rgba(17,20,26,0.08)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        position: 'relative',
      }}
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
    >
      {/* Logo / brand row */}
      <div
        style={{
          height: 48,
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: 10,
          borderBottom: '1px solid rgba(17,20,26,0.08)',
          flexShrink: 0,
        }}
      >
        {/* Shield icon */}
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: 'rgba(79,110,247,0.12)',
            border: '1px solid rgba(79,110,247,0.25)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" style={{ width: 14, height: 14, color: '#3b56d9' }} stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2z" />
          </svg>
        </div>

        {expanded && (
          <span
            style={{
              color: '#1b1f27',
              fontFamily: "'Plus Jakarta Sans', Inter, sans-serif",
              fontWeight: 600,
              fontSize: 13,
              whiteSpace: 'nowrap',
              letterSpacing: '0.02em',
              flex: 1,
            }}
          >
            GraphSentinel
          </span>
        )}

        {/* Pin toggle */}
        <button
          onClick={onPinToggle}
          title={pinned ? 'Unpin sidebar' : 'Pin sidebar'}
          style={{
            marginLeft: expanded ? 0 : 'auto',
            background: pinned ? 'rgba(79,110,247,0.12)' : 'none',
            border: 'none',
            color: pinned ? '#3b56d9' : 'rgba(27,31,39,0.32)',
            cursor: 'pointer',
            padding: 4,
            borderRadius: 6,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {pinned ? <Pin size={13} /> : <ChevronRight size={13} />}
        </button>
      </div>

      {/* Main nav */}
      <nav style={{ flex: 1, paddingTop: 6, overflowY: 'auto', overflowX: 'hidden' }}>
        {NAV_ITEMS.map(({ path, Icon, label, color }) => (
          <NavLink
            key={path}
            to={path}
            title={!expanded ? label : undefined}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '9px 16px',
              textDecoration: 'none',
              borderLeft: isActive ? `3px solid ${color}` : '3px solid transparent',
              background: isActive ? 'rgba(17,20,26,0.08)' : 'transparent',
              transition: 'background 150ms, border-color 150ms',
              position: 'relative',
              overflow: 'hidden',
            })}
          >
            <Icon
              size={18}
              style={{ color, flexShrink: 0, minWidth: 18 }}
            />

            {expanded && (
              <span
                style={{
                  color: 'rgba(27,31,39,0.80)',
                  fontSize: 12,
                  fontFamily: "'DM Mono', monospace",
                  whiteSpace: 'nowrap',
                  opacity: expanded ? 1 : 0,
                  transition: 'opacity 150ms 60ms',
                  flex: 1,
                }}
              >
                {label}
              </span>
            )}

            {/* Unread badge — alerts only */}
            {path === '/alerts' && unread > 0 && (
              <span
                style={{
                  marginLeft: 'auto',
                  background: '#b7791f',
                  color: '#fff',
                  borderRadius: 999,
                  fontSize: 9,
                  fontWeight: 700,
                  padding: '1px 5px',
                  minWidth: 16,
                  textAlign: 'center',
                  fontFamily: "'DM Mono', monospace",
                }}
              >
                {unread > 99 ? '99+' : unread}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom: Settings + user strip */}
      <div style={{ borderTop: '1px solid rgba(17,20,26,0.08)', flexShrink: 0 }}>
        <NavLink
          to="/settings"
          title={!expanded ? 'Settings' : undefined}
          style={({ isActive }) => ({
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '9px 16px',
            textDecoration: 'none',
            borderLeft: isActive ? '3px solid #5a616e' : '3px solid transparent',
            background: isActive ? 'rgba(17,20,26,0.08)' : 'transparent',
            transition: 'background 150ms',
          })}
        >
          <Settings size={18} style={{ color: '#5a616e', flexShrink: 0 }} />
          {expanded && (
            <span style={{ color: 'rgba(27,31,39,0.80)', fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
              Settings
            </span>
          )}
        </NavLink>

        {/* User profile strip */}
        {expanded && (
          <div
            style={{
              margin: '6px 10px 10px',
              padding: '8px 10px',
              background: 'rgba(17,20,26,0.05)',
              borderRadius: 8,
              border: '1px solid rgba(17,20,26,0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #1D9E75, #3b56d9)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 11,
                fontWeight: 700,
                color: '#fff',
                fontFamily: "'Plus Jakarta Sans', sans-serif",
                flexShrink: 0,
              }}
            >
              {useAuthStore.getState().user?.username ? useAuthStore.getState().user.username.substring(0,2).toUpperCase() : 'SD'}
            </div>
            <div>
              <div style={{ color: '#1b1f27', fontSize: 11, fontWeight: 600, fontFamily: "'Plus Jakarta Sans', sans-serif" }}>
                {useAuthStore.getState().user?.username || 'admin'}
              </div>
              <div style={{ color: 'rgba(27,31,39,0.45)', fontSize: 10, fontFamily: "'DM Mono', monospace" }}>
                Admin
              </div>
            </div>
          </div>
        )}

        {/* Collapsed avatar */}
        {!expanded && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '8px 0 10px' }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #1D9E75, #3b56d9)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 10,
                fontWeight: 700,
                color: '#fff',
              }}
            >
              {useAuthStore.getState().user?.username ? useAuthStore.getState().user.username.substring(0,2).toUpperCase() : 'KS'}
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
