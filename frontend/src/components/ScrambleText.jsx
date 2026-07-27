import React, { useState, useEffect, useRef, useCallback } from "react"

const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+~|}{[]:;?><"

export default function ScrambleText({ text, isHovered, className = "", forceStart = false }) {
  const [displayText, setDisplayText] = useState(text)
  const intervalRef = useRef(null)
  const frameRef = useRef(0)

  const stopScramble = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setDisplayText(text)
  }, [text])

  const startScramble = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }

    frameRef.current = 0
    const targetLength = text.length
    const totalFrames = targetLength * 4 + 4

    intervalRef.current = setInterval(() => {
      frameRef.current += 1
      const currentFrame = frameRef.current

      const scrambled = text
        .split("")
        .map((char, index) => {
          if (char === " ") return " "
          const decodeFrame = index * 4
          if (currentFrame >= decodeFrame) {
            return char
          }
          return CHARS[Math.floor(Math.random() * CHARS.length)]
        })
        .join("")

      setDisplayText(scrambled)

      if (currentFrame >= totalFrames) {
        stopScramble()
      }
    }, 25)
  }, [text, stopScramble])

  useEffect(() => {
    if (isHovered || forceStart) {
      startScramble()
    } else {
      stopScramble()
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [isHovered, forceStart, startScramble, stopScramble])

  return <span className={className}>{displayText}</span>
}
