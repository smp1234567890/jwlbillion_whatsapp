// Preloaded HTML5 Audio element for custom notification sound
let notificationAudio = null;

function getNotificationAudio() {
  if (typeof window === "undefined") return null;
  if (!notificationAudio) {
    try {
      notificationAudio = new Audio("/sounds/notification.mp3");
      notificationAudio.preload = "auto";
      notificationAudio.volume = 0.85;
    } catch (e) {
      console.warn("Failed to create notification Audio:", e);
    }
  }
  return notificationAudio;
}

// User-gesture unlock
if (typeof window !== "undefined") {
  const unlockAudio = () => {
    const audio = getNotificationAudio();
    if (audio) {
      // Warm up audio buffer silently on first click/touch
      audio.play().then(() => {
        audio.pause();
        audio.currentTime = 0;
      }).catch(() => {});
      window.removeEventListener("click", unlockAudio);
      window.removeEventListener("keydown", unlockAudio);
      window.removeEventListener("touchstart", unlockAudio);
    }
  };
  window.addEventListener("click", unlockAudio, { passive: true, once: true });
  window.addEventListener("keydown", unlockAudio, { passive: true, once: true });
  window.addEventListener("touchstart", unlockAudio, { passive: true, once: true });
}

export function playIncomingMessageSound(enabled = true) {
  if (!enabled) return;
  try {
    const audio = getNotificationAudio();
    if (audio) {
      audio.currentTime = 0;
      audio.play().catch((err) => {
        // Fallback: Web Audio API ping if media autoplay policy prevents audio element
        playSynthFallback();
      });
    } else {
      playSynthFallback();
    }
  } catch (e) {
    playSynthFallback();
  }
}

// Fallback synthesizer in case Audio element is blocked
function playSynthFallback() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    const now = ctx.currentTime;
    osc.type = "sine";
    osc.frequency.setValueAtTime(800, now);
    osc.frequency.exponentialRampToValueAtTime(1200, now + 0.08);
    gain.gain.setValueAtTime(0.3, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.35);
  } catch (e) {}
}
