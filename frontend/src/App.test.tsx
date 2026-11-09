import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

type Route = (body: unknown) => { status?: number; json: unknown }

let routes: Record<string, Route>
let requests: { path: string; body: unknown }[]

function reply(text: string, extra: object = {}) {
  return { json: { text, events: [], pending: [], ...extra } }
}

beforeEach(() => {
  requests = []
  routes = { '/api/sessions': () => ({ status: 201, json: { session_id: 's1' } }) }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = new URL(url).pathname
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : init?.body
      requests.push({ path, body })
      const route = routes[path]
      const { status = 200, json } = route ? route(body) : { status: 404, json: {} }
      return new Response(JSON.stringify(json), { status })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('MAIA chat', () => {
  it('sends a message and shows the reply with the tools used', async () => {
    routes['/api/sessions/s1/messages'] = () =>
      reply('6 brake pads available (BP-2207).', {
        events: [{ name: 'check_stock', ok: true, confirmed: null }],
      })
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Message'), 'How many brake pads?{Enter}')

    expect(await screen.findByText('6 brake pads available (BP-2207).')).toBeInTheDocument()
    expect(screen.getByText('Checked stock')).toBeInTheDocument()
    expect(requests.at(-1)).toEqual({
      path: '/api/sessions/s1/messages',
      body: { text: 'How many brake pads?' },
    })
  })

  it('asks for confirmation and sends the answer', async () => {
    routes['/api/sessions/s1/messages'] = () =>
      reply('Please confirm.', {
        pending: [{ tool: 'create_work_order', description: 'Open a high priority work order' }],
      })
    routes['/api/sessions/s1/confirmation'] = () =>
      reply('Work order opened.', {
        events: [{ name: 'create_work_order', ok: true, confirmed: true }],
      })
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Message'), 'Open it{Enter}')
    expect(await screen.findByText('Open a high priority work order')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText('Work order opened.')).toBeInTheDocument()
    expect(screen.queryByText('Needs your confirmation')).not.toBeInTheDocument()
    expect(requests.at(-1)?.body).toEqual({ approved: true })
  })

  it('shows the server message when the model is unavailable', async () => {
    routes['/api/sessions/s1/messages'] = () => ({
      status: 503,
      json: { detail: 'The AI model is unavailable right now. Please try again in a moment.' },
    })
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Message'), 'Hi{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('The AI model is unavailable')
  })

  it('shows readings and work orders in the side panel', async () => {
    routes['/api/sessions/s1/messages'] = () =>
      reply('4 mm is below the minimum.', {
        events: [
          {
            name: 'log_step',
            ok: true,
            confirmed: null,
            result: {
              step_log_id: 1,
              procedure_code: 'PROC-BRK-01',
              step: 4,
              reading: 4,
              unit: 'mm',
              assessment: {
                reading: 4,
                unit: 'mm',
                band: 'below_minimum',
                limits: 'warning 7, minimum 5, critical 3 mm',
                withdraw_from_service: false,
                work_order_priority: 'high',
              },
            },
          },
        ],
      })
    render(<App />)

    await userEvent.type(await screen.findByLabelText('Message'), 'Left pad is 4 mm{Enter}')

    const panel = await screen.findByRole('complementary', { name: 'Job overview' })
    expect(await within(panel).findByText('Below minimum')).toBeInTheDocument()
    expect(within(panel).getByText('4 mm')).toBeInTheDocument()
  })

  it('turns speech into a message', async () => {
    class FakeRecorder {
      mimeType = 'audio/webm'
      stream = { getTracks: () => [{ stop: () => {} }] }
      ondataavailable: ((event: { data: Blob }) => void) | null = null
      onstop: (() => void) | null = null
      start() {}
      stop() {
        this.ondataavailable?.({ data: new Blob(['audio'], { type: 'audio/webm' }) })
        this.onstop?.()
      }
    }
    vi.stubGlobal('MediaRecorder', FakeRecorder)
    vi.stubGlobal('navigator', { mediaDevices: { getUserMedia: async () => ({}) } })
    routes['/api/transcribe'] = () => ({ json: { text: 'Left pad is 4 mm.' } })
    routes['/api/sessions/s1/messages'] = () => reply('4 mm is below the minimum.')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Speak instead of typing' }))
    await userEvent.click(screen.getByRole('button', { name: 'Stop and send' }))

    expect(await screen.findByText('4 mm is below the minimum.')).toBeInTheDocument()
    expect(screen.getByText('Left pad is 4 mm.')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Spoken' })).toBeInTheDocument()
    expect(requests.at(-1)).toEqual({
      path: '/api/sessions/s1/messages',
      body: { text: 'Left pad is 4 mm.' },
    })
  })

  it('hides the microphone when the browser cannot record', async () => {
    render(<App />)

    await screen.findByRole('button', { name: 'Send' })
    expect(screen.queryByRole('button', { name: 'Speak instead of typing' })).toBeNull()
  })

  it('reads replies aloud when asked', async () => {
    const spoken: string[] = []
    vi.stubGlobal('speechSynthesis', {
      cancel: () => {},
      speak: (utterance: { text: string }) => spoken.push(utterance.text),
    })
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        lang = ''
        text: string
        constructor(text: string) {
          this.text = text
        }
      },
    )
    routes['/api/sessions/s1/messages'] = () => reply('Start with **lockout/tagout**.')
    render(<App />)

    await userEvent.click(await screen.findByRole('button', { name: 'Read replies aloud' }))
    await userEvent.type(screen.getByLabelText('Message'), 'Hi{Enter}')

    await screen.findByText('lockout/tagout')
    expect(spoken).toEqual(['Start with lockout/tagout.'])
  })

  it('opens the job overview as a side sheet on small screens', async () => {
    routes['/api/sessions/s1/messages'] = () =>
      reply('Step 1 logged.', {
        events: [
          {
            name: 'log_step',
            ok: true,
            confirmed: null,
            result: {
              step_log_id: 1,
              procedure_code: 'PROC-BRK-01',
              step: 1,
              reading: null,
              unit: null,
              assessment: null,
            },
          },
        ],
      })
    render(<App />)
    await userEvent.type(await screen.findByLabelText('Message'), 'Lockout done.{Enter}')
    await screen.findByText('Step 1 logged.')

    await userEvent.click(screen.getByRole('button', { name: 'Open job overview' }))

    const sheet = screen.getByRole('dialog', { name: 'Job overview' })
    expect(within(sheet).getByText('Step 1')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Job overview' })).toBeNull()
  })
})
