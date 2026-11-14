import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Project } from "./api";

export function useProject(id: string | undefined) {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    if (!id) return;
    try {
      setProject(await api.project(id));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { project, setProject, error, reload };
}

/** Tracks the current playback time of a <video>. */
export function useVideoTime() {
  const ref = useRef<HTMLVideoElement>(null);
  const [time, setTime] = useState(0);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    const on = () => setTime(v.currentTime);
    v.addEventListener("timeupdate", on);
    v.addEventListener("seeked", on);
    return () => {
      v.removeEventListener("timeupdate", on);
      v.removeEventListener("seeked", on);
    };
  });
  const seek = useCallback((t: number) => {
    if (ref.current) {
      ref.current.currentTime = Math.max(0, t);
      setTime(Math.max(0, t));
    }
  }, []);
  return { ref, time, seek };
}
