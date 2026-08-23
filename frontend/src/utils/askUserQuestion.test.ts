import { describe, it, expect } from 'vitest'
import { parseAskQuestions, parseAskAnswers } from './askUserQuestion'

const detail = JSON.stringify({
  questions: [
    {
      question: 'Push to dev now?',
      header: 'Push batch',
      multiSelect: false,
      options: [
        { label: 'Push — build & deploy', description: 'Fires CI.' },
        { label: "Hold — don't push yet", description: 'No CI.' },
      ],
    },
  ],
})

describe('parseAskQuestions', () => {
  it('reads the questions and their options out of the tool input', () => {
    const questions = parseAskQuestions(detail)

    expect(questions).toHaveLength(1)
    expect(questions[0].question).toBe('Push to dev now?')
    expect(questions[0].header).toBe('Push batch')
    expect(questions[0].options.map((o) => o.label)).toEqual([
      'Push — build & deploy',
      "Hold — don't push yet",
    ])
  })

  it('yields nothing rather than throwing on input it cannot read', () => {
    expect(parseAskQuestions(undefined)).toEqual([])
    expect(parseAskQuestions('not json')).toEqual([])
    expect(parseAskQuestions('{"questions": "nope"}')).toEqual([])
    expect(parseAskQuestions('{"questions": [{"question": 1}]}')).toEqual([])
  })
})

describe('parseAskAnswers', () => {
  it('pairs each question with what was chosen', () => {
    const answers = parseAskAnswers(
      'Your questions have been answered: "Push to dev now?"="Push — build & deploy", ' +
        '"Then what?"="Stop". You can now continue with these answers in mind.'
    )

    expect(answers).toEqual({
      'Push to dev now?': 'Push — build & deploy',
      'Then what?': 'Stop',
    })
  })

  it('is empty when there is nothing to pair up', () => {
    expect(parseAskAnswers(undefined)).toEqual({})
    expect(parseAskAnswers('interrupted by user')).toEqual({})
  })
})
