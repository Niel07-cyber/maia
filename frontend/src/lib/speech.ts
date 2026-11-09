// Voice for hands-free use: the browser records the technician, and reads MAIA's replies
// aloud with its built-in voices (free, nothing leaves the device for speaking).

import { useEffect, useRef, useState } from 'react'

/** Plain sentences from a Markdown reply, so the voice does not read out the symbols. */
export function toSpeech(markdown: string): string {
  return markdown
    .replace(/`([^`]*)`/g, '$1')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_#>]+/g, '')
    .replace(/^\s*(?:[-+]|\d+\.)\s+/gm, '')
    .replace(/([^.!?:])\s*\n+\s*/g, '$1. ') // a line break ends a sentence
    .replace(/\s*\n+\s*/g, ' ')
    .trim()
}

export function canSpeak(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

export function speak(text: string): void {
  if (!canSpeak()) return
  window.speechSynthesis.cancel() // a new reply replaces the one being read
  const utterance = new SpeechSynthesisUtterance(toSpeech(text))
  utterance.lang = 'en-GB'
  window.speechSynthesis.speak(utterance)
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel()
}

export function canRecord(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== 'undefined'
  )
}

/** Record from the microphone: start(), then stop() resolves with the recording. */
export function useRecorder() {
  const [recording, setRecording] = useState(false)
  const recorder = useRef<MediaRecorder | null>(null)

  useEffect(() => () => recorder.current?.stream.getTracks().forEach((track) => track.stop()), [])

  async function start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    recorder.current = new MediaRecorder(stream)
    recorder.current.start()
    setRecording(true)
  }

  function stop(): Promise<Blob> {
    return new Promise((resolve) => {
      const active = recorder.current
      if (!active) return resolve(new Blob())
      const chunks: Blob[] = []
      active.ondataavailable = (event) => chunks.push(event.data)
      active.onstop = () => {
        active.stream.getTracks().forEach((track) => track.stop()) // turn the mic off
        recorder.current = null
        setRecording(false)
        resolve(new Blob(chunks, { type: active.mimeType }))
      }
      active.stop()
    })
  }

  return { recording, start, stop }
}

const READ_ALOUD_KEY = 'maia-read-aloud'

/** Whether replies are read aloud, remembered per browser. Off by default. */
export function useReadAloud(): [boolean, () => void] {
  const [on, setOn] = useState(() => {
    try {
      return localStorage.getItem(READ_ALOUD_KEY) === 'on'
    } catch {
      return false
    }
  })

  function toggle() {
    setOn((current) => {
      const next = !current
      if (!next) stopSpeaking()
      try {
        localStorage.setItem(READ_ALOUD_KEY, next ? 'on' : 'off')
      } catch {
        // Not remembering the choice is fine.
      }
      return next
    })
  }

  return [on, toggle]
}
