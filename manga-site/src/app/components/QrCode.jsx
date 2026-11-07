import { useEffect, useState } from "react"
import QRCode from "qrcode"

// A QR code for `value`. Always dark on white, even in dark mode: some scanners can't read light-on-dark.
export function QrCode({ value, size = 240, label = "QR code" }) {
  const [src, setSrc] = useState(null)

  useEffect(() => {
    let live = true
    QRCode.toDataURL(value, { margin: 2, width: size * 2, errorCorrectionLevel: "M" })
      .then((url) => live && setSrc(url))
      .catch(() => live && setSrc(null))
    return () => {
      live = false
    }
  }, [value, size])

  return (
    <div className="rounded-lg bg-white p-1 shrink-0" style={{ width: size + 8, height: size + 8 }}>
      {src && <img src={src} width={size} height={size} alt={label} style={{ imageRendering: "pixelated" }} />}
    </div>
  )
}
