const PATHS = {
  walk: (
    <>
      <circle cx="13" cy="4.5" r="2" />
      <path d="M9 21l2.5-6.5L14 17v4M11.5 14.5L10 9.5l3.5-1.5 2.5 3.5 3 1M10 9.5L7 12" />
    </>
  ),
  cable: (
    <>
      <path d="M2 5l20-3M12 3.5V8" />
      <rect x="6" y="8" width="12" height="11" rx="3" />
      <path d="M6 13h12M10 19v2M14 19v2" />
    </>
  ),
  bus: (
    <>
      <rect x="4" y="3" width="16" height="15" rx="3" />
      <path d="M4 11h16M8 21v-3M16 21v-3" />
      <circle cx="8" cy="14.5" r="0.6" fill="currentColor" />
      <circle cx="16" cy="14.5" r="0.6" fill="currentColor" />
    </>
  ),
  van: (
    <>
      <path d="M3 16V8a2 2 0 0 1 2-2h9l4 4h1a2 2 0 0 1 2 2v4h-2" />
      <path d="M3 16h2M9 16h6M3 10h11" />
      <circle cx="7" cy="17" r="2" />
      <circle cx="17" cy="17" r="2" />
    </>
  ),
  moto: (
    <>
      <circle cx="5.5" cy="16.5" r="3" />
      <circle cx="18.5" cy="16.5" r="3" />
      <path d="M5.5 16.5h5l3.5-6h3l1.5 6M14 6.5h3l.5 4" />
    </>
  ),
  chat: (
    <path d="M4 18.5l1.2-3.6A8 8 0 1 1 8.6 18l-4.6.5zM8.5 10.5h7M8.5 13.5h4.5" />
  ),
  pin: (
    <>
      <path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </>
  ),
  alert: (
    <>
      <path d="M10.3 3.9L2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9.5v4.5M12 17.2v.1" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  coin: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M14.8 9.2c-.5-.9-1.6-1.4-2.8-1.4-1.6 0-2.8.8-2.8 2.1 0 3 5.8 1.5 5.8 4.3 0 1.3-1.3 2.1-3 2.1-1.3 0-2.5-.6-3-1.6M12 6v1.8M12 16.3V18" />
    </>
  ),
  spark: (
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16z" />
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  send: <path d="M4 12l16-8-6 16-2.5-6.5L4 12z" />,
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
    </>
  ),
  route: (
    <>
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <path d="M8.5 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.5" />
    </>
  ),
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <path d="M6 6l12 12M18 6L6 18" />
};

export default function Icon({ name, size = 22, stroke = 1.8, className = '', style }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}
