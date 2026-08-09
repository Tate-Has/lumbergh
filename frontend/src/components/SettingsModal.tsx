import { useState, useEffect, useCallback } from 'react'
import { X } from 'lucide-react'
import Button from './ui/Button'
import CloudSettings from './CloudSettings'
import SecuritySettings from './SecuritySettings'
import GeneralSettings from './GeneralSettings'
import BillSettings from './BillSettings'
import AISettingsTab from './AISettingsTab'
import { getDefaultProviderConfigs, type AIProviderConfig } from './aiProviders'
import { getApiBase } from '../config'

interface Props {
  onClose: () => void
}

interface AISettingsData {
  provider: string
  providers: Record<string, AIProviderConfig>
}

interface Settings {
  repoSearchDir: string
  gitGraphCommits: number
  myEmails?: string[]
  mineLookbackCommits?: number
  mineMaxBranchAgeDays?: number
  ai: AISettingsData
  defaultAgent?: string
  agentProviders?: Record<string, { label: string }>
  passwordSet?: boolean
  passwordSource?: string | null
  telemetryConsent?: boolean | null
  cloudUsername?: string
  tabVisibility?: Record<string, boolean>
  showSessionDots?: boolean
  scratchMaxAgeDays?: number
  questionDetectionEnabled?: boolean
  bill?: { harness?: string; personality?: string; customPersonality?: string }
}

type TabId = 'general' | 'bill' | 'ai' | 'cloud' | 'security'

export default function SettingsModal({ onClose }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>('general')
  const [repoSearchDir, setRepoSearchDir] = useState('')
  const [gitGraphCommits, setGitGraphCommits] = useState('100')
  const [myEmails, setMyEmails] = useState('')
  const [mineLookbackCommits, setMineLookbackCommits] = useState('5')
  const [mineMaxBranchAgeDays, setMineMaxBranchAgeDays] = useState('90')
  const [aiProvider, setAiProvider] = useState('ollama')
  const [providerConfigs, setProviderConfigs] =
    useState<Record<string, AIProviderConfig>>(getDefaultProviderConfigs)
  const [telemetryConsent, setTelemetryConsent] = useState(false)
  const [password, setPassword] = useState('')
  const [passwordSet, setPasswordSet] = useState(false)
  const [passwordSource, setPasswordSource] = useState<string | null>(null)
  const [passwordChanged, setPasswordChanged] = useState(false)
  const [defaultAgent, setDefaultAgent] = useState('claude-code')
  const [agentProviders, setAgentProviders] = useState<Record<string, { label: string }>>({})
  const [billHarness, setBillHarness] = useState('pi')
  const [billPersonality, setBillPersonality] = useState('professional')
  const [billCustomPersonality, setBillCustomPersonality] = useState('')
  const [tabVisibility, setTabVisibility] = useState<Record<string, boolean>>({
    git: true,
    files: true,
    todos: true,
    prompts: true,
    shared: true,
  })
  const [showSessionDots, setShowSessionDots] = useState(true)
  const [questionDetectionEnabled, setQuestionDetectionEnabled] = useState(false)
  const [scratchMaxAgeDays, setScratchMaxAgeDays] = useState('7')
  const [cloudUsername, setCloudUsername] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [restartNeeded, setRestartNeeded] = useState(false)

  const applyAiSettings = useCallback((ai: AISettingsData) => {
    setAiProvider(ai.provider || 'ollama')
    if (ai.providers) {
      setProviderConfigs((prev) => {
        const updated = { ...prev }
        Object.entries(ai.providers).forEach(([id, config]) => {
          if (updated[id]) {
            updated[id] = { ...updated[id], ...config }
          }
        })
        return updated
      })
    }
  }, [])

  const applyGraphSettings = useCallback((data: Settings) => {
    if (data.gitGraphCommits) setGitGraphCommits(String(data.gitGraphCommits))
    setMyEmails((data.myEmails ?? []).join(', '))
    if (data.mineLookbackCommits) setMineLookbackCommits(String(data.mineLookbackCommits))
    if (data.mineMaxBranchAgeDays != null)
      setMineMaxBranchAgeDays(String(data.mineMaxBranchAgeDays))
  }, [])

  const applyBillSettings = useCallback((bill: Settings['bill']) => {
    if (!bill) return
    if (bill.harness) setBillHarness(bill.harness)
    if (bill.personality) setBillPersonality(bill.personality)
    if (bill.customPersonality != null) setBillCustomPersonality(bill.customPersonality)
  }, [])

  const fetchSettings = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/settings`)
      if (!res.ok) throw new Error('Failed to fetch settings')
      const data: Settings = await res.json()
      setRepoSearchDir(data.repoSearchDir || '')
      applyGraphSettings(data)
      setPasswordSet(!!data.passwordSet)
      setPasswordSource(data.passwordSource ?? null)
      setTelemetryConsent(!!data.telemetryConsent)
      setCloudUsername(data.cloudUsername ?? null)
      if (data.defaultAgent) setDefaultAgent(data.defaultAgent)
      if (data.agentProviders) setAgentProviders(data.agentProviders)
      applyBillSettings(data.bill)
      if (data.tabVisibility) setTabVisibility(data.tabVisibility)
      if (data.showSessionDots != null) setShowSessionDots(data.showSessionDots)
      if (data.questionDetectionEnabled != null)
        setQuestionDetectionEnabled(data.questionDetectionEnabled)
      if (data.scratchMaxAgeDays != null) setScratchMaxAgeDays(String(data.scratchMaxAgeDays))
      if (data.ai) applyAiSettings(data.ai)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setIsLoading(false)
    }
  }, [applyAiSettings, applyBillSettings, applyGraphSettings])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const updateProviderConfig = (providerId: string, key: string, value: string) => {
    setProviderConfigs((prev) => ({
      ...prev,
      [providerId]: { ...prev[providerId], [key]: value },
    }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsSaving(true)
    setError(null)

    try {
      const payload: Record<string, unknown> = {}
      if (repoSearchDir.trim()) {
        payload.repoSearchDir = repoSearchDir.trim()
      }
      const parsedCommits = parseInt(gitGraphCommits) || 100
      payload.gitGraphCommits = Math.min(1000, Math.max(10, parsedCommits))
      payload.myEmails = myEmails
        .split(',')
        .map((email) => email.trim())
        .filter(Boolean)
      const parsedLookback = parseInt(mineLookbackCommits) || 5
      payload.mineLookbackCommits = Math.min(50, Math.max(1, parsedLookback))
      const parsedAge = parseInt(mineMaxBranchAgeDays)
      payload.mineMaxBranchAgeDays = Math.min(3650, Math.max(0, isNaN(parsedAge) ? 90 : parsedAge))
      payload.telemetryConsent = telemetryConsent
      payload.defaultAgent = defaultAgent
      payload.bill = {
        harness: billHarness,
        personality: billPersonality,
        customPersonality: billCustomPersonality,
      }
      payload.tabVisibility = tabVisibility
      payload.showSessionDots = showSessionDots
      payload.questionDetectionEnabled = questionDetectionEnabled
      payload.scratchMaxAgeDays = Math.max(0, parseInt(scratchMaxAgeDays) || 7)
      payload.ai = {
        provider: aiProvider,
        providers: providerConfigs,
      }
      if (passwordChanged) {
        payload.password = password
      }

      const res = await fetch(`${getApiBase()}/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to save settings')
      }

      await res.json()
      if (passwordChanged) {
        setRestartNeeded(true)
      } else {
        onClose()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: 'general', label: 'General' },
    { id: 'bill', label: 'Bill' },
    { id: 'ai', label: 'AI' },
    { id: 'cloud', label: 'Cloud' },
    { id: 'security', label: 'Security' },
  ]

  return (
    <div className="fixed inset-0 bg-bg-overlay backdrop-blur-[8px] flex items-center justify-center z-50 p-4">
      <div className="bg-bg-surface rounded-[var(--radius-2xl)] shadow-[var(--shadow-high)] w-full max-w-lg border border-border-default">
        <div className="flex items-center justify-between p-4 border-b border-border-default">
          <h2 className="text-lg font-semibold text-text-primary">Settings</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full bg-control-bg hover:bg-control-bg-hover flex items-center justify-center text-text-tertiary hover:text-text-primary transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-border-default">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-action border-b-2 border-action'
                  : 'text-text-tertiary hover:text-text-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-text-tertiary">Loading settings...</div>
        ) : (
          <form onSubmit={handleSubmit} className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
            {activeTab === 'general' && (
              <GeneralSettings
                repoSearchDir={repoSearchDir}
                onRepoSearchDirChange={setRepoSearchDir}
                gitGraphCommits={gitGraphCommits}
                onGitGraphCommitsChange={setGitGraphCommits}
                myEmails={myEmails}
                onMyEmailsChange={setMyEmails}
                mineLookbackCommits={mineLookbackCommits}
                onMineLookbackCommitsChange={setMineLookbackCommits}
                mineMaxBranchAgeDays={mineMaxBranchAgeDays}
                onMineMaxBranchAgeDaysChange={setMineMaxBranchAgeDays}
                defaultAgent={defaultAgent}
                onDefaultAgentChange={setDefaultAgent}
                agentProviders={agentProviders}
                tabVisibility={tabVisibility}
                onTabVisibilityChange={setTabVisibility}
                showSessionDots={showSessionDots}
                onShowSessionDotsChange={setShowSessionDots}
                questionDetectionEnabled={questionDetectionEnabled}
                onQuestionDetectionEnabledChange={setQuestionDetectionEnabled}
                scratchMaxAgeDays={scratchMaxAgeDays}
                onScratchMaxAgeDaysChange={setScratchMaxAgeDays}
                telemetryConsent={telemetryConsent}
                onTelemetryConsentChange={setTelemetryConsent}
              />
            )}

            {activeTab === 'bill' && (
              <BillSettings
                harness={billHarness}
                onHarnessChange={setBillHarness}
                agentProviders={agentProviders}
                personality={billPersonality}
                onPersonalityChange={setBillPersonality}
                customPersonality={billCustomPersonality}
                onCustomPersonalityChange={setBillCustomPersonality}
              />
            )}

            {activeTab === 'ai' && (
              <AISettingsTab
                aiProvider={aiProvider}
                onAiProviderChange={setAiProvider}
                providerConfigs={providerConfigs}
                onProviderConfigChange={updateProviderConfig}
                cloudUsername={cloudUsername}
              />
            )}

            {activeTab === 'cloud' && <CloudSettings onConnected={fetchSettings} />}

            {activeTab === 'security' && (
              <SecuritySettings
                password={password}
                onPasswordChange={(value) => {
                  setPassword(value)
                  setPasswordChanged(true)
                }}
                passwordSet={passwordSet}
                passwordSource={passwordSource}
                restartNeeded={restartNeeded}
              />
            )}

            {error && <div className="text-danger text-sm">{error}</div>}

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-text-tertiary hover:text-text-primary transition-colors"
              >
                Cancel
              </button>
              <Button type="submit" disabled={isSaving} variant="primary">
                {isSaving ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
