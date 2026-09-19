"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface AudioAttachment {
  blob: Blob;
  mime_type: string;
}

export function useAudioRecorder() {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  // getUserMedia is async: guard against a second tap while permission is
  // pending, which would otherwise open two streams and leak the first one.
  const isStartingRef = useRef(false);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  // If the component unmounts mid-recording (navigation, remount), release
  // the mic so it doesn't stay open in the background.
  useEffect(
    () => () => {
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        try {
          recorder.onstop = null;
          recorder.stop();
        } catch {
          // Already stopped — ignore.
        }
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      mediaRecorderRef.current = null;
    },
    [],
  );

  const startRecording = useCallback(async () => {
    if (
      mediaRecorderRef.current?.state === "recording" ||
      isStartingRef.current
    )
      return;
    if (typeof MediaRecorder === "undefined") {
      throw new Error("Audio recording is not supported by this browser.");
    }

    isStartingRef.current = true;
    try {
      chunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // The stop button may have been pressed (or the hook reset) while the
      // permission prompt was open — don't leave a stray stream behind.
      if (!isStartingRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;

      // Let the browser choose its native audio format. The backend normalizes
      // it with ffmpeg before sending it to the transcription API.
      let mediaRecorder: MediaRecorder;
      try {
        mediaRecorder = new MediaRecorder(stream);
      } catch (err) {
        stopTracks();
        throw err;
      }
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start();
      setIsRecording(true);
    } finally {
      isStartingRef.current = false;
    }
  }, [stopTracks]);

  const stopRecording = useCallback(() => {
    // Cancel a still-pending start so its late-arriving stream is discarded.
    isStartingRef.current = false;
    return new Promise<AudioAttachment | null>((resolve) => {
      const mediaRecorder = mediaRecorderRef.current;
      if (!mediaRecorder || mediaRecorder.state === "inactive") {
        stopTracks();
        mediaRecorderRef.current = null;
        resolve(null);
        return;
      }

      mediaRecorder.onstop = () => {
        const mime_type =
          mediaRecorder.mimeType || chunksRef.current[0]?.type || "audio/mp4";
        const blob = new Blob(chunksRef.current, { type: mime_type });
        stopTracks();
        mediaRecorderRef.current = null;
        // A tap so short no audio frames arrived (or a double-tap
        // start→stop race) yields an empty blob the backend rejects with
        // "Empty file" — surface it as null so callers can explain it.
        if (blob.size === 0) {
          resolve(null);
          return;
        }
        resolve({ blob, mime_type });
      };
      try {
        mediaRecorder.stop();
      } catch {
        stopTracks();
        mediaRecorderRef.current = null;
        resolve(null);
        return;
      }
      setIsRecording(false);
    });
  }, [stopTracks]);

  return { isRecording, startRecording, stopRecording };
}
