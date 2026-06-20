import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Drive the native Fullscreen API for a single element (e.g. a course iframe
 * wrapper). Returns a ref to attach to the element, the current fullscreen
 * state, and a toggle.
 */
export function useFullscreen<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const onChange = () => setIsFullscreen(document.fullscreenElement === ref.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const toggle = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else {
      void ref.current?.requestFullscreen();
    }
  }, []);

  return { ref, isFullscreen, toggle };
}
