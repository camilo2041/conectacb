import { useEffect, useRef, useState } from 'react';
import Icon from './Icon';
import { webchatUrl } from '../config';

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  // El iframe se crea al primer clic y luego se conserva para no perder la conversación.
  const [src, setSrc] = useState(null);
  const loaded = src !== null;
  const launcherRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = e => e.key === 'Escape' && setOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  const toggle = () => {
    setSrc(s => s ?? webchatUrl());
    setOpen(o => !o);
  };

  const close = () => {
    setOpen(false);
    launcherRef.current?.focus();
  };

  return (
    <>
      {loaded && (
        <div
          className={`chat-panel ${open ? 'is-open' : ''}`}
          role="dialog"
          aria-label="Chat de ConectaCB"
          aria-hidden={!open}
          inert={!open}
        >
          <div className="chat-panel__head">
            <span className="chat-panel__title">
              <span className="live-dot live-dot--ok" /> Chatea con ConectaCB
            </span>
            <button ref={closeRef} type="button" className="chat-panel__close" onClick={close} aria-label="Cerrar chat">
              <Icon name="close" size={18} />
            </button>
          </div>
          <iframe src={src}title="Chat de ConectaCB" allow="clipboard-write; microphone" />
        </div>
      )}

      <button
        ref={launcherRef}
        type="button"
        className={`chat-launcher ${open ? 'is-open' : ''}`}
        onClick={toggle}
        aria-expanded={open}
        aria-label={open ? 'Cerrar chat' : 'Abrir chat con ConectaCB'}
      >
        <span className="chat-launcher__tip">¿Dudas? Escríbenos</span>
        <Icon name={open ? 'close' : 'chat'} size={26} stroke={2} />
      </button>
    </>
  );
}
