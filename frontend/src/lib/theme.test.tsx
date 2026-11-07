import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { useTheme } from './theme'

afterEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
})

describe('useTheme', () => {
  it('switches the page to night shift and back', () => {
    const { result } = renderHook(() => useTheme())
    expect(result.current[0]).toBe('light')

    act(() => result.current[1]())

    expect(result.current[0]).toBe('dark')
    expect(document.documentElement).toHaveClass('dark')

    act(() => result.current[1]())

    expect(document.documentElement).not.toHaveClass('dark')
  })

  it('remembers the choice', () => {
    localStorage.setItem('maia-theme', 'dark')

    const { result } = renderHook(() => useTheme())

    expect(result.current[0]).toBe('dark')
  })
})
