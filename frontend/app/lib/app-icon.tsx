import { ImageResponse } from "next/og";

export const APP_ICON_BACKGROUND = "#ef4444";
export const APP_ICON_FOREGROUND = "#ffffff";

type AppIconOptions = {
  /** Maskable icons keep the glyph inside a safe zone and stay square. */
  maskable?: boolean;
};

export function renderAppIcon(size: number, { maskable = false }: AppIconOptions = {}) {
  // Maskable icons are cropped by the OS, so keep the glyph away from the edges.
  const padding = maskable ? Math.round(size * 0.2) : 0;
  const fontSize = Math.round((size - padding * 2) * 0.8);
  const radius = maskable ? 0 : Math.round(size * 0.22);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: APP_ICON_BACKGROUND,
          borderRadius: radius,
          padding,
        }}
      >
        <span
          style={{
            display: "flex",
            color: APP_ICON_FOREGROUND,
            fontSize,
            fontWeight: 700,
            lineHeight: 1,
          }}
        >
          m
        </span>
      </div>
    ),
    { width: size, height: size },
  );
}
