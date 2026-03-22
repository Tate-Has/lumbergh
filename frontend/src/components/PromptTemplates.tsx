import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Play,
  GripVertical,
  X,
  Upload,
  Download,
  RefreshCw,
  Search,
  Check,
  Unlink,
  CloudOff,
} from 'lucide-react'
import { getApiBase } from '../config'
import { useLocalStorageDraft } from '../hooks/useLocalStorageDraft'

// Simple UUID generator that works without crypto.randomUUID()
function generateId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

interface PromptTemplate {
  id: string
  name: string
  prompt: string
  source_code?: string
  source_version?: number
  auto_update?: boolean
}

interface CommunityPrompt {
  share_code: string
  name: string
  prompt: string // truncated to 200 chars
  author_username: string
  tags: string[]
  install_count: number
  version: number
}

function EditModeActions({
  template,
  scope,
  cloudConnected,
  sharingId,
  onCopyToGlobal,
  onCopyToProject,
  onDelete,
  onShare,
  onDetach,
}: {
  template: PromptTemplate
  scope: 'project' | 'global'
  cloudConnected: boolean
  sharingId: string | null
  onCopyToGlobal: (template: PromptTemplate) => void
  onCopyToProject: (template: PromptTemplate) => void
  onDelete: (id: string, scope: 'project' | 'global') => void
  onShare: (template: PromptTemplate) => void
  onDetach: (template: PromptTemplate, scope: 'project' | 'global') => void
}) {
  const [codeCopied, setCodeCopied] = useState(false)
  const isSharing = sharingId === template.id

  const handleCopyCode = (e: React.MouseEvent, code: string) => {
    e.stopPropagation()
    navigator.clipboard.writeText(code)
    setCodeCopied(true)
    setTimeout(() => setCodeCopied(false), 2000)
  }

  return (
    <>
      {cloudConnected && (
        <>
          {template.source_code ? (
            <>
              <span
                className="text-xs text-text-muted font-mono cursor-pointer hover:text-text-secondary"
                onClick={(e) => handleCopyCode(e, template.source_code!)}
                title="Click to copy share code"
              >
                {codeCopied ? <Check size={14} className="text-green-400" /> : template.source_code}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDetach(template, scope)
                }}
                className="text-sm text-text-muted hover:text-orange-400 transition-colors px-1"
                title="Detach from cloud (make local-only)"
              >
                <Unlink size={14} />
              </button>
            </>
          ) : (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onShare(template)
              }}
              disabled={isSharing}
              className="text-sm text-text-muted hover:text-blue-400 transition-colors px-1 disabled:opacity-50"
              title="Share to cloud"
            >
              {isSharing ? '...' : <Upload size={14} />}
            </button>
          )}
        </>
      )}
      {scope === 'project' ? (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onCopyToGlobal(template)
          }}
          className="text-sm text-text-muted hover:text-green-400 transition-colors px-1"
          title="Move to Global"
        >
          ↑G
        </button>
      ) : (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onCopyToProject(template)
          }}
          className="text-sm text-text-muted hover:text-green-400 transition-colors px-1"
          title="Copy to Project"
        >
          ↓P
        </button>
      )}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDelete(template.id, scope)
        }}
        className="text-sm text-text-muted hover:text-red-400 transition-colors px-1"
        title="Delete"
      >
        <X size={16} />
      </button>
    </>
  )
}

function TemplateItem({
  template,
  index,
  scope,
  editMode,
  sessionName,
  cloudConnected,
  isDragging,
  isDragOver,
  sharingId,
  updateAvailable,
  onDragStart,
  onDragOver,
  onDragEnd,
  onEdit,
  onSendToTerminal,
  onCopyToGlobal,
  onCopyToProject,
  onDelete,
  onShare,
  onUpdate,
  onDetach,
}: {
  template: PromptTemplate
  index: number
  scope: 'project' | 'global'
  editMode: boolean
  sessionName?: string | null
  cloudConnected: boolean
  isDragging: boolean
  isDragOver: boolean
  sharingId: string | null
  updateAvailable: CommunityPrompt | null
  onDragStart: (index: number, scope: 'project' | 'global') => void
  onDragOver: (e: React.DragEvent, index: number, scope: 'project' | 'global') => void
  onDragEnd: () => void
  onEdit: (template: PromptTemplate, scope: 'project' | 'global') => void
  onSendToTerminal: (template: PromptTemplate, sendEnter: boolean) => void
  onCopyToGlobal: (template: PromptTemplate) => void
  onCopyToProject: (template: PromptTemplate) => void
  onDelete: (id: string, scope: 'project' | 'global') => void
  onShare: (template: PromptTemplate) => void
  onUpdate: (template: PromptTemplate, latest: CommunityPrompt) => void
  onDetach: (template: PromptTemplate, scope: 'project' | 'global') => void
}) {
  return (
    <div
      draggable={editMode}
      onDragStart={() => onDragStart(index, scope)}
      onDragOver={(e) => onDragOver(e, index, scope)}
      onDragEnd={onDragEnd}
      onClick={editMode ? () => onEdit(template, scope) : undefined}
      className={`flex items-center gap-2 p-3 bg-bg-surface rounded border border-border-default group ${
        editMode ? 'cursor-pointer hover:border-blue-500/50' : ''
      } ${isDragging ? 'opacity-50' : ''} ${isDragOver ? 'border-blue-500' : ''}`}
    >
      {editMode && <GripVertical size={16} className="text-text-muted select-none" />}
      {!editMode && sessionName && (
        <button
          onClick={() => onSendToTerminal(template, false)}
          className="text-text-muted hover:text-yellow-400 transition-colors px-1"
          title="Send text (no Enter)"
        >
          <Play size={18} />
        </button>
      )}
      <span className="flex-1 text-text-primary truncate" title={template.prompt}>
        {template.name}
        {template.source_code && !editMode && (
          <span
            className="ml-1.5 text-xs text-text-muted"
            title={`Linked: ${template.source_code}`}
          >
            ☁
          </span>
        )}
      </span>
      {!editMode && updateAvailable && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onUpdate(template, updateAvailable)
          }}
          className="flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 transition-colors px-1"
          title={`Update available: v${updateAvailable.version}`}
        >
          <RefreshCw size={14} />
          <span>v{updateAvailable.version}</span>
        </button>
      )}
      {editMode && (
        <EditModeActions
          template={template}
          scope={scope}
          cloudConnected={cloudConnected}
          sharingId={sharingId}
          onCopyToGlobal={onCopyToGlobal}
          onCopyToProject={onCopyToProject}
          onDelete={onDelete}
          onShare={onShare}
          onDetach={onDetach}
        />
      )}
    </div>
  )
}

function TemplateSection({
  title,
  scope,
  templates,
  editMode,
  showForm,
  editingTemplate,
  onStartAdd,
  renderInlineEditForm,
  renderTemplateItem,
}: {
  title: string
  scope: 'project' | 'global'
  templates: PromptTemplate[]
  editMode: boolean
  showForm: 'project' | 'global' | null
  editingTemplate: PromptTemplate | null
  onStartAdd: (scope: 'project' | 'global') => void
  renderInlineEditForm: (template: PromptTemplate, scope: 'project' | 'global') => React.ReactNode
  renderTemplateItem: (
    template: PromptTemplate,
    index: number,
    scope: 'project' | 'global'
  ) => React.ReactNode
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-tertiary">{title}</h3>
        {editMode && showForm !== scope && (
          <button
            type="button"
            onClick={() => onStartAdd(scope)}
            className="text-xs px-2 py-1 bg-control-bg text-text-tertiary rounded hover:bg-control-bg-hover hover:text-text-secondary transition-colors"
          >
            + Add
          </button>
        )}
      </div>
      {showForm === scope && !editingTemplate && (
        <div className="mb-2">{renderInlineEditForm({ id: '', name: '', prompt: '' }, scope)}</div>
      )}
      {templates.length === 0 && showForm !== scope ? (
        <div className="text-text-muted text-sm py-2">No {title.toLowerCase()} yet.</div>
      ) : (
        <div className="space-y-2">
          {templates.map((template, index) => renderTemplateItem(template, index, scope))}
        </div>
      )}
    </div>
  )
}

function CommunitySection({
  prompts,
  searchQuery,
  onSearchChange,
  installedCodes,
  onInstall,
  loading,
}: {
  prompts: CommunityPrompt[]
  searchQuery: string
  onSearchChange: (q: string) => void
  installedCodes: Set<string>
  onInstall: (prompt: CommunityPrompt) => void
  loading: boolean
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium text-text-tertiary">Community</h3>
      </div>
      {/* Search */}
      <div className="relative mb-2">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search prompts..."
          className="w-full pl-8 pr-3 py-1.5 text-sm bg-input-bg text-text-primary rounded border border-input-border focus:outline-none focus:border-blue-500"
        />
      </div>
      {loading ? (
        <div className="text-text-muted text-sm py-2">Loading...</div>
      ) : prompts.length === 0 ? (
        <div className="text-text-muted text-sm py-2">
          {searchQuery ? 'No prompts match your search.' : 'No community prompts yet.'}
        </div>
      ) : (
        <div className="space-y-2">
          {prompts.map((p) => {
            const isInstalled = installedCodes.has(p.share_code)
            return (
              <div
                key={p.share_code}
                className="p-3 bg-bg-surface rounded border border-border-default"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-text-primary font-medium text-sm truncate flex-1">
                    {p.name}
                  </span>
                  <span className="text-xs text-text-muted">v{p.version}</span>
                  <span className="text-xs text-text-muted">@{p.author_username}</span>
                  {isInstalled ? (
                    <span className="text-green-400 px-1" title="Already installed">
                      <Check size={16} />
                    </span>
                  ) : (
                    <button
                      onClick={() => onInstall(p)}
                      className="text-text-muted hover:text-green-400 transition-colors px-1"
                      title="Add to Global"
                    >
                      <Download size={16} />
                    </button>
                  )}
                </div>
                {p.tags.length > 0 && (
                  <div className="flex gap-1 mb-1 flex-wrap">
                    {p.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs px-1.5 py-0.5 bg-blue-500/10 text-blue-400 rounded"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                <div className="text-xs text-text-muted truncate">{p.prompt}</div>
                <div className="text-xs text-text-muted mt-1">{p.install_count} installs</div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

interface PromptTemplatesProps {
  sessionName?: string | null
  onFocusTerminal?: () => void
}

export default function PromptTemplates({ sessionName, onFocusTerminal }: PromptTemplatesProps) {
  const [projectTemplates, setProjectTemplates] = useState<PromptTemplate[]>([])
  const [globalTemplates, setGlobalTemplates] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(!!sessionName)
  const [saving, setSaving] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<PromptTemplate | null>(null)
  const [showForm, setShowForm] = useState<'project' | 'global' | null>(null)
  const [formName, setFormName, clearFormName] = useLocalStorageDraft(
    `prompt-form:${sessionName}:name`
  )
  const [formPrompt, setFormPrompt, clearFormPrompt] = useLocalStorageDraft(
    `prompt-form:${sessionName}:prompt`
  )
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [dragScope, setDragScope] = useState<'project' | 'global' | null>(null)

  // Cloud / sharing state
  const [cloudConnected, setCloudConnected] = useState(false)
  const [sharingId, setSharingId] = useState<string | null>(null)
  const [communityPrompts, setCommunityPrompts] = useState<CommunityPrompt[]>([])
  const [communityLoading, setCommunityLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showImport, setShowImport] = useState(false)
  const [importCode, setImportCode] = useState('')
  const [importPreview, setImportPreview] = useState<CommunityPrompt | null>(null)
  const [importLoading, setImportLoading] = useState(false)
  const [availableUpdates, setAvailableUpdates] = useState<Record<string, CommunityPrompt>>({})
  const [updatePreview, setUpdatePreview] = useState<{
    template: PromptTemplate
    latest: CommunityPrompt
  } | null>(null)
  const [detachConfirm, setDetachConfirm] = useState<{
    template: PromptTemplate
    scope: 'project' | 'global'
  } | null>(null)
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout>>(null)

  // Check cloud connection on mount
  useEffect(() => {
    fetch(`${getApiBase()}/settings`)
      .then((res) => res.json())
      .then((data) => {
        setCloudConnected(!!data.cloudUsername)
      })
      .catch(() => setCloudConnected(false))
  }, [])

  // Fetch templates
  useEffect(() => {
    if (!sessionName) return
    Promise.all([
      fetch(`${getApiBase()}/sessions/${sessionName}/prompts`).then((res) => res.json()),
      fetch(`${getApiBase()}/global/prompts`).then((res) => res.json()),
    ])
      .then(([projectData, globalData]) => {
        setProjectTemplates(projectData.templates || [])
        setGlobalTemplates(globalData.templates || [])
        setLoading(false)
      })
      .catch((err) => {
        console.error('Failed to fetch prompts:', err)
        setLoading(false)
      })
  }, [sessionName])

  // Fetch community prompts when cloud-connected
  const fetchCommunity = useCallback(
    async (q: string = '') => {
      if (!cloudConnected) return
      setCommunityLoading(true)
      try {
        const params = q ? `?q=${encodeURIComponent(q)}` : ''
        const res = await fetch(`${getApiBase()}/cloud/prompts/community${params}`)
        if (res.ok) {
          const data = await res.json()
          setCommunityPrompts(data)
        }
      } catch (err) {
        console.error('Failed to fetch community prompts:', err)
      }
      setCommunityLoading(false)
    },
    [cloudConnected]
  )

  useEffect(() => {
    fetchCommunity()
  }, [fetchCommunity])

  // Debounced search
  useEffect(() => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    searchDebounceRef.current = setTimeout(() => {
      fetchCommunity(searchQuery)
    }, 400)
    return () => {
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current)
    }
  }, [searchQuery, fetchCommunity])

  // Apply auto-updates to a template list
  const applyAutoUpdates = useCallback(
    (
      templates: PromptTemplate[],
      updates: Record<string, CommunityPrompt>,
      save: (t: PromptTemplate[]) => Promise<void>,
      setter: React.Dispatch<React.SetStateAction<PromptTemplate[]>>
    ) => {
      const updated = templates.map((t) => {
        if (t.auto_update && t.source_code && updates[t.source_code]) {
          const latest = updates[t.source_code]
          return { ...t, prompt: latest.prompt, source_version: latest.version }
        }
        return t
      })
      if (JSON.stringify(updated) !== JSON.stringify(templates)) {
        setter(updated)
        save(updated)
      }
    },
    []
  )

  // Check for updates on linked prompts
  useEffect(() => {
    if (!cloudConnected) return
    const allTemplates = [...projectTemplates, ...globalTemplates]
    const linkedCodes = allTemplates
      .filter((t) => t.source_code && t.source_version)
      .map((t) => ({ code: t.source_code!, version: t.source_version! }))

    if (linkedCodes.length === 0) return

    const checkUpdates = async () => {
      const updates: Record<string, CommunityPrompt> = {}
      await Promise.all(
        linkedCodes.map(async ({ code, version }) => {
          try {
            const res = await fetch(`${getApiBase()}/cloud/prompts/shared/${code}`)
            if (res.ok) {
              const data = await res.json()
              if (data.version > version) {
                updates[code] = data
              }
            }
          } catch {
            // ignore
          }
        })
      )
      setAvailableUpdates(updates)

      const hasAutoUpdates = allTemplates.some(
        (t) => t.auto_update && t.source_code && updates[t.source_code]
      )
      if (hasAutoUpdates) {
        applyAutoUpdates(globalTemplates, updates, saveGlobalTemplates, setGlobalTemplates)
        applyAutoUpdates(projectTemplates, updates, saveProjectTemplates, setProjectTemplates)

        setAvailableUpdates((prev) => {
          const next = { ...prev }
          for (const t of allTemplates) {
            if (t.auto_update && t.source_code && next[t.source_code]) {
              delete next[t.source_code]
            }
          }
          return next
        })
      }
    }
    checkUpdates()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cloudConnected, projectTemplates.length, globalTemplates.length])

  const saveProjectTemplates = async (templates: PromptTemplate[]) => {
    if (!sessionName) return
    setSaving(true)
    try {
      await fetch(`${getApiBase()}/sessions/${sessionName}/prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templates }),
      })
    } catch (err) {
      console.error('Failed to save project prompts:', err)
    }
    setSaving(false)
  }

  const saveGlobalTemplates = async (templates: PromptTemplate[]) => {
    setSaving(true)
    try {
      await fetch(`${getApiBase()}/global/prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ templates }),
      })
    } catch (err) {
      console.error('Failed to save global prompts:', err)
    }
    setSaving(false)
  }

  const handleSendToTerminal = async (template: PromptTemplate, sendEnter: boolean) => {
    if (!sessionName) return
    try {
      await fetch(`${getApiBase()}/session/${sessionName}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: template.prompt, send_enter: sendEnter }),
      })
      onFocusTerminal?.()
    } catch (err) {
      console.error('Failed to send to terminal:', err)
    }
  }

  const upsertInScope = (
    scope: 'project' | 'global',
    template: PromptTemplate,
    existing: PromptTemplate | null
  ) => {
    if (scope === 'project') {
      const updated = existing
        ? projectTemplates.map((t) => (t.id === existing.id ? template : t))
        : [...projectTemplates, template]
      setProjectTemplates(updated)
      saveProjectTemplates(updated)
    } else {
      const updated = existing
        ? globalTemplates.map((t) => (t.id === existing.id ? template : t))
        : [...globalTemplates, template]
      setGlobalTemplates(updated)
      saveGlobalTemplates(updated)
    }
  }

  const handleSaveTemplate = () => {
    if (!formName.trim() || !formPrompt.trim() || !showForm) return

    const sanitizedName = formName
      .trim()
      .replace(/\s+/g, '_')
      .replace(/[^a-zA-Z0-9_-]/g, '')
    if (!sanitizedName) return

    // If editing a linked prompt and the content changed, detach it
    const isContentChanged = editingTemplate && editingTemplate.prompt !== formPrompt.trim()
    const keepLink = editingTemplate?.source_code && !isContentChanged

    const newTemplate: PromptTemplate = {
      id: editingTemplate?.id || generateId(),
      name: sanitizedName,
      prompt: formPrompt.trim(),
      ...(keepLink
        ? {
            source_code: editingTemplate!.source_code,
            source_version: editingTemplate!.source_version,
            auto_update: editingTemplate!.auto_update,
          }
        : {}),
    }

    upsertInScope(showForm, newTemplate, editingTemplate)

    clearFormName()
    clearFormPrompt()
    setEditingTemplate(null)
    setShowForm(null)
  }

  const handleEdit = (template: PromptTemplate, scope: 'project' | 'global') => {
    setEditingTemplate(template)
    setFormName(template.name)
    setFormPrompt(template.prompt)
    setShowForm(scope)
  }

  const handleCancelEdit = () => {
    setEditingTemplate(null)
    clearFormName()
    clearFormPrompt()
    setShowForm(null)
  }

  const handleStartAdd = (scope: 'project' | 'global') => {
    setEditingTemplate(null)
    // Don't clear drafts - localStorage may have unsaved content from a previous session
    setShowForm(scope)
  }

  const handleDelete = (id: string, scope: 'project' | 'global') => {
    if (scope === 'project') {
      const updated = projectTemplates.filter((t) => t.id !== id)
      setProjectTemplates(updated)
      saveProjectTemplates(updated)
    } else {
      const updated = globalTemplates.filter((t) => t.id !== id)
      setGlobalTemplates(updated)
      saveGlobalTemplates(updated)
    }
    if (editingTemplate?.id === id) {
      handleCancelEdit()
    }
  }

  const handleCopyToGlobal = async (template: PromptTemplate) => {
    if (!sessionName) return
    try {
      await fetch(`${getApiBase()}/sessions/${sessionName}/prompts/${template.id}/copy-to-global`, {
        method: 'POST',
      })
      // Refresh both lists
      const [projectData, globalData] = await Promise.all([
        fetch(`${getApiBase()}/sessions/${sessionName}/prompts`).then((res) => res.json()),
        fetch(`${getApiBase()}/global/prompts`).then((res) => res.json()),
      ])
      setProjectTemplates(projectData.templates || [])
      setGlobalTemplates(globalData.templates || [])
    } catch (err) {
      console.error('Failed to copy to global:', err)
    }
  }

  const handleCopyToProject = async (template: PromptTemplate) => {
    if (!sessionName) return
    try {
      await fetch(
        `${getApiBase()}/sessions/${sessionName}/global/prompts/${template.id}/copy-to-project`,
        {
          method: 'POST',
        }
      )
      // Refresh project list
      const projectData = await fetch(`${getApiBase()}/sessions/${sessionName}/prompts`).then(
        (res) => res.json()
      )
      setProjectTemplates(projectData.templates || [])
    } catch (err) {
      console.error('Failed to copy to project:', err)
    }
  }

  // Share a prompt to cloud
  const handleShare = async (template: PromptTemplate) => {
    setSharingId(template.id)
    try {
      const res = await fetch(`${getApiBase()}/cloud/prompts/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: template.name, prompt: template.prompt }),
      })
      if (!res.ok) throw new Error('Share failed')
      const data = await res.json()

      // Update template with source_code link
      const updatedTemplate: PromptTemplate = {
        ...template,
        source_code: data.share_code,
        source_version: data.version,
      }

      // Update in the right list
      const inProject = projectTemplates.some((t) => t.id === template.id)
      if (inProject) {
        const updated = projectTemplates.map((t) => (t.id === template.id ? updatedTemplate : t))
        setProjectTemplates(updated)
        saveProjectTemplates(updated)
      } else {
        const updated = globalTemplates.map((t) => (t.id === template.id ? updatedTemplate : t))
        setGlobalTemplates(updated)
        saveGlobalTemplates(updated)
      }
    } catch (err) {
      console.error('Failed to share prompt:', err)
    }
    setSharingId(null)
  }

  // Apply an update from cloud
  const handleApplyUpdate = (template: PromptTemplate, latest: CommunityPrompt) => {
    setUpdatePreview({ template, latest })
  }

  const confirmUpdate = (autoUpdate: boolean) => {
    if (!updatePreview) return
    const { template, latest } = updatePreview

    const updatedTemplate: PromptTemplate = {
      ...template,
      prompt: latest.prompt,
      source_version: latest.version,
      auto_update: autoUpdate,
    }

    const inProject = projectTemplates.some((t) => t.id === template.id)
    if (inProject) {
      const updated = projectTemplates.map((t) => (t.id === template.id ? updatedTemplate : t))
      setProjectTemplates(updated)
      saveProjectTemplates(updated)
    } else {
      const updated = globalTemplates.map((t) => (t.id === template.id ? updatedTemplate : t))
      setGlobalTemplates(updated)
      saveGlobalTemplates(updated)
    }

    // Remove from available updates
    if (template.source_code) {
      setAvailableUpdates((prev) => {
        const next = { ...prev }
        delete next[template.source_code!]
        return next
      })
    }
    setUpdatePreview(null)
  }

  // Detach a prompt from its cloud source
  const handleDetach = (template: PromptTemplate, scope: 'project' | 'global') => {
    setDetachConfirm({ template, scope })
  }

  const confirmDetach = () => {
    if (!detachConfirm) return
    const { template, scope } = detachConfirm

    const detached: PromptTemplate = {
      id: template.id,
      name: template.name,
      prompt: template.prompt,
    }

    if (scope === 'project') {
      const updated = projectTemplates.map((t) => (t.id === template.id ? detached : t))
      setProjectTemplates(updated)
      saveProjectTemplates(updated)
    } else {
      const updated = globalTemplates.map((t) => (t.id === template.id ? detached : t))
      setGlobalTemplates(updated)
      saveGlobalTemplates(updated)
    }
    setDetachConfirm(null)
  }

  // Import a prompt by share code
  const handleImportFetch = async () => {
    if (!importCode.trim()) return
    setImportLoading(true)
    setImportPreview(null)
    try {
      const res = await fetch(`${getApiBase()}/cloud/prompts/shared/${importCode.trim()}`)
      if (!res.ok) throw new Error('Not found')
      const data = await res.json()
      setImportPreview(data)
    } catch {
      setImportPreview(null)
      alert('Prompt not found')
    }
    setImportLoading(false)
  }

  const handleImportAdd = async (autoUpdate: boolean) => {
    if (!importPreview) return
    const newTemplate: PromptTemplate = {
      id: generateId(),
      name: importPreview.name,
      prompt: importPreview.prompt,
      source_code: importPreview.share_code,
      source_version: importPreview.version,
      auto_update: autoUpdate,
    }

    const updated = [...globalTemplates, newTemplate]
    setGlobalTemplates(updated)
    await saveGlobalTemplates(updated)

    // Track install
    fetch(`${getApiBase()}/cloud/prompts/${importPreview.share_code}/install`, {
      method: 'POST',
    }).catch(() => {})

    setImportPreview(null)
    setImportCode('')
    setShowImport(false)
  }

  // Install from community browse
  const handleCommunityInstall = async (prompt: CommunityPrompt) => {
    // Fetch full prompt content
    try {
      const res = await fetch(`${getApiBase()}/cloud/prompts/shared/${prompt.share_code}`)
      if (!res.ok) throw new Error('Failed to fetch')
      const full = await res.json()

      const newTemplate: PromptTemplate = {
        id: generateId(),
        name: full.name,
        prompt: full.prompt,
        source_code: full.share_code,
        source_version: full.version,
      }

      const updated = [...globalTemplates, newTemplate]
      setGlobalTemplates(updated)
      await saveGlobalTemplates(updated)

      // Track install
      fetch(`${getApiBase()}/cloud/prompts/${prompt.share_code}/install`, {
        method: 'POST',
      }).catch(() => {})
    } catch (err) {
      console.error('Failed to install community prompt:', err)
    }
  }

  // Drag and drop handlers
  const handleDragStart = (index: number, scope: 'project' | 'global') => {
    setDragIndex(index)
    setDragScope(scope)
  }

  const handleDragOver = (e: React.DragEvent, index: number, scope: 'project' | 'global') => {
    e.preventDefault()
    // Only allow drag within same scope
    if (scope === dragScope) {
      setDragOverIndex(index)
    }
  }

  const handleDragEnd = () => {
    if (dragIndex !== null && dragOverIndex !== null && dragIndex !== dragOverIndex && dragScope) {
      if (dragScope === 'project') {
        const updated = [...projectTemplates]
        const [dragged] = updated.splice(dragIndex, 1)
        updated.splice(dragOverIndex, 0, dragged)
        setProjectTemplates(updated)
        saveProjectTemplates(updated)
      } else {
        const updated = [...globalTemplates]
        const [dragged] = updated.splice(dragIndex, 1)
        updated.splice(dragOverIndex, 0, dragged)
        setGlobalTemplates(updated)
        saveGlobalTemplates(updated)
      }
    }
    setDragIndex(null)
    setDragOverIndex(null)
    setDragScope(null)
  }

  // Installed share codes for community section
  const installedCodes = new Set(
    [...projectTemplates, ...globalTemplates]
      .filter((t) => t.source_code)
      .map((t) => t.source_code!)
  )

  if (loading) {
    return <div className="flex items-center justify-center h-full text-text-muted">Loading...</div>
  }

  const editFormRef = (el: HTMLDivElement | null) => {
    if (!el) return
    const parent = el.closest('.overflow-y-auto')
    if (!parent) return
    const parentRect = parent.getBoundingClientRect()
    const elRect = el.getBoundingClientRect()
    const available = (parentRect.bottom - elRect.top) * 0.65 // use ~65% of available space
    const textarea = el.querySelector('textarea')
    if (textarea) {
      textarea.style.height = `${Math.max(120, available)}px`
    }
  }

  const renderInlineEditForm = (template: PromptTemplate, _scope: 'project' | 'global') => {
    const isLinkedEdit = editingTemplate?.source_code && editingTemplate.prompt !== formPrompt
    return (
      <div
        key={template.id}
        ref={editFormRef}
        className="p-3 bg-bg-surface rounded border border-blue-500"
      >
        <div className="mb-2">
          <input
            type="text"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            placeholder="Template name"
            autoFocus
            className="w-full px-3 py-2 bg-input-bg text-text-primary rounded border border-input-border focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="mb-2">
          <textarea
            value={formPrompt}
            onChange={(e) => setFormPrompt(e.target.value)}
            placeholder="Prompt text..."
            className="w-full min-h-[120px] px-3 py-2 bg-input-bg text-text-primary rounded border border-input-border focus:outline-none focus:border-blue-500 resize-vertical"
          />
        </div>
        {isLinkedEdit && (
          <div className="mb-2 flex items-center gap-1.5 text-xs text-amber-400">
            <CloudOff size={12} />
            <span>Editing content will detach this prompt from its cloud source</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleSaveTemplate}
            disabled={!formName.trim() || !formPrompt.trim()}
            className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Save
          </button>
          <button
            type="button"
            onClick={handleCancelEdit}
            className="px-3 py-1.5 bg-control-bg text-text-tertiary text-sm rounded hover:bg-control-bg-hover hover:text-text-secondary transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  const renderTemplateItem = (
    template: PromptTemplate,
    index: number,
    scope: 'project' | 'global'
  ) => {
    if (editMode && editingTemplate?.id === template.id && showForm === scope) {
      return renderInlineEditForm(template, scope)
    }

    return (
      <TemplateItem
        key={template.id}
        template={template}
        index={index}
        scope={scope}
        editMode={editMode}
        sessionName={sessionName}
        cloudConnected={cloudConnected}
        isDragging={dragScope === scope && dragIndex === index}
        isDragOver={dragScope === scope && dragOverIndex === index && dragIndex !== index}
        sharingId={sharingId}
        updateAvailable={
          template.source_code ? availableUpdates[template.source_code] || null : null
        }
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onEdit={handleEdit}
        onSendToTerminal={handleSendToTerminal}
        onCopyToGlobal={handleCopyToGlobal}
        onCopyToProject={handleCopyToProject}
        onDelete={handleDelete}
        onShare={handleShare}
        onUpdate={handleApplyUpdate}
        onDetach={handleDetach}
      />
    )
  }

  return (
    <div className="h-full flex flex-col p-4 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-text-secondary">Prompt Templates</h2>
        <div className="flex items-center gap-2">
          {cloudConnected && (
            <button
              onClick={() => setShowImport(!showImport)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                showImport
                  ? 'bg-blue-600 text-white hover:bg-blue-500'
                  : 'bg-control-bg text-text-tertiary hover:bg-control-bg-hover hover:text-text-secondary'
              }`}
            >
              Import
            </button>
          )}
          <button
            onClick={() => {
              if (editMode) handleCancelEdit()
              setEditMode(!editMode)
            }}
            className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
              editMode
                ? 'bg-blue-600 text-white hover:bg-blue-500'
                : 'bg-control-bg text-text-tertiary hover:bg-control-bg-hover hover:text-text-secondary'
            }`}
          >
            {editMode ? 'Done' : 'Edit'}
          </button>
        </div>
      </div>

      {/* Import form */}
      {showImport && (
        <div className="mb-4 p-3 bg-bg-surface rounded border border-border-default">
          <div className="flex items-center gap-2 mb-2">
            <input
              type="text"
              value={importCode}
              onChange={(e) => {
                setImportCode(e.target.value)
                setImportPreview(null)
              }}
              placeholder="Enter share code..."
              className="flex-1 px-3 py-1.5 text-sm bg-input-bg text-text-primary rounded border border-input-border focus:outline-none focus:border-blue-500"
              onKeyDown={(e) => e.key === 'Enter' && handleImportFetch()}
            />
            <button
              onClick={handleImportFetch}
              disabled={importLoading || !importCode.trim()}
              className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50 transition-colors"
            >
              {importLoading ? '...' : 'Fetch'}
            </button>
          </div>
          {importPreview && (
            <div className="p-2 bg-bg-base rounded border border-border-default">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium text-text-primary">{importPreview.name}</span>
                <span className="text-xs text-text-muted">v{importPreview.version}</span>
                <span className="text-xs text-text-muted">@{importPreview.author_username}</span>
              </div>
              <div className="text-xs text-text-muted mb-2 line-clamp-2">
                {importPreview.prompt}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleImportAdd(false)}
                  className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-500 transition-colors"
                >
                  Add to Global
                </button>
                <button
                  onClick={() => handleImportAdd(true)}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors"
                  title="Add and automatically update when new versions are published"
                >
                  Add + Auto-update
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Update preview modal */}
      {updatePreview && (
        <div className="mb-4 p-3 bg-bg-surface rounded border border-amber-500/50">
          <div className="text-sm font-medium text-text-primary mb-1">
            Update available for "{updatePreview.template.name}"
          </div>
          <div className="text-xs text-text-muted mb-1">
            v{updatePreview.template.source_version} → v{updatePreview.latest.version}
          </div>
          <div className="text-xs text-text-muted mb-2 p-2 bg-bg-base rounded max-h-32 overflow-y-auto whitespace-pre-wrap">
            {updatePreview.latest.prompt}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => confirmUpdate(false)}
              className="px-3 py-1 text-sm bg-amber-600 text-white rounded hover:bg-amber-500 transition-colors"
            >
              Update
            </button>
            <button
              onClick={() => confirmUpdate(true)}
              className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 transition-colors"
              title="Update and auto-update future versions"
            >
              Update + Auto-update
            </button>
            <button
              onClick={() => setUpdatePreview(null)}
              className="px-3 py-1 text-sm bg-control-bg text-text-tertiary rounded hover:bg-control-bg-hover transition-colors"
            >
              Skip
            </button>
          </div>
        </div>
      )}

      {/* Detach confirmation */}
      {detachConfirm && (
        <div className="mb-4 p-3 bg-bg-surface rounded border border-orange-500/50">
          <div className="text-sm text-text-primary mb-2">
            Detach "{detachConfirm.template.name}" from cloud source? It will become a local-only
            prompt and can be shared again as a new prompt.
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={confirmDetach}
              className="px-3 py-1 text-sm bg-orange-600 text-white rounded hover:bg-orange-500 transition-colors"
            >
              Detach
            </button>
            <button
              onClick={() => setDetachConfirm(null)}
              className="px-3 py-1 text-sm bg-control-bg text-text-tertiary rounded hover:bg-control-bg-hover transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Template lists */}
      <div className="flex-1 overflow-y-auto space-y-4">
        <TemplateSection
          title="Project Templates"
          scope="project"
          templates={projectTemplates}
          editMode={editMode}
          showForm={showForm}
          editingTemplate={editingTemplate}
          onStartAdd={handleStartAdd}
          renderInlineEditForm={renderInlineEditForm}
          renderTemplateItem={renderTemplateItem}
        />
        <TemplateSection
          title="Global Templates"
          scope="global"
          templates={globalTemplates}
          editMode={editMode}
          showForm={showForm}
          editingTemplate={editingTemplate}
          onStartAdd={handleStartAdd}
          renderInlineEditForm={renderInlineEditForm}
          renderTemplateItem={renderTemplateItem}
        />

        {/* Community section */}
        {cloudConnected && (
          <CommunitySection
            prompts={communityPrompts}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            installedCodes={installedCodes}
            onInstall={handleCommunityInstall}
            loading={communityLoading}
          />
        )}
      </div>

      {/* Saving indicator */}
      {saving && <div className="text-text-muted text-sm text-center py-2">Saving...</div>}
    </div>
  )
}
