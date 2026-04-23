'use client'

import React, { useRef } from 'react'
import { Upload, FileText, X } from 'lucide-react'

interface FileUploadFieldProps {
  files: File[]
  onFilesChange: (files: File[]) => void
  disabled?: boolean
  accept?: string
  maxFiles?: number
  maxSizeMB?: number
}

const ACCEPT_DEFAULT = '.pdf,.md,.markdown,.txt'

export default function FileUploadField({
  files,
  onFilesChange,
  disabled = false,
  accept = ACCEPT_DEFAULT,
  maxFiles = 5,
  maxSizeMB = 8,
}: FileUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragOver, setDragOver] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const accepted = accept.split(',').map((s) => s.trim().toLowerCase())

  const validate = (incoming: File[]): { ok: File[]; rejected: string[] } => {
    const ok: File[] = []
    const rejected: string[] = []
    for (const f of incoming) {
      const lower = f.name.toLowerCase()
      const matches = accepted.some((ext) => lower.endsWith(ext))
      if (!matches) {
        rejected.push(`${f.name} (unsupported type)`)
        continue
      }
      if (f.size > maxSizeMB * 1024 * 1024) {
        rejected.push(`${f.name} (too large, max ${maxSizeMB} MB)`)
        continue
      }
      ok.push(f)
    }
    return { ok, rejected }
  }

  const addFiles = (incoming: FileList | File[]) => {
    setError(null)
    const list = Array.from(incoming)
    const { ok, rejected } = validate(list)
    if (rejected.length > 0) {
      setError(`Skipped: ${rejected.join(', ')}`)
    }
    const merged = [...files, ...ok].slice(0, maxFiles)
    onFilesChange(merged)
  }

  const removeFile = (index: number) => {
    const next = files.filter((_, i) => i !== index)
    onFilesChange(next)
  }

  const handleClick = () => {
    if (!disabled) inputRef.current?.click()
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    if (disabled) return
    if (e.dataTransfer?.files?.length) {
      addFiles(e.dataTransfer.files)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="label-mono">Reality seeds (optional)</label>
        <span className="text-[10px] font-mono text-[var(--muted)]">
          PDF, MD, TXT · max {maxFiles} files
        </span>
      </div>

      {/* Drop zone */}
      <button
        type="button"
        onClick={handleClick}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        disabled={disabled}
        className={`w-full border border-dashed rounded-md px-4 py-5 transition-colors ${
          dragOver
            ? 'border-[var(--brand)] bg-[var(--brand-tint)]'
            : 'border-[var(--line-strong)] bg-[var(--bg)] hover:border-[var(--brand)] hover:bg-[var(--bg-soft)]'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <div className="flex flex-col items-center justify-center gap-1.5 text-center">
          <Upload className="h-4 w-4 text-[var(--muted)]" />
          <p className="text-xs text-[var(--ink)]">
            <span className="font-medium">Click to upload</span> or drag PDFs / docs here
          </p>
          <p className="text-[10px] font-mono text-[var(--muted)]">
            Quorum will extract text and use it as context for the ontology
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={accept}
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files)
            // Allow re-uploading the same file by resetting the input
            if (inputRef.current) inputRef.current.value = ''
          }}
          className="hidden"
          disabled={disabled}
        />
      </button>

      {/* Error / warning */}
      {error && (
        <p className="mt-1.5 text-[11px] text-[var(--brand)]">{error}</p>
      )}

      {/* File chips */}
      {files.length > 0 && (
        <div className="mt-2 space-y-1">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg-soft)] border border-[var(--line)] rounded text-[11px]"
            >
              <FileText className="h-3 w-3 text-[var(--brand)] flex-shrink-0" />
              <span className="text-[var(--ink)] truncate flex-1">{f.name}</span>
              <span className="text-[10px] font-mono text-[var(--muted)] flex-shrink-0">
                {formatBytes(f.size)}
              </span>
              <button
                type="button"
                onClick={() => removeFile(i)}
                disabled={disabled}
                className="text-[var(--muted)] hover:text-[var(--brand)] flex-shrink-0"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
