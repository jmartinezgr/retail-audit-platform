import { Laptop, Loader2, Send, Wrench } from "lucide-react"
import { useState } from "react"
import Markdown from "react-markdown"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ApiError } from "@/lib/api"
import { api } from "@/lib/api"
import { useI18n } from "@/lib/i18n"
import type { AgentToolCall } from "@/types/api"

// La demo hosteada (Vercel + Render) no tiene Ollama/Qdrant corriendo -
// en vez de dejar que cada pregunta falle con un 503, esta build-time
// flag (puesta en "false" solo en las env vars de Vercel, ver
// .env.example) oculta el chat entero detrás de una explicación clara,
// con instrucciones para correrlo en local. Default = habilitado (dev
// local no necesita tocar nada).
const COPILOT_AVAILABLE = import.meta.env.VITE_COPILOT_AVAILABLE !== "false"

const AGENT_README_URL =
  "https://github.com/jmartinezgr/retail-audit-platform/blob/main/apps/agent/README.md"

// El modelo responde en Markdown (negrita, listas) - sin esto se veía el
// "**texto**" literal en vez de negrita. Sin plugin de tipografía de
// Tailwind en este proyecto, así que los estilos van directo por
// `components` en vez de una clase `prose`.
const MARKDOWN_COMPONENTS = {
  p: (props: React.ComponentProps<"p">) => <p className="mb-2 last:mb-0" {...props} />,
  ul: (props: React.ComponentProps<"ul">) => <ul className="mb-2 list-disc pl-5 last:mb-0" {...props} />,
  ol: (props: React.ComponentProps<"ol">) => <ol className="mb-2 list-decimal pl-5 last:mb-0" {...props} />,
  li: (props: React.ComponentProps<"li">) => <li className="mb-0.5" {...props} />,
  strong: (props: React.ComponentProps<"strong">) => <strong className="font-semibold" {...props} />,
  code: (props: React.ComponentProps<"code">) => (
    <code className="bg-muted rounded px-1 py-0.5 font-mono text-xs" {...props} />
  ),
}

interface Turn {
  question: string
  answer?: string
  toolCalls?: AgentToolCall[]
  error?: string
  unavailable?: boolean
}

function ToolCallsDisclosure({ toolCalls, label }: { toolCalls: AgentToolCall[]; label: string }) {
  if (toolCalls.length === 0) return null
  return (
    <details className="mt-2 rounded-md border bg-muted/30 p-2 text-xs">
      <summary className="text-muted-foreground flex cursor-pointer items-center gap-1.5 font-medium">
        <Wrench className="size-3.5" /> {label}
      </summary>
      <div className="mt-2 flex flex-col gap-2">
        {toolCalls.map((call, i) => (
          <div key={i} className="rounded border bg-background p-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="outline" className="font-mono text-[11px] font-normal">
                {call.name}
              </Badge>
              <span className="text-muted-foreground font-mono">{JSON.stringify(call.args)}</span>
            </div>
            <pre className="text-muted-foreground mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all font-mono">
              {call.result}
            </pre>
          </div>
        ))}
      </div>
    </details>
  )
}

function CopilotDisabledNotice() {
  const { t } = useI18n()
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <Laptop className="text-muted-foreground size-8" />
        <div>
          <p className="font-medium">{t("copilot.disabledTitle")}</p>
          <p className="text-muted-foreground mx-auto mt-1 max-w-md text-sm">{t("copilot.disabledBody")}</p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={AGENT_README_URL} target="_blank" rel="noreferrer">
            {t("copilot.disabledCta")}
          </a>
        </Button>
      </CardContent>
    </Card>
  )
}

export function CopilotPage() {
  const { t } = useI18n()
  const [question, setQuestion] = useState("")
  const [turns, setTurns] = useState<Turn[]>([])
  const [asking, setAsking] = useState(false)

  const samples = [t("copilot.sample1"), t("copilot.sample2"), t("copilot.sample3")]

  if (!COPILOT_AVAILABLE) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">{t("copilot.title")}</h1>
            <Badge variant="secondary">{t("copilot.localBadge")}</Badge>
          </div>
          <p className="text-muted-foreground max-w-2xl text-sm">{t("copilot.subtitle")}</p>
        </div>
        <CopilotDisabledNotice />
      </div>
    )
  }

  async function ask(q: string) {
    const trimmed = q.trim()
    if (!trimmed || asking) return
    setQuestion("")
    setAsking(true)
    setTurns((prev) => [...prev, { question: trimmed }])
    try {
      const res = await api.agent.ask(trimmed)
      setTurns((prev) =>
        prev.map((turn, i) =>
          i === prev.length - 1 ? { ...turn, answer: res.answer, toolCalls: res.tool_calls } : turn,
        ),
      )
    } catch (e) {
      const unavailable = e instanceof ApiError && e.status === 503
      const message = e instanceof Error ? e.message : t("copilot.genericError")
      setTurns((prev) =>
        prev.map((turn, i) => (i === prev.length - 1 ? { ...turn, error: message, unavailable } : turn)),
      )
    } finally {
      setAsking(false)
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    void ask(question)
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{t("copilot.title")}</h1>
          <Badge variant="secondary">{t("copilot.localBadge")}</Badge>
        </div>
        <p className="text-muted-foreground max-w-2xl text-sm">{t("copilot.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("copilot.title")}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {turns.length === 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-muted-foreground text-sm">{t("copilot.emptyState")}</p>
              <div className="flex flex-wrap gap-2">
                {samples.map((s) => (
                  <Button key={s} type="button" variant="outline" size="sm" onClick={() => void ask(s)}>
                    {s}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-col gap-4">
            {turns.map((turn, i) => (
              <div key={i} className="flex flex-col gap-2">
                <div className="bg-muted ml-auto max-w-[85%] rounded-lg px-3 py-2 text-sm">{turn.question}</div>
                <div className="mr-auto max-w-[85%] rounded-lg border px-3 py-2 text-sm">
                  {turn.error ? (
                    <div>
                      <p className="text-destructive font-medium">
                        {turn.unavailable ? t("copilot.unavailableTitle") : t("copilot.genericError")}
                      </p>
                      <p className="text-muted-foreground mt-1 text-xs">
                        {turn.unavailable ? t("copilot.unavailableBody") : turn.error}
                      </p>
                    </div>
                  ) : turn.answer !== undefined ? (
                    <div>
                      <Markdown components={MARKDOWN_COMPONENTS}>{turn.answer}</Markdown>
                      {turn.toolCalls && (
                        <ToolCallsDisclosure
                          toolCalls={turn.toolCalls}
                          label={t("copilot.toolCallsLabel", { count: turn.toolCalls.length })}
                        />
                      )}
                    </div>
                  ) : (
                    <span className="text-muted-foreground flex items-center gap-1.5">
                      <Loader2 className="size-3.5 animate-spin" /> {t("copilot.thinking")}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("copilot.placeholder")}
              disabled={asking}
            />
            <Button type="submit" disabled={asking || !question.trim()}>
              {asking ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
              {t("copilot.ask")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
