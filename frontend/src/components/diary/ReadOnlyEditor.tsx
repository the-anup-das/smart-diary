"use client"
import * as React from "react"
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'

export function ReadOnlyEditor({ content, typography = "serif" }: { content: string; typography?: string }) {
  const editor = useEditor({
    immediatelyRender: false,
    editable: false,
    content: content,
    extensions: [
      StarterKit,
      Image,
    ],
    editorProps: {
      attributes: {
        class: `prose dark:prose-invert prose-lg md:prose-xl max-w-none focus:outline-none`,
      },
    },
  })

  // Watch for content changes
  React.useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content)
    }
  }, [content, editor])

  if (!editor) return null

  return (
    <div className={`w-full h-full bg-transparent ${typography === 'sans' ? 'font-sans' : 'font-serif'} text-lg leading-loose text-gray-800 dark:text-gray-200 px-2 lg:px-6 py-4`}>
      <EditorContent editor={editor} />
    </div>
  )
}
