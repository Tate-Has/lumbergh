import { useState } from 'react'
import { getApiBase } from '../../config'
import { parseAskAnswers, parseAskQuestions, type AskQuestion } from '../../utils/askUserQuestion'
import type { ToolItem } from '../../hooks/useConversationSocket'

/** Ask the terminal's picker to land on `index` and confirm.
 *
 * The picker opens on its first row, so the option's position in the list is
 * the whole instruction — no digit shortcuts, no free text.
 */
async function chooseOption(sessionName: string, index: number) {
  await fetch(`${getApiBase()}/session/${encodeURIComponent(sessionName)}/select-option`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index }),
  })
}

function Header({ question, pending }: { question: AskQuestion; pending: boolean }) {
  return (
    <div className="flex items-baseline gap-2">
      {question.header && (
        <span className="shrink-0 rounded bg-action/20 px-1.5 py-0.5 text-[11px] font-medium tracking-wide text-action uppercase">
          {question.header}
        </span>
      )}
      {pending && question.multiSelect && (
        <span className="text-xs text-text-tertiary">pick one or more</span>
      )}
    </div>
  )
}

function OptionButtons({
  question,
  sessionName,
  onAnswered,
}: {
  question: AskQuestion
  sessionName: string
  onAnswered: (label: string) => void
}) {
  const [sending, setSending] = useState(false)

  const choose = async (index: number, label: string) => {
    if (sending) return
    setSending(true)
    try {
      await chooseOption(sessionName, index)
      onAnswered(label)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      {question.options.map((option, index) => (
        <button
          key={option.label}
          disabled={sending}
          onClick={() => void choose(index, option.label)}
          className="rounded border border-border-default bg-bg-sunken px-2.5 py-2 text-left transition-colors hover:border-action hover:bg-control-bg-hover disabled:opacity-50"
        >
          <div className="flex items-baseline gap-2 text-sm text-text-primary">
            <span className="select-none text-xs text-text-muted">{index + 1}</span>
            <span className="font-medium">{option.label}</span>
          </div>
          {option.description && (
            <div className="mt-0.5 pl-5 text-xs leading-snug text-text-tertiary">
              {option.description}
            </div>
          )}
        </button>
      ))}
    </div>
  )
}

/** One question, and — while it is still open — a way to answer it.
 *
 * Only the question the picker is actually sitting on is answerable: the
 * terminal walks a multi-question ask in order, so offering the later ones
 * would send keystrokes to whichever question happens to be on screen.
 */
function QuestionBlock({
  question,
  sessionName,
  answer,
  answerable,
  onAnswered,
}: {
  question: AskQuestion
  sessionName: string
  answer?: string
  answerable: boolean
  onAnswered: (label: string) => void
}) {
  const pending = answer === undefined
  return (
    <div className="flex flex-col gap-2">
      <Header question={question} pending={pending} />
      <div className="text-sm leading-snug text-text-primary">{question.question}</div>
      {answer !== undefined ? (
        <div data-testid="question-answer" className="text-sm text-text-secondary">
          <span className="select-none text-success">✓ </span>
          {answer}
        </div>
      ) : answerable ? (
        <OptionButtons question={question} sessionName={sessionName} onAnswered={onAnswered} />
      ) : (
        <div className="text-xs text-text-tertiary">
          Answer the question above first — the terminal asks these in order.
        </div>
      )}
    </div>
  )
}

/** An AskUserQuestion, rendered as the thing it is rather than as a tool call.
 *
 * A folded "1 tool call" row is exactly wrong here: the session is stopped
 * until someone answers, and anyone living in this view has no other way to
 * see what is being asked.
 */
export default function QuestionCard({
  item,
  sessionName,
}: {
  item: ToolItem
  sessionName: string
}) {
  // What was chosen from here, before the transcript catches up with the result.
  const [sent, setSent] = useState<Record<number, string>>({})
  const questions = parseAskQuestions(item.tool_detail)
  const recorded = parseAskAnswers(item.result?.text)

  if (questions.length === 0) return null

  const answerFor = (question: AskQuestion, index: number) =>
    recorded[question.question] ?? sent[index]
  const firstOpen = questions.findIndex((q, i) => answerFor(q, i) === undefined)
  const waiting = firstOpen !== -1

  return (
    <div
      data-testid="question-card"
      className={`max-w-[72ch] rounded-lg border p-3 ${
        waiting ? 'border-action bg-action/5' : 'border-border-default bg-bg-surface'
      }`}
    >
      <div className="flex flex-col gap-4">
        {questions.map((question, index) => (
          <QuestionBlock
            key={`${question.question}-${index}`}
            question={question}
            sessionName={sessionName}
            answer={answerFor(question, index)}
            answerable={index === firstOpen}
            onAnswered={(label) => setSent((prev) => ({ ...prev, [index]: label }))}
          />
        ))}
      </div>
    </div>
  )
}
