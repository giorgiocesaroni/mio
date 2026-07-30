"use client";

import { useCallback, useRef, useState } from "react";
import { MediaRecorder as ExtMediaRecorder, register } from "extendable-media-recorder";
import { connect } from "extendable-media-recorder-wav-encoder";

interface AudioAttachment {
  blob: Blob;
  mime_type: string;
}

let registered = false;

async function ensureWavEncoder() {
  if (!registered) {
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
