// Formato internacional sin "+" (requerido por wa.me).
export const WHATSAPP_NUMBER = '573203414412';
export const WHATSAPP_DISPLAY = '+57 320 341 4412';
// Webchat de LucidBot: mismos parámetros que arma su plugin.js (ktt10.setup), sin cargar el script.
const WEBCHAT = { id: 'U85L1Wl9nQ1YOiEoNMk', accountId: '3102425', color: '#006dff' };
export const webchatUrl = () =>
  `https://panel.lucidbot.co/webchat/?${new URLSearchParams({
    id: WEBCHAT.id,
    page_id: WEBCHAT.accountId,
    color: WEBCHAT.color,
    dm: window.location.hostname,
    parent: window.location.href
  })}`;
export const WHATSAPP_URL = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent('Hola ConectaCB, ¿cómo llego a...?')}`;
