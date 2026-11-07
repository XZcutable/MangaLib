import { useEffect, useRef, useState } from "react"
import { X } from "lucide-react"
import { isNative } from "../lib/storage"

// The camera needs a secure page (https or localhost). The Android app counts as one; a plain-http web
// address doesn't, but there the phone's own camera app can open the link instead.
export const canScanQr = Boolean(navigator.mediaDevices?.getUserMedia) && (isNative || window.isSecureContext)

// Full-screen camera view that reports the first QR code it reads, then closes
export function QrScanner({ onResult, onClose, hint = "Point the camera at a myMangaLib QR code" }) {
  const video = useRef(null)
  const [error, setError] = useState(null)
  const onResultRef = useRef(onResult)
  onResultRef.current = onResult

  useEffect(() => {
    let scanner = null
    let stopped = false
    // Loaded only when needed, so the scanner isn't part of every page load
    import("qr-scanner")
      .then(async ({ default: QrScannerLib }) => {
        if (stopped) return
        scanner = new QrScannerLib(
          video.current,
          (result) => {
            if (stopped) return
            stopped = true
            scanner.stop()
            onResultRef.current(result.data)
          },
          { preferredCamera: "environment", highlightScanRegion: true, highlightCodeOutline: true, returnDetailedScanResult: true },
        )
        try {
          await scanner.start()
        } catch (error) {
          if (stopped) return
          const denied = /denied|NotAllowed|permission/i.test(String(error?.name || error?.message || error))
          setError(
            denied
              ? "Camera access is blocked. Allow the camera for myMangaLib in your phone's settings, or type the address instead."
              : "Couldn't start the camera.",
          )
        }
      })
      .catch(() => setError("Couldn't load the scanner."))
    return () => {
      stopped = true
      scanner?.destroy()
    }
  }, [])

  return (
    <div className="fixed inset-0 z-[60] bg-black flex flex-col" role="dialog" aria-label="Scan a QR code">
      <div className="flex items-center justify-between px-4 py-3 text-white">
        <p className="text-sm">{hint}</p>
        <button onClick={onClose} className="p-2 rounded-md hover:bg-white/10" aria-label="Close the scanner">
          <X className="w-6 h-6" />
        </button>
      </div>
      <div className="relative flex-1 min-h-0">
        <video ref={video} className="absolute inset-0 w-full h-full object-cover" playsInline muted />
        {error && (
          <div className="absolute inset-0 flex items-center justify-center p-6">
            <p className="text-center text-white bg-black/70 rounded-lg p-4">{error}</p>
          </div>
        )}
      </div>
    </div>
  )
}
