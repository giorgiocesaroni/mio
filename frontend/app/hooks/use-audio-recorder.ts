"use client";

import { useCallback, useRef, useState } from "react";
import { readFileAsBase64 } from "../lib/utils";

interface AudioAttachment {
  data: string;
  mime_type: string;
}

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    if (mediaRecorderRef.current?.state === "recording") return;
    chunksRef.current = [];
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : undefined,
    });
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
        const blob = new Blob(chunksRef.current, {
          type: mediaRecorder.mimeType,
        });
        const base64 = await readFileAsBase64(
          new File([blob], "voice", { type: mediaRecorder.mimeType }),
        );
        streamRef.current?.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
        resolve({ data: base64, mime_type: mediaRecorder.mimeType });
      };
      mediaRecorder.stop();
      setIsRecording(false);
    });
  }, []);

  return { isRecording, startRecording, stopRecording };
}
