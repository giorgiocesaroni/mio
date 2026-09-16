"use client";

import { useCallback, useRef, useState } from "react";

// NOTE: extendable-media-recorder touches `Worker` at module scope, which
// crashes server-side prerendering. It is dynamically imported on first
// recording so this module stays SSR-safe.

interface AudioAttachment {
  blob: Blob;
  mime_type: string;
}

let registered = false;

async function ensureWavEncoder() {
  if (!registered) {
    const { connect } = await import("extendable-media-recorder-wav-encoder");
    const { register } = await import("extendable-media-recorder");
    await register(await connect());
    registered = true;
  }
}

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<any>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    if (mediaRecorderRef.current?.state === "recording") return;
    await ensureWavEncoder();
    chunksRef.current = [];
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const { MediaRecorder: ExtMediaRecorder } = await import(
      "extendable-media-recorder"
    );
    const mediaRecorder = new ExtMediaRecorder(stream, { mimeType: "audio/wav" });
    mediaRecorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    mediaRecorderRef.current = mediaRecorder;
    mediaRecorder.start();
    setIsRecording(true);
  }, []);

  const stopRecording = useCallback(() => {
    return new Promise<AudioAttachment | null>((resolve) => {
      const mediaRecorder = mediaRecorderRef.current;
      if (!mediaRecorder || mediaRecorder.state === "inactive") {
        resolve(null);
        return;
      }
      mediaRecorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/wav" });
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        resolve({ blob, mime_type: "audio/wav" });
      };
      mediaRecorder.stop();
      setIsRecording(false);
    });
  }, []);

  return { isRecording, startRecording, stopRecording };
}
