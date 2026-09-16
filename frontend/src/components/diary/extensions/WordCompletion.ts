import { Extension } from "@tiptap/core"
import { Plugin, PluginKey, type EditorState, type Transaction } from "@tiptap/pm/state"
import { Decoration, DecorationSet } from "@tiptap/pm/view"
import type { CompletionIndex } from "@/lib/wordCompletion"

/**
 * WordCompletion - inline ghost text after the caret, accepted with Tab, dismissed with Escape.
 *
 * The document is never touched until the writer accepts: the suggestion is a widget
 * decoration, so undo history, autosave and word counts stay honest. Tab only accepts
 * when a suggestion is showing; otherwise it falls through to list indentation. On a
 * phone, where there is no Tab key, tapping the ghost text accepts it.
 */

export interface WordCompletionOptions {
  getIndex: () => CompletionIndex | null
  isEnabled: () => boolean
  minPrefix: number
}

interface Suggestion {
  pos: number
  prefix: string
  remainder: string
}

interface PluginState {
  suggestion: Suggestion | null
  /** Prefix the writer dismissed with Escape; stays quiet until they move on to another word. */
  dismissed: string | null
}

const pluginKey = new PluginKey<PluginState>("wordCompletion")

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    wordCompletion: {
      acceptWordCompletion: () => ReturnType
      dismissWordCompletion: () => ReturnType
    }
  }
}

function findSuggestion(state: EditorState, options: WordCompletionOptions, dismissed: string | null): Suggestion | null {
  if (!options.isEnabled()) return null
  const { selection } = state
  if (!selection.empty) return null
  const $from = selection.$from
  const parent = $from.parent
  if (!parent.isTextblock || parent.type.name === "codeBlock") return null

  const before = parent.textBetween(0, $from.parentOffset, undefined, "￼")
  const after = parent.textBetween($from.parentOffset, parent.content.size, undefined, "￼")
  if (/^[A-Za-z']/.test(after)) return null

  const match = /([A-Za-z][A-Za-z']*)$/.exec(before)
  if (!match) return null
  const prefix = match[1]
  if (prefix.length < options.minPrefix) return null
  if (dismissed && prefix.toLowerCase().startsWith(dismissed.toLowerCase())) return null

  const index = options.getIndex()
  if (!index) return null
  const word = index.complete(prefix)
  if (!word) return null

  let remainder = word.slice(prefix.length)
  if (prefix.length >= 2 && prefix === prefix.toUpperCase() && /[A-Z]/.test(prefix)) remainder = remainder.toUpperCase()
  return { pos: selection.from, prefix, remainder }
}

export const WordCompletion = Extension.create<WordCompletionOptions>({
  name: "wordCompletion",
  // Above the list keymap so Tab accepts a visible suggestion before it indents a bullet.
  priority: 1000,

  addOptions() {
    return {
      getIndex: () => null,
      isEnabled: () => true,
      minPrefix: 3,
    }
  },

  addCommands() {
    return {
      acceptWordCompletion:
        () =>
        ({ state, tr, dispatch }) => {
          const current = pluginKey.getState(state)?.suggestion
          if (!current) return false
          if (dispatch) {
            tr.insertText(current.remainder, current.pos)
            tr.setMeta(pluginKey, { type: "accept" })
          }
          return true
        },
      dismissWordCompletion:
        () =>
        ({ state, tr, dispatch }) => {
          const current = pluginKey.getState(state)?.suggestion
          if (!current) return false
          if (dispatch) tr.setMeta(pluginKey, { type: "dismiss", prefix: current.prefix })
          return true
        },
    }
  },

  addKeyboardShortcuts() {
    return {
      Tab: () => this.editor.commands.acceptWordCompletion(),
      Escape: () => this.editor.commands.dismissWordCompletion(),
    }
  },

  addProseMirrorPlugins() {
    const options = this.options
    const editor = this.editor

    return [
      new Plugin<PluginState>({
        key: pluginKey,
        state: {
          init: () => ({ suggestion: null, dismissed: null }),
          apply(tr: Transaction, prev: PluginState, _old: EditorState, newState: EditorState): PluginState {
            const meta = tr.getMeta(pluginKey) as { type: string; prefix?: string } | undefined
            if (meta?.type === "accept") return { suggestion: null, dismissed: null }
            if (meta?.type === "dismiss") return { suggestion: null, dismissed: meta.prefix ?? prev.dismissed }
            if (tr.docChanged) {
              // Typing past the dismissed word lifts the mute.
              const dismissed = prev.dismissed && isStillTyping(newState, prev.dismissed) ? prev.dismissed : null
              return { suggestion: findSuggestion(newState, options, dismissed), dismissed }
            }
            if (tr.selectionSet) return { suggestion: null, dismissed: prev.dismissed }
            return prev
          },
        },
        props: {
          decorations(state) {
            const current = pluginKey.getState(state)?.suggestion
            if (!current) return DecorationSet.empty
            const widget = Decoration.widget(
              current.pos,
              () => {
                const span = document.createElement("span")
                span.className = "word-ghost"
                span.setAttribute("aria-hidden", "true")
                span.textContent = current.remainder
                // Tap to accept on touch devices (no Tab key); mousedown keeps the caret in place.
                span.addEventListener("mousedown", event => {
                  event.preventDefault()
                  editor.commands.acceptWordCompletion()
                })
                return span
              },
              { side: 1, ignoreSelection: true, key: `ghost-${current.pos}-${current.remainder}` }
            )
            return DecorationSet.create(state.doc, [widget])
          },
        },
      }),
    ]
  },
})

/** True while the caret is still inside a word that begins with the dismissed prefix. */
function isStillTyping(state: EditorState, dismissed: string): boolean {
  const $from = state.selection.$from
  if (!$from.parent.isTextblock) return false
  const before = $from.parent.textBetween(0, $from.parentOffset, undefined, "￼")
  const match = /([A-Za-z][A-Za-z']*)$/.exec(before)
  return !!match && match[1].toLowerCase().startsWith(dismissed.toLowerCase())
}
