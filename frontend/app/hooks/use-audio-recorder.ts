"use client";

import { useCallback, useRef, useState } from "react";

interface AudioAttachment {
  blob: Blob;
  mime_type: string;
}

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    if (mediaRecorderRef.current?.state === "recording") return;
    if (typeof MediaRecorder === "undefined") {
      throw new Error("Audio recording is not supported by this browser.");
    }

    chunksRef.current = [];
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    // Let the browser choose its native audio format. The backend normalizes
    // it with ffmpeg before sending it to the transcription API.
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
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

      mediaRecorder.onstop = () => {
        const mime_type = mediaRecorder.mimeType || chunksRef.current[0]?.type || "audio/mp4";
        const blob = new Blob(chunksRef.current, { type: mime_type });
        streamRef.current?.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        resolve({ blob, mime_type });
      };
      mediaRecorder.stop();
      setIsRecording(false);
    });
  }, []);

  return { isRecording, startRecording, stopRecording };
}
