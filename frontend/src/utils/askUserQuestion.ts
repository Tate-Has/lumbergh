/** The AskUserQuestion tool call, read back out of the transcript.
 *
 * The terminal draws this as an interactive picker; the conversation view has
 * only the recorded tool call to work from, so the question, its options and
 * (once answered) the choice all have to be recovered from the JSON input and
 * the result text the tool wrote back.
 */
export const ASK_QUESTION_TOOL = 'AskUserQuestion'

export interface AskOption {
  label: string
  description?: string
}

export interface AskQuestion {
  question: string
  header?: string
  multiSelect?: boolean
  options: AskOption[]
}

function asOption(value: unknown): AskOption | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  if (typeof raw.label !== 'string') return null
  return {
    label: raw.label,
    description: typeof raw.description === 'string' ? raw.description : undefined,
  }
}

function asQuestion(value: unknown): AskQuestion | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  if (typeof raw.question !== 'string') return null
  const options = Array.isArray(raw.options)
    ? raw.options.map(asOption).filter((o): o is AskOption => o !== null)
    : []
  return {
    question: raw.question,
    header: typeof raw.header === 'string' ? raw.header : undefined,
    multiSelect: raw.multiSelect === true,
    options,
  }
}

export function parseAskQuestions(toolDetail?: string): AskQuestion[] {
  if (!toolDetail) return []
  let parsed: unknown
  try {
    parsed = JSON.parse(toolDetail)
  } catch {
    return []
  }
  if (!parsed || typeof parsed !== 'object') return []
  const questions = (parsed as Record<string, unknown>).questions
  if (!Array.isArray(questions)) return []
  return questions.map(asQuestion).filter((q): q is AskQuestion => q !== null)
}

// The tool writes its result back as: "…answered: "<question>"="<answer>", …".
const ANSWER_PAIR_RE = /"([^"]*)"="([^"]*)"/g

export function parseAskAnswers(resultText?: string): Record<string, string> {
  const answers: Record<string, string> = {}
  if (!resultText) return answers
  for (const [, question, answer] of resultText.matchAll(ANSWER_PAIR_RE)) {
    answers[question] = answer
  }
  return answers
}
