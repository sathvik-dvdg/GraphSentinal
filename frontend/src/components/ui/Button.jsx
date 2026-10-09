// ui/Button — the one button shape (styles in globals.css, .gs-btn).
// variant: primary (ink) | accent (crimson, the single call to action) |
// secondary (outline) | ghost | danger. size: md | sm.
export default function Button({ variant = 'secondary', size = 'md', active = false, className = '', type = 'button', children, ...rest }) {
  const cls = ['gs-btn', `gs-btn-${variant}`, size === 'sm' ? 'gs-btn-sm' : '', active ? 'gs-btn-active' : '', className]
    .filter(Boolean).join(' ')
  return <button type={type} className={cls} {...rest}>{children}</button>
}
