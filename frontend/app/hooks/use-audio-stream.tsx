"use client";

import { createContext, useContext, useEffect, useState } from "react";

interface AudioStreamContextValue {
  permissionGranted: boolean;
  error: string | null;
}

const AudioStreamContext = createContext<AudioStreamContextValue>({
  permissionGranted: false,
  error: null,
});

export function useAudioStream() {
  return useContext(AudioStreamContext);
}

export function AudioStreamProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((s) => {
        setPermissionGranted(true);
      })
      .catch((err) => setError(err.message));
  }, []);

  return (
    <AudioStreamContext.Provider value={{ permissionGranted, error }}>
      {children}
    </AudioStreamContext.Provider>
  );
}
